#!/usr/bin/env python
"""LIVE end-to-end check of Friday on this machine - not unit tests.

Runs the REAL stack end to end, exactly as the watcher would: three goals
are planned by a LIVE LLM call (L4), executed by the UNMODIFIED executor
(L3), verified by real L2 checks against real state, traced through the
real L0 log, recorded in the gate-6 tasks.jsonl format, and the outcome is
pinged to the desktop.

The three goals are read-only, or a no-op when nothing is playing (no
messages are sent, no windows are opened or closed, nothing plays):
  A. files:  find README.md in the project, report its absolute path
  B. window: verify a kitty terminal is open (real compositor state)
  C. media:  pause any playing audio (mutates state ONLY if a player is
             running - pausing is the goal's stated intent)

Defense in depth: a plan whose primitives fall outside the read-only
allowlist is REFUSED before execution and reported as a FAIL - an LLM that
hallucinates a side-effecting primitive must never act on it during a live
check.

Known flake: the windows goal's PASS depends on the LLM choosing the
boolean checks.window_has_class verify. If a run instead emits a count
verify (checks.window_client_count expect N) with a wrong N, the executor
honestly ABORTs and the goal FAILs - that is Friday catching a bad plan,
not a broken check; rerun to get a fresh plan.

Run:  ./.venv/bin/python -u gates/e2e_check.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.errors import FridayError  # noqa: E402
from friday.l1.notify import notify_send  # noqa: E402
from friday.l3 import executor  # noqa: E402
from friday.l4 import planner  # noqa: E402

# One run_id label per invocation, so L0 traces in the proof are cleanly
# scoped to this run even though the log accumulates across runs.
LABEL = f"e2e-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
LOG_FILE = ROOT / "var" / "logs" / "friday.jsonl"
TASKS_FILE = ROOT / "var" / "logs" / "tasks.jsonl"
PROOF = ROOT / "gates" / "E2E_PROOF.md"

# Every primitive an LLM plan is allowed to contain during this live check.
# Anything else (send_*, open_app, close_*, play_for, dev.run_shell, ...) is
# refused - the check must be able to run unattended without side effects.
ALLOWED_PRIMS = {
    "files.find_file",
    "window.list_clients",
    "window.get_active_window",
    "media.pause",
    "media.is_playing",
}

GOALS: list[tuple[str, str]] = [
    ("files", "find the file named README.md in this project and report its absolute path"),
    # A BOOLEAN claim ('verify that a kitty window is open') - phrased so the
    # LLM verifies via checks.window_has_class instead of guessing an exact
    # window count it cannot know (a first run showed the model emitting
    # checks.window_client_count expect 1 against a 3-window desktop; Friday
    # mechanically caught it and ABORTed with no side effects).
    ("windows", "verify that a terminal window with window class 'kitty' is currently open, and report the classes of the open windows"),
    ("media", "pause any playing audio"),
]

_lines: list[str] = []


def out(s: str = "") -> None:
    print(s)
    _lines.append(s)


# ------------------------------------------------------------- trace dump


def dump(run_id: str, label: str) -> None:
    lines = [
        json.loads(l) for l in LOG_FILE.read_text().splitlines()
        if json.loads(l).get("run_id") == run_id
    ]
    out(f"\n=== L0 trace: {label} ({len(lines)} lines, run_id={run_id}) ===")
    for rec in lines:
        outcome = rec["result"] if rec["result"] is not None else "None"
        if rec["exception"] is not None:
            outcome = f"{outcome} EXC: {rec['exception']}"
        extra = f" extra={rec['extra']}" if rec.get("extra") else ""
        shown = str(outcome)
        if len(shown) > 220:
            shown = shown[:220] + "..."
        out(
            f"[{rec['timestamp']}] {rec['layer']} step={rec['step_id']} "
            f"{rec['primitive']:28s} -> {shown}{extra}"
        )


def record(goal_id: str, goal: str, ok: bool, detail: dict[str, Any]) -> None:
    """One line in the gate-6 tasks.jsonl format (same shape the watcher
    writes for watch:<id> runs)."""
    rec = {
        "task_id": f"e2e:{goal_id}",
        "goal": goal,
        "gate6_passed": ok,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "proof": json.dumps(detail, ensure_ascii=False),
    }
    TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TASKS_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    out(f"[tasks.jsonl] appended e2e:{goal_id} gate6_passed={ok}")


# ------------------------------------------------------------------- goals


def run_goal(goal_id: str, goal: str, n: int, problems: list[str]) -> None:
    out("\n" + "=" * 72)
    out(f"GOAL {n} - {goal_id}: {goal!r}")
    out("=" * 72)

    out("\n--- L4: live LLM planning ---")
    try:
        llm_plan = planner.plan(goal, run_id=f"{LABEL}-g{n}-plan")
    except Exception as exc:
        out(f"L4 FAILED: {type(exc).__name__}: {exc}")
        problems.append(f"goal {n}: LLM planning failed ({type(exc).__name__})")
        record(goal_id, goal, False, {"status": "PLAN_FAILED", "error": str(exc)[:500]})
        return
    out("plan JSON returned by the LLM:")
    out(json.dumps(llm_plan, indent=2))

    prims = [s.get("primitive") for s in llm_plan.get("steps", [])]
    forbidden = [p for p in prims if p not in ALLOWED_PRIMS]
    if forbidden:
        out(f"\nREFUSED: plan wants side-effecting primitive(s) {forbidden} "
            f"- not in the read-only allowlist; NOT executed.")
        problems.append(f"goal {n}: plan refused (non-read-only primitives {forbidden})")
        record(goal_id, goal, False, {"status": "REFUSED", "primitives": prims})
        return

    out("\n--- L3: executor runs the LLM plan ---")
    try:
        result = executor.run_plan(llm_plan, run_id=f"{LABEL}-g{n}-exec")
        out(f"plan status: {result.status}")
        for sr in result.steps:
            out(
                f"  step {sr.step_id}: {sr.primitive:24s} {sr.status:12s} "
                f"attempts={sr.attempts} verify_actual={sr.verify_actual!r}"
            )
    except FridayError as exc:
        out(f"plan status: ABORTED -> {exc}")
        result = None
    except Exception as exc:  # never mask a raw internal failure
        out(f"plan status: RAISED {type(exc).__name__}: {exc}")
        result = None

    dump(f"{LABEL}-g{n}-plan", f"L4 planning goal {n}")
    dump(f"{LABEL}-g{n}-exec", f"execution goal {n}")

    ok = result is not None and result.status == "COMPLETED" \
        and all(s.status == "VERIFIED" for s in result.steps)
    if not ok:
        problems.append(f"goal {n}: not every step VERIFIED (status={getattr(result, 'status', None)})")
    detail = {
        "goal_id": goal_id,
        "status": getattr(result, "status", "ABORT") if result is not None else "ABORT",
        "primitives": prims,
        "steps": [
            {"step_id": s.step_id, "primitive": s.primitive, "status": s.status, "attempts": s.attempts}
            for s in (result.steps if result else [])
        ],
    }
    record(goal_id, goal, ok, detail)
    out(f"GOAL {n}: {'PASS' if ok else 'FAIL'}")


# ------------------------------------------------------------------- main


def main() -> None:
    out("=" * 72)
    out("FRIDAY E2E - live end-to-end check on this machine (not unit tests)")
    out("=" * 72)
    out(f"date: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    out(f"compositor: Hyprland via hyprctl (live)   claude CLI: live LLM planning")
    out(f"allowlist (read-only primitives only): {sorted(ALLOWED_PRIMS)}")
    out(f"tasks file: {TASKS_FILE}")

    problems: list[str] = []
    for n, (goal_id, goal) in enumerate(GOALS, start=1):
        run_goal(goal_id, goal, n, problems)

    ok = not problems
    out("\n" + "=" * 72)
    out("=== E2E VERDICT ===")
    for p in problems:
        out(f"  FAIL: {p}")
    if ok:
        out("  OK: all goals COMPLETED with every step VERIFIED, from live LLM plans")
    out("=" * 72)

    # best-effort desktop ping (a missing daemon must not fail the check)
    try:
        notify_send(
            title=f"Friday E2E: {'PASS' if ok else 'FAIL'} ({len(GOALS) - len(problems)}/{len(GOALS)} goals)",
            body=f"problems: {problems or 'none'}",
        )
        out("[notify] desktop notification sent")
    except Exception as exc:
        out(f"[notify] skipped (no daemon): {exc}")

    PROOF.write_text(
        "# E2E_PROOF — live end-to-end check of Friday\n\n"
        "Status date: " + datetime.now(timezone.utc).isoformat(timespec="seconds") + ".\n\n"
        "A LIVE run on this machine - not unit tests. Three goals were planned by a real LLM call\n"
        "(L4), executed by the unmodified executor (L3), verified by real L2 checks, traced through\n"
        "the real L0 log, recorded in the gate-6 tasks.jsonl format, and pinged to the desktop.\n"
        "All goals are read-only, or a no-op when nothing is playing; plans containing any\n"
        "side-effecting primitive were mechanically refused by an allowlist before execution.\n\n"
        f"## Verdict: {'PASS' if ok else 'FAIL'}\n\n"
        "## Raw output\n\n```\n" + "\n".join(_lines) + "\n```\n",
        encoding="utf-8",
    )
    out(f"\nproof written to {PROOF.relative_to(ROOT)}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
