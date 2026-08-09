#!/usr/bin/env python
"""Task 7 phase 3 (Gate-6-grade proof) - composite browser login on GitHub.

GOAL: "log in to GitHub using the stored credentials for 'github' and
      report whether the login succeeded"
      (LLM-planned by L4, executed by L3, verified by L2, logged through L0)

First full-stack composite over the secrets path. Phase 1 proved
browser.credentials + browser.login standalone; this task proves the
executor can drive them from an LLM plan:
  - the plan should follow the GitHub recipe in config/planner_facts.json:
    goto(/login) -> browser.login(service, real handles) -> read_page_text
  - session control is the harness's job: the script logs the persistent
    profile out first (github.com/logout shows a confirmation page with a
    "Sign out" button), so login() must do real work - the same prep
    bringup_login.py does.
  - the task's DoD asserts, from the raw L0 trace:
      1. every step VERIFIED and the plan used browser.login,
      2. login's returned url left /login (real navigation),
      3. the final page read shows the logged-in Dashboard,
      4. redaction: the actual password appears NOWHERE in the run's L0
         lines (fetched in-process, never printed).

Side effects: logs out and logs into the real GitHub account in the
Playwright chromium window.

Run:  ./.venv/bin/python -u gates/task7_browser_login.py [run_label]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.errors import FridayError, PrimitiveError  # noqa: E402
from friday.l1 import browser  # noqa: E402
from friday.l3 import executor  # noqa: E402
from friday.l4 import planner  # noqa: E402
from friday.secrets import get_credentials  # noqa: E402

GOAL = (
    "log in to GitHub using the stored credentials for 'github' and report "
    "whether the login succeeded"
)

SERVICE = "github"
LOGIN_URL = "https://github.com/login"
LOGOUT_URL = "https://github.com/logout"
SIGN_OUT_SEL = "Sign out"
LOGGED_IN_MARKER = "Dashboard"  # GitHub's home shows this only when logged in
# The two steps that PROVE the login (the report is the harness output +
# the final page read already in the trace via the verify's internal
# reads - an explicit read_page_text step is encouraged by the recipe but
# not required for the goal).
REQUIRED_PRIMITIVES = ("browser.goto", "browser.login")

# Optional argv[1] labels the run so re-runs get fresh run_ids.
RUN_LABEL = sys.argv[1] if len(sys.argv) > 1 else "task7-login"


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


def _login_result_url(records: list[dict[str, Any]]) -> str | None:
    """The url returned by the browser.login call in the trace."""
    for rec in records:
        if rec["layer"] == "L1" and rec["primitive"] == "browser.login":
            res = rec.get("result")
            if isinstance(res, dict) and isinstance(res.get("url"), str):
                return res["url"]
    return None


def _last_read_page_text(records: list[dict[str, Any]]) -> str | None:
    """The page text of the LAST browser.read_page_text line - the state of
    the page when the run ended (post-login verifies and the report both
    read it)."""
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
    password: str,
) -> tuple[bool, list[str]]:
    problems: list[str] = []

    # 1. the executor verified every step
    if result is None:
        problems.append("executor ABORTed before completing (see trace above)")
    elif result.status != "COMPLETED" or not all(
        s.status == "VERIFIED" for s in result.steps
    ):
        problems.append(f"not every step VERIFIED (status={result.status})")

    # 2. the plan composed the GitHub recipe (goto + login prove the login)
    prims = [s["primitive"] for s in plan["steps"]]
    for required in REQUIRED_PRIMITIVES:
        if required not in prims:
            problems.append(f"plan never called {required}")

    # 3. login really navigated away from /login
    url = _login_result_url(records)
    if url is None:
        problems.append("no browser.login result with a url in the L0 trace")
    elif "github.com" not in url or "/login" in url:
        problems.append(f"login url did not leave the login page: {url!r}")

    # 4. logged-in state visible in the final page read
    final = _last_read_page_text(records)
    if final is None:
        problems.append("no browser.read_page_text in the L0 trace")
    elif LOGGED_IN_MARKER not in final:
        problems.append(
            f"final page text missing logged-in marker {LOGGED_IN_MARKER!r}"
        )

    # 5. redaction DoD: the password appears nowhere in this run's L0 lines
    leaked = [rec for rec in records if password in json.dumps(rec)]
    if leaked:
        problems.append(f"password value appears in {len(leaked)} L0 log lines")

    return not problems, problems


def main() -> None:
    print("=" * 72)
    print("TASK 7 PHASE 3 - composite browser login (GitHub)")
    print("=" * 72)
    print(f"GOAL: {GOAL!r}")
    print("(harness session control: logging the persistent profile out first)")

    # session control (harness, not the plan): the persistent profile may
    # hold a GitHub session from an earlier run. Log out so the plan's
    # login() must do real work. github.com/logout shows a confirmation
    # page with a "Sign out" button (skipped harmlessly when no session).
    browser.goto(LOGOUT_URL)
    try:
        browser.click(SIGN_OUT_SEL)
    except PrimitiveError:
        pass  # no session to end

    print("\n--- L4: LLM planning ---")
    llm_plan = planner.plan(GOAL, run_id=f"{RUN_LABEL}-plan")
    print("LLM-produced plan JSON:")
    print(json.dumps(llm_plan, indent=2))

    print("\n--- L3: executor runs the LLM plan (real login) ---")
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
    dump(f"{RUN_LABEL}-exec", "execution (real login)")

    # DoD: read the raw L0 records for this run and check honestly
    log = ROOT / "var" / "logs" / "friday.jsonl"
    records = [
        json.loads(l) for l in log.read_text().splitlines()
        if json.loads(l).get("run_id") == f"{RUN_LABEL}-exec"
    ]
    password = get_credentials(SERVICE)["password"]  # in-process, never printed
    ok, problems = check_dod(llm_plan, result, records, password)
    print("\n=== TASK 7 DoD (from raw L0 trace) ===")
    for p in problems:
        print(f"  FAIL: {p}")
    if ok:
        url = _login_result_url(records)
        print("  OK: every step VERIFIED; plan used goto -> login -> read_page_text")
        print(f"  OK: login navigated: url={url}")
        print(f"  OK: logged-in marker {LOGGED_IN_MARKER!r} in the final page read")
        print("  OK: password appears nowhere in the L0 trace")

    # hygiene: nothing left running
    browser.close()

    print(f"\nTASK 7: {'DONE' if ok else 'FAILED'} "
          f"(goal -> LLM plan -> login -> verified; redaction enforced)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
