#!/usr/bin/env python
"""Task 6 (Gate-6-grade proof) - browser click: open the first search result.

GOAL: "search for 'example domain' on DuckDuckGo and open the first result,
      which should be the example.com website, and report the text of the
      page that opens"
      (LLM-planned by L4, executed by L3, verified by L2, logged through L0)

First full-stack proof of browser.click - the last unexercised browser
primitive. Task 4 proved type + press (the search); this task adds the
click that NAVIGATES. The task's DoD asserts, straight from the raw L0
trace:

  1. every step VERIFIED and the plan used the full interaction chain
     (browser.goto -> type_text -> press_key -> click),
  2. browser.click was actually called (the primitive being proven),
  3. the LAST page text read in the trace is example.com, not the
     DuckDuckGo results page: it contains "example domain" but NOT
     "duckduckgo" - i.e. the click really navigated, and the reported
     text is the page that opened.

Side effects: launches the real Playwright chromium window, searches
DuckDuckGo and opens example.com.

Run:  ./.venv/bin/python -u gates/task6_browser_click.py [run_label]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.errors import FridayError  # noqa: E402
from friday.l1 import browser  # noqa: E402
from friday.l3 import executor  # noqa: E402
from friday.l4 import planner  # noqa: E402

GOAL = (
    "search for 'example domain' on DuckDuckGo and open the first result, "
    "which should be the example.com website, and report the text of the "
    "page that opens"
)

# Optional argv[1] labels the run so re-runs get fresh run_ids (L0 traces
# accumulate in one log file; reusing a run_id would mix attempts).
RUN_LABEL = sys.argv[1] if len(sys.argv) > 1 else "task6-click"

# DoD: the plan must compose the full interaction chain; the click must
# navigate to the goal's expected target (example.com). Proved two ways:
# the click step's returned url, and the final page text (left DDG, page
# mentions Example Domain).
REQUIRED_PRIMITIVES = (
    "browser.goto",
    "browser.type_text",
    "browser.press_key",
    "browser.click",
)
TARGET_HOST = "example.com"  # the goal says the first result IS example.com
TARGET_TEXT = "example domain"  # present on the opened page
LEAVES_HOST = "duckduckgo"  # must NOT be in the final page text


def _click_result_url(records: list[dict[str, Any]]) -> str | None:
    """The url returned by the browser.click call in the trace. In this
    stack the click primitive returns the page url after the click; a
    navigation-triggering click yields the navigated-to url (seen in the
    green run: http://www.example.com/)."""
    for rec in records:
        if rec["layer"] == "L1" and rec["primitive"] == "browser.click":
            res = rec.get("result")
            if isinstance(res, dict) and isinstance(res.get("url"), str):
                return res["url"]
    return None


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


def _last_read_page_text(records: list[dict[str, Any]]) -> str | None:
    """The page text of the LAST browser.read_page_text line in the trace -
    i.e. the state of the page when the run ended (post-click verifies and
    the report step both read it)."""
    last: str | None = None
    for rec in records:
        if rec["layer"] == "L1" and rec["primitive"] == "browser.read_page_text":
            if isinstance(rec.get("result"), str) and rec["result"]:
                last = rec["result"]
    return last


def check_dod(
    plan: dict[str, Any],
    result: executor.PlanResult | None,
    records: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    problems: list[str] = []

    # 1. the executor verified every step
    if result is None:
        problems.append("executor ABORTed before completing (see trace above)")
    elif result.status != "COMPLETED" or not all(
        s.status == "VERIFIED" for s in result.steps
    ):
        problems.append(f"not every step VERIFIED (status={result.status})")

    # 2. the plan composed the full interaction chain, incl. browser.click
    prims = [s["primitive"] for s in plan["steps"]]
    for required in REQUIRED_PRIMITIVES:
        if required not in prims:
            problems.append(f"plan never called {required}")

    # 3. the click really navigated to the goal's target: its returned url
    #    is example.com AND the final page text is example.com
    click_url = _click_result_url(records)
    if click_url is None:
        problems.append("no browser.click result with a url in the L0 trace")
    elif TARGET_HOST not in click_url.lower():
        problems.append(
            f"browser.click returned url {click_url!r}, not {TARGET_HOST!r} - "
            "the click landed on the wrong page"
        )

    final = _last_read_page_text(records)
    if final is None:
        problems.append("no browser.read_page_text in the L0 trace")
    else:
        low = final.lower()
        if LEAVES_HOST in low:
            problems.append(
                f"final page text still mentions {LEAVES_HOST!r} - the click "
                "did not leave the search results page"
            )
        if TARGET_TEXT not in low:
            problems.append(
                f"final page text does not mention {TARGET_TEXT!r} - the "
                "opened page is not the expected target"
            )

    return not problems, problems


def main() -> None:
    print("=" * 72)
    print("TASK 6 - browser click: search DDG, open the first result")
    print("=" * 72)
    print(f"GOAL: {GOAL!r}")

    print("\n--- L4: LLM planning ---")
    llm_plan = planner.plan(GOAL, run_id=f"{RUN_LABEL}-plan")
    print("LLM-produced plan JSON:")
    print(json.dumps(llm_plan, indent=2))

    print("\n--- L3: executor runs the LLM plan (real browser) ---")
    result: executor.PlanResult | None = None
    try:
        result = executor.run_plan(llm_plan, run_id=f"{RUN_LABEL}-exec")
        print(f"plan status: {result.status}")
        for sr in result.steps:
            print(
                f"  step {sr.step_id}: {sr.primitive:26s} {sr.status:12s} "
                f"attempts={sr.attempts} verify_actual={sr.verify_actual!r}"
            )
    except FridayError as exc:
        print(f"plan status: ABORTED -> {exc}")

    dump(f"{RUN_LABEL}-plan", "L4 planning")
    dump(f"{RUN_LABEL}-exec", "execution (real browser)")

    # DoD: read the raw L0 records for this run and check the navigation
    log = ROOT / "var" / "logs" / "friday.jsonl"
    records = [
        json.loads(l) for l in log.read_text().splitlines()
        if json.loads(l).get("run_id") == f"{RUN_LABEL}-exec"
    ]
    ok, problems = check_dod(llm_plan, result, records)
    print("\n=== TASK 6 DoD (from raw L0 trace) ===")
    for p in problems:
        print(f"  FAIL: {p}")
    if ok:
        final = _last_read_page_text(records)
        preview = (final or "").splitlines()[0].strip() if final else ""
        click_url = _click_result_url(records)
        print("  OK: every step VERIFIED")
        print("  OK: plan composed goto -> type_text -> press_key -> click")
        print(f"  OK: browser.click navigated to {click_url!r}")
        print("  OK: final page is example.com, not the results page")
        print(f"  OK: reported page starts with: {preview!r}")

    # hygiene: close the browser so nothing holds the profile
    browser.close()

    print(f"\nTASK 6: {'DONE' if ok else 'FAILED'} "
          f"(goal -> LLM plan -> search -> click -> verified navigation)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
