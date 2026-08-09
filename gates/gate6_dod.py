#!/usr/bin/env python
"""Gate 6 DoD - first REAL composite through the full unmodified pipeline.

GOAL (typed exactly as you'd say it to Friday):
    "pause whatever's playing, then close every window except my terminal"

Full unmodified path: goal string -> L4 planner (dev.run LLM call) -> plan
JSON -> L3 executor -> L1 primitives + L2 verifies -> L0 log. No pre-staged
plan, no dry-run edit, no new primitives/checks/signatures.

Real-world preconditions (declared, not hidden):
  - the test tone is playing at volume 30 when the goal runs, so the
    "pause whatever's playing" step has a real effect to act on,
  - the desktop holds the user's real windows (kitty x2 incl. the window
    this run is being read through, brave x1).

SAFETY + SUFFICIENCY (hard constraint from the user: never close the
window they are reading this through - a kitty terminal; and the known L2
gap: window_focused proves only focus, so a partial close could verify
True): the harness snapshots the desktop before, marks every kitty window
as protected, and REFUSES to execute any plan that could close a protected
window OR that verifies a close_all step with anything weaker than the
SUFFICIENT check:
  - window.close_all must carry exclude_classes containing 'kitty',
  - every window.close_all step must verify with
    checks.window_only_classes(classes=[...the excluded classes]) expect
    true - asserting nothing outside the excluded set remains,
  - window.close_window selectors must not match 'kitty'.
A refused plan is printed raw and the run stops - a refusal is data, not a
silent fix.

DoD (raw, in order): exact goal string; the full LLM prompt; the generated
plan JSON; the full L0 trace (L3 state machine + L1 primitive lines); and
INDEPENDENT world-state proof - `hyprctl clients -j` before/after showing
the non-terminal client is gone and every protected terminal survives.

Run:  ./.venv/bin/python -u gates/gate6_dod.py [run_label]
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.errors import FridayError  # noqa: E402
from friday.l1 import media, window  # noqa: E402
from friday.l3 import executor  # noqa: E402
from friday.l4 import planner  # noqa: E402
from friday.observability import set_run_id  # noqa: E402

RUN_LABEL = sys.argv[1] if len(sys.argv) > 1 else "gate6-dod"
TEST_TONE = ROOT / "assets" / "test_tone.mp3"

GOAL = "pause whatever's playing, then close every window except my terminal"

PROTECTED_CLASS = "kitty"  # terminals - never closable


def _clients() -> list[dict[str, Any]]:
    return window.list_clients()


def _fmt(c: dict) -> str:
    return (f"{c.get('class')} | {str(c.get('title', ''))[:40]} "
            f"| ws {c.get('workspace', {}).get('id')} | {c.get('address')}")


def _hyprctl_raw() -> str:
    try:
        return subprocess.run(
            ["hyprctl", "clients", "-j"], capture_output=True, text=True, timeout=15
        ).stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "(hyprctl unavailable)"


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
            f"-> {str(outcome)[:140]}{extra}"
        )


def _close_steps_are_safe_and_sufficient(plan: dict[str, Any]) -> tuple[bool, str]:
    """The plan must contain media.pause and a window-close step that can
    never close a protected (kitty) window, and every window.close_all
    step must verify with the SUFFICIENT check - checks.window_only_classes
    over the excluded classes (window_focused only proves focus, so a
    partial close could otherwise verify True). Returns (ok, reason)."""
    prims = [s["primitive"] for s in plan["steps"]]
    if "media.pause" not in prims:
        return False, "plan never calls media.pause"
    close_steps = [s for s in plan["steps"] if s["primitive"] in ("window.close_all", "window.close_window")]
    if not close_steps:
        return False, "plan has no window-close step - 'close every window' is unsatisfied"
    if "window.close_all" not in prims:
        # 'close EVERY window except my terminal' is satisfiable only by
        # close_all - a close_window-only plan could leave other
        # non-terminal windows open and still verify per-step.
        return False, "plan closes windows but never calls window.close_all - 'every window' is unsatisfiable"
    for s in close_steps:
        args = s.get("args") or {}
        v = s.get("verify") or {}
        if s["primitive"] == "window.close_all":
            exc = args.get("exclude_classes") or []
            if not any(PROTECTED_CLASS in str(e).lower() for e in exc):
                return False, f"close_all exclude_classes {exc!r} does not protect {PROTECTED_CLASS!r}"
            v_check = str(v.get("check", ""))
            if not v_check.endswith("window_only_classes"):
                return False, (
                    f"close_all step verifies with {v_check!r}; must use "
                    "checks.window_only_classes - window_focused proves only focus, "
                    "not that everything else closed"
                )
            v_classes = (v.get("args") or {}).get("classes") or []
            missing = [e for e in exc if not any(
                str(e).lower() == str(c).lower() for c in v_classes
            )]
            if missing:
                return False, (
                    f"close_all verify classes {v_classes!r} do not cover excluded "
                    f"classes {missing!r}"
                )
            if v.get("expect") is not True:
                return False, "close_all verify expect must be true"
        else:  # window.close_window
            sel = str(args.get("selector", ""))
            if PROTECTED_CLASS in sel.lower():
                return False, f"close_window selector {sel!r} could match a protected {PROTECTED_CLASS} window"
    return True, "safe and sufficient"


def main() -> None:
    print("=" * 72)
    print("GATE 6 DoD - first real composite, full unmodified pipeline")
    print("=" * 72)
    print(f"GOAL STRING (verbatim): {GOAL!r}")
    set_run_id(RUN_LABEL)

    # ---- independent world state BEFORE (DoD item 5) ----
    before = _clients()
    protected_addrs = {
        str(c["address"]) for c in before
        if PROTECTED_CLASS in str(c.get("class", "")).lower()
    }
    active = window.get_active_window()
    active_addr = str(active.get("address")) if active else None
    print(f"\n[before] {len(before)} clients (raw hyprctl clients -j):")
    print(_hyprctl_raw())
    for c in before:
        print(f"  {_fmt(c)}")
    print(f"[before] active window: {active_addr}")
    print(f"[before] protected (terminal) addresses: {sorted(protected_addrs)}")

    # ---- real-world precondition: something IS playing ----
    print(f"\n[precondition] starting the test tone at volume 30 ('whatever's playing')")
    media.play(str(TEST_TONE), volume=30)
    time.sleep(0.6)
    playing = media.is_playing()
    print(f"[precondition] media.is_playing() -> {playing} (expect True)")
    if not playing:
        print("FAIL: precondition - nothing is playing; cannot prove a real pause")
        sys.exit(1)

    # ---- the ONLY input: the goal string ----
    print("\n--- L4: LLM planning ---")
    prompt = planner.build_prompt(GOAL)
    prompt_path = Path(f"/tmp/{RUN_LABEL}_prompt.txt")
    prompt_path.write_text(prompt)
    print(f"(full prompt at {prompt_path}; also printed below)")
    llm_plan = planner.plan(GOAL, run_id=f"{RUN_LABEL}-plan")
    print("\nGENERATED PLAN JSON:")
    print(json.dumps(llm_plan, indent=2))

    # ---- safety interlock: refuse BEFORE executing anything ----
    safe, reason = _close_steps_are_safe_and_sufficient(llm_plan)
    if not safe:
        print(f"\nREFUSING TO EXECUTE (safety): {reason}")
        print("The refused plan is printed above - this is data, not a silent fix.")
        media.stop()
        print(f"\nGATE 6 DoD: FAILED (refused before execution)")
        sys.exit(3)

    # ---- L3: unmodified executor ----
    print("\n--- L3: unmodified executor runs the plan ---")
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
    except Exception as exc:
        print(f"plan status: RAISED {type(exc).__name__}: {exc}")

    # ---- independent world state AFTER (DoD item 5) ----
    time.sleep(0.4)
    after = _clients()
    after_addrs = {str(c["address"]) for c in after}
    print(f"\n[after] {len(after)} clients (raw hyprctl clients -j):")
    print(_hyprctl_raw())
    for c in after:
        print(f"  {_fmt(c)}")
    paused = not media.is_playing()
    print(f"[after] media.is_playing() -> {not paused} (expect False - paused)")

    dump(f"{RUN_LABEL}-plan", "L4 planning")
    dump(f"{RUN_LABEL}-exec", "execution (real composite)")

    # ---- DoD ----
    problems: list[str] = []
    if result is None:
        problems.append("executor ABORTed before completing")
    elif result.status != "COMPLETED" or not all(s.status == "VERIFIED" for s in result.steps):
        problems.append(f"not every step VERIFIED (status={result.status})")
    missing_protected = protected_addrs - after_addrs
    if missing_protected:
        problems.append(f"PROTECTED window closed: {sorted(missing_protected)}")
    # The 'read through' window is by definition one of the PROTECTED
    # terminals - assert survival only when the window focused at start WAS
    # protected. A non-protected window focused at start (e.g. a
    # precondition-staged test window, which grabs focus) is supposed to be
    # closed by the goal; flagging it would be a false positive (this was
    # a real guard bug, found by run gate6-dod-d).
    if active_addr in protected_addrs and active_addr not in after_addrs:
        problems.append(f"the window this run was read through was closed: {active_addr}")
    non_protected_before = [c for c in before if str(c["address"]) not in protected_addrs]
    non_protected_after = [c for c in after if str(c["address"]) not in protected_addrs]
    if non_protected_before and non_protected_after:
        problems.append(f"non-terminal window(s) survived close: "
                        f"{[c['address'] for c in non_protected_after]}")
    if not non_protected_before:
        problems.append("nothing non-terminal was open before - the close effect is untested")
    if not paused:
        problems.append("media is still playing after the run - pause did not land")

    print("\n=== GATE 6 DoD (raw L0 trace + independent hyprctl before/after) ===")
    for p in problems:
        print(f"  FAIL: {p}")
    if not problems:
        print(f"  OK: goal -> LLM plan -> executor -> verified real-world effect")
        print(f"  OK: {len(non_protected_before)} non-terminal client(s) closed "
              f"({[c['class'] for c in non_protected_before]}); "
              f"{len(protected_addrs)} protected terminal(s) survived incl. the active window")
        print("  OK: close_all verified by checks.window_only_classes - the SUFFICIENT "
              "check (nothing outside the excluded set remains), not just focus")
        print(f"  OK: media paused (is_playing False) - the 'whatever's playing' step was real")
    ok = not problems

    # ---- counter (Section 4 of the Gate 6 plan) ----
    reg = ROOT / "var" / "logs" / "tasks.jsonl"
    reg.parent.mkdir(parents=True, exist_ok=True)
    line = {"task_id": "gate6", "goal": GOAL, "gate6_passed": bool(ok),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "proof": "gates/GATE6_DOD_PROOF.md"}
    with reg.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line) + "\n")

    media.stop()
    print(f"\nGATE 6 DoD: {'DONE' if ok else 'FAILED'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
