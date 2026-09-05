"""Proactive Suggestion Engine — mine patterns from task history and suggest triggers.

Friday doesn't just execute goals you hand it — this module looks at what
goals succeed, what fails, and what patterns recur, then proposes new triggers
that would automate repetitive work.

Source data:
  - var/logs/tasks.jsonl — goal execution history (success/failure, timestamps)
  - var/logs/friday.jsonl — L0 log with primitive call patterns
  - config/watcher.json — existing triggers (to avoid duplicates)
  - var/state/memory.jsonl — stored memories for context

Output:
  - Suggestion dicts with goal, rationale, proposed schedule, and confidence
  - Optional: write inert trigger proposals to gates/proposed_triggers/

This is the "goals-proposal stage" upgraded: instead of only mining failures,
it also mines successes and patterns to suggest NEW automations.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASKS_FILE = PROJECT_ROOT / "var" / "logs" / "tasks.jsonl"
DEFAULT_WATCHER_CONFIG = PROJECT_ROOT / "config" / "watcher.json"
DEFAULT_SUGGESTIONS_DIR = PROJECT_ROOT / "gates" / "proposed_triggers"


# ---------------------------------------------------------- data loading


def _load_tasks(days: int = 30) -> list[dict[str, Any]]:
    """Load task records from the last N days. Returns [] on any error."""
    path = Path(os.environ.get("FRIDAY_TASKS_FILE", str(DEFAULT_TASKS_FILE)))
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
    except OSError:
        return []

    cutoff = datetime.now(UTC).timestamp() - (days * 86400)
    tasks: list[dict[str, Any]] = []
    for line in lines:
        try:
            rec = json.loads(line)
            ts = rec.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if dt.timestamp() < cutoff:
                        continue
                except (ValueError, AttributeError):
                    pass
            tasks.append(rec)
        except (json.JSONDecodeError, ValueError):
            continue
    return tasks


def _load_existing_triggers() -> list[dict[str, Any]]:
    """Load existing trigger configs to avoid duplicate suggestions."""
    path = Path(os.environ.get(
        "FRIDAY_WATCHER_CONFIG", str(DEFAULT_WATCHER_CONFIG)
    ))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("triggers", [])
    except (OSError, json.JSONDecodeError):
        return []


# -------------------------------------------------------- pattern mining


def _normalize_goal(goal: str) -> str:
    """Normalize a goal string for grouping: lowercase, strip whitespace,
    collapse whitespace, remove specific nouns that vary between runs."""
    g = goal.lower().strip()
    # Collapse whitespace
    g = re.sub(r"\s+", " ", g)
    # Remove common specific nouns that vary between runs
    g = re.sub(r"\b(my|the|a|an|some)\b", "", g)
    g = re.sub(r"\s+", " ", g).strip()
    return g


def _goal_signature(goal: str) -> str:
    """A coarse signature for grouping similar goals. Strips specifics
    like file names, email addresses, and timestamps."""
    g = _normalize_goal(goal)
    # Remove email-like patterns
    g = re.sub(r"\S+@\S+", "<email>", g)
    # Remove file paths
    g = re.sub(r"[/\\]\S+", "<path>", g)
    # Remove quoted strings
    g = re.sub(r'"[^"]*"', "<string>", g)
    g = re.sub(r"'[^']*'", "<string>", g)
    # Remove numbers
    g = re.sub(r"\b\d+\b", "<n>", g)
    return g


def mine_recurring_goals(
    tasks: list[dict[str, Any]],
    min_occurrences: int = 2,
    min_success_rate: float = 0.3,
) -> list[dict[str, Any]]:
    """Find goals that appear multiple times in the task history.

    Groups by normalized goal text and returns patterns that appear
    at least `min_occurrences` times with at least `min_success_rate`
    success rate. Returns a list of pattern dicts sorted by frequency.
    """
    # Group by signature
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in tasks:
        goal = t.get("goal", "")
        if not goal:
            continue
        sig = _goal_signature(goal)
        groups[sig].append(t)

    patterns: list[dict[str, Any]] = []
    for sig, records in groups.items():
        if len(records) < min_occurrences:
            continue

        successes = sum(1 for r in records if r.get("gate6_passed", False))
        success_rate = successes / len(records) if records else 0

        if success_rate < min_success_rate:
            continue

        # Extract the most common original goal text as the representative
        goal_texts = [r.get("goal", "") for r in records if r.get("goal")]
        goal_counter = Counter(goal_texts)
        representative = goal_counter.most_common(1)[0][0] if goal_texts else sig

        # Extract timestamps for frequency analysis
        timestamps: list[str] = []
        for r in records:
            ts = r.get("timestamp", "")
            if ts:
                timestamps.append(ts)

        patterns.append({
            "signature": sig,
            "representative_goal": representative,
            "occurrences": len(records),
            "successes": successes,
            "success_rate": round(success_rate, 2),
            "first_seen": min(timestamps) if timestamps else "",
            "last_seen": max(timestamps) if timestamps else "",
        })

    patterns.sort(key=lambda p: (-p["occurrences"], -p["success_rate"]))
    return patterns


# ----------------------------------------------- schedule suggestion


def _suggest_schedule(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze timestamps to suggest a schedule for a recurring goal.

    Returns a schedule dict like:
      {"type": "time", "at": "09:00", "days": ["mon", "tue", "wed", "thu", "fri"]}
    """
    if not records:
        return {"type": "time", "at": "09:00", "days": ["mon", "tue", "wed", "thu", "fri"]}

    # Extract hours and weekdays from timestamps
    hours: list[int] = []
    weekdays: list[int] = []
    for r in records:
        ts = r.get("timestamp", "")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            hours.append(dt.hour)
            weekdays.append(dt.weekday())
        except (ValueError, AttributeError):
            continue

    if not hours:
        return {"type": "time", "at": "09:00", "days": ["mon", "tue", "wed", "thu", "fri"]}

    # Most common hour
    hour_counter = Counter(hours)
    common_hour = hour_counter.most_common(1)[0][0]

    # Most common weekdays
    day_counter = Counter(weekdays)
    _WEEKDAY_NAMES = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
    common_days = [_WEEKDAY_NAMES[d] for d, _ in day_counter.most_common(5)]

    return {
        "type": "time",
        "at": f"{common_hour:02d}:00",
        "days": sorted(common_days),
    }


# ----------------------------------------------- trigger dedup


def _is_already_covered(
    goal: str,
    existing_triggers: list[dict[str, Any]],
) -> bool:
    """Check if a goal is already covered by an existing trigger.
    Uses substring containment and significant-token overlap."""
    goal_lower = goal.lower()
    goal_tokens = set(re.findall(r"\w+", goal_lower))

    for t in existing_triggers:
        trigger_goal = t.get("goal", "").lower()
        if not trigger_goal:
            continue
        # Exact or substring match
        if goal_lower in trigger_goal or trigger_goal in goal_lower:
            return True
        # Token overlap
        trigger_tokens = set(re.findall(r"\w+", trigger_goal))
        if not trigger_tokens:
            continue
        overlap = len(goal_tokens & trigger_tokens) / max(len(goal_tokens | trigger_tokens), 1)
        if overlap >= 0.5:
            return True

    return False


# --------------------------------------------------- public API


def generate_suggestions(
    days: int = 30,
    min_occurrences: int = 2,
    min_success_rate: float = 0.3,
) -> list[dict[str, Any]]:
    """Generate proactive trigger suggestions from task history.

    Returns a list of suggestion dicts, each containing:
      - goal: the goal text to automate
      - rationale: why this was suggested
      - occurrences: how many times it was run
      - success_rate: historical success rate
      - proposed_schedule: suggested trigger schedule
      - confidence: high/medium/low based on data quality
    """
    tasks = _load_tasks(days=days)
    if not tasks:
        return []

    existing = _load_existing_triggers()
    patterns = mine_recurring_goals(tasks, min_occurrences, min_success_rate)

    suggestions: list[dict[str, Any]] = []
    for p in patterns:
        # Skip if already covered by an existing trigger
        if _is_already_covered(p["representative_goal"], existing):
            continue

        # Determine confidence level
        occ = p["occurrences"]
        sr = p["success_rate"]
        if occ >= 5 and sr >= 0.7:
            confidence = "high"
        elif occ >= 3 and sr >= 0.5:
            confidence = "medium"
        else:
            confidence = "low"

        # Build rationale
        rationale_parts = [
            f"Goal ran {occ} times in the last {days} days",
            f"with {sr:.0%} success rate",
        ]
        if p["first_seen"] and p["last_seen"]:
            rationale_parts.append(
                f"(first: {p['first_seen'][:10]}, last: {p['last_seen'][:10]})"
            )

        # Find the actual task records for this pattern to suggest a schedule
        sig = p["signature"]
        matching_tasks = [
            t for t in tasks
            if _goal_signature(t.get("goal", "")) == sig
        ]
        schedule = _suggest_schedule(matching_tasks)

        suggestions.append({
            "goal": p["representative_goal"],
            "rationale": ". ".join(rationale_parts) + ".",
            "occurrences": occ,
            "success_rate": sr,
            "proposed_schedule": schedule,
            "confidence": confidence,
        })

    return suggestions


def write_proposals(suggestions: list[dict[str, Any]]) -> int:
    """Write suggestion proposals as inert trigger configs to
    gates/proposed_triggers/. Returns the number written."""
    if not suggestions:
        return 0

    out_dir = Path(os.environ.get(
        "FRIDAY_SUGGESTIONS_DIR", str(DEFAULT_SUGGESTIONS_DIR)
    ))
    out_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for s in suggestions:
        # Generate a safe directory name from the goal
        safe_name = re.sub(r"[^a-z0-9]+", "_", s["goal"].lower())[:60].strip("_")
        if not safe_name:
            safe_name = f"suggestion_{written}"
        proposal_dir = out_dir / safe_name

        # Skip if already proposed
        if (proposal_dir / "trigger.json").exists():
            continue

        proposal_dir.mkdir(parents=True, exist_ok=True)

        # Write inert trigger config
        trigger = {
            "id": f"suggested-{safe_name}",
            "goal": s["goal"],
            "schedule": s["proposed_schedule"],
            "enabled": False,
            "notify": True,
            "allow": [],
        }
        (proposal_dir / "trigger.json").write_text(
            json.dumps(trigger, indent=2) + "\n", encoding="utf-8"
        )

        # Write rationale
        rationale = (
            f"# Suggestion: {s['goal']}\n\n"
            f"**Confidence**: {s['confidence']}\n"
            f"**Occurrences**: {s['occurrences']} times\n"
            f"**Success rate**: {s['success_rate']:.0%}\n"
            f"**Proposed schedule**: {json.dumps(s['proposed_schedule'])}\n\n"
            f"## Why?\n\n{s['rationale']}\n\n"
            f"## To enable\n\n"
            f"1. Review the trigger config in `trigger.json`\n"
            f"2. Set `enabled: true`\n"
            f"3. Add appropriate `allow` list entries\n"
            f"4. Copy to `config/watcher.json`\n"
        )
        (proposal_dir / "README.md").write_text(rationale, encoding="utf-8")

        written += 1

    return written


# --------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Friday proactive suggestion engine")
    ap.add_argument("--days", type=int, default=30, help="Look back N days")
    ap.add_argument("--min-occurrences", type=int, default=2, help="Minimum times a goal must appear")
    ap.add_argument("--min-success-rate", type=float, default=0.3, help="Minimum success rate")
    ap.add_argument("--dry-run", action="store_true", help="Print suggestions without writing")
    ap.add_argument("--write", action="store_true", help="Write proposals to gates/proposed_triggers/")
    args = ap.parse_args(argv)

    suggestions = generate_suggestions(
        days=args.days,
        min_occurrences=args.min_occurrences,
        min_success_rate=args.min_success_rate,
    )

    if not suggestions:
        print("No suggestions found — task history is too thin or all patterns are already covered.")
        return

    print(f"Found {len(suggestions)} suggestion(s):\n")
    for i, s in enumerate(suggestions, 1):
        print(f"  {i}. [{s['confidence'].upper()}] {s['goal']}")
        print(f"     {s['rationale']}")
        print(f"     Schedule: {s['proposed_schedule']}")
        print()

    if args.write and not args.dry_run:
        written = write_proposals(suggestions)
        print(f"Wrote {written} proposal(s) to {DEFAULT_SUGGESTIONS_DIR}")
    elif not args.dry_run:
        print("Dry run — no files written. Use --write to save proposals.")


if __name__ == "__main__":
    main()
