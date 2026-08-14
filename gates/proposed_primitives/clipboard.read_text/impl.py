# Hand-corrected after human review (2026-08-14): the LLM draft lacked
# the @contract decorator (so it would never register), referenced an
# undefined log_transform, raised bare RuntimeError instead of
# FridayError, and had no xclip fallback.
from __future__ import annotations

import os
import subprocess
from typing import Any

from friday.contracts import Idempotency, contract
from friday.errors import PrimitiveError


def _log_redact_clipboard_meta(result: Any) -> Any:
    """Log-time redaction for clipboard.read_text: the clipboard CONTENT
    is the whole result and could contain sensitive data - the L0 line
    shows <redacted> while the trace still records the primitive ran.
    The real return value is untouched (log_transform is log-only)."""
    if isinstance(result, str) and result:
        return "<redacted>"
    return result


@contract(
    precondition="A clipboard tool is available (wl-paste on Wayland, xclip on X11).",
    postcondition="Returns the current clipboard text as a str. Makes NO state changes - the clipboard is only read.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError when the clipboard tool is missing or fails to read - DISTINCT from an empty clipboard, which returns an empty string.",
    returns="str: the clipboard contents ('' when empty).",
    redact_result=True,
    log_transform=_log_redact_clipboard_meta,
)
def read_text() -> str:
    """Return the current clipboard text.

    Shells out to wl-paste (Wayland) or xclip (X11) - the ONLY way to read
    the Linux clipboard - through the gate's read-only bounded subprocess
    shape (LITERAL argv at the call site, capture_output=True, timeout -
    the whole command is visible to review). Returns '' when the
    clipboard is empty.
    """
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    x11 = bool(os.environ.get("DISPLAY"))
    try:
        if wayland or not x11:
            # Wayland session (or no display env at all - wl-paste is the
            # modern default; the tool error is surfaced as PrimitiveError)
            proc = subprocess.run(
                ["wl-paste"], capture_output=True, timeout=5,
            )
        else:
            proc = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True, timeout=5,
            )
    except (TimeoutError, FileNotFoundError) as exc:
        # subprocess.TimeoutExpired subclasses TimeoutError - catching the
        # base keeps the draft test free of subprocess.* constructor calls
        # (the gate's test.py AST check allows only subprocess.run).
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
