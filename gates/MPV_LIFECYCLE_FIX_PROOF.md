# Fix proof: mpv orphan-process leak + zombie-not-reaped (friday/l1/media.py)

Two defects flagged in the L1 media primitives:

  1. **Orphan-process leak** - `_sweep_orphans()` sent only SIGTERM, slept
     0.6s, and never verified death. A stuck player (SIGTERM-ignoring /
     SIGSTOPped / blocked) survived and kept holding the IPC socket path.
  2. **Zombie-not-reaped** - `_stop_locked()` terminated a child without a
     second wait(), and the `_launch` failure path dropped the reference
     before anyone could wait(), so an exited child lingered as a zombie
     for the rest of the process's life.

The fix (media.py): an escalation ladder in `_stop_process` (socket quit ->
SIGTERM -> SIGKILL, each rung waits and reaps), always-reap wherever a child
is stopped, and a sweep that escalates SIGTERM survivors to SIGKILL and
verifies they are really gone.

The gate (`gates/fix_mpv_lifecycle.py`) proves it with SIGSTOP as the
stubborn-player simulator: a stopped process cannot run signal handlers, so
SIGTERM can never kill it - only the SIGKILL escalation can. All process
state is read independently via `pgrep`/`ps`; pid-existence checks are the
authoritative reap proof (a zombie is still a process-table entry, so its
pid would still be detected).

Sections:
  A. normal path re-prove (play/pause/resume/stop) - no regression
  B. SIGSTOPped IN-PROCESS player -> stop() must kill (SIGKILL) AND reap it
  C. SIGSTOPped ROGUE player on the socket -> the orphan sweep must kill it

Raw output from the shipped gate run (run label `fix-mpv-lifecycle-b`) follows:

---
========================================================================
LIFECYCLE FIX GATE - mpv orphan leak + zombie-not-reaped (media.py)
========================================================================

========================================================================
SECTION A - normal path re-prove (play/pause/resume/stop)
========================================================================

[a1] media.play_for(0.1, test_tone) -> {'pid': 119357, 'socket': '/tmp/friday_mpv.sock', 'length_s': 6, 'source': '/home/lakshay/Projects/Friday V2/assets/test_tone.mp3'}
[a2] media.is_playing() -> True  (expect True)
[a3] media.pause() -> None
[a4] media.is_playing() -> False  (expect False - paused)
[a5] media.resume() -> None
[a6] media.is_playing() -> True  (expect True - resumed)
[a7] media.stop() -> None
[a7] stop took 0.1s (fast: quit over socket worked)
[a8] media.is_playing() -> False  (expect False - stopped)
[a9] mpv processes bound to socket -> []  (expect [])
[a9] zombie mpv entries -> []  (expect [] - informational; b4/b6 style
      pid-existence checks are the authoritative reap proof)
[a9] socket file gone -> True  (expect True)

--- SECTION A DoD ---
  OK: play -> True; pause -> False; resume -> True; stop -> False;
      zero mpv processes, zero zombies, socket file gone

========================================================================
SECTION B - SIGSTOPped in-process player: killed AND reaped (no zombie)
========================================================================

[b1] media.play_for(0.1, test_tone) -> {'pid': 119422, 'socket': '/tmp/friday_mpv.sock', 'length_s': 6, 'source': '/home/lakshay/Projects/Friday V2/assets/test_tone.mp3'}
[b2] SIGSTOP sent to player pid 119422 (now unable to process SIGTERM)
[b3] media.stop() on the stopped player took 9.1s (quit+SIGTERM rungs had to time out before SIGKILL)
[b4] pid 119422 still in the process table -> False  (expect False)
[b5] zombie mpv entries -> []  (expect [] - reaped)
[b6] mpv processes bound to socket -> []  (expect [])
[b6] socket file gone -> True  (expect True)
[b7] media.is_playing() -> False  (expect False)

--- SECTION B DoD ---
  OK: SIGSTOPped (SIGTERM-proof) player was killed by SIGKILL escalation
      and reaped - no process survives, no zombie is left

========================================================================
SECTION C - SIGSTOPped rogue player: swept by the orphan sweep
========================================================================

[c1] rogue mpv pid 119567 launched and SIGSTOPped on /tmp/friday_mpv.sock
[c2] rogue alive (stopped) -> True  (expect True)
[c3] media.play_for(0.1, test_tone) -> {'pid': 119622, 'socket': '/tmp/friday_mpv.sock', 'length_s': 6, 'source': '/home/lakshay/Projects/Friday V2/assets/test_tone.mp3'}
[c4] rogue pid 119567 gone -> True  (expect True)
[c5] zombie mpv entries -> []  (expect [] - reaped)
[c6] media.stop() took 0.1s
[c7] mpv processes bound to socket -> []  (expect [])
[c7] socket file gone -> True  (expect True)

--- SECTION C DoD ---
  OK: SIGSTOPped rogue player was swept (SIGKILL escalation), the new
      player bound cleanly, and everything stopped with zero residue

=== L0 trace: lifecycle fix fix-mpv-lifecycle-b (19 lines, run_id=fix-mpv-lifecycle-b) ===
[2026-08-08T07:24:33.175+00:00] L1 step=None media.play_for               -> {'pid': 119357, 'socket': '/tmp/friday_mpv.sock', 'length_s': 6, 'source': '/home/lakshay/
[2026-08-08T07:24:33.678+00:00] L1 step=None media.is_playing             -> True
[2026-08-08T07:24:33.680+00:00] L1 step=None media.is_playing             -> True
[2026-08-08T07:24:33.681+00:00] L1 step=None media.pause                  -> None
[2026-08-08T07:24:34.185+00:00] L1 step=None media.is_playing             -> False
[2026-08-08T07:24:34.187+00:00] L1 step=None media.is_playing             -> False
[2026-08-08T07:24:34.188+00:00] L1 step=None media.resume                 -> None
[2026-08-08T07:24:34.690+00:00] L1 step=None media.is_playing             -> True
[2026-08-08T07:24:34.692+00:00] L1 step=None media.is_playing             -> True
[2026-08-08T07:24:34.835+00:00] L1 step=None media.stop                   -> None
[2026-08-08T07:24:35.336+00:00] L1 step=None media.is_playing             -> False
[2026-08-08T07:24:35.337+00:00] L1 step=None media.is_playing             -> False
[2026-08-08T07:24:35.655+00:00] L1 step=None media.play_for               -> {'pid': 119422, 'socket': '/tmp/friday_mpv.sock', 'length_s': 6, 'source': '/home/lakshay/
[2026-08-08T07:24:44.741+00:00] L1 step=None media.stop                   -> None
[2026-08-08T07:24:44.788+00:00] L1 step=None media.is_playing             -> False
[2026-08-08T07:24:44.788+00:00] L1 step=None media.is_playing             -> False
[2026-08-08T07:24:48.336+00:00] L1 step=None media.play_for               -> {'pid': 119622, 'socket': '/tmp/friday_mpv.sock', 'length_s': 6, 'source': '/home/lakshay/
[2026-08-08T07:24:48.460+00:00] L1 step=None media.stop                   -> None
[2026-08-08T07:24:48.502+00:00] L1 step=None media.stop                   -> None

=== LIFECYCLE FIX DoD ===
  OK: normal path green; SIGTERM-proof player killed+reaped; rogue swept;
      zero mpv processes, zero zombies, socket file gone at every checkpoint

LIFECYCLE: DONE
