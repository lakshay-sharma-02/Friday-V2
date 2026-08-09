#!/usr/bin/env python
"""Live demo that the LLM planning calls work: a fresh, harmless goal is
planned by the LLM and executed through the same L3 executor end-to-end.

Goal: "pause any playing audio" - media.pause is commutative-safe and a
no-op when nothing is playing, so this run has zero side effects. The
verify (media is not playing) holds regardless of prior state.

Run:  ./.venv/bin/python -u gates/llm_demo.py
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

GOAL = "pause any playing audio"


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
            f"[{rec['timestamp']}] {rec['layer']} step={rec['step_id']} {rec['primitive']:26s} "
            f"-> {outcome}{extra}"
        )


def main() -> None:
    print("=" * 72)
    print("LIVE LLM DEMO - do the LLM planning calls work?")
    print("=" * 72)
    print(f"GOAL: {GOAL!r}")

    print("\n--- L4: LLM planning ---")
    llm_plan = planner.plan(GOAL, run_id="llm-demo")
    print("LLM-produced plan JSON:")
    print(json.dumps(llm_plan, indent=2))
    print(f"steps: {len(llm_plan['steps'])}")

    print("\n--- L3: executor runs the LLM plan ---")
    try:
        result = executor.run_plan(llm_plan, run_id="llm-demo-exec")
        print(f"plan status: {result.status}")
        for sr in result.steps:
            print(
                f"  step {sr.step_id}: {sr.primitive:22s} {sr.status:12s} "
                f"attempts={sr.attempts} verify_actual={sr.verify_actual!r}"
            )
    except FridayError as exc:
        print(f"plan status: ABORTED -> {exc}")

    dump("llm-demo", "L4 planning")
    dump("llm-demo-exec", "execution")

    ok = result.status == "COMPLETED" and all(s.status == "VERIFIED" for s in result.steps)
    print(f"\nDEMO: {'OK - LLM calls work end-to-end' if ok else 'FAILED'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
