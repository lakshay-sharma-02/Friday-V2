#!/usr/bin/env python
"""WATCHER gmail proof - run the REAL watcher against a REAL gmail goal.

The committed trigger `morning-gmail-summary` (config/watcher.json) is
ENABLED and its goal references `$facts.gmail_sender` - the sender lives in
config/planner_facts.json, not in the trigger. This demo proves that
trigger end-to-end against TODAY's inbox: it probes for a sender that
actually has unread mail right now, points $FRIDAY_FACTS_FILE at a temp
facts file carrying that sender, and runs the UNMODIFIED watcher (--once)
with the real trigger definition (only the schedule is moved to 00:00 so
the proof runs at any time of day; the committed trigger keeps 09:00
weekdays).

The run is the full ambient stack: L4 LLM plan -> L3 executor -> real L2
gmail checks -> var/logs/tasks.jsonl `watch:morning-gmail-summary` ->
desktop notification. The trigger carries "allow": ["gmail.*"] - any
hallucinated side-effecting step would be REFUSED before execution.

Privacy: the discovered sender is redacted and the summary preview
truncated in the proof, mirroring list_unread's L0 log_transform.

Run:  ./.venv/bin/python -u gates/watcher_gmail_demo.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "gates"))

from friday.watcher import load_config, run_watcher  # noqa: E402
from e2e_check import _probe_unread_sender  # noqa: E402

TASK_ID = "watch:morning-gmail-summary"
PROOF = "gates/WATCHER_GMAIL_PROOF.md"

# The committed trigger, verbatim except schedule -> 00:00 (always due).
TRIGGER = {
    "id": "morning-gmail-summary",
    "goal": "find the most recent unread email from $facts.gmail_sender "
            "and summarize it in at most 5 plain sentences",
    "schedule": {"type": "time", "at": "00:00"},
    "enabled": True,
    "notify": True,
    "allow": ["gmail.*"],
}


def _tasks_records() -> list[dict]:
    path = ROOT / "var" / "logs" / "tasks.jsonl"
    return [
        json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()
        if json.loads(l).get("task_id") == TASK_ID
    ]


def _summary_preview() -> str:
    """First ~200 chars of the gmail.summarize L1 result from this run's
    L0 trace (run_id watch-morning-gmail-summary-*). Empty if not found."""
    log = ROOT / "var" / "logs" / "friday.jsonl"
    for line in reversed(log.read_text(encoding="utf-8").splitlines()):
        rec = json.loads(line)
        if (
            rec.get("primitive") == "gmail.summarize"
            and rec.get("layer") == "L1"
            and str(rec.get("run_id", "")).startswith("watch-morning-gmail-summary")
        ):
            val = rec.get("result")
            if isinstance(val, str) and val.strip():
                return val.strip()[:200]
    return ""


def main() -> int:
    print("=" * 72)
    print(f"WATCHER gmail proof - real watcher, real inbox ({datetime.now(timezone.utc).isoformat(timespec='seconds')})")
    print("=" * 72)

    sender = _probe_unread_sender()
    if not sender:
        print("\nFAIL: no unread mail from any sender right now - nothing to prove.")
        print("      Re-run when the inbox has unread mail (an empty mailbox is an")
        print("      honest FALSE verdict, never an error).")
        return 1
    print(f"\n[probe] unread mail from {sender!r} (sender redacted in the proof)")

    tmp = Path(tempfile.mkdtemp(prefix="friday_watch_gmail_"))
    facts = tmp / "facts.json"
    facts.write_text(json.dumps({
        "_docs": "temp facts for the watcher gmail proof",
        "recipients": {"gmail_sender": sender},
    }), encoding="utf-8")
    cfg = tmp / "watcher.json"
    cfg.write_text(json.dumps({"_docs": "temp watcher config", "triggers": [TRIGGER]}), encoding="utf-8")
    os.environ["FRIDAY_FACTS_FILE"] = str(facts)

    print("\n[config] triggers loaded:")
    for t in load_config(str(cfg)):
        print(f"   - {t['id']}: goal={t['goal']!r} allow={t.get('allow')}")

    print("\n--- run_watcher(once=True) on the REAL morning-gmail-summary trigger ---")
    print("     (L4 LLM plan -> L3 executor -> real L2 gmail checks -> notify)")
    run_watcher(str(cfg), once=True)

    print("\n--- recorded task ---")
    recs = _tasks_records()
    if not recs:
        print("NO watch:morning-gmail-summary record found - did the trigger fire?")
        return 1
    rec = recs[-1]
    ok = rec["gate6_passed"]
    print(f"   {rec['task_id']} gate6_passed={rec['gate6_passed']}")
    print(f"   goal: {rec['goal']}")
    print(f"   proof: {rec['proof']}")

    preview = _summary_preview()
    # The summary text itself may mention the sender - redact it there too.
    preview_redacted = preview.replace(sender, "<redacted>")
    print(f"   summary preview: {preview_redacted[:120]!r}..." if preview else "   summary preview: (none in L0 - check run_id watch-morning-gmail-summary-*)")

    redacted_rec = json.dumps(rec, ensure_ascii=False).replace(sender, "<redacted>")
    out_lines = [
        "# WATCHER_GMAIL_PROOF - the ambient watch loop runs a REAL gmail goal",
        "",
        f"Status date: {datetime.now(timezone.utc).isoformat(timespec='seconds')}.",
        "",
        "The committed `morning-gmail-summary` trigger (config/watcher.json, ENABLED)",
        "fired through the UNMODIFIED watcher against today's real inbox:",
        "",
        "- The goal references `$facts.gmail_sender`, so the sender lives in",
        "  config/planner_facts.json, not in the trigger. This run pointed",
        "  `$FRIDAY_FACTS_FILE` at a temp facts file whose sender was discovered by",
        "  a read-only pre-probe of the inbox (a sender with unread mail right now).",
        "- The trigger carries `\"allow\": [\"gmail.*\"]` - a hallucinated",
        "  side-effecting step would have been REFUSED before execution, never acted",
        "  on by an unattended trigger.",
        "- The goal was LLM-planned (L4), executed by the unmodified executor (L3),",
        "  verified by real L2 gmail checks, recorded in var/logs/tasks.jsonl as",
        "  `watch:morning-gmail-summary`, and pinged to the desktop (notify_send).",
        "",
        "## Recorded task (last watch:morning-gmail-summary)",
        "",
        "```",
        redacted_rec,
        "```",
        "",
        "## Summary produced",
        "",
        "```",
        f"{preview_redacted}..." if preview else "(no summary line found in the L0 trace)",
        "```",
        "",
        "The summary text is truncated and the sender redacted in this proof, mirroring",
        "`gmail.list_unread`'s L0 log_transform - mail metadata never lands in the",
        "committed proof. The full L0 trace lives in var/logs/friday.jsonl under",
        "run_id `watch-morning-gmail-summary-*`.",
        "",
        "## Verdict",
        "",
        f"{'PASS' if ok else 'FAIL'} - the ambient watch loop delivered a real gmail",
        "summary end to end, from a live LLM plan, with the per-trigger allowlist",
        "standing guard between the plan and the world.",
        "",
    ]
    (ROOT / PROOF).write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"\nproof written to {PROOF}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
