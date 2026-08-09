"""WATCH - ambient watch loop.

A small daemon that turns goals into background automations. Triggers in
config/watcher.json fire on a time-of-day schedule or when a file appears,
and each firing runs a goal through the standard pipeline - L4 plans it
(or the trigger carries a deterministic pre-made plan, no LLM) and L3
executes it - then records the outcome in var/logs/tasks.jsonl in the same
gate-6 format and pings the desktop with notify_send.

Safety (inherited from the hardened core):
  - Every goal runs through the executor, which refuses EXECUTOR_BLOCKED
    primitives (window.shutdown) and any unknown primitive.
  - window.close_window/close_all refuse to touch protected classes
    (FRIDAY_PROTECTED_CLASSES, default kitty) - a trigger can never close
    the user's terminals.
  - dev.run_shell / dev.run(allow_bypass_permissions=True) refuse unless
    FRIDAY_ALLOW_DANGEROUS=1 is set.
  - Triggers run strictly serially - one goal at a time - because the L1
    media/browser state is a single-writer resource.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from friday.errors import FridayError
from friday.l1.notify import notify_send
from friday.l3.executor import run_plan
from friday.observability import emit_event

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "watcher.json"
DEFAULT_TASKS_FILE = PROJECT_ROOT / "var" / "logs" / "tasks.jsonl"

_WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


# ------------------------------------------------------------------ config


def load_config(path: str | Path) -> list[dict[str, Any]]:
    """Load and validate config/watcher.json: a list of trigger objects.
    A malformed trigger raises FridayError loudly - a silently-wrong
    schedule is worse than none."""
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FridayError(f"watcher config not found: {p}") from exc
    except json.JSONDecodeError as exc:
        raise FridayError(f"watcher config {p} is not valid JSON: {exc}") from exc
    triggers = data.get("triggers") if isinstance(data, dict) else None
    if not isinstance(triggers, list):
        raise FridayError(f"watcher config {p} must contain a 'triggers' list")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for t in triggers:
        _validate_trigger(t, seen)
        out.append(t)
    return out


def _validate_trigger(t: Any, seen: set[str]) -> None:
    if not isinstance(t, dict):
        raise FridayError("watcher: each trigger must be an object")
    tid = t.get("id")
    if not isinstance(tid, str) or not tid.strip():
        raise FridayError("watcher: trigger missing a non-empty 'id'")
    if tid in seen:
        raise FridayError(f"watcher: duplicate trigger id {tid!r}")
    seen.add(tid)
    if not (t.get("goal") or t.get("plan")):
        raise FridayError(f"watcher: trigger {tid!r} needs a 'goal' or a 'plan'")
    if t.get("plan") is not None and not isinstance(t["plan"], dict):
        raise FridayError(f"watcher: trigger {tid!r} 'plan' must be a plan object")
    sch = t.get("schedule")
    if not isinstance(sch, dict):
        raise FridayError(f"watcher: trigger {tid!r} missing a 'schedule' object")
    typ = sch.get("type")
    if typ == "time":
        at = sch.get("at")
        try:
            hh, mm = (int(x) for x in str(at).split(":"))
            if not (0 <= hh <= 23 and 0 <= mm <= 59):
                raise ValueError
        except (ValueError, AttributeError) as exc:
            raise FridayError(f"watcher: trigger {tid!r} schedule 'at' must be HH:MM") from exc
        days = sch.get("days")
        if days is not None:
            if not isinstance(days, list) or not all(isinstance(d, str) for d in days):
                raise FridayError(
                    f"watcher: trigger {tid!r} schedule 'days' must be a list of day names"
                )
            unknown = sorted({d[:3].lower() for d in days} - set(_WEEKDAYS))
            if unknown:
                raise FridayError(
                    f"watcher: trigger {tid!r} schedule 'days' has unknown day(s): "
                    f"{unknown} - use mon..sun"
                )
    elif typ == "file":
        if not isinstance(sch.get("directory"), str) or not sch["directory"].strip():
            raise FridayError(f"watcher: trigger {tid!r} file schedule needs a 'directory'")
    else:
        raise FridayError(f"watcher: trigger {tid!r} schedule 'type' must be 'time' or 'file'")


# --------------------------------------------------------------- scheduling


def _time_due(trigger: dict[str, Any], now: datetime, fired_dates: dict[str, str]) -> bool:
    """A time trigger fires at most once per day: once today's HH:MM has
    passed (and the day is enabled), it is marked fired for the day."""
    sch = trigger["schedule"]
    day_key = now.date().isoformat()
    if fired_dates.get(trigger["id"]) == day_key:
        return False
    days = sch.get("days")
    if days:
        enabled = {_WEEKDAYS[d[:3].lower()] for d in days if isinstance(d, str)}
        if now.weekday() not in enabled:
            return False
    hh, mm = (int(x) for x in sch["at"].split(":"))
    if now.hour * 60 + now.minute < hh * 60 + mm:
        return False
    fired_dates[trigger["id"]] = day_key
    return True


def _new_files(trigger: dict[str, Any], seen: set[str]) -> list[str]:
    """Files in the trigger's directory matching the name substring that
    have not been seen yet; each file fires at most once (tracked in
    `seen`, which lives for the daemon's lifetime - bounded by the number
    of distinct matching files that ever appear, one string each)."""
    sch = trigger["schedule"]
    base = Path(sch["directory"]).expanduser()
    if not base.is_dir():
        return []
    needle = sch.get("name", "").lower()
    try:
        if sch.get("recursive"):
            matches = [
                Path(dp) / fn
                for dp, _dirs, files in os.walk(base, followlinks=False)
                for fn in files
                if needle in fn.lower()
            ]
        else:
            matches = [
                p for p in base.iterdir() if p.is_file() and needle in p.name.lower()
            ]
    except OSError:
        return []
    new = [str(p) for p in matches if str(p) not in seen]
    seen.update(new)
    return new


# ---------------------------------------------------------------- execution


def _tasks_file() -> Path:
    return Path(os.environ.get("FRIDAY_TASKS_FILE", str(DEFAULT_TASKS_FILE)))


def _record_task(task_id: str, goal: str, ok: bool, detail: dict[str, Any]) -> None:
    """One JSON line in the gate-6 tasks counter format. Recording is
    best-effort: a broken record must not kill the watch loop."""
    rec = {
        "task_id": task_id,
        "goal": goal,
        "gate6_passed": ok,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "proof": json.dumps(detail, ensure_ascii=False),
    }
    try:
        path = _tasks_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError as exc:
        emit_event(
            layer="WATCH", primitive="tasks.record",
            exception=f"could not write {_tasks_file()}: {exc}", result="FAILED",
        )


def _make_plan(
    trigger: dict[str, Any], plan_cache: dict[str, dict[str, Any]], run_id: str
) -> dict[str, Any]:
    """A trigger's plan: a deterministic inline 'plan' (no LLM) wins; else
    the goal is planned through L4 and the successful plan is cached per
    goal for the daemon's lifetime (one LLM call per distinct goal, not
    per firing)."""
    if trigger.get("plan"):
        p = dict(trigger["plan"])
        p.setdefault("goal", trigger.get("goal", trigger["id"]))
        return p
    goal = trigger["goal"]
    if goal in plan_cache:
        return plan_cache[goal]
    from friday.l4.planner import plan as llm_plan

    p = llm_plan(goal, run_id=run_id)
    plan_cache[goal] = p
    return p


def _notify_outcome(trigger_id: str, ok: bool, detail: dict[str, Any]) -> None:
    """Desktop feedback for a finished trigger. Best-effort: a missing
    notification daemon must never fail the task record."""
    try:
        status = detail.get("status", "DONE" if ok else "FAILED")
        notify_send(
            title=f"Friday: {trigger_id} {status}",
            body=json.dumps(detail, ensure_ascii=False)[:300],
        )
    except FridayError as exc:
        emit_event(layer="WATCH", primitive="notify", exception=str(exc), result="FAILED")


def _run_trigger(
    trigger: dict[str, Any], plan_cache: dict[str, dict[str, Any]]
) -> tuple[bool, dict[str, Any]]:
    """Fire one trigger: plan -> execute -> record -> notify. Never
    raises: every outcome (including an internal bug) is recorded, so the
    loop survives a bad trigger."""
    t_id = trigger["id"]
    goal = trigger.get("goal") or (trigger.get("plan") or {}).get("goal") or t_id
    run_id = f"watch-{t_id}-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    emit_event(
        layer="WATCH", primitive="trigger", args={"id": t_id, "goal": goal}, result="RUNNING"
    )
    ok = False
    detail: dict[str, Any] = {"trigger": t_id, "status": "COMPLETED"}
    try:
        plan_dict = _make_plan(trigger, plan_cache, run_id)
        result = run_plan(plan_dict, run_id=run_id)
        ok = result.status == "COMPLETED"
        detail = {
            "trigger": t_id,
            "status": result.status,
            "steps": [
                {"step_id": s.step_id, "primitive": s.primitive, "status": s.status, "attempts": s.attempts}
                for s in result.steps
            ],
        }
    except FridayError as exc:
        ok = False
        detail = {"trigger": t_id, "status": "ABORT", "error": str(exc)[:500]}
        plan_cache.pop(goal, None)  # a failed plan must be replanned next firing
    except Exception as exc:  # internal bug: keep the loop alive, record it loudly
        ok = False
        detail = {"trigger": t_id, "status": "ERROR", "error": f"{type(exc).__name__}: {exc}"[:500]}
        plan_cache.pop(goal, None)  # same reason: don't cache a plan that errored
    _record_task(f"watch:{t_id}", goal, ok, detail)
    emit_event(
        layer="WATCH", primitive="trigger", args={"id": t_id},
        result="DONE" if ok else "FAILED", extra=detail,
    )
    if trigger.get("notify", True):
        _notify_outcome(t_id, ok, detail)
    return ok, detail


# -------------------------------------------------------------------- loop


def run_watcher(
    config_path: str | Path = DEFAULT_CONFIG,
    *,
    once: bool = False,
    poll_s: float = 30.0,
) -> None:
    """Run the watch loop. `once=True` fires every due trigger a single
    time and exits - useful for cron and for the gate proof. The loop is
    strictly serial and KeyboardInterrupt-safe."""
    if poll_s <= 0:
        raise FridayError(f"watcher poll_s must be positive, got {poll_s!r}")
    # NOTE: triggers are evaluated on LOCAL wall-clock time (datetime.now());
    # tasks.jsonl timestamps are UTC. The 09:00 trigger means 09:00 local.
    triggers = load_config(config_path)
    enabled = [t for t in triggers if t.get("enabled", True)]
    plan_cache: dict[str, dict[str, Any]] = {}
    fired_dates: dict[str, str] = {}
    seen: set[str] = set()
    emit_event(
        layer="WATCH", primitive="watcher",
        args={"triggers": [t["id"] for t in enabled], "once": once, "poll_s": poll_s},
        result="START",
    )
    try:
        while True:
            now = datetime.now()
            for t in enabled:
                sch = t["schedule"]
                if sch["type"] == "time":
                    due = _time_due(t, now, fired_dates)
                else:
                    due = bool(_new_files(t, seen))
                if due:
                    _run_trigger(t, plan_cache)
            if once:
                break
            time.sleep(poll_s)
    except KeyboardInterrupt:
        emit_event(
            layer="WATCH", primitive="watcher", result="STOP", extra={"reason": "interrupt"}
        )
        return
    emit_event(layer="WATCH", primitive="watcher", result="STOP")


def main(argv: list[str] | None = None) -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Friday ambient watch loop")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG), help="watcher config JSON")
    ap.add_argument("--once", action="store_true", help="fire due triggers once, then exit")
    ap.add_argument("--poll", type=float, default=30.0, help="loop poll interval seconds")
    args = ap.parse_args(argv)
    run_watcher(args.config, once=args.once, poll_s=args.poll)


if __name__ == "__main__":
    main()
