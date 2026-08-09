#!/usr/bin/env python
"""Lifecycle fix gate for friday/l1/media.py (mpv orphan leak + zombie-not-reaped).

Claude Code flagged two defects in the L1 media primitives: (1) an mpv
orphan-process leak - the orphan sweep only ever sent SIGTERM, slept, and
never verified death, so a stuck player (SIGTERM-ignoring / SIGSTOPped /
blocked) survived; (2) zombie-not-reaped - _stop_locked terminated a child
without a second wait, and the _launch failure path dropped the reference
before anyone could wait(), so an exited child lingered as a zombie for the
rest of the process's life.

The fix (media.py): an escalation ladder in _stop_process (socket quit ->
SIGTERM -> SIGKILL, each rung waits), always-reap everywhere a child is
stopped, and a sweep that escalates survivors to SIGKILL and verifies they
are really gone.

This gate proves it. SIGSTOP is the perfect stubborn-player simulator: a
stopped process cannot run signal handlers, so SIGTERM can never kill it -
only the SIGKILL escalation can. Every check reads real process state via
`ps`/`pgrep` (independent of the media module's own helpers).

Run:  ./.venv/bin/python -u gates/fix_mpv_lifecycle.py [run_label]
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.l1 import media  # noqa: E402
from friday.observability import set_run_id  # noqa: E402

RUN_LABEL = sys.argv[1] if len(sys.argv) > 1 else "fix-mpv-lifecycle"

TEST_TONE = ROOT / "assets" / "test_tone.mp3"
SOCKET = media.SOCKET_PATH


# ------------------------------------------------------------------ helpers


def _pid_exists(pid: int) -> bool:
    """True if the pid is still a process-table entry (incl. zombies)."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def _socket_procs() -> list[int]:
    """Independent pgrep for processes naming our IPC socket path."""
    try:
        out = subprocess.run(
            ["pgrep", "-f", f"mpv.*input-ipc-server={SOCKET}"],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    return [int(p) for p in out.stdout.split() if p.strip().isdigit()]


def _zombies_on_socket(tracked: set[int]) -> list[str]:
    """ps entries with stat 'Z' whose args reference our socket path.

    A zombie's /proc cmdline is empty, so its `ps args` column is blank and
    a text match on SOCKET alone would false-negative. Match tracked pids
    explicitly too (their pid identifies them even without a cmdline). This
    is belt-and-suspenders: the authoritative reap check is _pid_exists on
    each tracked pid - a zombie is still a process-table entry, so a True
    from _pid_exists is the real failure signal.
    """
    try:
        out = subprocess.run(
            ["ps", "-eo", "pid=,stat=,args="],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    return [
        line.strip() for line in out.stdout.splitlines()
        if line.split()[1].startswith("Z")
        and (SOCKET in line or int(line.split()[0]) in tracked)
    ]


def _socket_file_gone() -> bool:
    return not os.path.exists(SOCKET)


def _dump(run_id: str, label: str) -> None:
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
        print(
            f"[{rec['timestamp']}] {rec['layer']} step={rec['step_id']} {rec['primitive']:28s} "
            f"-> {str(outcome)[:90]}"
        )


def _sanity_preflight() -> list[str]:
    problems: list[str] = []
    procs = _socket_procs()
    if procs:
        problems.append(f"preflight: {len(procs)} mpv process(es) already on {SOCKET}: {procs}")
    if not _socket_file_gone():
        problems.append(f"preflight: stale socket file present at {SOCKET}")
    if not TEST_TONE.exists():
        problems.append(f"preflight: test tone missing at {TEST_TONE}")
    return problems


# ---------------------------------------------------------------- section A
# normal path re-prove: the fix must not have regressed the happy path


def section_normal() -> list[str]:
    print("\n" + "=" * 72)
    print("SECTION A - normal path re-prove (play/pause/resume/stop)")
    print("=" * 72)
    problems: list[str] = []

    print(f"\n[a1] media.play_for(0.1, test_tone) -> ", end="")
    launched = media.play_for(0.1, str(TEST_TONE), volume=30)
    print(f"{launched}")
    pid = int(launched["pid"])
    time.sleep(0.5)
    print(f"[a2] media.is_playing() -> {media.is_playing()}  (expect True)")
    if not media.is_playing():
        problems.append("a2: media not playing after play_for")

    print(f"[a3] media.pause() -> {media.pause()}")
    time.sleep(0.5)
    print(f"[a4] media.is_playing() -> {media.is_playing()}  (expect False - paused)")
    if media.is_playing():
        problems.append("a4: is_playing True while paused")

    print(f"[a5] media.resume() -> {media.resume()}")
    time.sleep(0.5)
    print(f"[a6] media.is_playing() -> {media.is_playing()}  (expect True - resumed)")
    if not media.is_playing():
        problems.append("a6: media not playing after resume")

    t0 = time.monotonic()
    print(f"[a7] media.stop() -> {media.stop()}")
    print(f"[a7] stop took {time.monotonic() - t0:.1f}s (fast: quit over socket worked)")
    time.sleep(0.5)
    print(f"[a8] media.is_playing() -> {media.is_playing()}  (expect False - stopped)")
    if media.is_playing():
        problems.append("a8: media still playing after stop")

    procs = _socket_procs()
    zombies = _zombies_on_socket({pid})
    print(f"[a9] mpv processes bound to socket -> {procs}  (expect [])")
    print(f"[a9] zombie mpv entries -> {zombies}  (expect [] - informational; b4/b6 style")
    print(f"      pid-existence checks are the authoritative reap proof)")
    print(f"[a9] socket file gone -> {_socket_file_gone()}  (expect True)")
    if procs:
        problems.append(f"a9: {len(procs)} mpv process(es) survived the normal stop")
    if zombies:
        problems.append(f"a9: zombie(s) left after the normal stop: {zombies}")
    if not _socket_file_gone():
        problems.append("a9: socket file still present after stop")

    print("\n--- SECTION A DoD ---")
    if problems:
        for p in problems:
            print(f"  FAIL: {p}")
    else:
        print("  OK: play -> True; pause -> False; resume -> True; stop -> False;")
        print("      zero mpv processes, zero zombies, socket file gone")
    return problems


# ---------------------------------------------------------------- section B
# stubborn IN-PROCESS player: SIGSTOP makes SIGTERM impossible; only the
# SIGKILL escalation + reap can remove it. This is the zombie-not-reaped fix.


def section_stubborn_owned() -> list[str]:
    print("\n" + "=" * 72)
    print("SECTION B - SIGSTOPped in-process player: killed AND reaped (no zombie)")
    print("=" * 72)
    problems: list[str] = []

    print(f"\n[b1] media.play_for(0.1, test_tone) -> ", end="")
    launched = media.play_for(0.1, str(TEST_TONE), volume=30)
    print(f"{launched}")
    pid = int(launched["pid"])
    os.kill(pid, signal.SIGSTOP)
    print(f"[b2] SIGSTOP sent to player pid {pid} (now unable to process SIGTERM)")

    t0 = time.monotonic()
    media.stop()
    took = time.monotonic() - t0
    print(f"[b3] media.stop() on the stopped player took {took:.1f}s "
          f"(quit+SIGTERM rungs had to time out before SIGKILL)")

    print(f"[b4] pid {pid} still in the process table -> {_pid_exists(pid)}  (expect False)")
    if _pid_exists(pid):
        problems.append(f"b4: player pid {pid} survived stop() - SIGKILL escalation did not fire")
    zombies = _zombies_on_socket({pid})
    print(f"[b5] zombie mpv entries -> {zombies}  (expect [] - reaped)")
    if zombies:
        problems.append(f"b5: zombie(s) left after killing the stuck player: {zombies}")
    procs = _socket_procs()
    print(f"[b6] mpv processes bound to socket -> {procs}  (expect [])")
    print(f"[b6] socket file gone -> {_socket_file_gone()}  (expect True)")
    if procs:
        problems.append(f"b6: mpv process(es) still bound after stop: {procs}")
    if not _socket_file_gone():
        problems.append("b6: socket file still present after stop")
    print(f"[b7] media.is_playing() -> {media.is_playing()}  (expect False)")
    if media.is_playing():
        problems.append("b7: is_playing True with no player")

    print("\n--- SECTION B DoD ---")
    if problems:
        for p in problems:
            print(f"  FAIL: {p}")
    else:
        print("  OK: SIGSTOPped (SIGTERM-proof) player was killed by SIGKILL escalation")
        print("      and reaped - no process survives, no zombie is left")
    return problems


# ---------------------------------------------------------------- section C
# stubborn ROGUE player on the socket: simulates a prior run's leaked player.
# The orphan sweep must kill it (SIGKILL escalation), not just nudge it.


def section_stubborn_rogue() -> list[str]:
    print("\n" + "=" * 72)
    print("SECTION C - SIGSTOPped rogue player: swept by the orphan sweep")
    print("=" * 72)
    problems: list[str] = []
    rogue: subprocess.Popen | None = None

    rogue = subprocess.Popen(
        ["mpv", "--no-terminal",
         f"--input-ipc-server={SOCKET}", "--volume=30", str(TEST_TONE)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    # wait for the rogue to bind the socket, then freeze it with SIGSTOP so
    # SIGTERM cannot kill it - the classic stuck-player case.
    deadline = time.monotonic() + 6.0
    while time.monotonic() < deadline and not os.path.exists(SOCKET):
        time.sleep(0.2)
    os.kill(rogue.pid, signal.SIGSTOP)
    print(f"\n[c1] rogue mpv pid {rogue.pid} launched and SIGSTOPped on {SOCKET}")
    print(f"[c2] rogue alive (stopped) -> {_pid_exists(rogue.pid)}  (expect True)")
    if not _pid_exists(rogue.pid):
        problems.append("c2: rogue died before the test - the scenario did not set up")
        rogue = None

    if rogue is not None:
        print(f"[c3] media.play_for(0.1, test_tone) -> ", end="")
        launched = media.play_for(0.1, str(TEST_TONE), volume=30)
        print(f"{launched}")
        # play_for's internal sweep must have SIGKILLed the rogue for the new
        # player to bind and answer - otherwise play_for would have raised.
        try:
            rogue.wait(timeout=3.0)  # reap our own child (the script's, not Friday's)
        except subprocess.TimeoutExpired:
            pass
        print(f"[c4] rogue pid {rogue.pid} gone -> {not _pid_exists(rogue.pid)}  (expect True)")
        if _pid_exists(rogue.pid):
            problems.append("c4: rogue player survived the orphan sweep - SIGTERM-only again")
        zombies = _zombies_on_socket({rogue.pid})
        print(f"[c5] zombie mpv entries -> {zombies}  (expect [] - reaped)")
        if zombies:
            problems.append(f"c5: zombie(s) left: {zombies}")

        t0 = time.monotonic()
        media.stop()
        print(f"[c6] media.stop() took {time.monotonic() - t0:.1f}s")
        procs = _socket_procs()
        print(f"[c7] mpv processes bound to socket -> {procs}  (expect [])")
        print(f"[c7] socket file gone -> {_socket_file_gone()}  (expect True)")
        if procs:
            problems.append(f"c7: mpv process(es) still bound after stop: {procs}")
        if not _socket_file_gone():
            problems.append("c7: socket file still present after stop")

    print("\n--- SECTION C DoD ---")
    if problems:
        for p in problems:
            print(f"  FAIL: {p}")
    else:
        print("  OK: SIGSTOPped rogue player was swept (SIGKILL escalation), the new")
        print("      player bound cleanly, and everything stopped with zero residue")
    return problems


# ------------------------------------------------------------------- main


def main() -> None:
    print("=" * 72)
    print("LIFECYCLE FIX GATE - mpv orphan leak + zombie-not-reaped (media.py)")
    print("=" * 72)
    set_run_id(RUN_LABEL)

    all_problems: list[str] = _sanity_preflight()
    if all_problems:
        for p in all_problems:
            print(f"  FAIL: {p}")
        print("\nREFUSING TO RUN: environment is not clean (a prior run leaked state)")
        print(f"\nLIFECYCLE: FAILED")
        sys.exit(1)

    try:
        all_problems += section_normal()
        all_problems += section_stubborn_owned()
        all_problems += section_stubborn_rogue()
    except Exception as exc:
        all_problems.append(f"unexpected exception: {type(exc).__name__}: {exc}")
    finally:
        # hygiene - never leave a player behind, no matter what raised
        try:
            media.stop()
        except Exception as exc:
            print(f"  [cleanup] stop() failed: {exc}")

    _dump(RUN_LABEL, f"lifecycle fix {RUN_LABEL}")

    print("\n=== LIFECYCLE FIX DoD ===")
    for p in all_problems:
        print(f"  FAIL: {p}")
    if not all_problems:
        print("  OK: normal path green; SIGTERM-proof player killed+reaped; rogue swept;")
        print("      zero mpv processes, zero zombies, socket file gone at every checkpoint")
    ok = not all_problems

    print(f"\nLIFECYCLE: {'DONE' if ok else 'FAILED'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
