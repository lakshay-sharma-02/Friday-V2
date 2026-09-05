"""Notify adapter — desktop notifications (cross-platform)."""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from friday_mcu.adapters import Adapter, register_adapter
from friday_mcu.core.contracts import Idempotency, contract
from friday_mcu.core.errors import PrimitiveError


@contract(
    precondition="title is non-empty.",
    postcondition="A desktop notification is displayed.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError if notification fails.",
    returns="dict: {delivered: bool}.",
)
def notify_send(title: str, body: str = "", timeout_ms: int = 5000) -> dict[str, bool]:
    """Send a desktop notification."""
    # Try Linux (notify-send), then Windows (PowerShell), then macOS
    if sys.platform == "linux":
        try:
            subprocess.run(
                ["notify-send", "-t", str(timeout_ms), title, body],
                capture_output=True,
                timeout=5,
            )
            return {"delivered": True}
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    elif sys.platform == "win32":
        try:
            ps_cmd = f"[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); [System.Windows.Forms.MessageBox]::Show('{body}', '{title}')"
            subprocess.run(["powershell", "-command", ps_cmd], capture_output=True, timeout=5)
            return {"delivered": True}
        except Exception:
            pass
    return {"delivered": False}


class NotifyAdapter(Adapter):
    @property
    def name(self) -> str:
        return "notify"

    @property
    def capabilities(self) -> list[str]:
        return ["notify_send"]

    async def initialize(self) -> None:
        pass

    async def execute(self, action: str, **kwargs: Any) -> Any:
        if action == "notify_send":
            return notify_send(**kwargs)
        raise PrimitiveError(f"Unknown notify action: {action}")

    async def observe(self) -> list:
        return []

    def health_check(self) -> bool:
        return True


try:
    register_adapter(NotifyAdapter())
except Exception:
    pass
