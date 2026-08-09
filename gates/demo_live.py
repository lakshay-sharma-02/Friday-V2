#!/usr/bin/env python
"""Live demo: a tiny composed task through L1 primitives + the L0 trace.

Runs: open Firefox -> browse to a URL -> read the page text -> close both,
then prints the structured JSONL trace of every primitive call (Gate 2's
observability) correlated by run_id - proving the task really happened.

Run:  ./.venv/bin/python -u gates/demo_live.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.l1 import browser, window  # noqa: E402
from friday.observability import set_run_id  # noqa: E402

RUN_ID = f"demo-{time.strftime('%H%M%S')}"
set_run_id(RUN_ID)
print(f"run_id: {RUN_ID}\n", flush=True)

print("[1] window.open_app('firefox')")
win = window.open_app("firefox")
print(f"    -> firefox client: {win}\n", flush=True)

print("[2] browser.goto('https://example.com')")
nav = browser.goto("https://example.com")
print(f"    -> {nav}\n", flush=True)

print("[3] browser.read_page_text()")
text = browser.read_page_text()
print(f"    -> {text[:120]!r}...\n", flush=True)

print("[4] browser.close() + window.close_window(firefox)")
browser.close()
window.close_window(win["address"])
print("    -> closed\n", flush=True)

# Dump the correlated trace for this run.
log = ROOT / "var" / "logs" / "friday.jsonl"
lines = [l for l in log.read_text().splitlines() if json.loads(l)["run_id"] == RUN_ID]
print(f"=== L0 trace ({len(lines)} lines, run_id={RUN_ID}) ===")
for l in lines:
    rec = json.loads(l)
    outcome = rec["result"] if rec["exception"] is None else f"EXC: {rec['exception']}"
    print(
        f"[{rec['timestamp']}] {rec['primitive']:18s} args={rec['args']} "
        f"-> {outcome} ({rec['duration_ms']}ms)"
    )
print("\nDEMO: DONE - every action traced in var/logs/friday.jsonl")
