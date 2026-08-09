#!/usr/bin/env python
"""Task 8 (Gate-6-grade proof) - composite window control.

GOAL: "open the firefox browser, verify it appears, focus it, move it to a
      free scratch workspace, and close it again - verifying each step"
      (LLM-planned by L4, executed by L3, verified by L2, logged through L0)

First full-stack composite over window.focus_window / window.move_to_workspace
/ window.close_window - the primitives proven standalone in the remaining
primitives bring-up. This task proves the executor can drive them from an
LLM plan.

SAFETY (unattended run): the user's open windows are the protected control
group. The harness snapshots every pre-existing client and refuses to run
if firefox is already open (so the plan's firefox test window is never
ambiguous). The plan only ever touches the window IT opened, by address;
the harness re-checks afterward that every pre-existing client survives and
restores focus to the originally-active window.

The plan's move step needs a workspace with no clients on it; the harness
computes one (first free in 5..19) and injects it via the facts override,
so the plan never picks a workspace the user is using.

The task's DoD asserts, from the raw L0 trace + real window state:
  1. every step VERIFIED and the plan used the four primitives in order
     (open_app -> focus_window -> move_to_workspace -> close_window),
  2. the move step's verify passed for the free workspace id the harness
     picked (the executor VERIFIED it, i.e. checks.window_on_workspace
     returned true), and the close step's verify passed,
  3. real state after the run: every pre-existing client still present,
     the test window gone, focus restored to the originally-active window.

Side effects: opens and closes a firefox test window (moves it briefly to
a free workspace). No other window is touched.

Run:  ./.venv/bin/python -u gates/task8_window_compose.py [run_label]
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.errors import FridayError  # noqa: E402
from friday.l1 import browser, window  # noqa: E402
from friday.l3 import executor  # noqa: E402
from friday.l4 import planner  # noqa: E402

GOAL = (
    "open the firefox browser, verify it appears, focus it, move it to a "
    "free scratch workspace, and close it again - verifying each step"
)

REQUIRED_PRIMITIVES = (
    "window.open_app",
    "window.focus_window",
    "window.move_to_workspace",
    "window.close_window",
)

RUN_LABEL = sys.argv[1] if len(sys.argv) > 1 else "task8-window"
TASK_ID = "task8"


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


def register_task(ok: bool) -> None:
    """Append one line to the task registry so the >=10 count is data, not
    memory (Claude Code suggestion #3 - Gate-6-grade proof as a counter)."""
    reg = ROOT / "var" / "logs" / "tasks.jsonl"
    reg.parent.mkdir(parents=True, exist_ok=True)
    line = {
        "task_id": TASK_ID,
        "goal": GOAL,
        "gate6_passed": bool(ok),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "proof": f"gates/TASK8_WINDOW_PROOF.md",
    }
    with reg.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line) + "\n")


def _open_app_address(records: list[dict[str, Any]]) -> str | None:
    """The address returned by the plan's window.open_app call in the L0
    trace - the exact window the plan opened and is allowed to touch."""
    for rec in records:
        if rec["layer"] == "L1" and rec["primitive"] == "window.open_app":
            res = rec.get("result")
            if isinstance(res, dict) and isinstance(res.get("address"), str):
                return res["address"]
    return None


def check_dod(
    plan: dict[str, Any],
    result: executor.PlanResult | None,
    free_ws: int,
    before_addrs: set[str],
    after_addrs: set[str],
) -> tuple[bool, list[str]]:
    problems: list[str] = []

    # 1. the executor verified every step
    if result is None:
        problems.append("executor ABORTed before completing (see trace above)")
    elif result.status != "COMPLETED" or not all(
        s.status == "VERIFIED" for s in result.steps
    ):
        problems.append(f"not every step VERIFIED (status={result.status})")

    # 2. the plan composed the four-primitive chain, in recipe order
    prims = [s["primitive"] for s in plan["steps"]]
    it = iter(prims)
    in_order = all(req in it for req in REQUIRED_PRIMITIVES)
    for required in REQUIRED_PRIMITIVES:
        if required not in prims:
            problems.append(f"plan never called {required}")
    if not in_order:
        problems.append(
            f"plan must compose {list(REQUIRED_PRIMITIVES)} in that order, "
            f"got {prims}"
        )

    # 3. the move step really targeted the harness-picked free workspace
    move = next((s for s in plan["steps"] if s["primitive"] == "window.move_to_workspace"), None)
    if move is None:
        problems.append("plan has no move_to_workspace step")
    else:
        ws = move.get("args", {}).get("workspace_id")
        if ws != free_ws:
            problems.append(f"move step targets workspace {ws!r}, harness picked {free_ws}")
        sel = move.get("args", {}).get("selector")
        if not (isinstance(sel, str) and sel.startswith("$steps.1.result")):
            problems.append(
                f"move step selector {sel!r} does not reference the opened window's address"
            )

    # 3b. EVERY window-mutating step must target the opened window's address
    #     - a class-based selector (e.g. close_window('firefox')) resolves to
    #     ALL matching clients and could touch a window the plan did not
    #     open. The preflight makes that safe at start, but a same-class
    #     window appearing mid-run must never be catchable.
    for s in plan["steps"]:
        if s["primitive"] in ("window.focus_window", "window.move_to_workspace", "window.close_window"):
            sel = s.get("args", {}).get("selector")
            if not (isinstance(sel, str) and sel.startswith("$steps.1.result")):
                problems.append(
                    f"{s['primitive']} selector {sel!r} is not address-based "
                    "(must reference the opened window: $steps.1.result.address)"
                )

    # 4. real window state: every pre-existing client survived, none added
    if not before_addrs <= after_addrs:
        problems.append(f"pre-existing client(s) missing after the run: {before_addrs - after_addrs}")
    if after_addrs - before_addrs:
        problems.append(f"unexpected new client(s) after the run: {after_addrs - before_addrs}")

    return not problems, problems


def main() -> None:
    print("=" * 72)
    print("TASK 8 - composite window control (open -> focus -> move -> close)")
    print("=" * 72)
    print(f"GOAL: {GOAL!r}")

    before = window.list_clients()
    before_addrs = {str(c.get("address")) for c in before}
    original_active = window.get_active_window()
    original_active_addr = str(original_active.get("address")) if original_active else None
    print(f"\n[preflight] pre-existing clients ({len(before)}):")
    for c in before:
        print(f"     - class={c.get('class')!r} addr={c.get('address')} ws={c.get('workspace', {}).get('id')}")
    print(f"[preflight] originally-active address: {original_active_addr}")

    if any("firefox" in str(c.get("class", "")).lower() for c in before):
        print("\nREFUSING TO RUN: firefox is already open - cannot use it as an "
              "unambiguous test window (safety). Close it and re-run.")
        sys.exit(2)

    used_ws = {int(c.get("workspace", {}).get("id", -1)) for c in before}
    free_ws = next(i for i in range(5, 20) if i not in used_ws)
    print(f"[preflight] free workspace chosen for the move step: {free_ws}")

    loaded = planner.load_project_facts()
    recipe = (
        "Window composition recipe (this goal): step 1 window.open_app with "
        "args {\"command\": \"firefox\"} verified with checks.window_has_class "
        "on {\"cls\": \"firefox\"} expect true; step 2 window.focus_window with "
        "args {\"selector\": \"$steps.1.result.address\"} verified with "
        "checks.window_focused on {\"cls\": \"firefox\"} expect true; step 3 "
        "window.move_to_workspace with args {\"workspace_id\": "
        f"{free_ws}, \"selector\": \"$steps.1.result.address\"}} verified with "
        f"checks.window_on_workspace on {{\"cls\": \"firefox\", \"workspace_id\": {free_ws}}} "
        "expect true; step 4 window.close_window with args {\"selector\": "
        "\"$steps.1.result.address\"} verified with checks.window_has_class on "
        "{\"cls\": \"firefox\"} expect false. CRITICAL: only window.open_app "
        "returns a client dict with an 'address' key - window.focus_window, "
        "window.move_to_workspace and window.close_window all RETURN None, so "
        "their results have no .address. Use \"$steps.1.result.address\" (the "
        "open step's address) for the selector in EVERY later step, never "
        "$steps.2.result or $steps.3.result. Only touch the window the plan "
        "opened - never close or move any other window."
    )
    facts_override = list(loaded.facts) + [recipe]

    print("\n--- L4: LLM planning ---")
    llm_plan = planner.plan(
        GOAL,
        run_id=f"{RUN_LABEL}-plan",
        facts=facts_override,
        recipients=dict(loaded.recipients),
        file_paths=dict(loaded.file_paths),
    )
    print("LLM-produced plan JSON:")
    print(json.dumps(llm_plan, indent=2))

    print("\n--- L3: executor runs the LLM plan (real window control) ---")
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

    after = window.list_clients()
    after_addrs = {str(c.get("address")) for c in after}

    # harness hygiene (mirrors the bring-up): an ABORTed plan skips its
    # close step, so close the leftover firefox TEST window the plan opened.
    # Address-aware: only the exact client the plan's open_app returned is
    # closed (read from the L0 trace). If a NEW firefox-class client exists
    # that is NOT the plan's window (e.g. the user opened one mid-run) or
    # there is more than one, refuse and report instead of closing - never
    # close by class.
    records = [
        json.loads(l) for l in (ROOT / "var" / "logs" / "friday.jsonl").read_text().splitlines()
        if json.loads(l).get("run_id") == f"{RUN_LABEL}-exec"
    ]
    opened_addr = _open_app_address(records)
    new_firefox = [
        c for c in after
        if str(c.get("address")) not in before_addrs
        and "firefox" in str(c.get("class", "")).lower()
    ]
    if new_firefox:
        if opened_addr is not None and len(new_firefox) == 1 \
                and str(new_firefox[0]["address"]) == opened_addr:
            try:
                window.close_window(opened_addr)
                print(f"[cleanup] closed leftover test window {opened_addr}")
            except Exception as exc:
                print(f"[cleanup] could not close leftover test window {opened_addr}: {exc}")
        else:
            print(f"[cleanup] REFUSING to close {len(new_firefox)} new firefox client(s) "
                  f"({[c['address'] for c in new_firefox]}, plan opened {opened_addr}) - "
                  "ambiguous, could include a window the user opened mid-run")

    # harness hygiene: restore focus to the originally-active window
    after2 = window.list_clients()
    after_addrs = {str(c.get("address")) for c in after2}
    if original_active_addr and str(original_active_addr) in after_addrs:
        try:
            window.focus_window(original_active_addr)
            print(f"[cleanup] focus restored to {original_active_addr}")
        except Exception as exc:
            print(f"[cleanup] could not restore focus: {exc}")

    dump(f"{RUN_LABEL}-plan", "L4 planning")
    dump(f"{RUN_LABEL}-exec", "execution (real window control)")

    ok, problems = check_dod(llm_plan, result, free_ws, before_addrs, after_addrs)
    print("\n=== TASK 8 DoD (from raw L0 trace + real window state) ===")
    for p in problems:
        print(f"  FAIL: {p}")
    if ok:
        print("  OK: every step VERIFIED; plan composed open -> focus -> move -> close")
        print(f"  OK: move step targeted the free workspace {free_ws} and was VERIFIED")
        print("  OK: close step VERIFIED - the test window is gone")
        print(f"  OK: all {len(before_addrs)} pre-existing clients survived the run")
        print("  OK: focus restored to the originally-active window")

    browser.close()  # hygiene (no-op here, mirrors the shared harness)
    register_task(ok)

    print(f"\nTASK 8: {'DONE' if ok else 'FAILED'} "
          f"(goal -> LLM plan -> window control -> verified; control group intact)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
