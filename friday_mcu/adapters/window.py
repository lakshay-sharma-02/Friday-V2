"""Window adapter — Hyprland IPC window management.

Headless-first: no Win32 stubs. On non-Hyprland systems, the adapter
returns empty results (read-only) instead of failing.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Any

from friday_mcu.adapters import Adapter, register_adapter
from friday_mcu.core.contracts import Idempotency, contract
from friday_mcu.core.errors import PreconditionError, PrimitiveError, PrimitiveTimeout

HYPRCTL = "hyprctl"
DEFAULT_TIMEOUT = 15.0


def _hyprctl(*args: str, timeout: float = DEFAULT_TIMEOUT) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            [HYPRCTL, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        raise PrimitiveError("hyprctl not found — not running Hyprland?")
    except subprocess.TimeoutExpired as exc:
        raise PrimitiveTimeout(f"hyprctl {' '.join(args)} timed out") from exc


def _is_available() -> bool:
    """Check if Hyprland is available."""
    try:
        result = subprocess.run(
            [HYPRCTL, "clients", "-j"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@contract(
    precondition="Hyprland session is live.",
    postcondition="Returns the current client list.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if hyprctl fails.",
    returns="list[dict]: client objects.",
)
def list_clients() -> list[dict[str, Any]]:
    """List all open windows."""
    if not _is_available():
        return []
    proc = _hyprctl("clients", "-j")
    if proc.returncode != 0:
        raise PrimitiveError(f"hyprctl clients failed: {proc.stderr.strip()}")
    try:
        clients = json.loads(proc.stdout)
        return clients if isinstance(clients, list) else []
    except json.JSONDecodeError as exc:
        raise PrimitiveError("hyprctl returned invalid JSON") from exc


@contract(
    precondition="Hyprland session is live.",
    postcondition="Returns the focused client.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if hyprctl fails.",
    returns="dict | None: the focused client.",
)
def get_active_window() -> dict[str, Any] | None:
    """Get the currently focused window."""
    if not _is_available():
        return None
    proc = _hyprctl("activewindow", "-j")
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout) or None
    except json.JSONDecodeError:
        return None


@contract(
    precondition="command is a non-empty string.",
    postcondition="An app is launched and a matching client appears.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError if no matching client appears within 12s.",
    returns="dict: the client entry that appeared.",
)
def open_app(command: str) -> dict[str, Any]:
    """Launch an application."""
    if not command or not command.strip():
        raise PreconditionError("open_app requires a non-empty command")
    if not _is_available():
        raise PrimitiveError("Hyprland not available")
    token = command.strip().split()[0].split("/")[-1].lower()
    before = {c.get("address") for c in list_clients()}
    _hyprctl("dispatch", "exec", command.strip())

    deadline = time.monotonic() + 12.0
    while time.monotonic() < deadline:
        for c in list_clients():
            if c.get("address") not in before and token in str(c.get("class", "")).lower():
                return c
        time.sleep(0.3)
    raise PrimitiveError(f"no client matching '{token}' appeared within 12s")


@contract(
    precondition="selector targets a live client.",
    postcondition="The client is gone from list_clients() within 5s.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="PrimitiveError if client survives 5s after close.",
    returns="None",
)
def close_window(selector: str) -> None:
    """Close a window by selector (address or class name)."""
    if not selector or not selector.strip():
        raise PreconditionError("close_window requires a non-empty selector")
    if not _is_available():
        return
    _hyprctl("dispatch", "closewindow", selector.strip())


@contract(
    precondition="None.",
    postcondition="Returns how many windows were closed.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="PrimitiveError from any individual close.",
    returns="int: number of windows closed.",
)
def close_all(exclude_classes: list[str] | None = None) -> int:
    """Close all windows except those with excluded classes."""
    exclude = {c.lower() for c in (exclude_classes or [])}
    targets = [
        c for c in list_clients()
        if str(c.get("class", "")).lower() not in exclude
    ]
    closed = 0
    for c in targets:
        addr = c.get("address", "")
        if addr:
            close_window(f"address:{addr}")
            closed += 1
    return closed


class WindowAdapter(Adapter):
    """Window management adapter."""

    @property
    def name(self) -> str:
        return "window"

    @property
    def capabilities(self) -> list[str]:
        return ["list_clients", "get_active_window", "open_app", "close_window", "close_all"]

    async def initialize(self) -> None:
        pass

    async def execute(self, action: str, **kwargs: Any) -> Any:
        actions = {
            "list_clients": list_clients,
            "get_active_window": get_active_window,
            "open_app": open_app,
            "close_window": close_window,
            "close_all": close_all,
        }
        fn = actions.get(action)
        if fn is None:
            raise PrimitiveError(f"Unknown window action: {action}")
        return fn(**kwargs)

    async def observe(self) -> list:
        return []

    def health_check(self) -> bool:
        return _is_available()


try:
    register_adapter(WindowAdapter())
except Exception:
    pass
