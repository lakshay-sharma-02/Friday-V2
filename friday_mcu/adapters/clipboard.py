"""Clipboard adapter — read/write clipboard content."""

from __future__ import annotations

import subprocess
from typing import Any

from friday_mcu.adapters import Adapter, register_adapter
from friday_mcu.core.contracts import Idempotency, contract
from friday_mcu.core.errors import PrimitiveError


def _run_clipboard(cmd: list[str], input_text: str = "") -> str:
    """Run a clipboard command and return output."""
    try:
        result = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout
    except FileNotFoundError:
        raise PrimitiveError("clipboard tool not found (install xclip or wl-clipboard)")
    except subprocess.TimeoutExpired as exc:
        raise PrimitiveError("clipboard command timed out") from exc


@contract(
    precondition="A clipboard tool is available.",
    postcondition="Returns the clipboard text content.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if clipboard read fails.",
    returns="str: the clipboard text.",
)
def read_text() -> str:
    """Read text from the clipboard."""
    # Try wl-paste (Wayland), then xclip (X11), then powershell (Windows)
    for cmd in [["wl-paste"], ["xclip", "-selection", "clipboard", "-o"]]:
        try:
            return _run_clipboard(cmd).strip()
        except PrimitiveError:
            continue
    # Windows fallback
    try:
        result = subprocess.run(
            ["powershell", "-command", "Get-Clipboard"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        raise PrimitiveError("no clipboard tool available")


@contract(
    precondition="text is a string.",
    postcondition="The text is in the clipboard.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="PrimitiveError if clipboard write fails.",
    returns="str: the text that was written.",
)
def write_text(text: str) -> str:
    """Write text to the clipboard."""
    for cmd in [["wl-copy"], ["xclip", "-selection", "clipboard"]]:
        try:
            _run_clipboard(cmd, input_text=text)
            return text
        except PrimitiveError:
            continue
    # Windows fallback
    try:
        subprocess.run(
            ["powershell", "-command", f"Set-Clipboard -Value '{text}'"],
            capture_output=True, text=True, timeout=5,
        )
        return text
    except Exception:
        raise PrimitiveError("no clipboard tool available")


class ClipboardAdapter(Adapter):
    @property
    def name(self) -> str:
        return "clipboard"

    @property
    def capabilities(self) -> list[str]:
        return ["read_text", "write_text"]

    async def initialize(self) -> None:
        pass

    async def execute(self, action: str, **kwargs: Any) -> Any:
        if action == "read_text":
            return read_text()
        elif action == "write_text":
            return write_text(**kwargs)
        raise PrimitiveError(f"Unknown clipboard action: {action}")

    async def observe(self) -> list:
        return []

    def health_check(self) -> bool:
        return True


try:
    register_adapter(ClipboardAdapter())
except Exception:
    pass
