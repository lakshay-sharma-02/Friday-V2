"""MCU Friday Watcher — ambient automation daemon.

Fires triggers from config/watcher.json through the MCU pipeline:
  trigger → planner (LLM/template/cache) → executor → memory → comms

Supports:
  - time triggers (daily at HH:MM, optional day filter)
  - file triggers (new file in directory)
  - special trigger types (whatsapp-media, telegram-media, telegram-text, discord-text)
  - deterministic inline plans (no LLM) or LLM-planned goals
  - per-trigger primitive allowlists
  - once-per-day fired state (persisted across restarts)
  - heartbeat reporting
  - proactive suggestions on each tick
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from friday_mcu.core.errors import FridayError
from friday_mcu.core.events import EventType, emit

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Deliberately separate from the V8 watcher's config/watcher.json — the two
# registries differ and a shared file made one watcher abort on the other's
# triggers.
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "watcher_mcu.json"
DEFAULT_TASKS_FILE = PROJECT_ROOT / "var" / "logs" / "mcu_tasks.jsonl"
DEFAULT_FIRED_STATE = PROJECT_ROOT / "var" / "state" / "mcu_watcher_fired.json"

_WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}

# Rate limiter for same-day retries of FAILED triggers.
RETRY_BACKOFF_S = 600.0


# ──────────────────────────────────────────────────────────────────── config


def load_config(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load and validate watcher.json. Returns list of trigger dicts."""
    p = Path(path) if path else DEFAULT_CONFIG
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
            f"watcher: trigger {tid!r} 'allow' must be a list of primitive patterns"
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
                    f"watcher: trigger {tid!r} schedule 'days' has unknown day(s): {unknown}"
                )
    elif typ == "file":
        if not isinstance(sch.get("directory"), str) or not sch["directory"].strip():
            raise FridayError(f"watcher: trigger {tid!r} file schedule needs a 'directory'")
    elif typ in ("whatsapp-media", "telegram-media", "telegram-text", "discord-text"):
        pass  # special types — no extra validation needed
    else:
        raise FridayError(
            f"watcher: trigger {tid!r} schedule 'type' must be 'time', 'file', "
            "'whatsapp-media', 'telegram-media', 'telegram-text', or 'discord-text'"
        )


# ──────────────────────────────────────────────────────────── scheduling


def _time_due(trigger: dict[str, Any], now: datetime, fired_dates: dict[str, str]) -> bool:
    """Has today's HH:MM passed (on an enabled day) and not already fired?"""
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


def _new_files(trigger: dict[str, Any], seen: set[str]) -> list[str]:
    """New matching files not yet seen."""
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


def _has_pending_media() -> bool:
    """Check WhatsApp pending media queue."""
    try:
        from friday_mcu.adapters.whatsapp import load_pending_media
        return bool(load_pending_media())
    except Exception:
        return False


def _has_telegram_media() -> bool:
    """Check Telegram for new media messages."""
    try:
        from friday_mcu.adapters.telegram import poll_media
        # Presence probe must not consume the queue — commit=False keeps the
        # offset untouched until the messages are actually processed.
        msgs = poll_media(limit=1, commit=False)
        return bool(msgs)
    except Exception:
        return False


def _has_telegram_text() -> bool:
    """Check Telegram for new text messages."""
    try:
        from friday_mcu.adapters.telegram import poll_text_messages
        msgs = poll_text_messages(limit=1)
        return bool(msgs)
    except Exception:
        return False


def _has_discord_text() -> bool:
    """Check Discord for new text messages."""
    try:
        from friday_mcu.adapters.discord import poll_messages
        msgs = poll_messages(limit=1)
        return bool(msgs)
    except Exception:
        return False


# ──────────────────────────────────────────────────────── allowlist


def _allowed_prim(primitive: str, allowed: list[str]) -> bool:
    """Check if a primitive passes the trigger's allowlist."""
    for pat in allowed:
        if pat == primitive:
            return True
        if pat.endswith(".*") and primitive.startswith(pat[:-1]):
            return True
    return False


# ────────────────────────────────────────────────────── goal execution


def _execute_plan(
    plan_dict: dict[str, Any],
    goal: str,
    run_id: str,
    confidence: float = 0.0,
) -> dict[str, Any]:
    """Run an already-built plan dict through the executor directly.

    Used for inline deterministic plans and cached plans — zero LLM calls.
    Every terminal state (COMPLETED, ABORT, ERROR) is recorded to the memory
    store and the learning loop — a failure the learner never sees cannot
    become a lesson.
    """
    from friday_mcu.brain.executor import run_plan

    def _record_outcome(status: str, elapsed: float, steps: list[dict[str, Any]], error: str) -> None:
        try:
            from friday_mcu.memory.learning import MemoryLearner
            from friday_mcu.memory.store import MemoryManager
            mgr = MemoryManager()
            if status == "COMPLETED":
                mgr.store(
                    key=f"watch_{run_id}",
                    content=f"Goal: {goal} -> {status} ({len(steps)} steps)",
                    memory_type="episodic",
                    tags=["watcher"],
                )
                mgr.procedural.store_pattern(
                    goal,
                    steps,
                    success=True,
                    confidence=0.9,
                )
            learner = MemoryLearner()
            learner.record_outcome(
                goal=goal,
                success=status == "COMPLETED",
                duration_s=elapsed,
                steps=steps,
                error=error,
            )
        except Exception:
            pass  # memory failure must not break the watcher

    t0 = time.monotonic()
    try:
        result = run_plan(
            {"goal": plan_dict.get("goal", goal), "steps": plan_dict.get("steps", [])},
            run_id=run_id,
            confidence=confidence,
        )
        elapsed = time.monotonic() - t0

        # Extract human-readable result from last successful step
        result_text = ""
        for sr in reversed(result.steps):
            if sr.status == "VERIFIED" and sr.result is not None:
                r = sr.result
                if isinstance(r, str):
                    result_text = r
                elif isinstance(r, dict):
                    for k in ("text", "body", "description", "summary", "content"):
                        if k in r and isinstance(r[k], str):
                            result_text = r[k]
                            break
                    if not result_text:
                        result_text = json.dumps(r, default=str)[:2000]
                else:
                    result_text = json.dumps(r, default=str)[:2000]
                break

        steps_data = [{"primitive": s.primitive, "status": s.status} for s in result.steps]
        _record_outcome(result.status, elapsed, steps_data, "")

        return {
            "status": result.status,
            "duration_s": round(elapsed, 2),
            "_result": result_text[:2000],
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
        elapsed = time.monotonic() - t0
        _record_outcome("ABORT", elapsed, [], str(exc)[:500])
        return {
            "status": "ABORT",
            "error": str(exc)[:500],
            "_result": str(exc)[:500],
            "duration_s": round(elapsed, 2),
            "steps": [],
        }
    except Exception as exc:
        elapsed = time.monotonic() - t0
        _record_outcome("ERROR", elapsed, [], f"{type(exc).__name__}: {exc}"[:500])
        return {
            "status": "ERROR",
            "error": f"{type(exc).__name__}: {exc}"[:500],
            "_result": f"Error: {exc}"[:500],
            "duration_s": round(elapsed, 2),
            "steps": [],
        }


def _execute_goal(goal: str, run_id: str) -> dict[str, Any]:
    """Plan a goal via the LLM, then execute the resulting plan."""
    from friday_mcu.brain.planner import plan as llm_plan

    try:
        p = llm_plan(goal, run_id=run_id)
    except FridayError as exc:
        return {
            "status": "ABORT",
            "error": str(exc)[:500],
            "_result": str(exc)[:500],
            "duration_s": 0.0,
            "steps": [],
        }
    except Exception as exc:
        return {
            "status": "ERROR",
            "error": f"{type(exc).__name__}: {exc}"[:500],
            "_result": f"Error: {exc}"[:500],
            "duration_s": 0.0,
            "steps": [],
        }
    return _execute_plan({"goal": p.goal, "steps": p.steps}, goal, run_id, confidence=p.confidence)


# ──────────────────────────────── special trigger handlers


def _run_whatsapp_media_trigger(trigger: dict[str, Any], run_id: str) -> dict[str, Any]:
    """Download pending WhatsApp media items."""
    t_id = trigger["id"]
    detail: dict[str, Any] = {"trigger": t_id}
    try:
        from friday_mcu.adapters.whatsapp import (
            clear_pending_media,
            download_media,
            load_pending_media,
        )
        pending = load_pending_media()
        if not pending:
            detail["status"] = "COMPLETED"
            detail["downloaded_count"] = 0
            return detail

        downloaded: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        processed_ids: list[str] = []

        for item in pending:
            media_id = item.get("media_id", "")
            if not media_id:
                continue
            try:
                result = download_media(media_id)
                downloaded.append({
                    "media_id": media_id,
                    "filename": result.get("filename", ""),
                    "path": result.get("path", ""),
                    "sender": item.get("sender", ""),
                })
                processed_ids.append(media_id)
            except Exception as exc:
                errors.append({"media_id": media_id, "error": f"{type(exc).__name__}: {exc}"})

        if processed_ids:
            clear_pending_media(processed_ids)

        detail["status"] = "COMPLETED" if downloaded else "FAILED"
        detail["downloaded_count"] = len(downloaded)
        detail["errors"] = errors
    except FridayError as exc:
        detail["status"] = "FAILED"
        detail["error"] = str(exc)[:500]
    except Exception as exc:
        detail["status"] = "ERROR"
        detail["error"] = f"{type(exc).__name__}: {exc}"[:500]
    return detail


def _run_telegram_media_trigger(trigger: dict[str, Any], run_id: str) -> dict[str, Any]:
    """Poll Telegram for new media and download."""
    t_id = trigger["id"]
    detail: dict[str, Any] = {"trigger": t_id}
    try:
        from friday_mcu.adapters.telegram import download_file, mark_read, poll_media

        # commit=False: nothing is consumed unless the whole batch succeeds.
        # Telegram's offset is contiguous, so a partial commit would skip the
        # failed message permanently — retry the batch instead (downloads
        # overwrite the same deterministic path, so retries are idempotent).
        messages = poll_media(limit=20, commit=False)
        if not messages:
            detail["status"] = "COMPLETED"
            detail["downloaded_count"] = 0
            return detail

        downloaded: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for msg in messages:
            file_id = msg.get("file_id", "")
            if not file_id:
                continue
            try:
                result = download_file(file_id, filename=msg.get("filename"))
                downloaded.append({
                    "file_id": file_id,
                    "filename": result.get("filename", ""),
                    "path": result.get("path", ""),
                    "sender": msg.get("from", ""),
                })
            except Exception as exc:
                errors.append({"file_id": file_id, "error": f"{type(exc).__name__}: {exc}"})

        if downloaded and not errors:
            update_ids = [m.get("update_id") for m in messages if m.get("update_id")]
            try:
                mark_read([int(u) for u in update_ids])
            except Exception:
                pass

        detail["status"] = "COMPLETED" if downloaded else "FAILED"
        detail["downloaded_count"] = len(downloaded)
        detail["errors"] = errors
    except FridayError as exc:
        detail["status"] = "FAILED"
        detail["error"] = str(exc)[:500]
    except Exception as exc:
        detail["status"] = "ERROR"
        detail["error"] = f"{type(exc).__name__}: {exc}"[:500]
    return detail


# ─── command prefix for text triggers

DEFAULT_COMMAND_PREFIX = "/goal"


def _get_command_prefix() -> str:
    return os.environ.get("FRIDAY_COMMAND_PREFIX", DEFAULT_COMMAND_PREFIX)


def _extract_goal(text: str, prefix: str) -> str | None:
    """Extract goal from a command-prefixed message. Returns None if not a goal."""
    if not prefix:
        return text.strip() if text.strip() else None
    text_stripped = text.strip()
    if text_stripped.lower().startswith(prefix.lower()):
        goal = text_stripped[len(prefix):].strip()
        return goal if goal else None
    return None


def _run_text_trigger(
    trigger: dict[str, Any], run_id: str, platform: str
) -> dict[str, Any]:
    """Handle telegram-text or discord-text triggers: poll, execute, reply."""
    t_id = trigger["id"]
    prefix = _get_command_prefix()
    detail: dict[str, Any] = {"trigger": t_id}

    try:
        if platform == "telegram":
            from friday_mcu.adapters.telegram import mark_read, poll_text_messages, send_text
            messages = poll_text_messages(limit=10)
            id_key = "chat_id"
        elif platform == "discord":
            from friday_mcu.adapters.discord import mark_channel_read, poll_messages, send_text
            raw = poll_messages(limit=10)
            messages = [
                {"text": m.get("content", ""), "chat_id": m.get("channel_id", ""), "from": m.get("author", ""), "message_id": m.get("id", "")}
                for m in raw
            ]
            id_key = "chat_id"
        else:
            detail["status"] = "FAILED"
            detail["error"] = f"unknown platform: {platform}"
            return detail

        if not messages:
            detail["status"] = "COMPLETED"
            detail["messages_processed"] = 0
            return detail

        results: list[dict[str, Any]] = []
        skipped = 0

        from friday_mcu.comms.commands import route as _route_message

        def _consume(msg: dict[str, Any]) -> None:
            """Mark a message handled so it is never re-queued forever."""
            if platform == "telegram" and msg.get("update_id"):
                try:
                    mark_read([int(msg["update_id"])])
                except Exception:
                    pass
            elif platform == "discord":
                try:
                    mark_channel_read(msg.get(id_key, ""), msg.get("message_id"))
                except Exception:
                    pass

        def _deliver(reply_text: str, chat_id: str) -> None:
            # Platform keyword differs: telegram is `to=`, discord is
            # `channel_id=`. Passing the wrong keyword raises TypeError which
            # used to be swallowed — Discord never got its replies.
            try:
                if platform == "telegram":
                    send_text(reply_text, to=chat_id)
                else:
                    send_text(reply_text, channel_id=chat_id)
            except Exception:
                pass  # reply failure must not break the loop

        for msg in messages:
            text = msg.get("text", "")
            chat_id = msg.get(id_key, "")
            if not text or not chat_id:
                continue

            routed = _route_message(text)
            entry: dict[str, Any] = {
                "message_id": msg.get("message_id"),
                "sender": msg.get("from", ""),
            }

            if routed is None:
                # Goal-prefixed message: planner → executor → natural reply.
                goal = _extract_goal(text, prefix)
                if goal is None:
                    _consume(msg)
                    skipped += 1
                    continue

                msg_run_id = f"{run_id}-{platform}-{msg.get('message_id', '')}"
                result = _execute_goal(goal, msg_run_id)

                from friday_mcu.comms.natural import NaturalComms
                _comms = NaturalComms()
                status = result.get("status", "UNKNOWN")
                _nat_msg = _comms.build_goal_result(
                    goal=goal,
                    result=result.get("_result", "") or result.get("error", "Done."),
                    context={
                        "success": status == "COMPLETED",
                        "error": result.get("error", ""),
                        "attempts": max((s.get("attempts", 1) for s in result.get("steps", [])), default=1),
                    },
                    platform=platform,
                )
                _deliver(_nat_msg.content[:1800], chat_id)
                entry.update({
                    "goal": goal[:200],
                    "status": status,
                    "duration_s": result.get("duration_s", 0),
                })
            elif routed.consumed:
                # Built-in command (/friday help|status|adapters|memory|phone)
                # — deterministic reply, zero LLM cost.
                if routed.reply:
                    _deliver(routed.reply[:1800], chat_id)
                entry.update({"goal": text[:200], "status": "COMMAND"})
            else:
                # Chatter without a goal prefix — consumed, no reply.
                skipped += 1
                _consume(msg)
                continue

            # Consumed once handled (goal attempted + reply sent), whatever the
            # outcome — retrying a goal that hard-fails would just re-fail.
            _consume(msg)
            results.append(entry)

        detail["status"] = "COMPLETED"
        detail["messages_processed"] = len(results)
        detail["messages_skipped"] = skipped
        detail["results"] = results
    except FridayError as exc:
        detail["status"] = "FAILED"
        detail["error"] = str(exc)[:500]
    except Exception as exc:
        detail["status"] = "ERROR"
        detail["error"] = f"{type(exc).__name__}: {exc}"[:500]
    return detail


# ────────────────────────────────────── trigger execution


def _make_plan(
    trigger: dict[str, Any], plan_cache: dict[str, dict[str, Any]], run_id: str
) -> dict[str, Any]:
    """Get the plan for a trigger: inline deterministic plan wins, else LLM."""
    if trigger.get("plan"):
        p = dict(trigger["plan"])
        p.setdefault("goal", trigger.get("goal", trigger["id"]))
        return p
    goal = trigger["goal"]
    if goal in plan_cache:
        return plan_cache[goal]
    from friday_mcu.brain.planner import plan as llm_plan

    p = llm_plan(goal, run_id=run_id)
    plan_cache[goal] = {"goal": p.goal, "steps": p.steps, "confidence": p.confidence}
    return plan_cache[goal]


def _run_trigger(
    trigger: dict[str, Any], plan_cache: dict[str, dict[str, Any]]
) -> tuple[bool, dict[str, Any]]:
    """Fire one trigger: plan → execute → record → notify. Never raises."""
    t_id = trigger["id"]
    goal = trigger.get("goal") or (trigger.get("plan") or {}).get("goal") or t_id
    run_id = f"mcu-watch-{t_id}-{datetime.now().strftime('%Y%m%dT%H%M%S')}"

    emit(EventType.GOAL_START, source="watcher", data={"trigger": t_id, "goal": goal})

    ok = False
    detail: dict[str, Any] = {"trigger": t_id, "status": "COMPLETED"}

    try:
        sch_type = trigger.get("schedule", {}).get("type")

        # Special trigger types
        if sch_type == "whatsapp-media":
            detail = _run_whatsapp_media_trigger(trigger, run_id)
            ok = detail.get("status") == "COMPLETED"
        elif sch_type == "telegram-media":
            detail = _run_telegram_media_trigger(trigger, run_id)
            ok = detail.get("status") == "COMPLETED"
        elif sch_type == "telegram-text":
            detail = _run_text_trigger(trigger, run_id, "telegram")
            ok = detail.get("status") == "COMPLETED"
        elif sch_type == "discord-text":
            detail = _run_text_trigger(trigger, run_id, "discord")
            ok = detail.get("status") == "COMPLETED"
        else:
            # Standard time/file trigger: plan → execute
            plan_dict = _make_plan(trigger, plan_cache, run_id)
            allowed = trigger.get("allow")

            # Allowlist enforcement
            if allowed:
                forbidden = [
                    s.get("primitive")
                    for s in plan_dict.get("steps", [])
                    if not _allowed_prim(s.get("primitive", ""), allowed)
                ]
                if forbidden:
                    plan_cache.pop(goal, None)
                    detail = {
                        "trigger": t_id,
                        "status": "REFUSED",
                        "forbidden": forbidden,
                        "allowed": allowed,
                    }
                    _record_task(f"mcu-watch:{t_id}", goal, False, detail)
                    emit(
                        EventType.GOAL_FAILED,
                        source="watcher",
                        data={"trigger": t_id, "status": "REFUSED", "forbidden": forbidden},
                    )
                    return False, detail

            # Inline deterministic plans and cached plans execute directly
            # (no LLM); only an uncached `goal` was planned in _make_plan.
            result = _execute_plan(
                plan_dict,
                goal,
                run_id,
                confidence=plan_dict.get("confidence", 0.0),
            )
            ok = result.get("status") == "COMPLETED"
            detail = {
                "trigger": t_id,
                "status": result.get("status", "FAILED"),
                "steps": result.get("steps", []),
                "duration_s": result.get("duration_s", 0),
            }
    except FridayError as exc:
        ok = False
        detail = {"trigger": t_id, "status": "ABORT", "error": str(exc)[:500]}
        plan_cache.pop(goal, None)
    except Exception as exc:
        ok = False
        detail = {"trigger": t_id, "status": "ERROR", "error": f"{type(exc).__name__}: {exc}"[:500]}
        plan_cache.pop(goal, None)

    _record_task(f"mcu-watch:{t_id}", goal, ok, detail)

    emit(
        EventType.GOAL_COMPLETE if ok else EventType.GOAL_FAILED,
        source="watcher",
        data={"trigger": t_id, "status": detail.get("status"), "duration_s": detail.get("duration_s")},
    )

    # Desktop notification
    if trigger.get("notify", True):
        _notify_outcome(t_id, ok, detail)

    return ok, detail


# ──────────────────────────────── persistence + notification


def _tasks_file() -> Path:
    return Path(os.environ.get("FRIDAY_MCU_TASKS_FILE", str(DEFAULT_TASKS_FILE)))


def _fired_state_file() -> Path:
    return Path(os.environ.get("FRIDAY_MCU_FIRED_FILE", str(DEFAULT_FIRED_STATE)))


def _file_seen_file() -> Path:
    """Persisted seen-file registry (so a restart never re-fires file triggers
    for every pre-existing matching file)."""
    return Path(os.environ.get("FRIDAY_MCU_SEEN_FILE", str(PROJECT_ROOT / "var" / "state" / "mcu_watcher_seen.json")))


def _notified_patterns_file() -> Path:
    """Persisted set of pattern IDs already reported proactively.

    Ensures a pattern insight is only sent once per TTL window, not on every
    poll tick. Pruned periodically of entries older than 7 days so a pattern
    that stops recurring can resurface.
    """
    return Path(
        os.environ.get(
            "FRIDAY_MCU_PROACTIVE_NOTIFIED",
            str(PROJECT_ROOT / "var" / "state" / "mcu_proactive_notified.json"),
        )
    )


# Patterns already notified within this TTL (seconds) are not re-sent.
_PROACTIVE_NOTIFIED_TTL_S = 7 * 24 * 3600  # 7 days


def _load_notified_patterns() -> dict[str, float]:
    """Load the {pattern_id: timestamp} map of already-notified patterns."""
    try:
        data = json.loads(_notified_patterns_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if isinstance(data, dict):
        return {str(k): float(v) for k, v in data.items() if isinstance(v, (int, float))}
    return {}


def _save_notified_patterns(patterns: dict[str, float]) -> None:
    """Persist the notified-pattern map, pruning expired entries."""
    now = time.time()
    pruned = {k: v for k, v in patterns.items() if now - v < _PROACTIVE_NOTIFIED_TTL_S}
    try:
        path = _notified_patterns_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(pruned, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def _load_seen() -> set[str]:
    try:
        data = json.loads(_file_seen_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    if isinstance(data, list):
        return {str(x) for x in data}
    return set()


def _save_seen(seen: set[str]) -> None:
    try:
        path = _file_seen_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        # Bound growth: file triggers add one entry per fired file forever.
        if len(seen) > 2000:
            seen = set(sorted(seen)[-2000:])
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(sorted(seen)), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def _load_fired_state() -> dict[str, str]:
    try:
        data = json.loads(_fired_state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if isinstance(v, str)}


def _save_fired_state(state: dict[str, str]) -> None:
    try:
        path = _fired_state_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def _record_task(task_id: str, goal: str, ok: bool, detail: dict[str, Any]) -> None:
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
    except OSError:
        pass


def _notify_outcome(trigger_id: str, ok: bool, detail: dict[str, Any]) -> None:
    try:
        from friday_mcu.adapters.notify import notify_send
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        status = detail.get("status", "DONE" if ok else "FAILED")
        error = detail.get("error", "")
        goal = detail.get("goal", trigger_id)
        duration = detail.get("duration_s", 0)

        if ok:
            msg = comms.build_goal_result(
                goal=goal,
                result=f"Trigger '{trigger_id}' completed in {duration:.1f}s" if duration else f"Trigger '{trigger_id}' completed",
                context={"success": True},
            )
        else:
            msg = comms.build_error_report(
                goal=f"trigger '{trigger_id}'",
                error=error or status,
                context={"attempts": detail.get("attempts", 0)},
            )

        notify_send(
            title=f"MCU Friday: {trigger_id} {status}",
            body=msg.content[:300],
        )
    except Exception:
        pass


def _in_retry_backoff(trigger_id: str, last_attempts: dict[str, float]) -> bool:
    last = last_attempts.get(trigger_id)
    return last is not None and time.monotonic() - last < RETRY_BACKOFF_S


# ──────────────────────────────── proactive + pattern hook


PROACTIVE_CONFIDENCE_FLOOR = 0.8
PROACTIVE_FREQUENCY_FLOOR = 5


def _scheduled_trigger_goals() -> set[str]:
    """Collect the goal strings from scheduled (time/file) triggers in the watcher
    config so that routine/scheduled goals are not reported as novel patterns."""
    try:
        triggers = load_config()
    except Exception:
        return set()
    goals: set[str] = set()
    for t in triggers:
        goal = t.get("goal")
        if goal:
            goals.add(goal.lower())
    return goals


def _is_scheduled_goal(goal_text: str, scheduled_goals: set[str]) -> bool:
    """Check whether a pattern's goal text matches any scheduled trigger goal."""
    g = goal_text.lower()
    for sg in scheduled_goals:
        if g in sg or sg in g:
            return True
    return False


def _run_proactive_tick() -> None:
    """Run the proactive engine tick: detect patterns → suggest → flush."""
    try:
        from friday_mcu.memory.store import MemoryManager
        from friday_mcu.observer.patterns import PatternDetector
        from friday_mcu.comms.proactive import ProactiveEngine, ProactiveMessage

        mgr = MemoryManager()
        recent = mgr.episodic.recent(100)
        tasks = [
            {
                "goal": m.content.split("->")[0].replace("Goal:", "").strip(),
                "gate6_passed": "success" in m.content.lower() or "completed" in m.content.lower(),
                "timestamp": m.created_at if isinstance(m.created_at, str) else datetime.fromtimestamp(m.created_at).isoformat(),
            }
            for m in recent
        ]

        if not tasks:
            return

        detector = PatternDetector()
        patterns = detector.analyze(tasks, min_occurrences=2)

        # Store detected patterns as semantic memories
        for p in patterns:
            if p.confidence >= 0.4:
                try:
                    mgr.semantic.store(
                        key=f"pattern_{p.type}_{p.id}",
                        content=f"[{p.type}] {p.description} (freq={p.frequency}, conf={p.confidence:.0%})",
                        tags=["observer", "pattern", p.type],
                    )
                except Exception:
                    pass

        # Load already-notified pattern IDs to avoid duplicate proactive messages
        notified = _load_notified_patterns()

        # Gather scheduled trigger goals so routine/repeatable triggers are
        # not reported as novel observations.
        scheduled_goals = _scheduled_trigger_goals()

        # Generate proactive suggestions from high-confidence patterns
        from friday_mcu.comms.natural import NaturalComms
        _nat = NaturalComms()
        engine = ProactiveEngine()
        for p in patterns:
            # Only consider goal-type patterns worth reporting
            if p.type != "goal":
                continue
            # Raise thresholds: only report truly recurring, high-confidence patterns
            if p.confidence < PROACTIVE_CONFIDENCE_FLOOR:
                continue
            if p.frequency < PROACTIVE_FREQUENCY_FLOOR:
                continue
            # Skip patterns that correspond to scheduled trigger goals
            if _is_scheduled_goal(p.description, scheduled_goals):
                continue
            # Skip patterns already reported within the TTL window
            if p.id in notified:
                continue

            _nat_msg = _nat.build_proactive_suggestion(
                suggestion=p.description,
                reason=f"Observed {p.frequency} times (confidence={p.confidence:.0%})",
            )
            msg = ProactiveMessage(
                content=_nat_msg.content,
                priority="low",
                confidence=p.confidence,
                reason=f"pattern_{p.type}",
            )
            engine.suggest(msg)
            notified[p.id] = time.time()

        # Persist the updated notified set (prunes expired entries)
        if notified:
            _save_notified_patterns(notified)

        # Flush (sends if conditions allow)
        engine.flush()
    except Exception:
        pass  # proactive tick must never crash the watcher


# ──────────────────────────────────────────────── heartbeat


def _emit_heartbeat(
    started: float,
    last_trigger_id: str | None,
    last_trigger_at: str | None,
    trigger_stats: dict[str, int] | None = None,
) -> None:
    args: dict[str, Any] = {
        "uptime_s": int(time.monotonic() - started),
        "last_trigger": last_trigger_id or "none",
        "last_trigger_at": last_trigger_at or "",
        "source": "mcu_watcher",
    }
    if trigger_stats:
        args["trigger_runs"] = trigger_stats.get("total", 0)
        args["trigger_success"] = trigger_stats.get("success", 0)
        args["trigger_failed"] = trigger_stats.get("failed", 0)

    emit(EventType.SYSTEM_HEALTH, source="mcu_watcher", data=args)


# ──────────────────────────────────────────────────── main loop


def run_watcher(
    config_path: str | Path | None = None,
    *,
    once: bool = False,
    poll_s: float = 30.0,
    heartbeat_s: float = 120.0,
) -> None:
    """Run the MCU watcher loop.

    once=True: fire due triggers once and exit (for cron / testing).
    daemon mode: poll every poll_s, heartbeat every heartbeat_s.
    """
    if poll_s <= 0:
        raise FridayError(f"watcher poll_s must be positive, got {poll_s!r}")

    triggers = load_config(config_path)
    enabled = [t for t in triggers if t.get("enabled", True)]
    plan_cache: dict[str, dict[str, Any]] = {}
    fired_dates = _load_fired_state()
    last_fired_saved = dict(fired_dates)
    last_attempts: dict[str, float] = {}
    seen = _load_seen()
    last_seen_saved = set(seen)
    consolidated_date = ""
    started = time.monotonic()
    trigger_stats: dict[str, int] = {"total": 0, "success": 0, "failed": 0}
    last_heartbeat = started
    last_trigger_id: str | None = None
    last_trigger_at: str | None = None

    emit(
        EventType.SYSTEM_HEALTH,
        source="mcu_watcher",
        data={
            "triggers": [t["id"] for t in enabled],
            "once": once,
            "poll_s": poll_s,
            "result": "START",
        },
    )

    try:
        while True:
            now = datetime.now()
            for t in enabled:
                sch = t["schedule"]
                rolled_back_files: list[str] | None = None
                if sch["type"] == "time":
                    due = _time_due(t, now, fired_dates) and not _in_retry_backoff(
                        t["id"], last_attempts
                    )
                elif sch["type"] == "whatsapp-media":
                    due = _has_pending_media() and not _in_retry_backoff(t["id"], last_attempts)
                elif sch["type"] == "telegram-media":
                    due = _has_telegram_media() and not _in_retry_backoff(t["id"], last_attempts)
                elif sch["type"] == "telegram-text":
                    due = _has_telegram_text() and not _in_retry_backoff(t["id"], last_attempts)
                elif sch["type"] == "discord-text":
                    due = _has_discord_text() and not _in_retry_backoff(t["id"], last_attempts)
                else:
                    # File detection pauses during backoff: re-adding the files
                    # to `seen` while a failed run waits would silently swallow
                    # the retry once the backoff expires.
                    if _in_retry_backoff(t["id"], last_attempts):
                        due = False
                    else:
                        rolled_back_files = _new_files(t, seen)
                        due = bool(rolled_back_files)

                if due:
                    trigger_stats["total"] += 1
                    ok, detail = _run_trigger(t, plan_cache)

                    if ok or detail.get("status") == "REFUSED":
                        trigger_stats["success"] += 1
                    else:
                        trigger_stats["failed"] += 1

                    last_attempts[t["id"]] = time.monotonic()
                    last_trigger_id = t["id"]
                    last_trigger_at = datetime.now(UTC).isoformat(timespec="seconds")

                    if ok or detail.get("status") == "REFUSED":
                        fired_dates[t["id"]] = datetime.now().date().isoformat()
                    elif rolled_back_files:
                        # Failed run: forget these files so they are re-detected
                        # (and re-fired) once the backoff expires.
                        seen.difference_update(rolled_back_files)

            # Persist fired state + seen-file registry
            if fired_dates != last_fired_saved:
                _save_fired_state(fired_dates)
                last_fired_saved = dict(fired_dates)
            if seen != last_seen_saved:
                _save_seen(seen)
                last_seen_saved = set(seen)

            # Daily memory consolidation (decay + prune) — once per date.
            day_key = now.date().isoformat()
            if consolidated_date != day_key:
                try:
                    from friday_mcu.memory.learning import MemoryLearner
                    from friday_mcu.memory.store import MemoryManager
                    MemoryManager().consolidate()
                    MemoryLearner().consolidate()
                except Exception:
                    pass
                consolidated_date = day_key

            # Proactive tick (patterns → suggestions → flush)
            _run_proactive_tick()

            if once:
                break

            # Heartbeat
            elapsed = time.monotonic()
            if heartbeat_s and elapsed - last_heartbeat >= heartbeat_s:
                last_heartbeat = elapsed
                _emit_heartbeat(started, last_trigger_id, last_trigger_at, trigger_stats)

            time.sleep(poll_s)

    except KeyboardInterrupt:
        emit(EventType.SYSTEM_HEALTH, source="mcu_watcher", data={"result": "STOP", "reason": "interrupt"})
        return

    emit(EventType.SYSTEM_HEALTH, source="mcu_watcher", data={"result": "STOP"})


# ──────────────────────────────────────────────────── CLI entry point


def main(argv: list[str] | None = None) -> None:
    import argparse

    ap = argparse.ArgumentParser(description="MCU Friday ambient watch loop")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG), help="watcher config JSON (default: config/watcher_mcu.json)")
    ap.add_argument("--once", action="store_true", help="fire due triggers once, then exit")
    ap.add_argument("--poll", type=float, default=30.0, help="loop poll interval seconds")
    ap.add_argument(
        "--heartbeat",
        type=float,
        default=None,
        help="daemon.alive interval seconds (default: 120)",
    )
    args = ap.parse_args(argv)
    heartbeat_s = (
        args.heartbeat
        if args.heartbeat is not None
        else float(os.environ.get("FRIDAY_MCU_HEARTBEAT_S", "120"))
    )
    run_watcher(args.config, once=args.once, poll_s=args.poll, heartbeat_s=heartbeat_s)


if __name__ == "__main__":
    main()
