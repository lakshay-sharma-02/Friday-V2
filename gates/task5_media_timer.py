#!/usr/bin/env python
"""Task 5 (Gate-6-grade proof) - media one-shot timer, full stack.

GOAL: "play the test tone for 1 minute and verify that it stops playing on
      its own after the minute is up, without stopping it manually"
      (LLM-planned by L4, executed by L3, verified by L2, logged through L0)

First end-to-end proof that media's one-shot timer works through the whole
stack: the LLM plan must call media.play_for(minutes=1) and then prove
playback stops BY ITSELF (mpv --length=60 ends it at ~60s; a 75s safety
timer is the backstop). The task's DoD asserts, straight from the raw L0
trace:

  1. every step VERIFIED,
  2. the plan called media.play_for and NEVER media.stop/media.pause
     (a manual stop would mask the timer and prove nothing),
  3. checks.media_playing first went False ~60s after playback started
     (>= 45s), not instantly - that time gap IS the timer.

Side effects: plays ~1 minute of real audio (assets/test_tone.mp3, a 70s
440Hz tone, cut at 60s by mpv --length). mpv exits by itself; media.stop()
is called at the very end purely as hygiene (a no-op once nothing plays).

Run:  ./.venv/bin/python -u gates/task5_media_timer.py [run_label]
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.errors import FridayError  # noqa: E402
from friday.l1 import media  # noqa: E402
from friday.l3 import executor  # noqa: E402
from friday.l4 import planner  # noqa: E402

GOAL = (
    "play the test tone for 1 minute and verify that it stops playing on "
    "its own after the minute is up, without stopping it manually"
)

# Optional argv[1] labels the run so re-runs get fresh run_ids (L0 traces
# accumulate in one log file; reusing a run_id would mix attempts).
RUN_LABEL = sys.argv[1] if len(sys.argv) > 1 else "task5-media"

MIN_AUTOSTOP_GAP_S = 45.0  # DoD: auto-stop must be seen >= 45s after play starts
MASKING_PRIMITIVES = ("media.stop", "media.pause")  # would mask the timer


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


def _epoch(ts: str) -> float:
    return datetime.fromisoformat(ts).timestamp()


def _play_start_ts(records: list[dict[str, Any]]) -> float | None:
    """Timestamp of the L1 media.play_for result line (playback started)."""
    for rec in records:
        if (
            rec["layer"] == "L1"
            and rec["primitive"] == "media.play_for"
            and rec["result"] is not None
        ):
            return _epoch(rec["timestamp"])
    return None


def _first_stopped_ts(
    records: list[dict[str, Any]], after_s: float
) -> float | None:
    """Timestamp of the first L2 checks.media_playing -> False line that is
    clearly AFTER playback started (skips the one-or-two startup polls that
    can catch mpv still idling in the first seconds). NOTE: the executor's
    verify poll STOPS at the first matching value, so an honest run carries
    exactly one False line - the one that ended the verification. A
    "persist across consecutive polls" variant would therefore never match;
    the >= MIN_AUTOSTOP_GAP_S timing requirement is what keeps this honest
    (a run that never really played, or stopped early, fails the gap)."""
    start = _play_start_ts(records)
    if start is None:
        return None
    for rec in records:
        if (
            rec["layer"] == "L2"
            and rec["primitive"] == "checks.media_playing"
            and rec["result"] is False
            and _epoch(rec["timestamp"]) >= start + after_s
        ):
            return _epoch(rec["timestamp"])
    return None


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

    # 2. the plan proves the TIMER, not a manual stop
    prims = [s["primitive"] for s in plan["steps"]]
    if "media.play_for" not in prims:
        problems.append("plan never called media.play_for")
    for masked in MASKING_PRIMITIVES:
        if masked in prims:
            problems.append(
                f"plan masks the timer with {masked} - auto-stop unproven"
            )

    # 3. auto-stop was actually OBSERVED, ~1 minute after start
    start = _play_start_ts(records)
    if start is None:
        problems.append("no media.play_for result line in the L0 trace")
    else:
        stopped = _first_stopped_ts(records, after_s=10.0)
        if stopped is None:
            problems.append(
                "checks.media_playing never went False in the trace "
                "(auto-stop never observed)"
            )
        else:
            gap = stopped - start
            if gap < MIN_AUTOSTOP_GAP_S:
                problems.append(
                    f"auto-stop observed after only {gap:.1f}s "
                    f"(DoD requires >= {MIN_AUTOSTOP_GAP_S}s) - it stopped "
                    "too early, the timer never ran"
                )

    return not problems, problems


def main() -> None:
    print("=" * 72)
    print("TASK 5 - media one-shot timer (play_for auto-stop) full stack")
    print("=" * 72)
    print(f"GOAL: {GOAL!r}")

    print("\n--- L4: LLM planning ---")
    llm_plan = planner.plan(GOAL, run_id=f"{RUN_LABEL}-plan")
    print("LLM-produced plan JSON:")
    print(json.dumps(llm_plan, indent=2))

    print("\n--- L3: executor runs the LLM plan (real audio) ---")
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
    dump(f"{RUN_LABEL}-exec", "execution (real audio)")

    # DoD: read the raw L0 records for this run and check the timer honestly
    log = ROOT / "var" / "logs" / "friday.jsonl"
    records = [
        json.loads(l) for l in log.read_text().splitlines()
        if json.loads(l).get("run_id") == f"{RUN_LABEL}-exec"
    ]
    ok, problems = check_dod(llm_plan, result, records)
    print("\n=== TASK 5 DoD (from raw L0 trace) ===")
    for p in problems:
        print(f"  FAIL: {p}")
    if ok:
        start = _play_start_ts(records)
        stopped = _first_stopped_ts(records, after_s=10.0)
        print("  OK: every step VERIFIED")
        print(f"  OK: play started, auto-stop observed after {stopped - start:.1f}s")
        print("  OK: no media.stop/media.pause in the plan - the stop was the timer's")

    # hygiene: nothing left bound to the socket (no-op when already stopped)
    media.stop()

    print(f"\nTASK 5: {'DONE' if ok else 'FAILED'} "
          f"(goal -> LLM plan -> play_for -> auto-stop verified in trace)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
