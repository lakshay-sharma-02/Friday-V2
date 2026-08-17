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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from friday.capability_gaps import record_gap
from friday.errors import FridayError
from friday.l1.notify import notify_send
from friday.l3.executor import run_plan
from friday.observability import emit_event, reset_run_id

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "watcher.json"
DEFAULT_TASKS_FILE = PROJECT_ROOT / "var" / "logs" / "tasks.jsonl"
# Once-per-day trigger state, persisted so a service restart does NOT
# re-fire a trigger that already ran today (var/ is gitignored runtime
# data; FRIDAY_FIRED_FILE overrides, matching the FRIDAY_*_FILE pattern).
DEFAULT_FIRED_STATE = PROJECT_ROOT / "var" / "state" / "watcher_fired.json"

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
    allow = t.get("allow")
    if allow is not None and (
        not isinstance(allow, list) or not all(isinstance(a, str) and a.strip() for a in allow)
    ):
        raise FridayError(
            f"watcher: trigger {tid!r} 'allow' must be a list of primitive "
            'patterns like ["gmail.*"]'
        )
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
    """PURE schedule check: has today's HH:MM passed (on an enabled day)
    and has the trigger NOT already been marked fired for today? Does NOT
    mutate - the caller records fired state only after the goal genuinely
    COMPLETES (a FAILED attempt stays eligible to retry later today)."""
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
    return not now.hour * 60 + now.minute < hh * 60 + mm


# Minimum gap between RETRY attempts of a FAILED same-day trigger. A
# transient failure (LLM API down, gmail auth blip) must not silently
# consume the day's slot, but a persistently-failing trigger must not
# hammer the LLM API every poll. 10 minutes = at most ~6 attempts/hour on
# a persistent failure; the morning digest only retries meaningfully when
# the underlying failure clears. Choice recorded in PLAN_STATUS.md.
RETRY_BACKOFF_S = 600.0


def _in_retry_backoff(trigger_id: str, last_attempts: dict[str, float]) -> bool:
    """Rate limiter for same-day retries: a trigger that just attempted is
    not retried until RETRY_BACKOFF_S has elapsed. Only FAILED runs ever
    re-enter the eligible set (a COMPLETED run is marked fired), so this
    gates retries, never normal firings. Yesterday's attempt is far
    outside the window and never blocks a new day."""
    last = last_attempts.get(trigger_id)
    return last is not None and time.monotonic() - last < RETRY_BACKOFF_S


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
            matches = [p for p in base.iterdir() if p.is_file() and needle in p.name.lower()]
    except OSError:
        return []
    new = [str(p) for p in matches if str(p) not in seen]
    seen.update(new)
    return new


# ---------------------------------------------------------------- execution


def _allowed_prim(primitive: str, allowed: list[str]) -> bool:
    """Trigger allowlist match: exact name, or a `mod.*` prefix pattern
    (e.g. "gmail.*" matches gmail.list_unread / gmail.summarize). With no
    allowlist every executor-resolvable primitive is permitted. Only step
    PRIMITIVES are checked - L2 verify checks are read-only by
    construction (Gate 3) and always run."""
    for pat in allowed:
        if pat == primitive:
            return True
        if pat.endswith(".*") and primitive.startswith(pat[:-1]):
            return True
    return False


def _tasks_file() -> Path:
    return Path(os.environ.get("FRIDAY_TASKS_FILE", str(DEFAULT_TASKS_FILE)))


def _fired_state_file() -> Path:
    return Path(os.environ.get("FRIDAY_FIRED_FILE", str(DEFAULT_FIRED_STATE)))


def _load_fired_state() -> dict[str, str]:
    """Prior once-per-day state: {trigger_id: YYYY-MM-DD}. Fails SAFE:
    a missing, unreadable, or corrupt file (non-dict, wrong types) is
    treated as not-yet-fired ({}) - a broken state file never blocks a
    trigger and never crashes the loop; the worst case is one duplicate
    firing on the day the file is lost."""
    try:
        data = json.loads(_fired_state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if isinstance(v, str)}


def _save_fired_state(state: dict[str, str]) -> None:
    """Persist fired state. Best-effort: a broken write must never kill
    the loop - the in-memory dict keeps working for the daemon's life and
    the loss just means one possible re-fire after the next restart.
    Written ATOMICALLY (temp file + os.replace) so a crash mid-write
    cannot leave a truncated state file that forces a duplicate firing."""
    try:
        path = _fired_state_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        emit_event(
            layer="WATCH",
            primitive="fired-state.save",
            exception=f"could not write {_fired_state_file()}: {exc}",
            result="FAILED",
        )


def _record_task(task_id: str, goal: str, ok: bool, detail: dict[str, Any]) -> None:
    """One JSON line in the gate-6 tasks counter format. Recording is
    best-effort: a broken record must not kill the watch loop."""
    rec = {
        "task_id": task_id,
        "goal": goal,
        "gate6_passed": ok,
        "timestamp": datetime.now(UTC).isoformat(timespec="microseconds"),
        "proof": json.dumps(detail, ensure_ascii=False),
    }
    try:
        path = _tasks_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError as exc:
        emit_event(
            layer="WATCH",
            primitive="tasks.record",
            exception=f"could not write {_tasks_file()}: {exc}",
            result="FAILED",
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
        allowed = trigger.get("allow")
        if allowed:
            forbidden = [
                s.get("primitive")
                for s in plan_dict.get("steps", [])
                if not _allowed_prim(s.get("primitive"), allowed)
            ]
            if forbidden:
                # refuse BEFORE execution: a hallucinated side-effecting
                # step must never act from an unattended trigger
                plan_cache.pop(goal, None)
                # One capability-gap record per forbidden primitive, with
                # that step's arg SHAPE (never values) - the triage loop
                # treats each disallowed primitive as a proposal candidate.
                for s in plan_dict.get("steps", []):
                    if s.get("primitive") in forbidden:
                        record_gap(
                            source="watcher",
                            trigger_id=t_id,
                            attempted_primitive=s.get("primitive"),
                            attempted_args=s.get("args") or {},
                            goal_context=goal,
                            refusal_reason=f"trigger allowlist {allowed}",
                        )
                detail = {
                    "trigger": t_id,
                    "status": "REFUSED",
                    "forbidden": forbidden,
                    "allowed": allowed,
                }
                _record_task(f"watch:{t_id}", goal, False, detail)
                emit_event(
                    layer="WATCH",
                    primitive="trigger",
                    args={"id": t_id},
                    result="FAILED",
                    extra=detail,
                )
                if trigger.get("notify", True):
                    _notify_outcome(t_id, False, detail)
                return False, detail
        result = run_plan(plan_dict, run_id=run_id)
        ok = result.status == "COMPLETED"
        detail = {
            "trigger": t_id,
            "status": result.status,
            "steps": [
                {
                    "step_id": s.step_id,
                    "primitive": s.primitive,
                    "status": s.status,
                    "attempts": s.attempts,
                }
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
        layer="WATCH",
        primitive="trigger",
        args={"id": t_id},
        result="DONE" if ok else "FAILED",
        extra=detail,
    )
    if trigger.get("notify", True):
        _notify_outcome(t_id, ok, detail)
    return ok, detail


# -------------------------------------------------------------------- loop


def _emit_heartbeat(
    started: float,
    last_trigger_id: str | None,
    last_trigger_at: str | None,
) -> None:
    """One daemon.alive line on the heartbeat interval - the seed of an
    ambient event bus, deliberately minimal: uptime, the last trigger
    that fired (id + UTC time), and two capability-gap counts: the TOTAL
    records ever (capability_gaps) and the UNPROCESSED ones still
    awaiting triage (gaps_pending_triage) - the latter is the real
    backlog signal the reviewer watches to decide whether proposals are
    outpacing human review (a total that only grows is not actionable;
    the pending count is what triage has not yet drafted). Best-effort:
    a broken gap file reports -1, never a crash."""
    from friday.capability_gaps import all_gaps, unprocessed_gaps

    try:
        gap_count = len(all_gaps())
        pending = len(unprocessed_gaps())
    except Exception:
        gap_count = -1
        pending = -1
    emit_event(
        layer="WATCH",
        primitive="daemon.alive",
        result="ALIVE",
        args={
            "uptime_s": int(time.monotonic() - started),
            "last_trigger": last_trigger_id or "none",
            "last_trigger_at": last_trigger_at or "",
            "capability_gaps": gap_count,
            "gaps_pending_triage": pending,
        },
    )


def run_watcher(
    config_path: str | Path = DEFAULT_CONFIG,
    *,
    once: bool = False,
    poll_s: float = 30.0,
    heartbeat_s: float = 120.0,
) -> None:
    """Run the watch loop. `once=True` fires every due trigger a single
    time and exits - useful for cron and for the gate proof. In daemon
    mode a daemon.alive heartbeat is emitted every `heartbeat_s` seconds
    (0 disables it). The loop is strictly serial and
    KeyboardInterrupt-safe.

    Once-per-day state is PERSISTED (var/state/watcher_fired.json): a
    trigger that COMPLETED today does not run again today just because
    the service restarted; a new day rolls over naturally (state is
    keyed by ISO date). Corrupt/missing state fails safe to
    not-yet-fired. A FAILED run is NOT marked fired - it stays eligible
    to retry later the same day, rate-limited by RETRY_BACKOFF_S (a
    transient failure must not silently consume the day's slot). File
    triggers are unaffected - their seen-set is daemon-lifetime by
    design."""
    if poll_s <= 0:
        raise FridayError(f"watcher poll_s must be positive, got {poll_s!r}")
    if heartbeat_s and heartbeat_s <= 0:
        raise FridayError(f"watcher heartbeat_s must be positive, got {heartbeat_s!r}")
    # NOTE: triggers are evaluated on LOCAL wall-clock time (datetime.now());
    # tasks.jsonl timestamps are UTC. The 09:00 trigger means 09:00 local.
    triggers = load_config(config_path)
    enabled = [t for t in triggers if t.get("enabled", True)]
    plan_cache: dict[str, dict[str, Any]] = {}
    # Persisted once-per-day state: a restart must not re-fire today's
    # triggers. `last_fired_saved` tracks what is already on disk so the
    # file is written only when a trigger actually fires.
    fired_dates = _load_fired_state()
    last_fired_saved = dict(fired_dates)
    # Same-day retry rate limiter for FAILED runs (in-memory by design -
    # a restart resetting it is fine: backoff is a rate limit, not state).
    last_attempts: dict[str, float] = {}
    seen: set[str] = set()
    started = time.monotonic()
    # NOTE: last_heartbeat starts at `started`, NOT 0.0 - time.monotonic()
    # is boot-relative, so `elapsed - 0` would look like an instant
    # deadline and fire the first heartbeat immediately.
    last_heartbeat = started
    last_trigger_id: str | None = None
    last_trigger_at: str | None = None
    emit_event(
        layer="WATCH",
        primitive="watcher",
        args={
            "triggers": [t["id"] for t in enabled],
            "once": once,
            "poll_s": poll_s,
            "heartbeat_s": heartbeat_s,
            "fired_state_loaded": len(fired_dates),
        },
        result="START",
    )
    try:
        while True:
            now = datetime.now()
            for t in enabled:
                sch = t["schedule"]
                if sch["type"] == "time":
                    due = _time_due(t, now, fired_dates) and not _in_retry_backoff(
                        t["id"], last_attempts
                    )
                else:
                    due = bool(_new_files(t, seen))
                if due:
                    ok, detail = _run_trigger(t, plan_cache)
                    # The trigger run scoped the observability run_id to
                    # itself; restore the process-default so daemon.alive
                    # heartbeats (and any other ambient line) are NOT
                    # misattributed to this run for the rest of the
                    # process lifetime (the run_id leak).
                    reset_run_id()
                    last_attempts[t["id"]] = time.monotonic()
                    last_trigger_id = t["id"]
                    last_trigger_at = datetime.now(UTC).isoformat(timespec="seconds")
                    if ok or detail.get("status") == "REFUSED":
                        # fired-state is recorded on genuine SUCCESS or a
                        # deliberate ALLOWLIST REFUSAL (a refusal IS the safe
                        # terminal outcome for today - retrying would replan
                        # and re-refuse, costing an LLM call + a gap record
                        # every backoff). A FAILED/ABORTed/ERROR run stays
                        # eligible to retry later today, rate-limited by
                        # RETRY_BACKOFF_S - a transient failure must not
                        # silently kill the day's slot.
                        fired_dates[t["id"]] = datetime.now().date().isoformat()
            if fired_dates != last_fired_saved:
                _save_fired_state(fired_dates)
                last_fired_saved = dict(fired_dates)
            if once:
                break
            elapsed = time.monotonic()
            if heartbeat_s and elapsed - last_heartbeat >= heartbeat_s:
                last_heartbeat = elapsed
                _emit_heartbeat(started, last_trigger_id, last_trigger_at)
            time.sleep(poll_s)
    except KeyboardInterrupt:
        emit_event(layer="WATCH", primitive="watcher", result="STOP", extra={"reason": "interrupt"})
        return
    emit_event(layer="WATCH", primitive="watcher", result="STOP")


def main(argv: list[str] | None = None) -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Friday ambient watch loop")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG), help="watcher config JSON")
    ap.add_argument("--once", action="store_true", help="fire due triggers once, then exit")
    ap.add_argument("--poll", type=float, default=30.0, help="loop poll interval seconds")
    ap.add_argument(
        "--heartbeat",
        type=float,
        default=None,
        help="daemon.alive interval seconds (default: $FRIDAY_HEARTBEAT_S or 120)",
    )
    args = ap.parse_args(argv)
    heartbeat_s = (
        args.heartbeat
        if args.heartbeat is not None
        else float(os.environ.get("FRIDAY_HEARTBEAT_S", "120"))
    )
    run_watcher(args.config, once=args.once, poll_s=args.poll, heartbeat_s=heartbeat_s)


if __name__ == "__main__":
    main()
