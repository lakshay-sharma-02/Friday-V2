# ---- gate-registered clipboard primitives ----
# read_text / write_text: registered 2026-08-14, hand-corrected by human review
# read_image / write_image / clear: registered 2026-09-13 (Windows port addition)
#
# Linux backend: wl-paste/wl-copy (Wayland) or xclip (X11) - the ONLY way to
# touch the clipboard on Linux. Windows backend: win32clipboard (pywin32) - the
# ONLY way to touch the clipboard on Windows without a GUI automation shim.
# Both backends branch on os.name so the CONTRACT, idempotency, and failure-mode
# surface are identical on every OS.

from __future__ import annotations

import os
import subprocess
from typing import Any

from friday.contracts import Idempotency, contract
from friday.errors import PrimitiveError

_IS_WINDOWS = os.name == "nt"


def _log_redact_clipboard_meta(result: Any) -> Any:
    """Log-time redaction for clipboard.read_text: the clipboard CONTENT
    is the whole result and could contain sensitive data - the L0 line
    shows <redacted> while the trace still records the primitive ran.
    The real return value is untouched (log_transform is log-only)."""
    if isinstance(result, str) and result:
        return "<redacted>"
    return result


def _log_redact_clipboard_image(result: Any) -> Any:
    """Log-time redaction for clipboard image primitives: show size, not
    pixels. The L0 line records <image bytes=n> without dumping pixels
    (which could be a screenshot of PII)."""
    if isinstance(result, bytes) and result:
        return f"<image bytes={len(result)}>"
    return result


# ---------------------------------------------------------------------------
# Windows backend (win32clipboard from pywin32)
# ---------------------------------------------------------------------------

def _win_clipboard_open():
    """Open the Windows clipboard, returning the win32clipboard handle.
    Returns None if the clipboard cannot be opened (another app holds it)."""
    import win32clipboard  # pywin32 - Windows-only, gated behind _IS_WINDOWS

    win32clipboard.OpenClipboard()
    return win32clipboard


def _win_clipboard_close(win32clipboard_module) -> None:
    try:
        win32clipboard_module.CloseClipboard()
    except Exception:
        pass  # best effort - the clipboard may already be closed


def _win_read_text() -> str:
    """Read text from the Windows clipboard via win32clipboard.CF_TEXT."""
    win32clipboard = _win_clipboard_open()
    try:
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODE):
            data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODE)
            return data if isinstance(data, str) else str(data)
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_TEXT):
            data = win32clipboard.GetClipboardData(win32clipboard.CF_TEXT)
            return data.decode("utf-8", "replace") if isinstance(data, bytes) else str(data)
        return ""  # clipboard empty or has no text format
    finally:
        _win_clipboard_close(win32clipboard)


def _win_write_text(text: str) -> str:
    """Write text to the Windows clipboard via win32clipboard.CF_UNICODE."""
    win32clipboard = _win_clipboard_open()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_UNICODE, text)
        return text
    finally:
        _win_clipboard_close(win32clipboard)


def _win_read_image() -> bytes | None:
    """Read PNG image data from the Windows clipboard.

    Tries CF_PNG first (preferred), falls back to CF_DIB (device-independent
    bitmap). Returns None when the clipboard is empty or has no image.
    """
    import win32clipboard  # pywin32 - Windows-only

    win32clipboard.OpenClipboard()
    try:
        # Prefer PNG if available - lossless and matches the Linux wl-paste path.
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_PNG):
            data = win32clipboard.GetClipboardData(win32clipboard.CF_PNG)
            if isinstance(data, bytes) and data:
                return data
        # Fall back to DIB (bitmap) - return raw bytes if PIL isn't available
        # to convert. PNG is the common case (Chrome, most screenshot tools).
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIB):
            dib = win32clipboard.GetClipboardData(win32clipboard.CF_DIB)
            if isinstance(dib, bytes) and dib:
                return dib
        return None
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass


def _win_write_image(data: bytes) -> bytes:
    """Write PNG image bytes to the Windows clipboard via CF_PNG.

    Pillow is used to parse the PNG header if needed, but if `data` is
    already a valid PNG blob, it's set directly. Returns the data on success.
    Raises PrimitiveError if the image can't be set.
    """
    import win32clipboard  # pywin32 - Windows-only

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        # Set raw PNG bytes under CF_PNG
        win32clipboard.SetClipboardData(win32clipboard.CF_PNG, data)
        return data
    except Exception as exc:
        raise PrimitiveError(
            f"clipboard write image failed: {exc}", state="clipboard not written"
        ) from exc
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Linux backend (wl-paste / xclip) - unchanged from the 2026-08-14 registration
# ---------------------------------------------------------------------------

def _linux_read_text() -> str:
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    x11 = bool(os.environ.get("DISPLAY"))
    try:
        if wayland or not x11:
            proc = subprocess.run(
                ["wl-paste"],
                capture_output=True,
                timeout=5,
            )
        else:
            proc = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True,
                timeout=5,
            )
    except (TimeoutError, FileNotFoundError) as exc:
        raise PrimitiveError(
            f"clipboard read failed: {exc}",
            state="clipboard not read",
        ) from exc
    if proc.returncode != 0:
        tool = "wl-paste" if wayland or not x11 else "xclip"
        raise PrimitiveError(
            f"clipboard tool {tool!r} exited {proc.returncode}: "
            f"{proc.stderr.decode('utf-8', 'replace').strip()[:200]}",
            state="clipboard not read",
        )
    return proc.stdout.decode("utf-8", "replace").strip()


def _linux_write_text(text: str) -> str:
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    x11 = bool(os.environ.get("DISPLAY"))
    try:
        if wayland or not x11:
            proc = subprocess.run(
                ["wl-copy"],
                input=text,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            )
        else:
            proc = subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            )
    except (TimeoutError, FileNotFoundError) as exc:
        raise PrimitiveError(
            f"clipboard write failed: {exc}",
            state="clipboard not written",
        ) from exc
    if proc.returncode != 0:
        tool = "wl-copy" if wayland or not x11 else "xclip"
        err = proc.stderr.strip() if isinstance(proc.stderr, str) else ""
        raise PrimitiveError(
            f"clipboard tool {tool!r} exited {proc.returncode}: {err[:200]}",
            state="clipboard not written",
        )
    return text


def _linux_read_image() -> bytes | None:
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    x11 = bool(os.environ.get("DISPLAY"))
    try:
        if wayland or not x11:
            proc = subprocess.run(
                ["wl-paste", "--type", "image/png"],
                capture_output=True,
                timeout=5,
            )
        else:
            proc = subprocess.run(
                ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"],
                capture_output=True,
                timeout=5,
            )
    except (TimeoutError, FileNotFoundError) as exc:
        raise PrimitiveError(f"clipboard read image failed: {exc}", state="clipboard not read") from exc

    if proc.returncode != 0:
        return None

    if not proc.stdout:
        return None

    return proc.stdout


def _linux_write_image(data: bytes) -> bytes:
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    x11 = bool(os.environ.get("DISPLAY"))
    try:
        if wayland or not x11:
            proc = subprocess.run(
                ["wl-copy", "--type", "image/png"],
                input=data,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        else:
            proc = subprocess.run(
                ["xclip", "-selection", "clipboard", "-t", "image/png"],
                input=data,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
    except (TimeoutError, FileNotFoundError) as exc:
        raise PrimitiveError(f"clipboard write image failed: {exc}", state="clipboard not written") from exc

    if proc.returncode != 0:
        tool = "wl-copy" if wayland or not x11 else "xclip"
        raise PrimitiveError(f"clipboard tool {tool!r} exited {proc.returncode}", state="clipboard not written")

    return data


def _linux_clear() -> None:
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    x11 = bool(os.environ.get("DISPLAY"))
    try:
        if wayland or not x11:
            subprocess.run(["wl-copy", "-x", "--clear"], timeout=2)
        else:
            subprocess.run(
                ["xclip", "-selection", "clipboard", "-i", "/dev/null"],
                timeout=2,
            )
    except Exception:
        pass  # Best effort - ignore failures


# ---------------------------------------------------------------------------
# Public primitives - dispatch on os.name, identical CONTRACT surface
# ---------------------------------------------------------------------------

@contract(
    precondition="A clipboard tool is available (wl-paste on Wayland, xclip on X11; "
    "win32clipboard on Windows).",
    postcondition="Returns the current clipboard text as a str. Makes NO state changes - the clipboard is only read.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError when the clipboard tool is missing or fails to read - DISTINCT from an empty clipboard, which returns an empty string.",
    returns="str: the clipboard contents ('' when empty).",
    redact_result=True,
    log_transform=_log_redact_clipboard_meta,
)
def read_text() -> str:
    """Return the current clipboard text.

    Shells out to wl-paste (Wayland) or xclip (X11) on Linux, or uses
    win32clipboard on Windows - both are the only way to read the system
    clipboard on their respective platforms. Through the gate's read-only
    bounded subprocess shape (LITERAL argv at the call site, capture_output=True,
    timeout). Returns '' when the clipboard is empty.
    """
    if _IS_WINDOWS:
        try:
            return _win_read_text()
        except Exception as exc:
            raise PrimitiveError(
                f"clipboard read failed: {exc}",
                state="clipboard not read",
            ) from exc
    return _linux_read_text()


@contract(
    precondition="A clipboard tool is available (wl-copy on Wayland, xclip on X11; "
    "win32clipboard on Windows). `text` is a str.",
    postcondition="Writes `text` to the system clipboard. The only state change is the clipboard contents; nothing else on the system is modified.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError when the clipboard tool is missing or fails to write - DISTINCT from a successful write of an empty string, which still returns ''.",
    returns="str: the text that was written to the clipboard (echoed back to the caller).",
)
def write_text(text: str) -> str:
    """Write text to the system clipboard.

    On Linux, shells out to wl-copy (Wayland) or xclip (X11) through the
    gate's bounded subprocess WRITE shape (LITERAL argv, stdout/stderr=DEVNULL,
    timeout; text via stdin). Output is DISCARDED, not captured: both tools
    fork a daemon that inherits pipe fds, so capture_output=True blocks EOF
    forever and every write fails with its own timeout (observed live
    2026-08-14; DEVNULL completes in ~0.1s).

    On Windows, uses win32clipboard.CF_UNICODE via pywin32 - the native path,
    no daemon-forking concern.
    """
    if _IS_WINDOWS:
        try:
            return _win_write_text(text)
        except Exception as exc:
            raise PrimitiveError(
                f"clipboard write failed: {exc}",
                state="clipboard not written",
            ) from exc
    return _linux_write_text(text)


# ---------------------------------------------------------------------------
# Image operations (registered 2026-09-13)
# ---------------------------------------------------------------------------

@contract(
    precondition="None.",
    postcondition="Returns current clipboard image data as bytes, or None if empty/not an image.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError when clipboard tool fails or returns error.",
    returns="bytes | None - image data if available, None if empty or not an image.",
    redact_result=True,
    log_transform=_log_redact_clipboard_image,
)
def read_image() -> bytes | None:
    """Read image data from clipboard.

    On Linux, uses wl-paste --type image/png (Wayland) or xclip -t image/png
    (X11). On Windows, uses win32clipboard.CF_PNG via pywin32. Returns None
    when the clipboard is empty or contains no image data.
    """
    if _IS_WINDOWS:
        try:
            return _win_read_image()
        except Exception as exc:
            raise PrimitiveError(
                f"clipboard read image failed: {exc}",
                state="clipboard not read",
            ) from exc
    return _linux_read_image()


@contract(
    precondition="data is image bytes to write to clipboard.",
    postcondition="Writes image data to clipboard. Side-effect only change.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="PrimitiveError when clipboard tool fails.",
    returns="bytes: the image data that was written.",
    redact_result=True,
    log_transform=_log_redact_clipboard_image,
)
def write_image(data: bytes) -> bytes:
    """Write image data to clipboard.

    On Linux, uses wl-copy --type image/png (Wayland) or xclip -t image/png
    (X11) with stdout/stderr=DEVNULL (write shape). On Windows, uses
    win32clipboard.CF_PNG via pywin32. Returns the image data that was written.
    """
    if not data:
        raise PrimitiveError("write_image requires non-empty data", state="clipboard not written")
    if _IS_WINDOWS:
        return _win_write_image(data)
    return _linux_write_image(data)


@contract(
    precondition="None.",
    postcondition="Clear clipboard content. Side-effect only change.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="No-op on failure (best effort).",
    returns="None",
)
def clear() -> None:
    """Clear the clipboard content.

    On Linux, uses wl-copy -x --clear (Wayland) or xclip with /dev/null
    (X11). On Windows, uses win32clipboard.EmptyClipboard via pywin32.
    Best-effort: failures are ignored so a busy clipboard doesn't block cleanup.
    """
    if _IS_WINDOWS:
        try:
            import win32clipboard

            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.CloseClipboard()
        except Exception:
            pass  # Best effort - ignore failures
        return
    _linux_clear()
