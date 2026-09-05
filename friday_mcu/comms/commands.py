"""Chat command layer — the phone-facing Jarvis surface.

The watcher's text triggers turn chat messages into goals, but a real
assistant also answers plain questions without planning anything:
  /friday help      -> what you can say
  /friday status    -> is everything up? adapters, channels, memory
  /friday adapters  -> per-platform health
  /friday memory    -> memory store summary
  /goal <anything>  -> run a real goal (planner -> executor -> verified reply)

`route()` decides: built-in command replies come back instantly (zero LLM
cost, deterministic); anything else falls through to the caller's goal path.
Unknown slash-commands get a gentle help nudge instead of being ignored.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

COMMAND_PREFIX = "/friday"
GOAL_PREFIX_ENV = "FRIDAY_COMMAND_PREFIX"
DEFAULT_GOAL_PREFIX = "/goal"

MAX_RESPONSE = 1800


@dataclass
class RouteResult:
    """Outcome of routing one inbound chat message."""

    reply: str | None = None  # deterministic reply (None -> caller runs a goal)
    consumed: bool = False    # caller must not re-route or re-execute


def _plain(text: str) -> str:
    return " ".join(text.strip().split())


def _goal_prefix() -> str:
    return os.environ.get(GOAL_PREFIX_ENV, DEFAULT_GOAL_PREFIX)


def _is_command(text: str) -> bool:
    return text.startswith("/")


def _status_block() -> str:
    """Compact system status: adapters, channels, memory counts, platforms."""
    lines: list[str] = []
    try:
        from friday_mcu.adapters import list_adapters
        from friday_mcu.core.registry import ensure_registry
        ensure_registry()
        adapters = list_adapters()
        healthy = sum(1 for a in adapters.values() if a.health_check())
        lines.append(f"Adapters: {len(adapters)} ({healthy} healthy)")
        names = [a.name for a in adapters.values() if a.health_check()]
        if names:
            lines.append("Ready: " + ", ".join(sorted(names)))
    except Exception:
        lines.append("Adapters: unavailable")
    try:
        from friday_mcu.comms import channels
        chans = sorted(channels.list_channels().keys())
        lines.append("Channels: " + (", ".join(chans) if chans else "none"))
    except Exception:
        pass
    try:
        from friday_mcu.memory.store import MemoryManager
        mgr = MemoryManager()
        lines.append(
            f"Memory: {len(mgr.episodic.recent(1000))} episodic, "
            f"{len(mgr.semantic.list_all())} semantic"
        )
    except Exception:
        lines.append("Memory: unavailable")
    try:
        from friday_mcu.env import _status_summary
        lines.append("Platforms: " + (", ".join(_status_summary()) if _status_summary() else "none"))
    except Exception:
        pass
    return "\n".join(lines)


def _adapters_block() -> str:
    lines: list[str] = []
    try:
        from friday_mcu.adapters import list_adapters
        from friday_mcu.core.registry import ensure_registry
        ensure_registry()
        adapters = list_adapters()
        if not adapters:
            return "No adapters registered."
        for name in sorted(adapters):
            a = adapters[name]
            ok = a.health_check()
            caps = ", ".join(a.capabilities[:6])
            lines.append(f"{'+' if ok else 'x'} {name}: {caps}")
    except Exception as exc:
        lines.append(f"Adapters unavailable: {exc}")
    return "\n".join(lines) or "No adapters."


def _memory_block() -> str:
    lines: list[str] = []
    try:
        from friday_mcu.memory.learning import MemoryLearner
        from friday_mcu.memory.store import MemoryManager
        mgr = MemoryManager()
        recent = mgr.episodic.recent(5)
        lines.append(
            f"Episodic: {len(mgr.episodic.recent(1000))} | "
            f"Semantic: {len(mgr.semantic.list_all())} | "
            f"Procedural patterns: {len(mgr.procedural.all_patterns())}"
        )
        for m in recent:
            lines.append(f"- {m.content[:90]}")
        stats = MemoryLearner().get_stats()
        lines.append(f"Lessons: {stats.get('total_lessons', 0)} (outcomes: {stats.get('total_outcomes', 0)})")
    except Exception as exc:
        lines.append(f"Memory unavailable: {exc}")
    return "\n".join(lines)


def _help_block() -> str:
    goal = _goal_prefix()
    return (
        "I'm Friday. Commands:\n"
        f"{COMMAND_PREFIX} help | status | adapters | memory | phone\n"
        f"{goal} <goal>  -> run anything, e.g. "
        f'"{goal} summarize my unread email"\n'
        "Try /friday status to see what I can reach."
    )


def _phone_block() -> str:
    """Phone-side state when the companion has reported it (see phone.py)."""
    try:
        from friday_mcu.phone import get_phone_state
        state = get_phone_state()
        if not state or not state.get("last_seen"):
            return "No phone telemetry yet — pair a phone bridge (POST /v1/phone)."
        age_min = int((time.time() - state["last_seen"]) / 60)
        parts = []
        if state.get("device"):
            parts.append(f"device: {state['device']}")
        if state.get("activity"):
            parts.append(f"activity: {state['activity']}")
        if state.get("battery") is not None:
            parts.append(f"battery: {state['battery']}%")
        if state.get("do_not_disturb"):
            parts.append("dnd: on")
        if state.get("location"):
            parts.append(f"location: {state['location']}")
        sms_unread = state.get("sms_unread")
        if isinstance(sms_unread, (int, float)) and int(sms_unread) > 0:
            parts.append(f"sms: {int(sms_unread)} unread")
        sms_latest = state.get("sms_latest")
        if sms_latest:
            parts.append(f"latest: {' '.join(str(sms_latest).split())[:50]}")
        missed = state.get("missed_calls")
        if isinstance(missed, (int, float)) and int(missed) > 0:
            parts.append(f"missed calls: {int(missed)}")
        notif = state.get("notifications")
        if isinstance(notif, (int, float)) and int(notif) > 0:
            parts.append(f"notifications: {int(notif)}")
        parts.append(f"seen {age_min}m ago")
        return "Phone: " + ", ".join(parts)
    except Exception:
        return "Phone state unavailable."


_COMMANDS: dict[str, Any] = {
    "help": _help_block,
    "status": lambda: _status_block() + "\n\n" + _phone_block(),
    "adapters": _adapters_block,
    "memory": _memory_block,
    "phone": _phone_block,
}


def route(text: str) -> RouteResult | None:
    """Route a chat message. Returns a RouteResult for handled messages
    (deterministic reply or consumed goal), or None to let the caller treat
    the whole message as a goal via the configured goal prefix.
    """
    clean = _plain(text)
    if not clean:
        return RouteResult(reply="Say something, boss.")
    if not _is_command(clean):
        # Goal-prefixed messages are handled by the caller (they need the LLM
        # path); everything else is chatter — not consumed, no reply.
        if clean.lower().startswith(_goal_prefix().lower()):
            return None
        return RouteResult(reply=None, consumed=False)

    head, _, rest = clean.partition(" ")
    cmd = head.lower()

    if cmd == _goal_prefix().lower():
        goal = rest.strip()
        if not goal:
            return RouteResult(reply=f"Usage: {cmd} <goal>", consumed=True)
        return None  # caller plans + executes the goal

    # /friday [action] — action defaults to help when no subcommand given.
    if cmd == COMMAND_PREFIX:
        action = (rest or "").strip().lower() or "help"
    elif cmd.startswith(COMMAND_PREFIX + ":"):
        action = cmd.split(":", 1)[1].strip().lower() or "help"
    elif cmd in ("/help", "help"):
        return RouteResult(reply=_help_block(), consumed=True)
    else:
        # /status /adapters /memory /phone short forms and unknown slashes.
        action = cmd[1:] if cmd.startswith("/") and cmd[1:] in _COMMANDS else "help"

    handler = _COMMANDS.get(action)
    if handler is None:
        return RouteResult(reply=_help_block(), consumed=True)
    try:
        return RouteResult(reply=handler()[:MAX_RESPONSE], consumed=True)
    except Exception as exc:
        return RouteResult(reply=f"Status check failed: {type(exc).__name__}: {exc}"[:MAX_RESPONSE], consumed=True)


def extract_goal(text: str, prefix: str | None = None) -> str | None:
    """Back-compat: pull the goal out of a '<prefix> goal' message."""
    prefix = prefix if prefix is not None else _goal_prefix()
    if not prefix:
        return text.strip() or None
    clean = _plain(text)
    if clean.lower().startswith(prefix.lower()):
        goal = clean[len(prefix):].strip()
        return goal if goal else None
    return None
