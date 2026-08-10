"""Capability-gap records - the raw material of the self-improvement loop.

When a plan step is REFUSED or ABORTs because its primitive is unknown,
unregistered, blocked, or not on a trigger's allowlist, the refusal is a
signal: a goal was attempted that Friday's L1 cannot currently satisfy.
Instead of letting that die as a log line, `record_gap` writes one
structured record to var/logs/capability_gaps.jsonl so a later triage
step (friday/gap_triage.py) can group refusals by missing primitive and
draft a proposed L1 contract for human review.

Writing a record is BEST-EFFORT: a broken gap file must never break the
executor or the watch loop - the refusal already happened and is already
in the L0 log; the gap record is additive.

Format (one JSON line per gap):

    { gap_id, timestamp, source ("watcher"|"executor"),
      trigger_id OR goal_id, attempted_primitive,
      attempted_args_shape (key -> type tags, never values),
      goal_context (the natural-language goal string), refusal_reason }

Processing state for the triage is tracked in capability_gaps.done: one
gap_id per line. `unprocessed_gaps` returns gaps whose id is not yet
done; `mark_processed` appends ids. Idempotent: re-processing a gap is a
no-op, and a crash between consume and mark simply re-offers the gap.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_GAPS_FILE = Path(__file__).resolve().parents[1] / "var" / "logs" / "capability_gaps.jsonl"


def _gaps_file() -> Path:
    return Path(os.environ.get("FRIDAY_GAPS_FILE", str(DEFAULT_GAPS_FILE)))


def _done_file() -> Path:
    return _gaps_file().with_suffix(".done")


def _type_tag(value: Any) -> str:
    """A privacy-safe shape tag for one arg value: type + size/len, never
    the value itself (args can carry secrets, mail addresses, bodies)."""
    if isinstance(value, dict):
        return f"dict:{len(value)}"
    if isinstance(value, list):
        return f"list:{len(value)}"
    if isinstance(value, str):
        return f"str:{len(value)}"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return type(value).__name__
    if value is None:
        return "none"
    return type(value).__name__


def record_gap(
    *,
    source: str,
    attempted_primitive: str,
    goal_context: str,
    refusal_reason: str,
    attempted_args: dict[str, Any] | None = None,
    trigger_id: str | None = None,
    goal_id: str | None = None,
) -> str:
    """Append one capability-gap record. Returns the gap_id (for tests and
    for the triage's done-tracking). Never raises - best-effort by design."""
    gap_id = f"{time.time_ns():x}{len(goal_context) % 97:02x}"
    rec: dict[str, Any] = {
        "gap_id": gap_id,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "source": source,
        "attempted_primitive": attempted_primitive,
        "attempted_args_shape": {
            k: _type_tag(v) for k, v in (attempted_args or {}).items()
        },
        "goal_context": goal_context,
        "refusal_reason": refusal_reason,
    }
    if trigger_id is not None:
        rec["trigger_id"] = trigger_id
    if goal_id is not None:
        rec["goal_id"] = goal_id
    try:
        path = _gaps_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        # additive only - the refusal already happened and is in the L0 log.
        # Exception, not OSError: an unpaired surrogate in a goal string
        # would raise UnicodeEncodeError and must not break the caller.
        pass
    return gap_id


def all_gaps() -> list[dict[str, Any]]:
    """Every recorded gap, in file order. Malformed/truncated lines are
    skipped, never raised on - a partial append must not crash the triage."""
    try:
        raw = _gaps_file().read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    out: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _processed_ids() -> set[str]:
    try:
        raw = _done_file().read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()
    return {l.strip() for l in raw.splitlines() if l.strip()}


def unprocessed_gaps() -> list[dict[str, Any]]:
    """Gaps not yet handed to the triage. Idempotent: marking a gap done
    removes it from future runs; a crashed triage run just re-offers it."""
    done = _processed_ids()
    return [g for g in all_gaps() if g.get("gap_id") not in done]


def mark_processed(gap_ids: list[str]) -> None:
    """Record which gaps the triage consumed. Best-effort and idempotent -
    appending an already-present id is harmless (a set is used on read)."""
    if not gap_ids:
        return
    try:
        path = _done_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            for gid in gap_ids:
                fh.write(gid + "\n")
    except Exception:
        pass  # best-effort; an unwritable done file never breaks the triage


def group_by_primitive(gaps: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group gap records by attempted_primitive, preserving first-seen
    order - repeated refusals for the same missing primitive become ONE
    triage unit, with every driving goal_context kept for the rationale."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for g in gaps:
        groups.setdefault(g.get("attempted_primitive", "?"), []).append(g)
    return groups
