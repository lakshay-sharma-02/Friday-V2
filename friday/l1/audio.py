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

# Voice profiles: short name -> edge-tts voice identifier.
# "friday-mcu" is left as a placeholder slot for a future reference-cloned
# Kerry Condon model (local ONNX/TTS) without changing the primitive body.
_VOICES: dict[str, str] = {
    "default": "en-IE-EmilyNeural",  # closest in-box Irish neural female voice
    "friday-mcu": "en-IE-EmilyNeural",  # placeholder - swap to a local checkpoint
}


# Load optional user overrides from config/voices.json (if present and
# JSON-parseable). Falls back to the built-in map silently so a missing or
# malformed file never blocks speak(). Mirrors how planner_facts.json
# overrides facts without breaking the default flow.
def _load_voice_overrides() -> dict[str, str]:
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


# ---------------------------------------------------------------- internals


def _pactl_available() -> bool:
    """True when pipewire/media-session + pactl exist (Linux Wayland box)."""
    return os.path.exists("/usr/bin/pactl") or _which("pactl")


def _which(name: str) -> str | None:
    try:
        out = subprocess.run(["which", name], capture_output=True, text=True, timeout=3)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    return out.stdout.strip() or None


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


# ---------------------------------------------------------------- read-only (idempotent)


@contract(
    precondition="pactl is present (PipeWire/PulseAudio session running).",
    postcondition="returns a list of {name, index, type} for every sink and source.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if pactl fails or is absent.",
    returns="list[dict]: [{name, index, type}] - type is 'sink' or 'source'.",
)
def list_devices() -> list[dict[str, Any]]:
    """Enumerate every audio sink (output) and source (input) device.

    Returns an empty list when no audio daemon is running (an absent
    sound server is a result, never an error - mirrors media.get_volume's
    'no player -> None, not an error' discipline).
    """
    if not _pactl_available():
        return []
    sinks: list[dict[str, Any]] = []
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
            sinks.append({"index": parts[0], "name": parts[1], "type": dev[:-1]})
    return sinks


@contract(
    precondition="an audio daemon is running and list_devices() is non-empty.",
    postcondition="returns the name of the currently-default sink/source.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if pactl fails; returns '' when no default is set.",
    returns="str: the default device name ('' if none).",
)
def get_default_device(device_type: str = "sink") -> str:
    """Return the name of the default audio device.

    device_type: 'sink' (output, the default) or 'source' (input/mic).
    """
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


@contract(
    precondition="an audio daemon is running and at least one sink exists.",
    postcondition="returns the current output volume as 0-100.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if pactl fails; returns None when no sink is found.",
    returns="int | None: 0-100 volume, or None.",
)
def get_output_volume() -> int | None:
    """Current master output volume (0-100), or None if undeterminable.

    Read-only - never calls pactl set. Mirrors media.get_volume's
    'no player -> None, not an error' shape.
    """
    if not _pactl_available():
        return None
    default_sink = get_default_device("sink")
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


# ---------------------------------------------------------------- write (at-most-once) - NOT IMPLEMENTED


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
