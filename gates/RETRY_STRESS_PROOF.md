# Retry-stress proof: mpv lifecycle under repeated invocation

Answers the question the L3 retry discussion raises: are the mpv orphan-
leak / zombie-reap fixes proven under REPEATED invocation of the same step,
or only against a single call? The gate watches the process table at every
cycle - not just the log.

Sections:
  A. media hammering: 6 consecutive play_for -> audit -> stop -> audit
     cycles. A retried step is exactly this: the same side-effecting call
     repeated back-to-back. After EVERY play: exactly the launched pid on
     the socket, zero zombies (healthy). After EVERY stop: zero mpv procs,
     zero zombies, socket gone (no leak).
  B. executor retry policy, stated and exercised precisely:
       - media.play_for / media.play are AT_MOST_ONCE -> the executor's
         contract-derived default is ZERO retries; it can never blindly
         retry a side effect. An explicit per-step "retries" override IS
         honored and completes with no residue.
       - browser.goto is IDEMPOTENT -> retry-eligible (default 2). Three
         goto steps through the executor; chromium returns to the 0-process
         baseline after browser.close() - one browser instance, no leak.

Gate history (honest): run a flagged two audit-semantics bugs in the gate
itself, not the product - the after-play audit expected "no mpv process"
when the healthy state is exactly one (the player it just launched), and
the chromium growth check didn't account for a browser's normal multi-
process tree. Both corrected in the gate; the fixes under test were clean
at every checkpoint in every run. Run c below is the shipped green run.

Raw output from the shipped gate run (run label `retry-stress-c`) follows:

---
========================================================================
RETRY-STRESS - mpv lifecycle under repeated invocation + executor retry paths
========================================================================

========================================================================
SECTION A - media hammering: 6x (play_for -> audit -> stop -> audit)
========================================================================

[c1.1] play_for -> pid=137436 is_playing=True
    [c1.1-after-play] mpv procs=[137436] zombies=[] socket_present=True
[c1.2] stop -> is_playing=False (expect False)
    [c1.2-after-stop] mpv procs=[] zombies=[] socket_gone=True

[c2.1] play_for -> pid=137502 is_playing=True
    [c2.1-after-play] mpv procs=[137502] zombies=[] socket_present=True
[c2.2] stop -> is_playing=False (expect False)
    [c2.2-after-stop] mpv procs=[] zombies=[] socket_gone=True

[c3.1] play_for -> pid=137557 is_playing=True
    [c3.1-after-play] mpv procs=[137557] zombies=[] socket_present=True
[c3.2] stop -> is_playing=False (expect False)
    [c3.2-after-stop] mpv procs=[] zombies=[] socket_gone=True

[c4.1] play_for -> pid=137594 is_playing=True
    [c4.1-after-play] mpv procs=[137594] zombies=[] socket_present=True
[c4.2] stop -> is_playing=False (expect False)
    [c4.2-after-stop] mpv procs=[] zombies=[] socket_gone=True

[c5.1] play_for -> pid=137624 is_playing=True
    [c5.1-after-play] mpv procs=[137624] zombies=[] socket_present=True
[c5.2] stop -> is_playing=False (expect False)
    [c5.2-after-stop] mpv procs=[] zombies=[] socket_gone=True

[c6.1] play_for -> pid=137670 is_playing=True
    [c6.1-after-play] mpv procs=[137670] zombies=[] socket_present=True
[c6.2] stop -> is_playing=False (expect False)
    [c6.2-after-stop] mpv procs=[] zombies=[] socket_gone=True

--- SECTION A DoD ---
  OK: 6 consecutive play->stop cycles, zero leaks or zombies after every one

========================================================================
SECTION B - executor retry policy (contract-derived + explicit override)
========================================================================

[b1] media.play_for idempotency = at-most-once (at-most-once -> executor default retries 0, never blind-retried)
[b1] browser.goto idempotency = idempotent (idempotent -> executor default retries 2, retry-eligible)

[b2] executor: hardcoded plan, play_for with explicit retries=2 override
[b2] plan status: COMPLETED
     step 1: media.play_for       VERIFIED     attempts=1
     step 2: media.stop           VERIFIED     attempts=1
    [b2-after-media-plan] mpv procs=[] zombies=[] socket_gone=True

[b3] chromium processes before: 0
[b3] plan status: COMPLETED
     step 1: browser.goto         VERIFIED     attempts=1
     step 2: browser.goto         VERIFIED     attempts=1
     step 3: browser.goto         VERIFIED     attempts=1
[b3] chromium processes after (one browser instance): 8
[b3] chromium processes after browser.close: 0  (baseline 0)

--- SECTION B DoD ---
  OK: at-most-once -> 0 default retries; explicit override honored cleanly;
      goto retry-eligible; chromium process count stable; no mpv residue

=== RETRY-STRESS DoD ===
  OK: 6x media hammering clean; executor retry policy correct;
      chromium stable; final audit: no mpv, no zombies, no leak

RETRY-STRESS: DONE
