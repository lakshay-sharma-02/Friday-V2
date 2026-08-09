#!/usr/bin/env python
"""Gate 4 - L3 executor proof.

DoD (master plan): a hardcoded plan - zero LLM involved - runs under the
L3 state machine and every step reaches VERIFIED, shown as raw L0 log
output. Also proves the FAILED -> RETRY -> ABORT path with a deliberately
failing plan.

Run:  ./.venv/bin/python -u gates/gate4_proof.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.errors import FridayError  # noqa: E402
from friday.l3 import executor  # noqa: E402

PLANS = ROOT / "gates" / "plans"


def dump_trace(run_id: str, label: str) -> None:
    log = ROOT / "var" / "logs" / "friday.jsonl"
    lines = [
        json.loads(l) for l in log.read_text().splitlines()
        if json.loads(l).get("run_id") == run_id
    ]
    print(f"\n=== L0 trace: {label} ({len(lines)} lines, run_id={run_id}) ===")
    for rec in lines:
        # Show BOTH the state-transition result and any exception text -
        # hiding the result when an exception exists would make
        # RETRY_EXHAUSTED / ABORT invisible in the DoD artifact.
        outcome = rec["result"] if rec["result"] is not None else "None"
        if rec["exception"] is not None:
            outcome = f"{outcome} EXC: {rec['exception']}"
        extra = f" extra={rec['extra']}" if rec.get("extra") else ""
        print(
            f"[{rec['timestamp']}] {rec['layer']} step={rec['step_id']} {rec['primitive']:28s} "
            f"-> {outcome}{extra}"
        )


def run_plan(label: str, plan_file: str, run_id: str) -> None:
    print("\n" + "=" * 72)
    print(f"PLAN: {label} ({plan_file})")
    print("=" * 72)
    plan = executor.load_plan(PLANS / plan_file)
    print(f"goal: {plan['goal']}")
    print(f"steps: {len(plan['steps'])}")
    try:
        result = executor.run_plan(plan, run_id=run_id)
        print(f"plan status: {result.status}")
        for sr in result.steps:
            print(
                f"  step {sr.step_id}: {sr.primitive:24s} {sr.status:12s} "
                f"attempts={sr.attempts} verify_actual={sr.verify_actual!r}"
            )
    except FridayError as exc:
        print(f"plan status: ABORTED -> {exc}")
    dump_trace(run_id, label)


def main() -> None:
    run_plan("happy path (all steps VERIFIED)", "hardcoded_gate4.json", "gate4-happy")
    run_plan("failing path (RETRY -> ABORT)", "failing_gate4.json", "gate4-fail")
    print("\nGATE 4: DONE (run the two traces above; happy path must show VERIFIED on every step)")


if __name__ == "__main__":
    main()
