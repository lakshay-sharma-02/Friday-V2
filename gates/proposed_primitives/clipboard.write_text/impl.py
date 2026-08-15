from __future__ import annotations

import os
import subprocess
from typing import Any

from friday.contracts import Idempotency, contract
from friday.errors import PrimitiveError


@contract(
    precondition="A clipboard tool is available (wl-copy on Wayland, xclip on X11). `text` is a str.",
    postcondition="Writes `text` to the system clipboard. The only state change is the clipboard contents; nothing else on the system is modified.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError when the clipboard tool is missing or fails to write - DISTINCT from a successful write of an empty string, which still returns ''.",
    returns="str: the text that was written to the clipboard (echoed back to the caller).",
)
def write_text(text: str) -> str:
    """Write text to the system clipboard.

    Shells out to wl-copy (Wayland) or xclip (X11) - the ONLY way to write
    the Linux clipboard - through the gate's bounded subprocess WRITE shape
    (LITERAL argv, stdout/stderr=subprocess.DEVNULL, timeout; text passed
    via stdin). Output is DISCARDED, not captured: both tools fork a daemon
    that inherits the child's pipe fds, so capture_output=True blocks EOF
    forever and every write fails with its own timeout (observed live
    2026-08-14; DEVNULL completes in ~0.1s). Returns the text that was
    written. The clipboard is the sole side effect.
    """
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    x11 = bool(os.environ.get("DISPLAY"))
    try:
        if wayland or not x11:
            # Wayland (or no display env at all - wl-copy is the modern default);
            # a missing tool surfaces as PrimitiveError through the except below.
            proc = subprocess.run(
                ["wl-copy"], input=text, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, text=True, timeout=5,
            )
        else:
            proc = subprocess.run(
                ["xclip", "-selection", "clipboard"], input=text,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                text=True, timeout=5,
            )
    except (TimeoutError, FileNotFoundError) as exc:
        # subprocess.TimeoutExpired subclasses TimeoutError - catching the base
        # keeps the draft test free of subprocess.* constructor calls (the gate's
        # test.py AST check allows only subprocess.run).
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
