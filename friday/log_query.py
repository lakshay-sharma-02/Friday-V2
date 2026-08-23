"""L0 Log Query — structured querying for friday.jsonl.

Provides functions to filter, aggregate, and analyze the structured
JSON log that friday.jsonl produces. Enables goals like:
  - "show me all failed steps"
  - "what was the average duration of gmail.summarize?"
  - "how many goals ran today?"
  - "what primitives were called in the last hour?"

Usage:
    from friday.log_query import query_logs, summarize_by_primitive
    results = query_logs(layer="L3", primitive="plan", status="FAILED")
    summary = summarize_by_primitive(hours=24)
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG = PROJECT_ROOT / "var" / "logs" / "friday.jsonl"


def _log_path() -> Path:
    return Path(os.environ.get("FRIDAY_LOG_FILE", str(DEFAULT_LOG)))


def _load_recent(hours: int = 24, limit: int = 10000) -> list[dict[str, Any]]:
    """Load log entries from the last N hours."""
    path = _log_path()
    if not path.exists():
        return []

    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    entries: list[dict[str, Any]] = []

    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                ts_str = rec.get("timestamp", "")
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        if ts < cutoff:
                            continue
                    except ValueError:
                        pass
                entries.append(rec)
                if len(entries) >= limit:
                    break
            except (json.JSONDecodeError, ValueError):
                continue
    except OSError:
        return []

    return entries


def query_logs(
    *,
    hours: int = 24,
    layer: str | None = None,
    primitive: str | None = None,
    run_id: str | None = None,
    has_error: bool | None = None,
    min_duration_ms: float | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Query log entries with filters.

    Args:
        hours: Only include entries from the last N hours.
        layer: Filter by layer (L0, L1, L2, L3, L4, WATCH, etc.).
        primitive: Filter by primitive name (substring match).
        run_id: Filter by run ID.
        has_error: If True, only entries with exceptions; if False, only successes.
        min_duration_ms: Only entries slower than this threshold.
        limit: Max entries to return.

    Returns:
        List of matching log records, newest first.
    """
    entries = _load_recent(hours=hours)
    results: list[dict[str, Any]] = []

    for rec in entries:
        if layer and rec.get("layer") != layer:
            continue
        if primitive and primitive not in (rec.get("primitive") or ""):
            continue
        if run_id and rec.get("run_id") != run_id:
            continue
        if has_error is True and not rec.get("exception"):
            continue
        if has_error is False and rec.get("exception"):
            continue
        if min_duration_ms is not None and (rec.get("duration_ms") or 0) < min_duration_ms:
            continue
        results.append(rec)
        if len(results) >= limit:
            break

    return results


def summarize_by_primitive(hours: int = 24) -> dict[str, dict[str, Any]]:
    """Summarize primitive usage over the last N hours.

    Returns a dict keyed by primitive name with:
      - count: total calls
      - errors: call count with exceptions
      - avg_duration_ms: average duration
      - p95_duration_ms: 95th percentile duration
    """
    entries = _load_recent(hours=hours)
    by_prim: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for rec in entries:
        prim = rec.get("primitive") or "unknown"
        by_prim[prim].append(rec)

    summary: dict[str, dict[str, Any]] = {}
    for prim, recs in sorted(by_prim.items()):
        durations = [r.get("duration_ms", 0) for r in recs if r.get("duration_ms")]
        errors = sum(1 for r in recs if r.get("exception"))
        durations.sort()
        p95_idx = int(len(durations) * 0.95) if durations else 0
        summary[prim] = {
            "count": len(recs),
            "errors": errors,
            "avg_duration_ms": round(sum(durations) / len(durations), 1) if durations else 0,
            "p95_duration_ms": round(durations[p95_idx], 1) if durations else 0,
        }
    return summary


def summarize_by_run(hours: int = 24) -> dict[str, dict[str, Any]]:
    """Summarize each run (by run_id) over the last N hours.

    Returns a dict keyed by run_id with:
      - goal: the goal string (if available)
      - steps: number of steps
      - status: COMPLETED / ABORTED / UNKNOWN
      - duration_ms: total duration
      - errors: number of error steps
    """
    entries = _load_recent(hours=hours)
    by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for rec in entries:
        rid = rec.get("run_id") or "unknown"
        by_run[rid].append(rec)

    summary: dict[str, dict[str, Any]] = {}
    for rid, recs in sorted(by_run.items()):
        goal = ""
        status = "UNKNOWN"
        errors = 0
        total_ms = 0.0

        for r in recs:
            if r.get("primitive") == "plan" and r.get("result") in ("ACCEPTED", "PENDING"):
                goal = (r.get("args") or {}).get("goal", "")[:80]
            if r.get("primitive") == "plan" and r.get("result") in ("COMPLETED", "ABORTED"):
                status = r["result"]
            if r.get("exception"):
                errors += 1
            total_ms += r.get("duration_ms", 0)

        summary[rid] = {
            "goal": goal,
            "steps": len(recs),
            "status": status,
            "duration_ms": round(total_ms, 1),
            "errors": errors,
        }
    return summary


def get_recent_goals(hours: int = 24) -> list[dict[str, Any]]:
    """Get recent goals with their outcomes."""
    entries = _load_recent(hours=hours)
    goals: list[dict[str, Any]] = []
    seen_runs: set[str] = set()

    for rec in entries:
        if rec.get("primitive") == "plan" and rec.get("result") == "ACCEPTED":
            rid = rec.get("run_id", "")
            if rid in seen_runs:
                continue
            seen_runs.add(rid)
            goals.append({
                "run_id": rid,
                "goal": (rec.get("args") or {}).get("goal", ""),
                "timestamp": rec.get("timestamp", ""),
            })

    return goals


def format_summary(summary: dict[str, dict[str, Any]], title: str = "Summary") -> str:
    """Format a summary dict as a readable string."""
    lines = [f"\n📊 {title}", "=" * 60]
    for key, info in sorted(summary.items()):
        lines.append(f"\n  {key}:")
        for k, v in info.items():
            lines.append(f"    {k}: {v}")
    return "\n".join(lines)
