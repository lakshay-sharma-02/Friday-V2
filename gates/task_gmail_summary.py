#!/usr/bin/env python
"""Task #10 (Phase 2) - Gmail unread-email summary, full pipeline.

GOAL: "find the most recent unread email from <sender> and summarize it"
      (LLM-planned, executed by L3, verified by L2, logged through L0)

Discipline, same as every prior task:
  - goal string in -> L4 LLM plan -> L3 executor -> L2 verify -> L0 log,
    unmodified pipeline, zero scaffolding.
  - verification STRONGER than absence-of-exception: the fetched-message
    step is verified by checks.gmail_message_matches on its OWN message_id
    (proves the email is actually from the expected sender), and the
    summary text itself is printed raw as the human-verifiable deliverable.
  - read-only end to end: gmail.readonly scope, nothing marked read.

Run:  ./.venv/bin/python -u gates/task_gmail_summary.py <sender>
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.errors import FridayError  # noqa: E402
from friday.l3 import executor  # noqa: E402
from friday.l4 import planner  # noqa: E402

TASK_ID = "gmail-summary"
SENDER = sys.argv[1] if len(sys.argv) > 1 else ""
GOAL = f"find the most recent unread email from {SENDER} and summarize it"
# Unique run tag per invocation so each run's L0 dump is this run's lines
# only (runs share task_id in the registry, never run_id in the log).
RUN_TAG = f"{TASK_ID}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"


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


def register_task(ok: bool, proof: str) -> None:
    reg = ROOT / "var" / "logs" / "tasks.jsonl"
    reg.parent.mkdir(parents=True, exist_ok=True)
    line = {
        "task_id": TASK_ID,
        "goal": GOAL,
        "gate6_passed": ok,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "proof": proof,
    }
    with reg.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line) + "\n")


def main() -> None:
    if not SENDER:
        print("usage: task_gmail_summary.py <sender-email-or-name>", flush=True)
        sys.exit(2)

    print("=" * 72)
    print("TASK gmail-summary - Gmail unread-email summary (read-only)")
    print("=" * 72)
    print(f"GOAL: {GOAL!r}")

    print("\n--- L4: LLM planning ---")
    llm_plan = planner.plan(GOAL, run_id=f"{RUN_TAG}-plan")
    print("LLM-produced plan JSON:")
    print(json.dumps(llm_plan, indent=2))

    # Interlock (same discipline as Gate 6's harness): a gmail goal is a
    # pure read-only API task. Refuse any plan that reaches for the
    # browser or dev.run - the mailbox is read via the API, not by opening
    # mail.google.com, and no login flow belongs in a gmail plan. This
    # stops an over-eager plan before any step executes.
    non_gmail = [
        s["primitive"] for s in llm_plan.get("steps", [])
        if not str(s.get("primitive", "")).startswith("gmail.")
    ]
    if non_gmail:
        print("\nINTERLOCK: REFUSED - plan contains non-gmail primitives "
              f"{non_gmail} for a pure gmail goal; nothing executed.")
        register_task(False, "gates/TASK_GMAIL_SUMMARY_PROOF.md")
        print(f"TASK {TASK_ID}: FAILED (interlock refusal, no execution)")
        sys.exit(1)

    print("\n--- L3: executor runs the LLM plan (real read-only fetch + summary) ---")
    all_verified = False
    try:
        result = executor.run_plan(llm_plan, run_id=f"{RUN_TAG}-exec")
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

    dump(f"{RUN_TAG}-plan", "L4 planning")
    dump(f"{RUN_TAG}-exec", "execution (real read-only run)")

    # DoD: verification stronger than no-exception.
    matches_ok = False
    summary = ""
    log = ROOT / "var" / "logs" / "friday.jsonl"
    for rec in (json.loads(l) for l in log.read_text().splitlines()):
        if rec.get("run_id") != f"{RUN_TAG}-exec":
            continue
        if rec.get("layer") == "L2" and rec.get("primitive") == "checks.gmail_message_matches":
            if rec.get("result") is True:
                matches_ok = True
        if rec.get("layer") == "L1" and rec.get("primitive") == "gmail.summarize":
            res = rec.get("result")
            if isinstance(res, str) and res:
                summary = res

    print("\n=== TASK DoD (raw L0 trace + stronger-than-no-exception verify) ===")
    print(f"  OK: checks.gmail_message_matches -> True (message really is from "
          f"{SENDER!r}): {matches_ok}")
    print(f"  OK: gmail.summarize produced non-empty summary: {bool(summary)}")
    print(f"  OK: all steps VERIFIED: {all_verified}")
    if summary:
        print(f"\nTHE SUMMARY (raw deliverable):\n{summary}")

    ok = all_verified and matches_ok and bool(summary)
    proof = "gates/TASK_GMAIL_SUMMARY_PROOF.md"
    register_task(ok, proof)
    print(f"\nTASK {TASK_ID}: {'DONE' if ok else 'FAILED'} - registered in "
          f"var/logs/tasks.jsonl as gate6_passed={ok}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
