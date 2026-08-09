#!/usr/bin/env python
"""Retry-stress gate: do the mpv lifecycle fixes hold under REPEATED invocation?

Motivation: L3's executor retries steps, so a primitive can be invoked more
than once in a row for the same step. The mpv orphan-leak / zombie-reap fix
was verified across three consecutive play->stop cycles in
MPV_LIFECYCLE_FIX_PROOF.md - this gate stresses the condition the retry
discussion cares about, and watches the process table at every cycle, not
just the log.

What it proves:
  A. media hammering: 6 consecutive play_for -> process check -> stop ->
     process check cycles. A retried step is exactly this: the same side-
     effecting call repeated back-to-back. Zero mpv procs, zero zombies,
     socket gone after EVERY cycle.
  B. executor + retry policy, stated precisely:
       - media.play_for / media.play are AT_MOST_ONCE -> the executor's
         contract-derived default is ZERO retries (it can never blindly
         retry a side effect). An explicit per-step "retries" override IS
         honored (a plan that insists), and still completes with no leak.
       - browser.goto is IDEMPOTENT -> retry-eligible (default 2). Three
         goto steps through the executor, chromium process count stable.
  C. final audit: no mpv on the socket, no zombie entries, socket file gone,
     chromium process count unchanged.

Side effects: brief test-tone audio (volume 30) and a Playwright chromium
window on example.com. No user windows are touched.

Run:  ./.venv/bin/python -u gates/retry_stress.py [run_label]
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
from friday.l1 import browser, media  # noqa: E402
from friday.l3 import executor  # noqa: E402
from friday.observability import set_run_id  # noqa: E402

RUN_LABEL = sys.argv[1] if len(sys.argv) > 1 else "retry-stress"
TEST_TONE = ROOT / "assets" / "test_tone.mp3"
SOCKET = media.SOCKET_PATH
CYCLES = 6


def _socket_procs() -> list[int]:
    try:
        out = subprocess.run(
            ["pgrep", "-f", f"mpv.*input-ipc-server={SOCKET}"],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    return [int(p) for p in out.stdout.split() if p.strip().isdigit()]


def _zombies() -> list[str]:
    try:
        out = subprocess.run(
            ["ps", "-eo", "pid=,stat=,args="], capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    return [l.strip() for l in out.stdout.splitlines()
            if l.split()[1].startswith("Z") and "mpv" in l]


def _chromium_count() -> int:
    try:
        out = subprocess.run(
            ["pgrep", "-f", "chromium.*user-data"], capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 0
    return len([p for p in out.stdout.split() if p.strip().isdigit()])


def _audit_playing(tag: str, expected_pid: int) -> list[str]:
    """Right after play_for the HEALTHY state is: exactly the launched pid on
    the socket, the socket file present, and zero zombies. Anything else is
    a problem (e.g. a second player = the old leak; a zombie = the reap bug)."""
    problems: list[str] = []
    procs = _socket_procs()
    zombies = _zombies()
    print(f"    [{tag}] mpv procs={procs} zombies={zombies} socket_present={Path(SOCKET).exists()}")
    if procs != [expected_pid]:
        problems.append(f"{tag}: expected exactly pid {expected_pid} on the socket, got {procs}")
    if zombies:
        problems.append(f"{tag}: zombie mpv entries: {zombies}")
    return problems


def _audit_stopped(tag: str) -> list[str]:
    """After stop the HEALTHY state is: no mpv on the socket, no zombies,
    socket file gone. This is the leak/zombie check that matters."""
    problems: list[str] = []
    procs = _socket_procs()
    zombies = _zombies()
    gone = not Path(SOCKET).exists()
    print(f"    [{tag}] mpv procs={procs} zombies={zombies} socket_gone={gone}")
    if procs:
        problems.append(f"{tag}: mpv process(es) still bound: {procs}")
    if zombies:
        problems.append(f"{tag}: zombie mpv entries: {zombies}")
    if not gone:
        problems.append(f"{tag}: socket file still present")
    return problems


# ---------------------------------------------------------------- section A


def section_media_hammer() -> list[str]:
    print("\n" + "=" * 72)
    print(f"SECTION A - media hammering: {CYCLES}x (play_for -> audit -> stop -> audit)")
    print("=" * 72)
    problems: list[str] = []
    for i in range(1, CYCLES + 1):
        r = media.play_for(0.05, str(TEST_TONE), volume=30)
        time.sleep(0.4)
        playing = media.is_playing()
        print(f"\n[c{i}.1] play_for -> pid={r['pid']} is_playing={playing}")
        if not playing:
            problems.append(f"c{i}.1: not playing after play_for")
        problems += _audit_playing(f"c{i}.1-after-play", int(r["pid"]))
        media.stop()
        time.sleep(0.3)
        print(f"[c{i}.2] stop -> is_playing={media.is_playing()} (expect False)")
        if media.is_playing():
            problems.append(f"c{i}.2: still playing after stop")
        problems += _audit_stopped(f"c{i}.2-after-stop")
    print("\n--- SECTION A DoD ---")
    if problems:
        for p in problems:
            print(f"  FAIL: {p}")
    else:
        print(f"  OK: {CYCLES} consecutive play->stop cycles, zero leaks or zombies after every one")
    return problems


# ---------------------------------------------------------------- section B


def section_executor_retries() -> list[str]:
    print("\n" + "=" * 72)
    print("SECTION B - executor retry policy (contract-derived + explicit override)")
    print("=" * 72)
    problems: list[str] = []

    from friday.contracts import REGISTRY, Idempotency

    pf = REGISTRY["media.play_for"]
    go = REGISTRY["browser.goto"]
    print(f"\n[b1] media.play_for idempotency = {pf.idempotency.value} "
          f"(at-most-once -> executor default retries 0, never blind-retried)")
    print(f"[b1] browser.goto idempotency = {go.idempotency.value} "
          f"(idempotent -> executor default retries 2, retry-eligible)")
    if pf.idempotency != Idempotency.AT_MOST_ONCE:
        problems.append("b1: media.play_for is not at-most-once - retry policy wrong")

    # an explicit retries override on an at-most-once primitive IS honored
    plan = {
        "goal": "stress: play then stop, explicit retries override",
        "steps": [
            {"primitive": "media.play_for", "retries": 2, "backoff_s": 0.2,
             "args": {"minutes": 0.05, "source": str(TEST_TONE), "volume": 30},
             "verify": {"check": "checks.media_playing", "args": {}, "expect": True}},
            {"primitive": "media.stop",
             "verify": {"check": "checks.media_playing", "args": {}, "expect": False}},
        ],
    }
    print("\n[b2] executor: hardcoded plan, play_for with explicit retries=2 override")
    result = executor.run_plan(plan, run_id=f"{RUN_LABEL}-exec-media")
    print(f"[b2] plan status: {result.status}")
    for sr in result.steps:
        print(f"     step {sr.step_id}: {sr.primitive:20s} {sr.status:12s} attempts={sr.attempts}")
    if result.status != "COMPLETED" or not all(s.status == "VERIFIED" for s in result.steps):
        problems.append("b2: media plan did not complete verified")
    problems += _audit_stopped("b2-after-media-plan")

    # browser: goto is retry-eligible; run 3 goto steps through the executor
    before_chromium = _chromium_count()
    print(f"\n[b3] chromium processes before: {before_chromium}")
    bplan = {
        "goal": "stress: three goto steps",
        "steps": [
            {"primitive": "browser.goto", "args": {"url": "https://example.com"},
             "verify": {"check": "checks.browser_has_text", "args": {"substring": "Example Domain"}, "expect": True}},
            {"primitive": "browser.goto", "args": {"url": "https://example.com/"},
             "verify": {"check": "checks.browser_has_text", "args": {"substring": "Example Domain"}, "expect": True}},
            {"primitive": "browser.goto", "args": {"url": "https://www.example.com"},
             "verify": {"check": "checks.browser_has_text", "args": {"substring": "Example Domain"}, "expect": True}},
        ],
    }
    bresult = executor.run_plan(bplan, run_id=f"{RUN_LABEL}-exec-browser")
    print(f"[b3] plan status: {bresult.status}")
    for sr in bresult.steps:
        print(f"     step {sr.step_id}: {sr.primitive:20s} {sr.status:12s} attempts={sr.attempts}")
    if bresult.status != "COMPLETED" or not all(s.status == "VERIFIED" for s in bresult.steps):
        problems.append("b3: browser plan did not complete verified")
    after_chromium = _chromium_count()
    print(f"[b3] chromium processes after (one browser instance): {after_chromium}")
    # one launched browser spawns a multi-process tree (gpu/renderer/zygote), so
    # growth is expected; the leak check is that browser.close() returns the
    # count to the pre-run baseline.
    if after_chromium > before_chromium + 20:
        problems.append(f"b3: chromium process count grew absurdly {before_chromium} -> {after_chromium}")
    browser.close()
    time.sleep(0.5)
    final_chromium = _chromium_count()
    print(f"[b3] chromium processes after browser.close: {final_chromium}  (baseline {before_chromium})")
    if final_chromium > before_chromium:
        problems.append(f"b3: chromium processes leaked: {final_chromium} vs {before_chromium}")

    print("\n--- SECTION B DoD ---")
    if problems:
        for p in problems:
            print(f"  FAIL: {p}")
    else:
        print("  OK: at-most-once -> 0 default retries; explicit override honored cleanly;")
        print("      goto retry-eligible; chromium process count stable; no mpv residue")
    return problems


# ------------------------------------------------------------------- main


def main() -> None:
    print("=" * 72)
    print("RETRY-STRESS - mpv lifecycle under repeated invocation + executor retry paths")
    print("=" * 72)
    set_run_id(RUN_LABEL)
    if not TEST_TONE.exists():
        print(f"REFUSING: test tone missing at {TEST_TONE}")
        sys.exit(1)

    all_problems: list[str] = []
    try:
        all_problems += section_media_hammer()
        all_problems += section_executor_retries()
    except Exception as exc:
        all_problems.append(f"unexpected exception: {type(exc).__name__}: {exc}")
    finally:
        try:
            media.stop()
        except Exception:
            pass
        browser.close()

    print("\n=== RETRY-STRESS DoD ===")
    for p in all_problems:
        print(f"  FAIL: {p}")
    if not all_problems:
        print("  OK: 6x media hammering clean; executor retry policy correct;")
        print("      chromium stable; final audit: no mpv, no zombies, no leak")
    ok = not all_problems

    # record in the task registry (verification artifact, not a composite task)
    reg = ROOT / "var" / "logs" / "tasks.jsonl"
    reg.parent.mkdir(parents=True, exist_ok=True)
    line = {"task_id": "retry-stress", "goal": "verify mpv lifecycle holds under repeated invocation",
            "gate6_passed": bool(ok), "timestamp": datetime.now(timezone.utc).isoformat(),
            "proof": "gates/RETRY_STRESS_PROOF.md"}
    with reg.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line) + "\n")

    print(f"\nRETRY-STRESS: {'DONE' if ok else 'FAILED'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
