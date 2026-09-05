"""Phone telemetry store.

The phone is half of the Jarvis world and Friday currently knows nothing about
it. A companion app (or a Tasker/Automate HTTP bridge, or a WebSocket client)
POSTs small state snapshots here; Friday persists them and surfaces them in
/status replies and planner context so behavior can react to *you* (presence,
quiet hours, "away from desk") instead of only to the PC.

No secrets are ever stored — just presence-ish fields the user chooses to
share. The store is a tiny JSON file (var/state/phone_state.json) so it
survives restarts; FRIDAY_PHONE_STATE_FILE overrides the path for tests.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_FILE = PROJECT_ROOT / "var" / "state" / "phone_state.json"

_ALLOWED = {
    "device", "battery", "charging", "activity", "location", "do_not_disturb",
    "wifi", "nearby", "note",
    # SMS / call / notification sensors (reported by the phone bridge).
    "sms_unread", "sms_latest", "missed_calls", "notifications", "notifications_top",
}


def _state_file() -> Path:
    return Path(os.environ.get("FRIDAY_PHONE_STATE_FILE", str(DEFAULT_STATE_FILE)))


def _load() -> dict[str, Any]:
    try:
        data = json.loads(_state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(state: dict[str, Any]) -> None:
    try:
        path = _state_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def update_phone_state(payload: dict[str, Any]) -> dict[str, Any]:
    """Merge one telemetry snapshot. Returns the merged state.

    `payload` may carry arbitrary keys; only allowlisted keys are persisted.
    `last_seen` is always refreshed to now.
    """
    state = _load()
    for key, value in payload.items():
        if key in _ALLOWED:
            if value is not None and str(value).strip() != "":
                state[key] = value
            elif key in state:
                del state[key]
    state["last_seen"] = time.time()
    _save(state)
    return state


def get_phone_state() -> dict[str, Any]:
    """Current persisted phone state (or {} before first report)."""
    state = _load()
    if state.get("last_seen"):
        return state
    return {}


def _clean(value: Any) -> str:
    """Single-line string coercion (SMS bodies may contain newlines)."""
    return " ".join(str(value).split())


def phone_context() -> str:
    """One-line-ish context block for planner prompts when the phone is live."""
    state = get_phone_state()
    if not state:
        return ""
    age_min = int((time.time() - state["last_seen"]) / 60)
    parts = []
    device = state.get("device")
    activity = state.get("activity")
    battery = state.get("battery")
    dnd = state.get("do_not_disturb")
    location = state.get("location")
    if device:
        parts.append(f"phone: {device}")
    if activity:
        parts.append(f"user activity: {_clean(activity)}")
    if location:
        parts.append(f"location: {_clean(location)}")
    if isinstance(battery, (int, float)):
        parts.append(f"battery {int(battery)}%")
    if dnd:
        parts.append("do-not-disturb ON")
    sms_unread = state.get("sms_unread")
    if isinstance(sms_unread, (int, float)) and int(sms_unread) > 0:
        parts.append(f"sms: {int(sms_unread)} unread")
    sms_latest = state.get("sms_latest")
    if sms_latest:
        parts.append(f"latest sms: {_clean(sms_latest)[:60]}")
    missed = state.get("missed_calls")
    if isinstance(missed, (int, float)) and int(missed) > 0:
        parts.append(f"{int(missed)} missed calls")
    notif = state.get("notifications")
    if isinstance(notif, (int, float)) and int(notif) > 0:
        parts.append(f"{int(notif)} notifications")
    top = state.get("notifications_top")
    if notif and top:
        parts.append(f"top app: {_clean(top)[:30]}")
    parts.append(f"last seen {age_min}m ago")
    return "PHONE:\n  " + "\n  ".join(parts)
