"""Media adapter — mpv IPC control.

Keeps the proven mpv IPC pattern from V8, adapted to the adapter model.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import socket
import subprocess
import threading
import time
from typing import Any

from friday_mcu.core.contracts import Idempotency, contract
from friday_mcu.core.errors import PreconditionError, PrimitiveError

SOCKET_PATH = "/tmp/friday_mpv.sock"
DEFAULT_VOLUME = 70

_lock = threading.Lock()
_proc: subprocess.Popen | None = None


def _socket_send(payload: dict[str, Any], timeout: float = 2.0) -> dict[str, Any] | None:
    """Send one newline-delimited JSON request to mpv's IPC socket."""
    af_unix = getattr(socket, "AF_UNIX", None)
    if af_unix is None:
        return None  # Windows — no Unix socket
    try:
        s = socket.socket(af_unix, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(SOCKET_PATH)
        s.sendall((json.dumps(payload) + "\n").encode())
        data = b""
        while not data.endswith(b"\n"):
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
        s.close()
        if not data:
            return None
        parsed = json.loads(data.decode())
        return parsed if isinstance(parsed, dict) else None
    except (OSError, json.JSONDecodeError, TimeoutError):
        return None


def _wait_socket(timeout: float = 8.0) -> bool:
    """Wait for the mpv IPC socket to become ready."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _socket_send({"command": ["get_property", "mpv-version"]}) is not None:
            return True
        time.sleep(0.25)
    return False


@contract(
    precondition="source is a non-empty local path or URL.",
    postcondition="Audio from source plays at the given volume.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError if mpv cannot start or its IPC socket never appears.",
    returns="dict: {pid, socket, source}.",
)
def play(source: str, volume: int = DEFAULT_VOLUME) -> dict[str, Any]:
    """Play audio from a source using mpv."""
    global _proc
    if not source or not source.strip():
        raise PreconditionError("play requires a non-empty source")

    with _lock:
        # Stop any existing player
        if _proc is not None:
            with contextlib.suppress(Exception):
                _proc.terminate()
                _proc.wait(timeout=3)
            _proc = None

        # Clean up socket
        if os.path.exists(SOCKET_PATH):
            with contextlib.suppress(OSError):
                os.unlink(SOCKET_PATH)

        try:
            proc = subprocess.Popen(
                [
                    "mpv",
                    "--no-terminal",
                    f"--input-ipc-server={SOCKET_PATH}",
                    f"--volume={volume}",
                    source,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            _proc = proc
        except FileNotFoundError as exc:
            raise PrimitiveError("mpv binary not found", state="no player started") from exc

        if not _wait_socket():
            if _proc:
                with contextlib.suppress(Exception):
                    _proc.terminate()
                    _proc.wait(timeout=3)
            _proc = None
            raise PrimitiveError(
                f"mpv IPC socket never became ready at {SOCKET_PATH}",
                state="mpv was launched but unreachable",
            )

        return {"pid": proc.pid, "socket": SOCKET_PATH, "source": source}


@contract(
    precondition="None.",
    postcondition="No mpv process is left playing.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="None expected; stubborn processes are SIGTERM'd.",
    returns="None",
)
def stop() -> None:
    """Stop all media playback."""
    global _proc
    with _lock:
        if _proc is not None:
            with contextlib.suppress(Exception):
                _socket_send({"command": ["quit"]}, timeout=1.0)
                _proc.wait(timeout=5)
            if _proc.poll() is None:
                with contextlib.suppress(ProcessLookupError):
                    _proc.terminate()
                with contextlib.suppress(Exception):
                    _proc.wait(timeout=3)
            _proc = None

        # Clean up socket
        if os.path.exists(SOCKET_PATH):
            with contextlib.suppress(OSError):
                os.unlink(SOCKET_PATH)


@contract(
    precondition="None.",
    postcondition="Makes no state changes.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="Never raises: no player -> False.",
    returns="bool",
)
def is_playing() -> bool:
    """Check if media is currently playing."""
    reply = _socket_send({"command": ["get_property", "idle-active"]})
    if reply is None:
        return False
    return reply.get("data", True) is False  # idle-active=False means playing


@contract(
    precondition="None.",
    postcondition="Makes no state changes.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="Never raises: no player -> empty string.",
    returns="str: the currently playing title.",
)
def get_playing_title() -> str:
    """Get the title of the currently playing media."""
    reply = _socket_send({"command": ["get_property", "media-title"]})
    if reply is None:
        return ""
    return str(reply.get("data", ""))


@contract(
    precondition="None.",
    postcondition="Makes no state changes.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="Never raises: no player -> 0.",
    returns="int: the current volume (0-100).",
)
def get_volume() -> int:
    """Get the current volume level."""
    reply = _socket_send({"command": ["get_property", "volume"]})
    if reply is None:
        return 0
    return int(reply.get("data", 0))


@contract(
    precondition="None.",
    postcondition="Media is paused.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="PrimitiveError if no player is active.",
    returns="None",
)
def pause() -> None:
    """Pause media playback."""
    reply = _socket_send({"command": ["set_property", "pause", True]})
    if reply is None:
        raise PrimitiveError("no player active", state="cannot pause")


@contract(
    precondition="None.",
    postcondition="Media is playing.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="PrimitiveError if no player is active.",
    returns="None",
)
def resume() -> None:
    """Resume media playback."""
    reply = _socket_send({"command": ["set_property", "pause", False]})
    if reply is None:
        raise PrimitiveError("no player active", state="cannot resume")


# ── Adapter class

from friday_mcu.adapters import Adapter, register_adapter


class MediaAdapter(Adapter):
    """Media playback adapter (mpv IPC)."""

    @property
    def name(self) -> str:
        return "media"

    @property
    def capabilities(self) -> list[str]:
        return ["play", "stop", "pause", "resume", "is_playing", "get_volume", "get_playing_title"]

    async def initialize(self) -> None:
        pass  # mpv is started on-demand

    async def execute(self, action: str, **kwargs: Any) -> Any:
        if action == "play":
            return play(**kwargs)
        elif action == "stop":
            return stop()
        elif action == "pause":
            return pause()
        elif action == "resume":
            return resume()
        elif action == "is_playing":
            return is_playing()
        elif action == "get_volume":
            return get_volume()
        elif action == "get_playing_title":
            return get_playing_title()
        raise PrimitiveError(f"Unknown media action: {action}")

    async def observe(self) -> list[Event]:
        return []

    def health_check(self) -> bool:
        """Check if mpv is available."""
        try:
            result = subprocess.run(["which", "mpv"], capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False


try:
    register_adapter(MediaAdapter())
except Exception:
    pass
