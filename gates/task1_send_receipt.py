#!/usr/bin/env python
"""Task 1 (Gate-6-grade proof) - described-file send.

GOAL: "send the receipt pdf from my downloads to my whatsapp"
      (LLM-planned, executed by L3, verified by L2, logged through L0)

First live proof of the files.find_file -> $steps.N.result.path ->
messaging composition, plus $facts.downloads directory resolution:
  1. L4 LLM plans the goal: files.find_file locates the file by
     DESCRIPTION (no exact filename in the goal), the send step
     references the found path.
  2. The L3 executor runs it; the find step is verified via
     checks.file_exists on its OWN result, the send via
     checks.message_sent on its own returned message id.
  3. The raw L0 trace shows the found path and the fresh wamid.

Requires a file matching 'receipt' in ~/Downloads (the fixture
friday_demo_receipt.pdf is used when present). This sends ONE real
WhatsApp message to the configured default phone.

Run:  ./.venv/bin/python -u gates/task1_send_receipt.py
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

GOAL = "send the receipt pdf from my downloads to my whatsapp"


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
    print("TASK 1 - described-file send: find_file + $facts + messaging")
    print("=" * 72)
    print(f"GOAL: {GOAL!r}")

    print("\n--- L4: LLM planning ---")
    llm_plan = planner.plan(GOAL, run_id="task1-receipt-plan")
    print("LLM-produced plan JSON:")
    print(json.dumps(llm_plan, indent=2))

    print("\n--- L3: executor runs the LLM plan (real send) ---")
    all_verified = False
    try:
        result = executor.run_plan(llm_plan, run_id="task1-receipt-exec")
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

    dump("task1-receipt-plan", "L4 planning")
    dump("task1-receipt-exec", "execution (real send)")

    print(f"\nTASK 1: {'DONE' if all_verified else 'FAILED'} "
          f"(goal -> LLM plan -> find_file -> send -> verified; wamid in trace above)")
    sys.exit(0 if all_verified else 1)


if __name__ == "__main__":
    main()
