#!/usr/bin/env python
"""Task 4 (Gate-6-grade proof) - first click/type browser interaction.

GOAL: "search for 'example domain' on DuckDuckGo and report the first
      result title"
      (LLM-planned, executed by L3, verified by L2, logged through L0)

First full-stack proof of browser INTERACTION (typing + key press + read;
Tasks 1-3 only sent or navigated). The LLM plan is expected to compose:
  browser.goto(duckduckgo)  -> verify homepage marker
  browser.type_text(query)  -> verify checks.browser_input_has_value
  browser.press_key(Enter)  -> verify results page shows the first result
  browser.read_page_text()  -> the returned text IS the reported title
Every step verified; the raw L0 trace shows the searched page text.

Side effects: launches a real Playwright chromium window and performs a
web search on DuckDuckGo.

Run:  ./.venv/bin/python -u gates/task4_ddg_search.py [run_label]
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

GOAL = "search for 'example domain' on DuckDuckGo and report the first result title"

# Optional argv[1] labels the run so re-runs get fresh run_ids (L0 traces
# accumulate in one log file; reusing a run_id would mix attempts).
RUN_LABEL = sys.argv[1] if len(sys.argv) > 1 else "task4-ddg"


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
    print("TASK 4 - first click/type interaction: DuckDuckGo search")
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

    print(f"\nTASK 4: {'DONE' if all_verified else 'FAILED'} "
          f"(goal -> LLM plan -> type/press -> verified; first result title in trace)")
    sys.exit(0 if all_verified else 1)


if __name__ == "__main__":
    main()
