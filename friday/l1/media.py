"""L1 primitive: media (mpv over its own IPC socket).

mpv has no MPRIS on most setups, so playerctl alone cannot control it. We
drive mpv directly via `--input-ipc-server` on a fixed Unix socket.

Rules baked in from prior builds:
  - "play for N min then stop" uses a one-shot threading.Timer, never a
    polling loop. mpv's native `--length` additionally guarantees the stop
    even if this process dies (streams where --length is ignored are
    covered by the timer).
  - stop() sweeps for orphaned mpv processes still bound to the socket path
    (a prior run's leaked process is invisible if you only track the
    in-process handle).
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

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError

# IPC socket path - platform-aware. Linux uses a Unix socket
# (/tmp/friday_mpv.sock); Windows mpv has no Unix-socket support and
# requires a named pipe (\\.\pipe\friday_mpv). The pipe path form is
# identical to what mpv's --input-ipc-server accepts on Windows.
# See gates/PORTABILITY.md (aspirational Windows port).
SOCKET_PATH = r"\\.\pipe\friday_mpv" if os.name == "nt" else "/tmp/friday_mpv.sock"
MPV_STDERR_LOG = "/tmp/friday_mpv_stderr.log"  # debug log; empty when all is well
DEFAULT_VOLUME = 70
_STARTUP_TIMEOUT = 8.0

_lock = threading.Lock()
_proc: subprocess.Popen | None = None
_timer: threading.Timer | None = None


# ---------------------------------------------------------------- internals


def _pgrep_socket() -> list[int]:
    """PIDs of mpv processes still bound to our IPC socket path.

    POSIX: `pgrep -f` matches mpv procs whose cmdline contains the
    --input-ipc-server=PATH argument (and therefore the named socket file).
    Windows: `tasklist` matches `mpv.exe` procs that were launched with
    our pipe argument (matched via the cmdline column). pgrep/fuser don't
    exist on Windows so the search is done with stdlib tasklist parsing.
    """
    if os.name == "nt":
        return _pgrep_socket_windows()
    pattern = f"mpv.*input-ipc-server={SOCKET_PATH}"
    try:
        out = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True, timeout=5)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    return [int(p) for p in out.stdout.split() if p.strip().isdigit()]


def _pgrep_socket_windows() -> list[int]:
    r"""Windows fallback: match mpv.exe procs whose cmdline names our pipe.

    Uses tasklist (stdlib subprocess, no pywin32 needed) and matches on
    the --input-ipc-server=\\.\pipe\friday_mpv argument to avoid catching
    unrelated mpv instances. A proc whose cmdline we can't read is skipped
    (never killed on guesswork).
    """
    try:
        out = subprocess.run(
            ["tasklist", "/v", "/fo", "csv"],
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    if out.returncode != 0:
        return []
    import csv as _csv

    needle = "input-ipc-server"
    pids: list[int] = []
    # tasklist csv: header row then "name","pid","...","window title"
    for row in _csv.reader(out.stdout.strip().splitlines()[1:]):
        if len(row) < 2:
            continue
        cmdline = " ".join(row)  # tasklist doesn't expose full cmdline easily
        # Fallback: match on the image name 'mpv.exe' - narrower than 'mpv'
        # but tasklist csv image names are the executable.
        if row[0].lower().startswith("mpv") and needle in cmdline:
            try:
                pids.append(int(row[1]))
            except ValueError:
                continue
    return pids


def _pid_alive(pid: int) -> bool:
    """True if the pid exists as a process-table entry (signal 0 probe)."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def _wait_pid_gone(pid: int, timeout: float) -> bool:
    """Wait up to 'timeout' for the pid to leave the process table."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return True
        time.sleep(0.1)
    return False


def _stop_process(proc: subprocess.Popen) -> None:
    """Stop a player we launched and always reap it.

    Escalation ladder: mpv 'quit' over the socket -> SIGTERM -> SIGKILL.
    Each rung waits for the process to exit, and wait() reaps the child
    whichever rung finished it - an exited child can never linger as a
    zombie. If the child is already gone, poll() reaps it and we return.
    """
    if proc.poll() is not None:
        return  # already exited; poll() collected it
    _socket_send({"command": ["quit"]}, timeout=1.0)
    try:
        proc.wait(timeout=5.0)
        return
    except subprocess.TimeoutExpired:
        pass
    with contextlib.suppress(ProcessLookupError):
        proc.terminate()
    try:
        proc.wait(timeout=3.0)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        proc.kill()  # SIGKILL is uncatchable - no player can ignore it
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        # The entry is reaped by the next wait()/poll(), or by init once this
        # process exits - either way it cannot hold the socket.
        pass


def _sweep_orphans() -> list[int]:
    """Kill every listener still holding SOCKET_PATH; never let one survive.

    Two mechanisms: pgrep matches mpv processes whose cmdline names our
    socket; `fuser -k` (if present) catches listeners whose cmdline does not
    mention mpv, e.g. wrapper processes. SIGTERM alone can be ignored by a
    stuck player, so each survivor escalates to SIGKILL after a bounded
    wait, then we verify it is really gone. Any swept pid that is one of our
    own children is reaped so it cannot linger as a zombie (only the parent
    can wait() it).
    """
    global _proc
    if _proc is not None:
        # Defensive, currently future-proofing: every existing call path
        # clears _proc before sweeping (_stop_locked / _launch failure). If a
        # future path forgets, we must not sweep while still holding a live
        # or un-reaped child reference - stop it first so no zombie survives.
        _stop_process(_proc)
        _proc = None
    pids = _pgrep_socket()
    for pid in pids:
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGTERM)
    survivors = [p for p in pids if not _wait_pid_gone(p, 1.5)]
    # SIGKILL is POSIX-only - Windows has no such signal; fall back to
    # SIGTERM there (the Windows port does not use this module yet, but
    # the module must import and typecheck on every platform).
    sigkill = getattr(signal, "SIGKILL", signal.SIGTERM)
    for pid in survivors:
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, sigkill)
    for pid in survivors:
        _wait_pid_gone(pid, 1.5)
    # `fuser -k` is a Linux-only fallback to kill listeners whose cmdline
    # doesn't name mpv (e.g. wrappers). On Windows there is no fuser and no
    # Unix socket path to fight over - named-pipe instances are owned by mpv
    # alone, so the pgrep/tasklist sweep above is sufficient.
    if os.name != "nt":
        with contextlib.suppress(FileNotFoundError, subprocess.TimeoutExpired):
            subprocess.run(["fuser", "-k", SOCKET_PATH], capture_output=True, timeout=5)
    return pids


def _prepare_socket() -> None:
    """Make SOCKET_PATH safe to bind: sweep orphans and unlink a stale
    socket file. Without this, a leaked listener on the path answers IPC
    probes while our own mpv fails to bind and silently exits."""
    _sweep_orphans()
    if os.path.exists(SOCKET_PATH):
        with contextlib.suppress(OSError):
            os.unlink(SOCKET_PATH)


def _socket_send(payload: dict[str, Any], timeout: float = 2.0) -> dict[str, Any] | None:
    r"""Send one newline-delimited JSON request; return the reply, or None if
    no player is listening (connection refused / timeout / garbage).

    POSIX: AF_UNIX stream socket to the mpv --input-ipc-server path.
    Windows: mpv has no Unix-socket support; it exposes a named pipe
    (\\.\pipe\friday_mpv) which we talk to via pywin32 win32file.
    """
    if os.name == "nt":
        return _npipe_send(payload, timeout=timeout)
    # POSIX path below.
    af_unix = getattr(socket, "AF_UNIX", None)
    if af_unix is None:
        return None
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


def _npipe_send(payload: dict[str, Any], timeout: float = 2.0) -> dict[str, Any] | None:
    """Windows named-pipe client to mpv's --input-ipc-server.\\.\\pipe\\...\\s.

    mpv's IPC protocol is identical over a named pipe as over a Unix socket
    (one JSON command + newline per request, reply terminated by \\n). We
    open the pipe with GENERIC_READ | GENERIC_WRITE, send the command, then
    read until newline. A missing mpv (pipe not listening) surfaces as
    FileNotFoundError / pywintypes.error -> None (no player), matching the
    POSIX branch's 'no player listening' semantics.
    """
    import pywintypes
    import win32file

    try:
        handle = win32file.CreateFile(
            SOCKET_PATH,
            win32file.GENERIC_READ | win32file.GENERIC_WRITE,
            0,  # no sharing - mpv owns the pipe instance
            None,
            win32file.OPEN_EXISTING,
            0,
            None,
        )
    except (pywintypes.error, FileNotFoundError, OSError):
        # ERROR_FILE_NOT_FOUND / ERROR_PIPE_BUSY = no listener / busy pipe.
        return None

    try:
        data = (json.dumps(payload) + "\n").encode()
        win32file.WriteFile(handle, data)
        reply = b""
        deadline = time.monotonic() + timeout
        while not reply.endswith(b"\n") and time.monotonic() < deadline:
            # ReadFile may block until a byte arrives; we keep looping until
            # newline or timeout. 4096-byte chunks match the POSIX branch.
            try:
                _, chunk = win32file.ReadFile(handle, 4096)
                if not chunk:
                    break
                reply += chunk
            except pywintypes.error as exc:
                # ERROR_BROKEN_PIPE: mpv closed the pipe mid-read.
                if exc.winerror == 109:
                    break
                raise
        if not reply:
            return None
        try:
            parsed = json.loads(reply.decode(errors="replace"))
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    finally:
        try:
            win32file.CloseHandle(handle)
        except Exception:
            pass


def _wait_socket(timeout: float = _STARTUP_TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _socket_send({"command": ["get_property", "mpv-version"]}) is not None:
            return True
        time.sleep(0.25)
    return False


def _cancel_timer() -> None:
    global _timer
    if _timer is not None:
        _timer.cancel()
        _timer = None


def _stop_locked() -> None:
    """Stop the in-process player (and reap it). Caller must hold _lock."""
    global _proc
    proc = _proc
    if proc is not None:
        _stop_process(proc)
    _proc = None


def _safety_stop() -> None:
    with _lock:
        _stop_locked()
        _sweep_orphans()


def _launch(cmd: list[str], what: str) -> dict[str, Any]:
    global _proc
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=open(MPV_STDERR_LOG, "w"),
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        raise PrimitiveError("mpv binary not found", state="no player started") from exc
    _proc = proc
    if not _wait_socket():
        # Reap the just-launched child before dropping the reference - an
        # exited mpv we never wait() on would linger as a zombie for the
        # rest of this process's life.
        _stop_process(proc)
        _proc = None
        _sweep_orphans()
        raise PrimitiveError(
            f"mpv IPC socket never became ready at {SOCKET_PATH}",
            state="mpv was launched but unreachable; swept",
        )
    return {"pid": proc.pid, "socket": SOCKET_PATH}


# ------------------------------------------------------------------ public


@contract(
    precondition="minutes > 0 and source is a non-empty local path or URL.",
    postcondition="Audio from source plays at the given volume and stops after 'minutes' "
    "minutes (mpv --length plus a one-shot safety timer).",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError if mpv cannot start or its IPC socket never appears; any "
    "pre-existing player is stopped first (replaced, not stacked).",
    returns="dict: {pid, socket, length_s, source}.",
)
def play_for(minutes: float, source: str, volume: int = DEFAULT_VOLUME) -> dict[str, Any]:
    if minutes <= 0:
        raise PreconditionError("play_for requires minutes > 0")
    if not source or not source.strip():
        raise PreconditionError("play_for requires a non-empty source")
    length_s = int(minutes * 60)
    with _lock:
        _stop_locked()
        _cancel_timer()
        _prepare_socket()
        result = _launch(
            [
                "mpv",
                "--no-terminal",
                f"--input-ipc-server={SOCKET_PATH}",
                f"--volume={volume}",
                f"--length={length_s}",
                source,
            ],
            "play_for",
        )
        # One-shot timer, never a polling loop. --length is authoritative;
        # the timer covers sources where --length is ignored.
        _timer = threading.Timer(length_s + 15.0, _safety_stop)
        _timer.daemon = True
        _timer.start()
        return {**result, "length_s": length_s, "source": source}


@contract(
    precondition="source is a non-empty local path or URL.",
    postcondition="Audio from source plays at the given volume until stop() is called.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError if mpv cannot start or its IPC socket never appears; any "
    "pre-existing player is stopped first.",
    returns="dict: {pid, socket, source}.",
)
def play(source: str, volume: int = DEFAULT_VOLUME) -> dict[str, Any]:
    if not source or not source.strip():
        raise PreconditionError("play requires a non-empty source")
    with _lock:
        _stop_locked()
        _cancel_timer()
        _prepare_socket()
        result = _launch(
            [
                "mpv",
                "--no-terminal",
                f"--input-ipc-server={SOCKET_PATH}",
                f"--volume={volume}",
                source,
            ],
            "play",
        )
        return {**result, "source": source}


@contract(
    precondition="None - stopping with nothing playing is a harmless no-op.",
    postcondition="No mpv process is left bound to SOCKET_PATH and the socket file is gone.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="None expected; stubborn processes are SIGTERM'd by the orphan sweep.",
    returns="None",
)
def stop() -> None:
    with _lock:
        _stop_locked()
        _cancel_timer()
        _sweep_orphans()
        if os.path.exists(SOCKET_PATH):
            with contextlib.suppress(OSError):
                os.unlink(SOCKET_PATH)


def _reply_ok(reply: dict[str, Any] | None) -> bool:
    """mpv replies carry `"error": "success"` on success - treat that as ok."""
    return reply is not None and reply.get("error") in (None, "success")


@contract(
    precondition="None.",
    postcondition="Makes no state changes; reports whether audio is currently playing.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="Never raises: no player -> False.",
    returns="bool",
)
def is_playing() -> bool:
    idle = _socket_send({"command": ["get_property", "core-idle"]})
    if idle is None or not _reply_ok(idle):
        return False
    paused = _socket_send({"command": ["get_property", "pause"]})
    if paused and _reply_ok(paused) and paused.get("data"):
        return False
    return not bool(idle.get("data"))


@contract(
    precondition="0 <= percent <= 100.",
    postcondition="If a player is running, its volume is set to percent.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="PreconditionError on out-of-range volume; no-op (not an error) when no "
    "player is running.",
    returns="None",
)
def set_volume(percent: int) -> None:
    if not 0 <= percent <= 100:
        raise PreconditionError("volume must be between 0 and 100")
    _socket_send({"command": ["set_property", "volume", percent]})


@contract(
    precondition="None.",
    postcondition="If a player is running it pauses.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="No-op when no player is running.",
    returns="None",
)
def pause() -> None:
    _socket_send({"command": ["set_property", "pause", True]})


@contract(
    precondition="None.",
    postcondition="If a paused player is running it resumes.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="No-op when no player is running.",
    returns="None",
)
def resume() -> None:
    _socket_send({"command": ["set_property", "pause", False]})


# ---- gate-registered media.get_volume (2026-08-14) ----


@contract(
    precondition="None - reports current state with no caller obligations.",
    postcondition="Makes NO state changes. Returns the current playback volume "
    "(0-100) of the running mpv player, or None if no player is reachable. "
    "Distinct from set_volume, which writes.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="Never raises: a missing or unreachable mpv player is reported "
    "as None, not an error. An mpv IPC reply that lacks a volume value is "
    "also treated as None.",
    returns="int | None - the current volume in the 0-100 range, or None when no player responds.",
)
def get_volume() -> int | None:
    """Return the current mpv playback volume (0-100), or None if no player is reachable.

    Read-only counterpart to set_volume. Sends a single get_property
    request over the mpv IPC socket; if the player is not running, the socket
    request fails, or the reply carries an error, returns None instead of
    raising - the goal \"what is the current media volume level\" is answered
    with absence, not a crash.
    """
    reply = _socket_send({"command": ["get_property", "volume"]})
    if reply is None or not _reply_ok(reply):
        return None
    data = reply.get("data")
    if isinstance(data, (int, float)) and 0 <= data <= 100:
        return int(data)
    return None


# ---- gate-registered media.get_playing_title (2026-08-14) ----


@contract(
    precondition="None - reports current state with no caller obligations.",
    postcondition="Makes NO state changes. Returns the current media-title property of "
    "the running mpv player, or None if no player is reachable. Distinct from "
    "media.play/play_for, which start playback.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="Never raises: a missing or unreachable mpv player is reported "
    "as None, not an error. An mpv IPC reply that lacks a title value or "
    "carries an error is also treated as None.",
    returns="str | None - the current media title (mpv 'media-title' "
    "property), or None when no player responds or the property is "
    "unavailable.",
)
def get_playing_title() -> str | None:
    """Return the current mpv media title, or None if no player is reachable.

    Read-only query counterpart to play/play_for. Sends a single
    get_property request for 'media-title' over the mpv IPC socket;
    if the player is not running, the socket request fails, or the
    reply carries an error, returns None instead of raising - the goal
    "what song is currently playing" is answered with absence, not a
    crash.
    """
    reply = _socket_send({"command": ["get_property", "media-title"]})
    if reply is None or not _reply_ok(reply):
        return None
    data = reply.get("data")
    if isinstance(data, str) and data.strip():
        return data
    return None


# ---- gate-registered media.seek (2026-08-15) ----
@contract(
    precondition="position_s >= 0; player is running (or returns gracefully).",
    postcondition="Seeks the player to the specified position in seconds.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="No-op when no player is running; PrimitiveError on invalid position.",
    returns="dict: {success: bool, position_s: float}.",
)
def seek(position_s: float) -> dict[str, Any]:
    """Seek to a position in the currently playing media.

    Seeks the mpv player to the specified position in seconds.
    If no player is running, returns {success: False} gracefully
    rather than raising an error.

    Args:
        position_s: Position to seek to (>= 0.0)

    Returns:
        dict with success status and the position seeked to
    """
    if position_s < 0:
        raise PreconditionError("seek requires position_s >= 0")
    reply = _socket_send({"command": ["set_property", "time-pos", position_s]})
    return {"success": _reply_ok(reply), "position_s": position_s}


# ---- media.list_playlists ----
@contract(
    precondition="None.",
    postcondition="Returns list of available playlist entries (title and position).",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="No-op when no player running; returns empty list gracefully.",
    returns="list[dict]: list of {index, title, duration_s, played_count, duration_str}.",
)
def list_playlists() -> list[dict[str, Any]]:
    """List the current playlist contents.

    Returns a list of playlist entries with their properties (index,
    title, duration, etc.). Returns empty list when no player is running.

    Returns:
        List of playlist entry dicts
    """
    reply = _socket_send({"command": ["get_property", "playlist"]})
    if reply is None or not _reply_ok(reply):
        return []
    playlist = reply.get("data", [])
    if not isinstance(playlist, list):
        return []
    result = []
    for entry in playlist:
        if not isinstance(entry, dict):
            continue
        title = entry.get("title", "") or "Unknown"
        result.append(
            {
                "index": entry.get("index", -1),
                "title": str(title),
                "duration_s": entry.get("duration", -1),
                "played_count": entry.get("played_count", 0),
            }
        )
    return result


# ---- media.play_media ----
@contract(
    precondition="source is a non-empty local path or URL.",
    postcondition="Plays media file/URL at the given volume until stopped.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError if mpv cannot start or its IPC socket never appears.",
    returns="dict: {pid, socket, source, volume}.",
)
def play_media(source: str, volume: int = DEFAULT_VOLUME) -> dict[str, Any]:
    """Play a media file or URL directly.

    Convenience wrapper around play() with explicit source parameter.
    Stops any currently playing media before starting new playback.

    Args:
        source: Path to media file or URL
        volume: Volume level (0-100, default 70)

    Returns:
        dict with pid, socket path, source, and volume
    """
    if not source or not source.strip():
        raise PreconditionError("play_media requires a non-empty source")
    if not 0 <= volume <= 100:
        raise PreconditionError("volume must be between 0 and 100")
    return play(source, volume=volume)
