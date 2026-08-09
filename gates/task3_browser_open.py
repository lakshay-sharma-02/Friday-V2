#!/usr/bin/env python
"""Task 3 (Gate-6-grade proof) - first full-stack browser task.

GOAL: "open example.com in the browser and verify it loaded"
      (LLM-planned, executed by L3, verified by L2, logged through L0)

The browser primitive was proven standalone at Gate 1 and read-only at
Gate 3, but has never gone through LLM planning -> executor -> verify.
This is that first pass: the LLM plan emits browser.goto(url) and the
verify asserts the real page state via checks.browser_has_text (read-only,
DOM-based - no screenshots). Zero auth ambiguity, minimal moving parts.

Side effects: launches a real (visible) Playwright chromium window and
navigates to https://example.com. The browser is left open after the plan
completes (the goal does not ask to close it).

Run:  ./.venv/bin/python -u gates/task3_browser_open.py
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

GOAL = "open example.com in the browser and verify it shows 'Example Domain'"

# Optional argv[1] labels the run so re-runs get fresh run_ids (L0 traces
# accumulate in one log file; reusing a run_id would mix attempts).
RUN_LABEL = sys.argv[1] if len(sys.argv) > 1 else "task3-browser"


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
            f"-> {outcome}{extra}"
        )


def main() -> None:
    print("=" * 72)
    print("TASK 3 - first full-stack browser task: open + verify example.com")
    print("=" * 72)
    print(f"GOAL: {GOAL!r}")

    print("\n--- L4: LLM planning ---")
    llm_plan = planner.plan(GOAL, run_id=f"{RUN_LABEL}-plan")
    print("LLM-produced plan JSON:")
    print(json.dumps(llm_plan, indent=2))

    print("\n--- L3: executor runs the LLM plan (real browser) ---")
    all_verified = False
    try:
        result = executor.run_plan(llm_plan, run_id=f"{RUN_LABEL}-exec")
        print(f"plan status: {result.status}")
        for sr in result.steps:
            print(
                f"  step {sr.step_id}: {sr.primitive:26s} {sr.status:12s} "
                f"attempts={sr.attempts} verify_actual={sr.verify_actual!r}"
            )
        all_verified = result.status == "COMPLETED" and all(
            s.status == "VERIFIED" for s in result.steps
        )
    except FridayError as exc:
        print(f"plan status: ABORTED -> {exc}")

    dump(f"{RUN_LABEL}-plan", "L4 planning")
    dump(f"{RUN_LABEL}-exec", "execution (real browser)")

    print(f"\nTASK 3: {'DONE' if all_verified else 'FAILED'} "
          f"(goal -> LLM plan -> browser -> verified; trace above)")
    sys.exit(0 if all_verified else 1)


if __name__ == "__main__":
    main()
