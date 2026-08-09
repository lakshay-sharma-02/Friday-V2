#!/usr/bin/env python
"""Gate 6 - first real composite task through the full stack.

GOAL: "send the README.md file to my WhatsApp, Telegram and Discord"
      (LLM-planned, executed by L3, verified by L2, logged through L0)

DoD: goal-string-in -> real-world-effect-out, shown raw start to finish:
  1. L4 LLM plans the goal into executor-consumable JSON.
  2. The L3 executor runs it; every step VERIFIED (each send's returned
     message id asserted via checks.message_sent and the step's own result).
  3. The raw L0 trace shows real message ids from all three platforms:
     WhatsApp wamid, Telegram id, Discord snowflake.

This sends REAL messages to the configured recipients (WhatsApp default
phone, Telegram chat, Discord channel from credentials).

Run:  ./.venv/bin/python -u gates/gate6_send_all.py
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

GOAL = "send the README.md file to my WhatsApp, Telegram and Discord"


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
    print("GATE 6 - composite task: send README to WhatsApp + Telegram + Discord")
    print("=" * 72)
    print(f"GOAL: {GOAL!r}")

    print("\n--- L4: LLM planning ---")
    llm_plan = planner.plan(GOAL, run_id="gate6-plan")
    print("LLM-produced plan JSON:")
    print(json.dumps(llm_plan, indent=2))

    print("\n--- L3: executor runs the LLM plan (real sends) ---")
    all_verified = False
    try:
        result = executor.run_plan(llm_plan, run_id="gate6-exec")
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

    dump("gate6-plan", "L4 planning")
    dump("gate6-exec", "execution (real sends)")

    print(f"\nGATE 6: {'DONE' if all_verified else 'FAILED'} "
          f"(goal -> LLM plan -> executor -> verified; message ids in trace above)")
    sys.exit(0 if all_verified else 1)


if __name__ == "__main__":
    main()
