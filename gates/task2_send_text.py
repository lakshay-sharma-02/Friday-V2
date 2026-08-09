#!/usr/bin/env python
"""Task 2 (Gate-6-grade proof) - send_text on all three platforms.

GOAL: "send the text message 'friday send_text proof' to my WhatsApp,
      Telegram and Discord"
      (LLM-planned, executed by L3, verified by L2, logged through L0)

First full-stack proof of the TEXT path (Gate 6 proved only document
sends): the LLM plan emits one whatsapp.send_text, telegram.send_text and
discord.send_text step; each is verified via checks.message_sent on that
step's OWN returned message id. Recipients come from configured
credentials / $facts refs - no recipient is hardcoded in the goal.

This sends three REAL text messages to the configured recipients.

Run:  ./.venv/bin/python -u gates/task2_send_text.py
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

GOAL = "send the text message 'friday send_text proof' to my WhatsApp, Telegram and Discord"


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
    print("TASK 2 - send_text on WhatsApp + Telegram + Discord")
    print("=" * 72)
    print(f"GOAL: {GOAL!r}")

    print("\n--- L4: LLM planning ---")
    llm_plan = planner.plan(GOAL, run_id="task2-text-plan")
    print("LLM-produced plan JSON:")
    print(json.dumps(llm_plan, indent=2))

    print("\n--- L3: executor runs the LLM plan (real sends) ---")
    all_verified = False
    try:
        result = executor.run_plan(llm_plan, run_id="task2-text-exec")
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

    dump("task2-text-plan", "L4 planning")
    dump("task2-text-exec", "execution (real sends)")

    print(f"\nTASK 2: {'DONE' if all_verified else 'FAILED'} "
          f"(goal -> LLM plan -> executor -> verified; message ids in trace above)")
    sys.exit(0 if all_verified else 1)


if __name__ == "__main__":
    main()
