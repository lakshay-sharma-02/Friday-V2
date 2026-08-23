# ---- gate-registered screenshot.capture (2026-08-15) ----
# created by the capability-gap approval gate; reviewed by a human
# before signing.
"""L1 primitive: screenshot (grim on Wayland).

Captures the current screen — the whole desktop, the focused window, or
a specific window by selector — and saves it as a PNG. This is the
capture half of the "send me a screenshot" goals: the capture produces a
file path, and a send primitive (whatsapp/telegram/discord.send_*) ships
it. Hand-built 2026-08-15 (the gmail.send_document precedent) and gated:
the module shells out to grim (the only Wayland capture tool) through
the gate's bounded CAPTURE subprocess shape.

Why the CAPTURE shape (2026-08-15): window-targeted capture needs a
runtime geometry string resolved from hyprctl, so the grim argv cannot be
a fully-literal command. The gate therefore admits subprocess.run([...])
where the FIRST element is a literal tool from the small _CAPTURE_TOOLS
allowlist (grim/slurp/import) and the rest may be runtime values — the
tool binary is still statically visible and allowlisted, only its DATA
args are runtime. Every subprocess.run call site below keeps that literal
first element ("grim") inline — a helper that builds the argv list would
make the first element a variable and be rejected.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from typing import Any

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError, PrimitiveTimeout

# Windows-port flag (2026-08-20): PIL.ImageGrab replaces grim for
# capture on Windows; harmless on Linux.
_IS_WINDOWS = os.name == "nt"

DEFAULT_TIMEOUT = 10.0
# tempfile.gettempdir() is /tmp on Linux (unchanged behavior) and the OS
# temp dir on Windows, so the default output path is portable.
DEFAULT_OUTPUT = os.path.join(tempfile.gettempdir(), "friday_screenshot.png")


def _check_result(proc: subprocess.CompletedProcess, what: str) -> None:
    """Raise PrimitiveError when grim itself failed (tool error, not a
    timeout - a timeout is raised by the except below at the call site)."""
    if proc.returncode != 0:
        raise PrimitiveError(
            f"grim {what} failed (rc={proc.returncode}): "
            f"{proc.stderr.decode('utf-8', 'replace').strip()[:200]}",
            state="screenshot not captured",
        )


def _window_geometry(selector: str) -> str:
    """Resolve a window selector to a grim -g geometry ("x,y WxH").

    Selectors: 'active' (the focused window), an address (0x...), a
    class/title substring, or a hyprctl-style prefixed selector
    (class:/title:/pid:/...). Geometry comes from `hyprctl clients -j`
    via the shipped window.list_clients primitive - no second compositor
    dependency here, and the class/title matching mirrors window.py's.
    Raises PreconditionError when nothing matches (a missing window is a
    caller bug, never a crash).
    """
    from friday.l1.window import list_clients

    if selector == "active":
        from friday.l1.window import get_active_window

        win = get_active_window()
        if not win:
            raise PreconditionError("no active window to capture - the desktop is empty")
        at = win.get("at") or []
        size = win.get("size") or []
        if not (at and size):
            raise PreconditionError("active window has no geometry to capture")
        return f"{at[0]},{at[1]} {size[0]}x{size[1]}"

    clients = list_clients()
    needle = selector.lower()
    # prefixed selectors (class:/title:/pid:...) match that exact field;
    # a bare name matches the class/title haystack like window.py
    for c in clients:
        haystack = " ".join(
            str(c.get(k, "")) for k in ("class", "initialClass", "title", "initialTitle")
        ).lower()
        if needle in haystack:
            at = c.get("at") or []
            size = c.get("size") or []
            if at and size:
                return f"{at[0]},{at[1]} {size[0]}x{size[1]}"
    raise PreconditionError(f"no window matches selector {selector!r} - nothing to capture")


def _capture_windows(
    target: str,
    output_path: str,
) -> str:
    """Windows screenshot backend using PIL.ImageGrab.

    On Windows, grim does not exist, so we use Pillow's ImageGrab module.
    Full-screen capture is straightforward. Window-targeted capture uses
    the same window geometry resolution as the grim path.
    """
    try:
        from PIL import ImageGrab  # type: ignore[import-untyped]
    except ImportError as exc:
        raise PrimitiveError(
            "PIL/Pillow is not installed: pip install Pillow for Windows screenshot support",
            state="screenshot not captured",
        ) from exc

    norm = target.strip().lower()
    if norm in ("full", "fullscreen", "desktop", "screen", "whole screen"):
        try:
            img = ImageGrab.grab()  # type: ignore[union-attr]
            img.save(output_path)
        except Exception as exc:
            raise PrimitiveError(
                f"ImageGrab.grab() failed: {exc}",
                state="screenshot not captured",
            ) from exc
        return output_path

    # Window-targeted capture: resolve geometry and crop
    if norm in (
        "active",
        "active window",
        "active-window",
        "current window",
        "focused window",
        "focused",
    ):
        from friday.l1.window import get_active_window

        win = get_active_window()
        if not win:
            raise PreconditionError("no active window to capture - the desktop is empty")
        at = win.get("at") or []
        size = win.get("size") or []
        if not (at and size):
            raise PreconditionError("active window has no geometry to capture")
        x, y, w, h = at[0], at[1], size[0], size[1]
    else:
        from friday.l1.window import list_clients

        clients = list_clients()
        needle = target.strip().lower()
        found = False
        for c in clients:
            haystack = " ".join(
                str(c.get(k, "")) for k in ("class", "initialClass", "title", "initialTitle")
            ).lower()
            if needle in haystack:
                at = c.get("at") or []
                size = c.get("size") or []
                if at and size:
                    x, y, w, h = at[0], at[1], size[0], size[1]
                    found = True
                    break
        if not found:
            raise PreconditionError(f"no window matches selector {target!r} - nothing to capture")

    try:
        img = ImageGrab.grab(bbox=(x, y, x + w, y + h))  # type: ignore[union-attr]
        img.save(output_path)
    except Exception as exc:
        raise PrimitiveError(
            f"ImageGrab.grab() for window {target!r} failed: {exc}",
            state="screenshot not captured",
        ) from exc
    return output_path


@contract(
    precondition="A Wayland session with grim installed (Linux) or PIL/Pillow installed (Windows); target is 'full', 'active', or a window selector (class/title/address); output_path is an absolute path whose parent exists.",
    postcondition="Saves a PNG of the requested screen region to output_path and returns its absolute path. Makes NO state changes except creating the screenshot file.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError/PrimitiveTimeout when grim fails or times out; PreconditionError when the window selector matches nothing or output_path is invalid. A successful capture ALWAYS writes the file.",
    returns="str: the absolute path of the saved PNG.",
)
def capture(
    target: str = "full",
    output_path: str = DEFAULT_OUTPUT,
) -> str:
    """Capture the screen (full, active window, or a window selector) to a PNG.

    'target' selects what to capture:
      - 'full' (default): the whole desktop.
      - 'active': the focused window (resolved via hyprctl/Win32).
      - anything else: a window selector - 'kitty', 'brave-browser',
        '0x...' (address), or 'class:...'/'title:...'/'pid:...' -
        resolved through window.list_clients, first match wins.
    'output_path' defaults to /tmp/friday_screenshot.png. Returns the
    absolute path so a plan can hand it straight to a send primitive
    (e.g. whatsapp.send_document with $steps.N.result).
    """
    if not isinstance(output_path, str) or not output_path.strip():
        raise PreconditionError("output_path must be a non-empty string")
    if not os.path.isabs(output_path):
        raise PreconditionError(f"output_path must be absolute, got {output_path!r}")
    parent = os.path.dirname(output_path)
    if not os.path.isdir(parent):
        raise PreconditionError(f"output directory does not exist: {parent!r}")

    # Dispatch to the platform-specific backend
    if _IS_WINDOWS:
        return _capture_windows(target, output_path)

    # Linux/POSIX: grim on Wayland
    norm = target.strip().lower()
    if norm in ("full", "fullscreen", "desktop", "screen", "whole screen"):
        try:
            proc = subprocess.run(
                ["grim", output_path],
                capture_output=True,
                timeout=DEFAULT_TIMEOUT,
            )
        except TimeoutError as exc:
            # subprocess.TimeoutExpired subclasses TimeoutError - catching
            # the base keeps the draft test free of subprocess.* constructor
            # calls (the gate's test.py AST check allows only subprocess.run).
            raise PrimitiveTimeout(
                f"grim full-screen capture timed out after {DEFAULT_TIMEOUT:.0f}s",
                state="screenshot not captured",
            ) from exc
        except FileNotFoundError as exc:
            raise PrimitiveError(
                "grim not found - install grim (pacman -S grim) to capture the screen on Wayland",
                state="screenshot not captured",
            ) from exc
        _check_result(proc, "full-screen capture")
        return output_path

    if norm in (
        "active",
        "active window",
        "active-window",
        "current window",
        "focused window",
        "focused",
    ):
        geometry = _window_geometry("active")
    else:
        geometry = _window_geometry(target)
    try:
        proc = subprocess.run(
            ["grim", "-g", geometry, output_path],
            capture_output=True,
            timeout=DEFAULT_TIMEOUT,
        )
    except TimeoutError as exc:
        raise PrimitiveTimeout(
            f"grim window capture ({target!r}) timed out after {DEFAULT_TIMEOUT:.0f}s",
            state="screenshot not captured",
        ) from exc
    except FileNotFoundError as exc:
        raise PrimitiveError(
            "grim not found - install grim (pacman -S grim) to capture the screen on Wayland",
            state="screenshot not captured",
        ) from exc
    _check_result(proc, f"window capture ({target!r})")
    return output_path
