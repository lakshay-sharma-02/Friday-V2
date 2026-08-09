#!/usr/bin/env python
"""Gate 5 - L4 planning proof.

DoD (master plan): feed the IDENTICAL goal used in Gate 4 to the LLM
planner; the LLM-produced plan must run through the SAME L3 executor to the
same verified outcome (every step VERIFIED). Any deviation from the
hardcoded plan is printed for explanation, not swept under.

Sequence:
  1. Read the Gate 4 hardcoded plan; take its goal string verbatim.
  2. planner.plan(goal) -> LLM-produced plan JSON (schema the executor
     consumes unmodified).
  3. Run the hardcoded plan through the executor (baseline).
  4. Run the LLM plan through the SAME executor.
  5. Dump all three L0 traces raw; print a deviation report.

Run:  ./.venv/bin/python -u gates/gate5_proof.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.errors import FridayError  # noqa: E402
from friday.l3 import executor  # noqa: E402
from friday.l4 import planner  # noqa: E402

PLANS = ROOT / "gates" / "plans"


def dump_trace(run_id: str, label: str) -> None:
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
            f"[{rec['timestamp']}] {rec['layer']} step={rec['step_id']} {rec['primitive']:28s} "
            f"-> {outcome}{extra}"
        )


def run_plan(label: str, plan: dict, run_id: str) -> bool:
    """Run a plan through the executor; return True if every step VERIFIED."""
    print(f"\n--- {label} ---")
    print(f"goal: {plan['goal']}")
    print(f"steps: {len(plan['steps'])}")
    all_verified = True
    try:
        result = executor.run_plan(plan, run_id=run_id)
        print(f"plan status: {result.status}")
        for sr in result.steps:
            print(
                f"  step {sr.step_id}: {sr.primitive:24s} {sr.status:12s} "
                f"attempts={sr.attempts} verify_actual={sr.verify_actual!r}"
            )
            all_verified &= sr.status == "VERIFIED"
    except FridayError as exc:
        print(f"plan status: ABORTED -> {exc}")
        all_verified = False
    return all_verified


def main() -> None:
    baseline = executor.load_plan(PLANS / "hardcoded_gate4.json")
    goal = str(baseline["goal"])
    print("=" * 72)
    print("GATE 5 - L4 planning proof")
    print("=" * 72)
    print(f"GOAL (identical string to Gate 4): {goal!r}")

    # 1. LLM planning (run_id set here so the L4 trace is its own run)
    print("\n=== L4 planning (LLM) ===")
    llm_plan = planner.plan(goal, run_id="gate5-plan")
    print("LLM-produced plan JSON:")
    print(json.dumps(llm_plan, indent=2))

    # 2 + 3. both plans through the SAME executor
    baseline_ok = run_plan("baseline (hardcoded) plan", baseline, "gate5-baseline")
    llm_ok = run_plan("LLM plan", llm_plan, "gate5-llm")

    # 4. deviation report
    print("\n=== deviation: baseline vs LLM plan ===")
    n = max(len(baseline["steps"]), len(llm_plan["steps"]))
    print(f"{'#':>2}  {'baseline primitive':24s} {'LLM primitive':24s} {'baseline verify':24s} {'LLM verify':24s}")
    for i in range(n):
        b = baseline["steps"][i] if i < len(baseline["steps"]) else {}
        l = llm_plan["steps"][i] if i < len(llm_plan["steps"]) else {}
        bp = b.get("primitive", "-")
        lp = l.get("primitive", "-")
        bv = (b.get("verify") or {}).get("check", "-")
        lv = (l.get("verify") or {}).get("check", "-")
        flag = "  (same)" if bp == lp and bv == lv else ""
        print(f"{i + 1:>2}  {bp:24s} {lp:24s} {bv:24s} {lv:24s}{flag}")

    dump_trace("gate5-plan", "L4 planning")
    dump_trace("gate5-baseline", "baseline execution")
    dump_trace("gate5-llm", "LLM plan execution")

    if baseline_ok and llm_ok:
        print("\nGATE 5: DONE (identical goal -> LLM plan -> same executor -> all steps VERIFIED)")
        sys.exit(0)
    print("\nGATE 5: FAILED (see traces above)")
    sys.exit(1)


if __name__ == "__main__":
    main()
