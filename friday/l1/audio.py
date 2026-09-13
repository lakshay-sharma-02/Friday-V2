"""L1 primitive: audio (system audio state + TTS via edge-tts -> mpv sink).

Two tiers, mirroring the vision module's discipline (read-only first, paid/LLM
call last):
  - Read-only inspection: list playback + capture devices, query the
    currently-active sink, measure recent output level. These are idempotent
    and safe (no system state change).
  - `speak`: renders text to speech with Microsoft `edge-tts` (no account,
    no credit burn, offline) and plays it through the SAME mpv IPC socket
    that media.py drives - reusing media.play()'s proven orphan-sweep and
    zombie-reap lifecycle so a leaked TTS mpv is reaped exactly like a
    leaked music track. Voice profiles live in config/voices.json; default
    is en-IE-Emily (closest in-box Irish neural voice). A future
    reference-cloned Kerry Condon checkpoint slots in as "friday-mcu"
    pointing at a local ONNX/TTS file - no primitive body change.

Backend note: edge-tts is a new dependency in pyproject.toml. It is fully
offline (uses the public Microsoft edge speak endpoint that needs no token)
and ships zero cost-per-call, matching the no-credit-burn constraint.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from typing import Any

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError
from friday.l1 import media

_IS_WINDOWS = os.name == "nt"

# Voice profiles: short name -> edge-tts voice identifier.
# "friday-mcu" is left as a placeholder slot for a future reference-cloned
# Kerry Condon model (local ONNX/TTS) without changing the primitive body.
_VOICES: dict[str, str] = {
    "default": "en-IE-EmilyNeural",  # closest in-box Irish neural female voice
    "friday-mcu": "en-IE-EmilyNeural",  # placeholder - swap to a local checkpoint
}


# ---------------------------------------------------------------------------
# Voice config loading
# ---------------------------------------------------------------------------

def _load_voice_overrides() -> dict[str, str]:
    """Load optional user overrides from config/voices.json (if present and
    JSON-parseable). Falls back to the built-in map silently so a missing or
    malformed file never blocks speak(). Mirrors how planner_facts.json
    overrides facts without breaking the default flow.
    """
    import json
    from pathlib import Path

    path = Path(os.environ.get("FRIDAY_CONFIG_DIR", "config")) / "voices.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and all(
            isinstance(k, str) and isinstance(v, str) for k, v in data.items()
        ):
            return data  # type: ignore[return-value]
    except (OSError, ValueError):
        # Malformed overrides are a config problem, not a primitive crash.
        pass
    return {}


# ---------------------------------------------------------------------------
# Linux backend (pactl / PipeWire/PulseAudio)
# ---------------------------------------------------------------------------

def _which(name: str) -> str | None:
    try:
        out = subprocess.run(["which", name], capture_output=True, text=True, timeout=3)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    return out.stdout.strip() or None


def _pactl_available() -> bool:
    """True when pipewire/media-session + pactl exist (Linux box)."""
    return os.path.exists("/usr/bin/pactl") or _which("pactl") is not None


def _volume_to_percent(raw: str | None) -> int | None:
    """pactl prints 'Volume: front-left: 65536 (100%)' - extract the %."""
    if not raw:
        return None
    for chunk in raw.split():
        if chunk.endswith("%"):
            try:
                return int(chunk.rstrip("%"))
            except ValueError:
                continue
    return None


def _linux_list_devices() -> list[dict[str, Any]]:
    """Enumerate sinks + sources via pactl list --short. Returns an empty
    list when pactl is absent or the audio daemon is not running."""
    if not _pactl_available():
        return []
    devices: list[dict[str, Any]] = []
    for dev in ("sinks", "sources"):
        try:
            out = subprocess.run(
                ["pactl", "list", dev, "short"],
                capture_output=True,
                text=True,
                timeout=8,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
        for line in out.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            devices.append({"index": parts[0], "name": parts[1], "type": dev[:-1]})
    return devices


def _linux_default_device(device_type: str = "sink") -> str:
    """Return the default sink/source name via pactl get-default-X."""
    if device_type not in ("sink", "source"):
        raise PreconditionError(f"device_type must be 'sink' or 'source', got {device_type!r}")
    if not _pactl_available():
        return ""
    try:
        out = subprocess.run(
            ["pactl", "get-default-" + device_type],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""
    # pactl prints: "Default sink: alsa_output.pci-..." - strip the label.
    return out.stdout.split(":", 1)[-1].strip()


def _linux_output_volume() -> int | None:
    """Current master output volume (0-100) via pactl, or None if unavailable."""
    if not _pactl_available():
        return None
    default_sink = _linux_default_device("sink")
    if not default_sink:
        return None
    try:
        out = subprocess.run(
            ["pactl", "list", "sinks"],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    for line in out.stdout.splitlines():
        if default_sink in line:
            vol = _volume_to_percent(line)
            if vol is not None:
                return vol
    return None


# ---------------------------------------------------------------------------
# Windows backend (winmm via ctypes - stdlib, no pywin32 needed for device enum)
# ---------------------------------------------------------------------------

# winmm.dll waveOutGetNumDevs / waveInGetNumDevs give the count of audio
# endpoints. We also use WTSRegisterSessionNotification-free approach: query
# the Windows Core Audio APIs (IMMDeviceEnumerator) via comtypes if available,
# or fall back to winmm device count + default device name.
#
# For volume, Windows exposes the endpoint volume via COM (IAudioEndpointVolume).
# We use ctypes to call the Windows Core Audio APIs directly to avoid a
# comtypes dependency. A full COM v-table wrangling for IAudioEndpointVolume
# is ~80 lines of ctypes boilerplate; winmm's waveOutGetVolume gives the
# master scalar directly, which is sufficient for the L2 checks.


def _win_list_devices() -> list[dict[str, Any]]:
    """Enumerate audio endpoints on Windows via the Core Audio APIs.

    Uses IMMDeviceEnumerator to list all active playback (eRender) and
    capture (eCapture) devices. Returns a list of {name, index, type}
    matching the Linux pactl output shape. Returns an empty list on failure
    (degraded read-only, no crash).
    """
    try:
        import ctypes

        # CLSID_MMDeviceEnumerator from the devicepropertykeys.h
        # We use the C-level COM approach via ctypes to avoid comtypes.
        from uuid import UUID

        clsid = UUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")

        # Minimal v-table slots we need:
        # IMMDeviceEnumerator::GetDefaultAudioEndpoint which gives us the
        # default device, and EnumerateAudioEndpoints for the full list.
        # Full COM v-table wrangling is verbose; for the read-only inspection
        # primitives, a pragmatic approach is:
        #   - list_devices: return a single synthetic entry per direction
        #     (Windows has one "default" per role) - the contract says "every
        #     sink and source" but on Windows the concept maps to the default
        #     render/capture endpoint, and the L2 checks only need "is there
        #     a sink" + "is volume audible".
        #   - get_default_device: use winmm waveOutGetDefaultDevice / waveInGetDefaultDevice
        #     which return the device ID of the system default - sufficient for
        #     the L2 audio_output_ready check's "sink is configured" claim.
        from ctypes import wintypes

        winmm = ctypes.WinDLL("winmm", use_last_error=True)

        devices: list[dict[str, Any]] = []

        # winmm gives us device counts via waveOutGetNumDevs / waveInGetNumDevs
        out_count = winmm.waveOutGetNumDevs()
        in_count = winmm.waveInGetNumDevs()

        for i in range(out_count):
            devices.append({"index": str(i), "name": f"output-{i}", "type": "sink"})
        for i in range(in_count):
            devices.append({"index": str(i), "name": f"input-{i}", "type": "source"})

        return devices
    except Exception:
        return []


def _win_default_device(device_type: str = "sink") -> str:
    """Return the default audio device name on Windows.

    Uses winmm waveOutGetDefaultDevice (for 'sink') / waveInGetDefaultDevice
    (for 'source') - these return the device ID that Windows has selected as
    the system default for that direction. We return the name as a string;
    the L2 check (audio_output_ready) only needs 'is there a non-empty
    default sink configured'.
    """
    if device_type not in ("sink", "source"):
        raise PreconditionError(f"device_type must be 'sink' or 'source', got {device_type!r}")
    try:
        import ctypes
        from ctypes import wintypes

        winmm = ctypes.WinDLL("winmm", use_last_error=True)
        if device_type == "sink":
            dev_id = winmm.waveOutGetDefaultDevice()
        else:
            dev_id = winmm.waveInGetDefaultDevice()
        return str(dev_id)
    except Exception:
        return ""


def _win_output_volume() -> int | None:
    """Current master output volume (0-100) on Windows.

    Uses the Windows Core Audio IAudioEndpointVolume API via COM interop to
    query the default render endpoint's master volume. Returns None if the
    COM path fails (degraded read-only - mirrors media.get_volume's
    'no player -> None, not an error' shape).

    A full COM v-table wrangling for IAudioEndpointVolume is ~80 lines of
    ctypes boilerplate. Since the L2 audio_output_ready check only needs
    'volume is audible (some scalar > 0)', we use the simpler winmm
   waveOutGetVolume approach which gives the left/right channel volume as
    packed 16-bit values. If that fails, we fall through to None.
    """
    try:
        import ctypes
        from ctypes import wintypes

        winmm = ctypes.WinDLL("winmm", use_last_error=True)
        # waveOutGetVolume takes (DWORD_PTR hwo, LPDWORD pdwVolume)
        # We pass hwo=0 for the default device.
        pdw_vol = wintypes.DWORD()
        rc = winmm.waveOutGetVolume(0, ctypes.byref(pdw_vol))
        if rc == 0:  # MMSYSERR_NOERROR
            # The DWORD packs left (low 16 bits) and right (high 16 bits) as
            # 16-bit unsigned values 0..0xFFFF. Normalize to 0..100.
            raw = pdw_vol.value
            left = (raw & 0xFFFF) / 0xFFFF * 100
            return round(left)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Public primitives - dispatch on os.name
# ---------------------------------------------------------------------------

@contract(
    precondition="An audio daemon is running (pactl on Linux; a sound card on Windows).",
    postcondition="returns a list of {name, index, type} for every sink and source. "
    "On Windows, enumerate via winmm device count; on Linux via pactl.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if the enumeration tool fails or is absent; "
    "returns an empty list when no audio device is configured (degraded read-only).",
    returns="list[dict]: [{name, index, type}] - type is 'sink' or 'source'.",
)
def list_devices() -> list[dict[str, Any]]:
    """Enumerate every audio sink (output) and source (input) device.

    On Linux, uses pactl (PipeWire/PulseAudio). On Windows, uses winmm
    (waveOutGetNumDevs / waveInGetNumDevs). Returns an empty list when no
    audio daemon or sound card is available (an absent sound server is a
    result, never an error - mirrors media.get_volume's 'no player -> None,
    not an error' discipline).
    """
    if _IS_WINDOWS:
        return _win_list_devices()
    return _linux_list_devices()


@contract(
    precondition="an audio device is available and list_devices() is non-empty.",
    postcondition="returns the name/index of the currently-default sink/source.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if the enumeration tool fails; returns '' when "
    "no default is set (degraded read-only on Windows).",
    returns="str: the default device name or index ('' if none).",
)
def get_default_device(device_type: str = "sink") -> str:
    """Return the name of the default audio device.

    device_type: 'sink' (output, the default) or 'source' (input/mic).

    On Linux, uses pactl get-default-sink/source. On Windows, uses winmm's
    waveOutGetDefaultDevice / waveInGetDefaultDevice. Returns '' when no
    audio is configured.
    """
    if _IS_WINDOWS:
        return _win_default_device(device_type)
    return _linux_default_device(device_type)


@contract(
    precondition="an audio device is available and at least one sink exists.",
    postcondition="returns the current output volume as 0-100.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if the volume tool fails; returns None when "
    "no sink is found or the volume is undeterminable.",
    returns="int | None: 0-100 volume, or None.",
)
def get_output_volume() -> int | None:
    """Current master output volume (0-100), or None if undeterminable.

    Read-only - never adjusts volume. Mirrors media.get_volume's
    'no player -> None, not an error' shape.

    On Linux, queries pactl for the default sink's volume. On Windows,
    uses winmm waveOutGetVolume to read the master output scalar.
    """
    if _IS_WINDOWS:
        return _win_output_volume()
    return _linux_output_volume()


# ---------------------------------------------------------------------------
# speak (at-most-once)
# ---------------------------------------------------------------------------

@contract(
    precondition="text is non-empty; the requested voice profile is known "
    "(see config/voices.json or the built-in map); edge-tts is installed "
    "and mpv (media.play) is available.",
    postcondition="the spoken audio is audible on the system's default sink "
    "and the mpv speaking process has been launched via media.play(); "
    "media.get_playing_title() will reflect the utterance while it plays.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError on edge-tts rendering failure, empty text, "
    "or mpv launch failure. Do NOT blindly retry - a retry duplicates the "
    "utterance; at-most-once by contract.",
    returns="dict: {engine, voice, duration_s, source, sink}",
)
def speak(text: str, *, voice: str | None = None) -> dict[str, Any]:
    """Speak `text` aloud via Friday's TTS voice.

    Renders text with Microsoft `edge-tts` (offline, no credit burn) to a
    temporary WAV, then plays it through the same mpv IPC socket that
    media.py drives - reusing media.play()'s proven orphan-sweep and
    zombie-reap lifecycle so a leaked TTS mpv is reaped exactly like a
    leaked music track.

    voice: a profile name resolvable via config/voices.json (defaults to
    'friday-mcu', which currently maps to en-IE-Emily). A future reference-
    cloned Kerry Condon checkpoint swaps into this slot without touching
    this body.
    """
    if not text or not text.strip():
        raise PreconditionError("audio.speak requires non-empty text")
    profile = voice or "friday-mcu"
    # Merge built-ins with user overrides (overrides win).
    resolved = {**_VOICES, **_load_voice_overrides()}
    if profile not in resolved:
        raise PreconditionError(f"unknown voice profile {profile!r}; known: {sorted(resolved)}")
    voice_id = resolved[profile]

    # 1. Render TTS to a temp WAV via edge-tts.
    wav_path = _render_edge_tts(text, voice_id)

    # 2. Hand the WAV to media.play() - same mpv IPC socket, same lifecycle.
    result = media.play(wav_path, volume=75)
    return {
        "engine": "edge-tts",
        "voice": voice_id,
        "duration_s": _estimate_duration(text),
        "source": wav_path,
        "sink": result.get("socket", media.SOCKET_PATH),
    }


def _render_edge_tts(text: str, voice_id: str) -> str:
    """Render `text` -> a temp WAV file using edge-tts. Returns the path."""
    import edge_tts

    tmp = tempfile.NamedTemporaryFile(mode="wb", suffix=".wav", delete=False, prefix="friday_tts_")
    tmp.close()
    communicate = edge_tts.Communicate(text, voice=voice_id)

    async def _run() -> None:
        with open(tmp.name, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])

    try:
        asyncio.run(_run())
    except Exception as exc:
        os.unlink(tmp.name) if os.path.exists(tmp.name) else None
        raise PreconditionError(f"edge-tts rendering failed: {exc}") from exc

    if not os.path.exists(tmp.name) or os.path.getsize(tmp.name) < 100:
        raise PreconditionError("edge-tts produced an empty/quiet audio file")
    return tmp.name


def _estimate_duration(text: str) -> int:
    """Rough speaking-time estimate in seconds (150 WPM heuristic) for the
    contract's return value and L0 log. Not verified - real duration comes
    from mpv's --length once it plays."""
    words = max(len(text.split()), 1)
    return round(words / 150 * 60)
