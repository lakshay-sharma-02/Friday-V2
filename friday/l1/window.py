"""L1 primitive: window (hyprctl IPC).

Pure IPC, no GUI/vision. Covers open / close / focus / list /
move-workspace / shutdown, per the V8 master plan.

All functions shell out to `hyprctl`; the compositor session must be live
(HYPRLAND_INSTANCE_SIGNATURE set and `hyprctl clients -j` returning JSON).
"""

from __future__ import annotations

import json
import subprocess
import time
from typing import Any, Callable

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError, PrimitiveTimeout

HYPRCTL = "hyprctl"
DEFAULT_TIMEOUT = 15.0


def _hyprctl(*args: str, timeout: float = DEFAULT_TIMEOUT) -> subprocess.CompletedProcess:
    try:
        proc = subprocess.run(
            [HYPRCTL, *args], capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as exc:
        raise PrimitiveTimeout(
            f"hyprctl {' '.join(args)} timed out after {timeout:.0f}s",
            state="unknown; the command may or may not have been applied",
        ) from exc
    if proc.returncode != 0:
        raise PrimitiveError(
            f"hyprctl {' '.join(args)} failed (rc={proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}",
            state="command not applied",
        )
    return proc


def _wait_until(predicate: Callable[[], bool], timeout: float, interval: float = 0.25) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def _wait_until_return(fn: Callable[[], Any], timeout: float, interval: float = 0.3) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        val = fn()
        if val:
            return val
        time.sleep(interval)
    return None


def _selector_arg(selector: str) -> str:
    """Normalize a window selector for hyprctl dispatch.

    Addresses need the 'address:' prefix. Selectors that already carry an
    explicit prefix (class:/title:/pid:/...) pass through unchanged. A bare
    name is treated as a class and gets the 'class:' prefix - hyprctl
    accepts a bare class name with rc=0 but silently does nothing for
    closewindow, so the prefix is not optional. (Verified empirically:
    'closewindow firefox' closes nothing; 'closewindow class:firefox'
    closes one window.)"""
    if selector.startswith("0x"):
        return f"address:{selector}"
    if ":" in selector:
        return selector
    return f"class:{selector}"


def _client_haystack(c: dict) -> str:
    return " ".join(
        str(c.get(k, "")) for k in ("class", "initialClass", "title", "initialTitle")
    ).lower()


def _compact_client(c: dict) -> dict[str, Any]:
    """Compact client summary for the L0 log line ONLY - the real return
    value keeps every hyprctl field. Raw client dicts carry ~10 fields of
    window geometry (at/size/monitor/fullscreen/xwayland/pinned/...) that
    bloat every line; a desktop of several windows dumped on each polled
    list_clients call is the log's dominant payload. The projection keeps
    everything a trace needs to identify and follow a window: address,
    class, title, workspace id, pid, mapped."""
    ws = c.get("workspace") or {}
    return {
        "address": c.get("address"),
        "class": c.get("class"),
        "title": str(c.get("title") or ""),
        "workspace_id": ws.get("id") if isinstance(ws, dict) else None,
        "pid": c.get("pid"),
        "mapped": c.get("mapped"),
    }


def _log_clients_result(result: Any) -> Any:
    """Log-time projection for window primitives: a list of clients is
    compacted per client; a single client dict is compacted once. Note
    Task 8's harness reads the logged window.open_app result for its
    'address' - the projection preserves it."""
    if isinstance(result, list):
        return [_compact_client(c) for c in result]
    if isinstance(result, dict):
        return _compact_client(result)
    return result


@contract(
    precondition="Hyprland session is live.",
    postcondition="Returns the current client list; makes no state changes.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if hyprctl fails or returns invalid JSON; "
    "PrimitiveTimeout if hyprctl hangs.",
    returns="list[dict]: raw client objects from `hyprctl clients -j`.",
    log_transform=_log_clients_result,
)
def list_clients() -> list[dict[str, Any]]:
    proc = _hyprctl("clients", "-j")
    try:
        clients = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise PrimitiveError(
            "hyprctl clients -j returned invalid JSON", state="read-only; no state changed"
        ) from exc
    return clients if isinstance(clients, list) else []


@contract(
    precondition="Hyprland session is live.",
    postcondition="Returns the focused client; makes no state changes.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if hyprctl fails.",
    returns="dict | None: the focused client, or None if nothing is focused.",
    log_transform=_log_clients_result,
)
def get_active_window() -> dict[str, Any] | None:
    proc = _hyprctl("activewindow", "-j")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise PrimitiveError(
            "hyprctl activewindow -j returned invalid JSON", state="read-only; no state changed"
        ) from exc
    return data or None


@contract(
    precondition="command is a non-empty string naming an executable (e.g. 'firefox').",
    postcondition="hyprctl dispatch exec ran; within 12s a client matching the command's "
    "first token is present (newly appeared, or already running before the call).",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError if no matching client appears within 12s - the app may still "
    "have been dispatched, so verify with list_clients(). PreconditionError on empty command.",
    returns="dict: the client entry that appeared.",
    log_transform=_log_clients_result,
)
def open_app(command: str) -> dict[str, Any]:
    if not command or not command.strip():
        raise PreconditionError("open_app requires a non-empty command")
    token = command.strip().split()[0].split("/")[-1].lower()
    before = list_clients()
    before_addrs = {c.get("address") for c in before}
    pre_existing = [c for c in before if token in _client_haystack(c)]
    _hyprctl("dispatch", "exec", command.strip())

    def _match(c: dict) -> bool:
        return token in _client_haystack(c)

    def _find() -> dict | None:
        clients = list_clients()
        for c in clients:
            if _match(c) and c.get("address") not in before_addrs:
                return c
        # If nothing was open at all before, the first matching client counts.
        if not before_addrs:
            for c in clients:
                if _match(c):
                    return c
        return None

    found = _wait_until_return(_find, timeout=12.0, interval=0.3)
    if found is None and pre_existing:
        # The app was already running and chose not to spawn a new client
        # (single-instance apps just focus). That is success.
        return pre_existing[0]
    if found is None:
        raise PrimitiveError(
            f"no client matching '{token}' appeared within 12s of dispatching '{command}'",
            state="command was dispatched to hyprctl; verify with list_clients()",
        )
    return found


@contract(
    precondition="selector is a client address (0x...) or a hyprctl class/name.",
    postcondition="If a client matched the selector it is gone from list_clients() within 5s; "
    "closing an already-closed window is a no-op. A bare class/name closes "
    "every matching client (resolved to addresses first).",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="PrimitiveError if a resolved address survives 5s after its close dispatch.",
    returns="None",
)
def close_window(selector: str) -> None:
    if not selector or not selector.strip():
        raise PreconditionError("close_window requires a non-empty selector")
    selector = selector.strip()
    if selector.startswith("0x"):
        targets = [selector]
    else:
        # Bare class/name: resolve to concrete addresses first. hyprctl's
        # `closewindow class:...` selector matching is unreliable (firefox's
        # window class is 'Navigator', not 'firefox'), while closing by
        # address always works - so never depend on the class: selector.
        targets = [
            str(c["address"]) for c in list_clients()
            if selector.lower() in _client_haystack(c)
        ]
    if not targets:
        return  # nothing matched; already closed
    for address in targets:
        _hyprctl("dispatch", "closewindow", f"address:{address}")

        def _gone() -> bool:
            return all(str(c.get("address")) != address for c in list_clients())

        if not _wait_until(_gone, timeout=5.0):
            raise PrimitiveError(
                f"window '{address}' still present after close",
                state="close dispatched; verify with list_clients()",
            )


@contract(
    precondition="None - an empty desktop is a valid target.",
    postcondition="Every client whose class is not in exclude_classes is closed; returns how "
    "many were closed.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="PrimitiveError from any individual close; earlier closes are not rolled back "
    "(verify with list_clients()).",
    returns="int: number of clients closed.",
)
def close_all(exclude_classes: list[str] | None = None) -> int:
    exclude = {c.lower() for c in (exclude_classes or [])}
    closed = 0
    for c in list_clients():
        if str(c.get("class", "")).lower() in exclude:
            continue
        close_window(str(c["address"]))
        closed += 1
    return closed


@contract(
    precondition="selector targets a live client.",
    postcondition="The matching client becomes the active (focused) window within 5s.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="PrimitiveError if the selector never becomes active.",
    returns="None",
)
def focus_window(selector: str) -> None:
    if not selector or not selector.strip():
        raise PreconditionError("focus_window requires a non-empty selector")
    selector = selector.strip()
    _hyprctl("dispatch", "focuswindow", _selector_arg(selector))

    def _focused() -> bool:
        aw = get_active_window()
        if not aw:
            return False
        return str(aw.get("address")) == selector or (
            not selector.startswith("0x") and selector.lower() in _client_haystack(aw)
        )

    if not _wait_until(_focused, timeout=5.0):
        raise PrimitiveError(
            f"could not focus '{selector}'",
            state="focus dispatched; verify with get_active_window()",
        )


@contract(
    precondition="workspace_id >= 1 and selector targets a live client.",
    postcondition="The client's workspace.id becomes workspace_id within 5s.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="PrimitiveError if hyprctl rejects the arguments or the move never lands.",
    returns="None",
)
def move_to_workspace(workspace_id: int, selector: str) -> None:
    if workspace_id < 1:
        raise PreconditionError("workspace_id must be >= 1")
    if not selector or not selector.strip():
        raise PreconditionError("move_to_workspace requires a non-empty selector")
    selector = selector.strip()
    _hyprctl("dispatch", "movetoworkspace", f"{workspace_id},{_selector_arg(selector)}")

    def _moved() -> bool:
        for c in list_clients():
            if str(c.get("address")) == selector or (
                not selector.startswith("0x") and selector.lower() in _client_haystack(c)
            ):
                return int(c.get("workspace", {}).get("id", -1)) == workspace_id
        return False

    if not _wait_until(_moved, timeout=5.0):
        raise PrimitiveError(
            f"client '{selector}' did not reach workspace {workspace_id}",
            state="move dispatched; verify with list_clients()",
        )


@contract(
    precondition="You actually want the compositor session to end.",
    postcondition="Hyprland exits; the session ends. This is destructive.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError if hyprctl rejects the exit command.",
    returns="None",
)
def shutdown() -> None:
    _hyprctl("dispatch", "exit")
