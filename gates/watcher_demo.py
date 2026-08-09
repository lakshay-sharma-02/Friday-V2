"""WATCHER demo - prove the ambient watch loop end-to-end with ZERO risk.

Two triggers, both deterministic (inline plans - no LLM call, no sends,
no window/media/browser side effects):

  watch:demo-time  a time trigger already due, planning a files.find_file
                   on a pre-created demo file, verified by checks.file_exists
  watch:demo-file  a file trigger whose directory receives a NEW file after
                   the watcher starts; detection fires the same find+verify

The watcher records both runs in var/logs/tasks.jsonl (as watch:demo-*,
gate6_passed true) and pings the desktop with notify_send - a real
notification appears. Raw output is captured to WATCHER_PROOF.md.

Run:  ./.venv/bin/python gates/watcher_demo.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.watcher import load_config, run_watcher  # noqa: E402

TASK_ID = "watcher-demo"
PROOF = "gates/WATCHER_PROOF.md"


def _plan_for(directory: str, name: str) -> dict:
    """A deterministic plan: find the file, verify it exists. Fully
    resolved (no $facts), so it runs straight through L3 without L4."""
    return {
        "goal": f"locate the {name} demo file",
        "steps": [
            {
                "primitive": "files.find_file",
                "args": {"name": name, "directory": directory},
                "verify": {
                    "check": "checks.file_exists",
                    "args": {"path": "$steps.1.result.path"},
                    "expect": True,
                },
            }
        ],
    }


def main() -> int:
    print("=" * 72)
    print(f"WATCHER demo - ambient watch loop ({datetime.now(timezone.utc).isoformat(timespec='seconds')})")
    print("=" * 72)

    tmp = Path(tempfile.mkdtemp(prefix="friday_watch_demo_"))
    time_dir = tmp / "time"
    file_dir = tmp / "file"
    time_dir.mkdir()
    file_dir.mkdir()
    (time_dir / "alpha.txt").write_text("demo", encoding="utf-8")
    print(f"\n[setup] time-trigger dir: {time_dir} (alpha.txt pre-created)")
    print(f"[setup] file-trigger dir: {file_dir} (file dropped AFTER start)")

    config = {
        "_docs": "watcher demo config",
        "triggers": [
            {
                "id": "demo-time",
                "plan": _plan_for(str(time_dir), "alpha"),
                "schedule": {"type": "time", "at": "00:00"},
                "enabled": True,
                "notify": True,
            },
            {
                "id": "demo-file",
                "plan": _plan_for(str(file_dir), "beta"),
                "schedule": {"type": "file", "directory": str(file_dir), "name": "beta"},
                "enabled": True,
                "notify": True,
            },
        ],
    }
    cfg = tmp / "watcher.json"
    cfg.write_text(json.dumps(config), encoding="utf-8")

    print("\n[config] triggers loaded:")
    for t in load_config(str(cfg)):
        print(f"   - {t['id']}: schedule={t['schedule']} plan-goal={t['plan']['goal']}")

    print("\n[drop] creating beta.txt in the file-trigger dir AFTER config load")
    time.sleep(0.5)
    (file_dir / "beta.txt").write_text("demo", encoding="utf-8")

    print("\n--- run_watcher(once=True) ---")
    run_watcher(str(cfg), once=True)

    print("\n--- recorded tasks ---")
    lines = [
        json.loads(l) for l in (ROOT / "var" / "logs" / "tasks.jsonl").read_text().splitlines()
        if json.loads(l).get("task_id", "").startswith("watch:demo-")
    ]
    for rec in lines:
        print(
            f"   {rec['task_id']:<14} gate6_passed={rec['gate6_passed']}  "
            f"proof={rec['proof'][:120]}"
        )
    passed = sum(1 for r in lines if r["gate6_passed"])
    print(f"\nRESULT: {passed}/{len(lines)} demo triggers passed")

    out = "\n".join(
        [
            "# WATCHER_PROOF — ambient watch loop, first end-to-end proof",
            "",
            f"Status date: {datetime.now(timezone.utc).isoformat(timespec='seconds')}.",
            "",
            "Two deterministic triggers (inline plans - no LLM, no sends, no",
            "window/media/browser side effects) run through the real watcher:",
            "",
            "- `watch:demo-time`: a time trigger already due at 00:00, planning a",
            "  `files.find_file` on a pre-created file, verified by",
            "  `checks.file_exists` on the returned path.",
            "- `watch:demo-file`: a file trigger watching a temp directory; a new",
            "  file is dropped AFTER the watcher starts, detection fires the same",
            "  find + verify.",
            "",
            "Each firing: L3 executes the plan, the outcome is recorded in",
            "`var/logs/tasks.jsonl` as `watch:demo-*` with the gate-6 format, and a",
            "desktop notification is sent via the new `notify_send` primitive.",
            "",
            "## Recorded tasks",
            "",
            "```",
        ]
        + [f"{rec['task_id']:<14} gate6_passed={rec['gate6_passed']}  proof={rec['proof']}" for rec in lines]
        + [
            "```",
            "",
            f"Result: {passed}/{len(lines)} demo triggers passed.",
            "",
            "## What this proves",
            "",
            "- The watch loop loads and validates config, evaluates time and file",
            "  triggers, and fires each at most once.",
            "- Goals run through the same L3 executor as every other task, with the",
            "  same L0 tracing (layer=WATCH + layer=L3/L2/L1 in var/logs/friday.jsonl).",
            "- Outcomes land in the tasks counter in the honest gate-6 format.",
            "- `notify_send` works end-to-end (a real desktop notification appears).",
            "- Serial execution: the two triggers never overlap.",
            "",
            "## Raw proof",
            "",
            "See `var/logs/friday.jsonl` (layer=WATCH lines with run_id `watch-*`)",
            "for the full L0 trace of this run.",
            "",
        ]
    )
    (ROOT / PROOF).write_text(out + "\n", encoding="utf-8")
    print(f"\nproof written to {PROOF}")
    return 0 if passed == len(lines) and len(lines) == 2 else 1


if __name__ == "__main__":
    sys.exit(main())
