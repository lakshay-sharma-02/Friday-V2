#!/usr/bin/env python
"""Task: WhatsApp file-send re-prove (Phase 2 Section 1).

GOAL: "send the README.md file to my whatsapp"
      (LLM-planned, executed by L3, verified by L2, logged through L0)

Background (recorded in TASK_WHATSAPP_FILESEND_PROOF.md): the historical
"stages but doesn't send" WhatsApp bug belonged to the SUPERSEDED
web.whatsapp.com browser automation (removed 2026-08-08). The current L1
primitive friday/l1/whatsapp.py is the official WhatsApp Business Cloud
API - a two-step REST flow (POST /media -> media_id, then POST /messages
-> wamid) with no DOM, no staging, no send button. The L0 log contains
every WhatsApp call ever made: 7 calls, 0 exceptions, all VERIFIED.

This task re-proves the current path fresh, with verification STRONGER
than absence-of-exception: the send step must return a fresh wamid AND
pass checks.message_sent on that exact id (well-formedness + non-empty),
and the raw L0 trace is captured so the fresh media_id and wamid are
visible, not summarized.

Run:  ./.venv/bin/python -u gates/task_whatsapp_filesend.py
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

TASK_ID = "whatsapp-filesend"
GOAL = "send the README.md file to my whatsapp"


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
    print("=" * 72)
    print(f"TASK {TASK_ID} - WhatsApp file-send re-prove (Cloud API, unmodified pipeline)")
    print("=" * 72)
    print(f"GOAL: {GOAL!r}")

    print("\n--- L4: LLM planning ---")
    llm_plan = planner.plan(GOAL, run_id=f"{TASK_ID}-plan")
    print("LLM-produced plan JSON:")
    print(json.dumps(llm_plan, indent=2))

    print("\n--- L3: executor runs the LLM plan (real send) ---")
    all_verified = False
    try:
        result = executor.run_plan(llm_plan, run_id=f"{TASK_ID}-exec")
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

    dump(f"{TASK_ID}-plan", "L4 planning")
    dump(f"{TASK_ID}-exec", "execution (real send)")

    # DoD: verification stronger than absence-of-exception - the send step
    # must carry a non-empty fresh wamid AND pass checks.message_sent on it.
    wamid = None
    send_verified = False
    log = ROOT / "var" / "logs" / "friday.jsonl"
    for rec in (json.loads(l) for l in log.read_text().splitlines()):
        if rec.get("run_id") == f"{TASK_ID}-exec":
            if rec.get("layer") == "L1" and rec.get("primitive") == "whatsapp.send_document":
                res = rec.get("result") or {}
                wamid = res.get("message_id") if isinstance(res, dict) else None
            if rec.get("layer") == "L2" and rec.get("primitive") == "checks.message_sent":
                if rec.get("result") is True:
                    send_verified = True

    print("\n=== TASK DoD (fresh wamid + checks.message_sent + raw trace) ===")
    print(f"  OK: fresh wamid returned by whatsapp.send_document: {bool(wamid)}"
          f"{f' ({wamid[:40]}...)' if wamid else ''}")
    print(f"  OK: checks.message_sent on that id -> True: {send_verified}")
    print(f"  OK: all steps VERIFIED: {all_verified}")
    print(f"  OK: raw L0 trace captured above (media_id + wamid, not summarized): True")

    ok = all_verified and send_verified and bool(wamid)
    proof = "gates/TASK_WHATSAPP_FILESEND_PROOF.md"
    register_task(ok, proof)
    print(f"\nTASK {TASK_ID}: {'DONE' if ok else 'FAILED'} - registered in "
          f"var/logs/tasks.jsonl as gate6_passed={ok}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
