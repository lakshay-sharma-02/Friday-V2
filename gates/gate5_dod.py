#!/usr/bin/env python
"""Gate 5 DoD re-verification against the EXISTING L4 pipeline (no rebuild).

The Gate 5 prompt's DoD has an anti-cheese requirement: it must be
provable that a plan came from a live LLM call, not a lookup keyed on the
goal string. So TWO goals run through the SAME unmodified pipeline:

  1. GOAL1 - the identical goal string from Gate 4's hardcoded plan
     (gates/plans/hardcoded_gate4.json). Deviations from the hardcoded
     composition must be explainable, not just present.
  2. GOAL2 - a goal string that has never appeared anywhere in this
     codebase or any prior conversation, exercising at least one primitive
     Gate 4 never touched (browser.goto / browser.read_page_text - Gate 4
     used only window.open_app, window.close_window, media.play_for,
     media.stop).

For each goal, raw and unmodified:
  - the exact prompt handed to the LLM (planner.build_prompt is what
    planner.plan() calls on attempt 1, so it IS the context the model saw),
  - the raw plan JSON the LLM returned (planner.plan output),
  - the raw L0 log from the UNMODIFIED executor (run_plan), PENDING through
    every step's VERIFIED to plan COMPLETED.
  If a goal fails, the raw failure is printed - no silent retries.

Anti-cheese is also checked mechanically: each goal's L4 trace must contain
the layer=L4 plan.attempt lines (the live dev.run LLM call is L0-logged),
and GOAL2's plan must contain a primitive outside Gate 4's set.

Safety (unattended): preflight refuses if firefox is already open (GOAL1
opens firefox); leftover test window cleanup is address-aware (only the
exact window the plan's open_app returned, read from the trace); media.stop
and browser.close always run in finally. The user's windows are untouched.

Run:  ./.venv/bin/python -u gates/gate5_dod.py [run_label]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.errors import FridayError  # noqa: E402
from friday.l1 import browser, media, window  # noqa: E402
from friday.l3 import executor  # noqa: E402
from friday.l4 import planner  # noqa: E402
from friday.observability import set_run_id  # noqa: E402

RUN_LABEL = sys.argv[1] if len(sys.argv) > 1 else "gate5-dod"

GOAL1 = (
    "open firefox, verify it appears, close it, verify it is gone, play "
    "the test tone briefly, verify it started, stop it, verify it stopped"
)
GOAL2 = (
    "open the Wikipedia article about the Saturn V rocket in the browser, "
    "verify the page shows 'Saturn V', and report the page's text"
)

# primitives Gate 4's hardcoded plan touched (from hardcoded_gate4.json)
GATE4_PRIMS = {"window.open_app", "window.close_window", "media.play_for", "media.stop"}
# primitives GOAL2 must exercise that Gate 4 never touched
GOAL2_MUST_USE = ("browser.goto", "browser.read_page_text")


def dump(run_id: str, label: str) -> None:
    log = ROOT / "var" / "logs" / "friday.jsonl"
    lines = [
        json.loads(l) for l in log.read_text().splitlines()
        if json.loads(l).get("run_id") == run_id
    ]
    print(f"\n=== L0 trace: {label} ({len(lines)} lines, run_id={run_id}) ===")
    for rec in lines:
        outcome = rec["result"] if rec["result"] is not None else "None"
        if rec["exception"] is not None:
            outcome = f"{outcome} EXC: {rec['exception']}"
        extra = f" extra={rec['extra']}" if rec.get("extra") else ""
        print(
            f"[{rec['timestamp']}] {rec['layer']} step={rec['step_id']} {rec['primitive']:30s} "
            f"-> {str(outcome)[:160]}{extra}"
        )


def run_goal(goal: str, label: str, n: int, problems: list[str]) -> None:
    print("\n" + "=" * 72)
    print(f"GOAL {n} - {label}")
    print("=" * 72)
    print(f"GOAL STRING: {goal!r}")

    # the exact prompt planner.plan() hands the LLM on attempt 1
    prompt = planner.build_prompt(goal)
    prompt_path = Path(f"/tmp/gate5_prompt_{n}.txt")
    prompt_path.write_text(prompt)
    print(f"\n--- PROMPT HANDED TO THE LLM (full, also at {prompt_path}) ---")
    print(prompt)

    print(f"\n--- L4: LLM plan for goal {n} ---")
    llm_plan = planner.plan(goal, run_id=f"{RUN_LABEL}-g{n}-plan")
    print("RAW PLAN JSON RETURNED BY THE LLM:")
    print(json.dumps(llm_plan, indent=2))

    print(f"\n--- L3: unmodified executor runs the plan (goal {n}) ---")
    result: executor.PlanResult | None = None
    try:
        result = executor.run_plan(llm_plan, run_id=f"{RUN_LABEL}-g{n}-exec")
        print(f"plan status: {result.status}")
        for sr in result.steps:
            print(
                f"  step {sr.step_id}: {sr.primitive:26s} {sr.status:12s} "
                f"attempts={sr.attempts} verify_actual={sr.verify_actual!r}"
            )
    except FridayError as exc:
        print(f"plan status: ABORTED -> {exc}")
    except Exception as exc:  # never mask a raw internal failure
        print(f"plan status: RAISED {type(exc).__name__}: {exc}")

    dump(f"{RUN_LABEL}-g{n}-plan", f"L4 planning goal {n}")
    dump(f"{RUN_LABEL}-g{n}-exec", f"execution goal {n}")

    # --- DoD checks ---
    prims = [s["primitive"] for s in llm_plan["steps"]]
    if result is None:
        problems.append(f"goal {n}: executor ABORTed before completing")
    elif result.status != "COMPLETED" or not all(s.status == "VERIFIED" for s in result.steps):
        problems.append(f"goal {n}: not every step VERIFIED (status={result.status})")

    # anti-cheese: the L4 trace must show the live LLM call lines
    log = ROOT / "var" / "logs" / "friday.jsonl"
    plan_lines = [
        json.loads(l) for l in log.read_text().splitlines()
        if json.loads(l).get("run_id") == f"{RUN_LABEL}-g{n}-plan"
    ]
    l4_attempts = [r for r in plan_lines if r["layer"] == "L4" and "plan.attempt" in r["primitive"]]
    if not l4_attempts:
        problems.append(f"goal {n}: no L4 plan.attempt lines - plan may not have come from a live LLM call")
    l4_accept = [r for r in plan_lines if r["layer"] == "L4" and r["primitive"] == "plan" and r["result"] == "ACCEPTED"]
    if not l4_accept:
        problems.append(f"goal {n}: no L4 plan ACCEPTED line")

    if n == 1:
        # deviations vs the hardcoded Gate 4 plan must be explainable: list them
        hardcoded = ["window.open_app", "window.close_window", "media.play_for", "media.stop"]
        missing = [p for p in hardcoded if p not in prims]
        extra = [p for p in prims if p not in hardcoded]
        print(f"\n[goal 1 deviation report] hardcoded={hardcoded}")
        print(f"[goal 1 deviation report] LLM plan prims={prims}")
        if missing:
            print(f"[goal 1 deviation report] MISSING vs hardcoded: {missing}")
        if extra:
            print(f"[goal 1 deviation report] EXTRA vs hardcoded: {extra}")
    else:
        if not any(p in prims for p in GOAL2_MUST_USE):
            problems.append(f"goal 2: plan never used a Gate-4-untouched primitive ({GOAL2_MUST_USE})")
        overlap = set(prims) & GATE4_PRIMS
        print(f"[goal 2] plan primitives: {prims}")
        print(f"[goal 2] overlap with Gate-4-touched primitives: {sorted(overlap) or 'none'}")


def main() -> None:
    print("=" * 72)
    print("GATE 5 DoD - two-goal anti-cheese run against the EXISTING L4 pipeline")
    print("=" * 72)
    set_run_id(RUN_LABEL)

    # safety preflight: GOAL1 opens firefox - refuse if one is already open
    if any("firefox" in str(c.get("class", "")).lower() for c in window.list_clients()):
        print("\nREFUSING TO RUN: firefox is already open (GOAL1 needs it as a test window).")
        sys.exit(2)

    problems: list[str] = []
    try:
        run_goal(GOAL1, "the identical Gate 4 goal", 1, problems)
        run_goal(GOAL2, "a never-before-seen goal (Saturn V Wikipedia)", 2, problems)
    finally:
        # hygiene: stop media, close a leftover test window (address-aware),
        # close the browser - never leave anything running
        try:
            media.stop()
        except Exception:
            pass
        log = ROOT / "var" / "logs" / "friday.jsonl"
        opened = None
        for l in log.read_text().splitlines():
            rec = json.loads(l)
            if rec.get("run_id") == f"{RUN_LABEL}-g1-exec" and rec["layer"] == "L1" \
                    and rec["primitive"] == "window.open_app" and isinstance(rec.get("result"), dict):
                opened = rec["result"].get("address")
                break
        for c in window.list_clients():
            if "firefox" in str(c.get("class", "")).lower():
                addr = str(c["address"])
                if opened is not None and addr == opened:
                    try:
                        window.close_window(addr)
                        print(f"[cleanup] closed leftover test window {addr}")
                    except Exception as exc:
                        print(f"[cleanup] could not close {addr}: {exc}")
                else:
                    print(f"[cleanup] REFUSING to close firefox client {addr} "
                          f"(plan opened {opened}) - not ours, leaving it")
        browser.close()

    print("\n=== GATE 5 DoD ===")
    for p in problems:
        print(f"  FAIL: {p}")
    if not problems:
        print("  OK: both goals: every step VERIFIED, plans came from live LLM calls (L4 lines in trace),")
        print("      goal 1 deviations vs hardcoded (if any) reported above, goal 2 used a Gate-4-untouched primitive")
    ok = not problems
    print(f"\nGATE 5 DoD: {'DONE' if ok else 'FAILED'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
