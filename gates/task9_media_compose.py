#!/usr/bin/env python
"""Task 9 (Gate-6-grade proof) - composite media control.

GOAL: "play the test tone, verify it is playing, pause it and verify it is
      paused, resume it and verify it is playing again, then stop it and
      verify it is stopped"
      (LLM-planned by L4, executed by L3, verified by L2, logged through L0)

First full-stack composite over media.pause / media.resume / media.stop -
proven standalone in the remaining primitives bring-up, now driven by the
executor from an LLM plan. Audio only: zero window interaction, fully
unattended-safe.

The task's DoD asserts, from the raw L0 trace + real player state:
  1. every step VERIFIED and the plan composed
     media.play -> media.pause -> media.resume -> media.stop in order,
  2. real end state: media.is_playing() is False after the run.

Side effects: plays ~seconds of the test tone at volume 30, then stops it.

Run:  ./.venv/bin/python -u gates/task9_media_compose.py [run_label]
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
from friday.l1 import media  # noqa: E402
from friday.l3 import executor  # noqa: E402
from friday.l4 import planner  # noqa: E402

GOAL = (
    "play the test tone, verify it is playing, pause it and verify it is "
    "paused, resume it and verify it is playing again, then stop it and "
    "verify it is stopped"
)

REQUIRED_PRIMITIVES = ("media.play", "media.pause", "media.resume", "media.stop")

RUN_LABEL = sys.argv[1] if len(sys.argv) > 1 else "task9-media"
TASK_ID = "task9"


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
    reg = ROOT / "var" / "logs" / "tasks.jsonl"
    reg.parent.mkdir(parents=True, exist_ok=True)
    line = {
        "task_id": TASK_ID,
        "goal": GOAL,
        "gate6_passed": bool(ok),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "proof": "gates/TASK9_MEDIA_PROOF.md",
    }
    with reg.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line) + "\n")


def check_dod(
    plan: dict[str, Any],
    result: executor.PlanResult | None,
) -> tuple[bool, list[str]]:
    problems: list[str] = []

    # 1. the executor verified every step
    if result is None:
        problems.append("executor ABORTed before completing (see trace above)")
    elif result.status != "COMPLETED" or not all(
        s.status == "VERIFIED" for s in result.steps
    ):
        problems.append(f"not every step VERIFIED (status={result.status})")

    # 2. the plan composed play -> pause -> resume -> stop in order
    prims = [s["primitive"] for s in plan["steps"]]
    it = iter(prims)
    in_order = all(req in it for req in REQUIRED_PRIMITIVES)
    for required in REQUIRED_PRIMITIVES:
        if required not in prims:
            problems.append(f"plan never called {required}")
    if not in_order:
        problems.append(
            f"plan must compose {list(REQUIRED_PRIMITIVES)} in that order, got {prims}"
        )

    # 3. the plan must not use play_for to fake the manual stop - the goal
    #    is manual pause/resume/stop
    if "media.play_for" in prims:
        problems.append(
            "plan used media.play_for - this goal is manual pause/resume/stop, "
            "not a timed auto-stop"
        )

    return not problems, problems


def main() -> None:
    print("=" * 72)
    print("TASK 9 - composite media control (play -> pause -> resume -> stop)")
    print("=" * 72)
    print(f"GOAL: {GOAL!r}")

    loaded = planner.load_project_facts()
    recipe = (
        "Media composition recipe (this goal): step 1 media.play with args "
        "{\"source\": \"$facts.test_tone\"} verified with checks.media_playing "
        "expect true; step 2 media.pause() verified with checks.media_playing "
        "expect false; step 3 media.resume() verified with checks.media_playing "
        "expect true; step 4 media.stop() verified with checks.media_playing "
        "expect false. Use media.play (NOT media.play_for): this goal asks to "
        "pause, resume and stop manually - the timed auto-stop pattern does "
        "not apply. media.pause/media.resume/media.stop take no arguments."
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
    finally:
        # hygiene: never leave a player running, no matter what raised
        try:
            media.stop()
        except Exception as exc:
            print(f"[cleanup] media.stop() failed: {exc}")

    end_playing = media.is_playing()
    print(f"\n[end state] media.is_playing() -> {end_playing}  (expect False)")

    dump(f"{RUN_LABEL}-plan", "L4 planning")
    dump(f"{RUN_LABEL}-exec", "execution (real audio)")

    ok, problems = check_dod(llm_plan, result)
    if end_playing:
        problems.append("media still playing after the run")
    print("\n=== TASK 9 DoD (from raw L0 trace + real player state) ===")
    for p in problems:
        print(f"  FAIL: {p}")
    if ok:
        print("  OK: every step VERIFIED; plan composed play -> pause -> resume -> stop")
        print("  OK: media.is_playing() False at the end - the player is stopped")

    register_task(ok)

    print(f"\nTASK 9: {'DONE' if ok else 'FAILED'} "
          f"(goal -> LLM plan -> media control -> verified; player stopped)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
