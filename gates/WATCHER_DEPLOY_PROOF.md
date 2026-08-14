# WATCHER_DEPLOY_PROOF — persistent systemd service + heartbeat

Status date: 2026-08-10 (late night IST).

The watcher is no longer a proof script. It now runs as a persistent
systemd **user** service (`friday-watcher.service`) that starts at login,
restarts on failure, polls `config/watcher.json` every 30 s, fires the
enabled `morning-gmail-summary` trigger, and emits a `daemon.alive`
heartbeat every 60 s into the standard L0 log. Everything below is real
captured output from this machine — nothing synthetic.

## 1. The legacy deployment that was silently failing (found, not assumed)

The spec said "check for any existing service files first". There was a
deployment from July: `~/.config/systemd/user/friday-watch.service` +
`friday-watch.timer` (firing every 2 minutes) running
`python -m friday.cli watch --run-once`. **`friday.cli` no longer
exists.** The unit had been failing every 2 minutes since July. Journal
evidence from minutes before replacement:

```
Aug 10 23:28:16 lakshay python[40092]: /usr/bin/python: Error while finding module specification for 'friday.cli' (ModuleNotFoundError: No module named 'friday')
Aug 10 23:28:16 lakshay systemd[619]: friday-watch.service: Main process exited, code=exited, status=1/FAILURE
Aug 10 23:28:16 lakshay systemd[619]: friday-watch.service: Failed with result 'exit-code'.
Aug 10 23:28:16 lakshay systemd[619]: Failed to start Friday ambient watch cycle.
```

Action: disabled and removed the legacy units (so the machine stops
spawning a failing job every 2 minutes), installed
`deploy/friday-watcher.service` as the source of truth.

## 2. Install + enable (real commands, real output)

```
$ systemctl --user disable --now friday-watch.timer      # legacy: removed
$ rm -f ~/.config/systemd/user/friday-watch.service ~/.config/systemd/user/friday-watch.timer
$ cp deploy/friday-watcher.service ~/.config/systemd/user/
$ systemctl --user daemon-reload
$ systemctl --user enable --now friday-watcher.service
$ systemctl --user is-enabled friday-watcher.service
enabled
$ systemctl --user is-active friday-watcher.service
active
```

## 3. Real status under the running service

```
$ systemctl --user status friday-watcher.service --no-pager
● friday-watcher.service - Friday ambient watch loop (persistent daemon + heartbeat)
     Loaded: loaded (/home/lakshay/.config/systemd/user/friday-watcher.service; enabled; preset: enabled)
     Active: active (running) since Mon 2026-08-10 23:32:10 IST; 3min 8s ago
 Invocation: 6a73e0591c2c4eac8b084e32056fda8b
   Main PID: 43392 (python)
      Tasks: 1 (limit: 3874)
     Memory: 99.7M (peak: 278.1M)
        CPU: 16.870s
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/friday-watcher.service
             └─43392 "/home/lakshay/Projects/Friday V2/.venv/bin/python" -m friday.watcher --poll 30
```

## 4. The morning trigger fires and COMPLETES under the persistent service

The daemon's very first pass (23:29) found the 09:00 trigger past due for
today and fired it through the real stack — LLM plan, executor, L2
verification, notification. Task record (real, gate-6 format):

```json
{
  "task_id": "watch:morning-gmail-summary",
  "goal": "find the most recent unread email from $facts.gmail_sender and summarize it in at most 5 plain sentences",
  "gate6_passed": true,
  "timestamp": "2026-08-10T18:00:02.809582+00:00",
  "proof": "{\"trigger\": \"morning-gmail-summary\", \"status\": \"COMPLETED\", \"steps\": [{\"step_id\": 1, \"primitive\": \"gmail.list_unread\", \"status\": \"VERIFIED\", \"attempts\": 1}, {\"step_id\": 2, \"primitive\": \"gmail.get_message\", \"status\": \"VERIFIED\", \"attempts\": 1}, {\"step_id\": 3, \"primitive\": \"gmail.summarize\", \"status\": \"VERIFIED\", \"attempts\": 1}]}"
}
```

(3/3 steps VERIFIED — same trigger, same allowlist `["gmail.*"]`, same
`$facts.gmail_sender`, now running unattended under systemd instead of a
proof script. The live plan's catalog included `files.find_file_exact`,
so the registered capability-gap primitive is visible to the persistent
planner too.)

## 5. daemon.alive heartbeats over real elapsed time

`FRIDAY_HEARTBEAT_S=60` (set in the unit) → one heartbeat per minute.
Real lines from `var/logs/friday.jsonl` across consecutive minutes,
post-restart (uptime counted from the 23:32:10 restart):

```
{"layer":"WATCH","primitive":"daemon.alive","args":{"uptime_s":72,"last_trigger":"morning-gmail-summary","last_trigger_at":"2026-08-10T18:02:52+00:00","capability_gaps":15},"result":"ALIVE","timestamp":"2026-08-10T18:03:22.545+00:00"}
{"layer":"WATCH","primitive":"daemon.alive","args":{"uptime_s":132,"last_trigger":"morning-gmail-summary","last_trigger_at":"2026-08-10T18:02:52+00:00","capability_gaps":15},"result":"ALIVE","timestamp":"2026-08-10T18:04:22.547+00:00"}
```

- `uptime_s` 72 → 132: exactly 60 s apart, correct baseline from start.
- `last_trigger`/`last_trigger_at`: the persistent daemon's own state.
- `capability_gaps`: the ambient-volume signal the triage loop consumes.

**The heartbeat immediately caught a real bug in its own first release.**
The first daemon run's heartbeat fired at `uptime_s: 39` instead of ≥60 —
`last_heartbeat` was initialized to `0.0` while `time.monotonic()` is
boot-relative, so the first interval looked instantly overdue. Fixed
(`last_heartbeat = started`), regression-tested in `tests/test_watcher.py`,
and the service restarted onto the fix — the lines above are the fixed
code. That is the heartbeat doing its job within an hour of deployment.

## 6. The ambient capability-gap signal (first real reading)

`capability_gaps: 15` in the heartbeat = 15 records in
`var/logs/capability_gaps.jsonl` at that moment. The honest breakdown:

```
files.do_thing      10   (source: executor  - capability-gap demo runs)
whatsapp.send_text   5   (source: watcher   - trigger "allow-x")
```

The 5 `whatsapp.send_text` records were **not generated by the service**
— their `trigger_id` is `allow-x`, a unit-test fixture (watcher
allowlist-refusal test). They were a **test-hermeticity leak**: that test
set `FRIDAY_TASKS_FILE` but not `FRIDAY_GAPS_FILE`, and
`tests/helpers.py` did not isolate the gap file by default, so each run
of the allowlist-refusal test wrote one real record. Their timestamps
(17:56, 17:58, 18:01×2, 18:02) match this session's focused test runs —
the heartbeat counter rose during the service window because *test runs*
were writing, not because the daemon refused anything. **Leak fixed** in
the same session: `FRIDAY_GAPS_FILE`/`FRIDAY_PROPOSALS_DIR`/`FRIDAY_L1_DIR`
are now in `EnvTestCase`'s snapshot list and the gap file is isolated to a
temp path by default; a regression assertion pins the allow-x test to its
temp file, and the real gap file's line count was verified unchanged
(17 -> 17) across the focused suite AND after the full 318-test run.

**The service itself generated zero ambient gaps** across ~10 minutes of
unattended operation (two COMPLETED trigger runs, no refusals). Early
answer to the "does it fill up faster than you can review" question:
with the current single `gmail.*`-allowlisted trigger, ambient
gap-generation is flat at zero; volume will only rise when new
goals/triggers with side-effecting or unknown primitives go live — which
is exactly when the automated gate (previous round) already filters
drafts before a human sees them. Watch the heartbeat's
`capability_gaps` field for this number to move.

The 5 leaked allow-x gaps are allowlist-refusals of `whatsapp.send_text`
— a primitive that **already exists** in `friday/l1/whatsapp.py`. The
real fix for that class is the trigger's allowlist, never a new
primitive (the triage prompt says exactly this), so they were consumed by
inspection: their `gap_id`s appended to `capability_gaps.done` (15 ids: 10
demo + 5 leak) so the triage loop never LLM-drafts an existing primitive.
A future demo run's triage is therefore LLM-free.

## 7. Day-2 operations

`deploy/RUNBOOK.md` — is-it-running checks, live logs (L0 + heartbeat +
journal), stop/start/restart, undo, today's gaps/proposals/tasks at a
glance, and reinstall steps.

## 8. Fired state is now persisted — a restart does NOT re-fire

**The known limit from the first deployment is fixed.** Once-per-day
state now lives in `var/state/watcher_fired.json` (one `{trigger_id:
YYYY-MM-DD}` entry each; `var/` is gitignored runtime data;
`FRIDAY_FIRED_FILE` overrides). The daemon loads it at startup, writes it
only when a trigger COMPLETES (a failed run stays eligible to retry
later today, rate-limited by `RETRY_BACKOFF_S`), fails safe
(corrupt/missing → not-yet-fired, never a crash), and writes ATOMICALLY
(temp + `os.replace`) so a crash mid-write cannot truncate it into a
forced duplicate. Date rollover is natural: the check is
`state[id] == today's date`, so yesterday's entry never blocks today.

Real restart demonstration on the live service (the state file was
seeded with today's date — accurately, since the trigger genuinely fired
four times today: 04:08/04:09 from prior demo runs, 18:00/18:02 from
this deployment — the seed records real history, not a fiction):

```
$ grep -c watch:morning-gmail-summary var/logs/tasks.jsonl   # before restart
4
$ systemctl --user restart friday-watcher.service
$ sleep 35   # a full poll cycle on the restarted daemon
$ grep -c watch:morning-gmail-summary var/logs/tasks.jsonl   # after restart
4                      <- UNCHANGED: no duplicate digest

$ grep fired_state_loaded var/logs/friday.jsonl | tail -1
{'triggers': ['morning-gmail-summary'], 'once': False, 'poll_s': 30.0,
 'heartbeat_s': 60.0, 'fired_state_loaded': 1}   <- daemon loaded the state

$ grep daemon.alive var/logs/friday.jsonl | tail -2
uptime_s: 1152 | last_trigger_at: 2026-08-10T18:02:52+00:00
uptime_s: 1212 | last_trigger_at: 2026-08-10T18:02:52+00:00
                                              <- still 18:02:52: nothing re-fired
```

Contrast the pre-fix behavior (§4): the 23:32 restart re-sent the digest
that had gone out at 23:29. A restart today produces **zero** new
actions. Unit coverage: same-day restart does not re-fire, new-day rolls
over and fires, corrupt/missing state fails safe, daemon mode persists
across restart (`tests/test_watcher.py` `TestFiredState`). The demo
gate-scripts set a temp `FRIDAY_FIRED_FILE` so their proofs stay
reproducible regardless of what the real daemon did today.

## 9. Known limits / honest caveats (this deployment)

- **A FAILED firing is RETRIED (fired-on-success); a REFUSED firing is
  terminal.** Fired-state is recorded when a goal genuinely COMPLETES or
  is deliberately ALLOWLIST-REFUSED — a transient failure (LLM API down,
  gmail auth blip) no longer silently consumes the day's slot, while a
  refusal (the safe terminal outcome) never retries into a replan-refuse
  loop of LLM calls + gap records. The same-day retry is rate-limited by
  `RETRY_BACKOFF_S` (600 s, in-memory per daemon lifetime), so a
  persistently-failing trigger never hammers the LLM API (~6 attempts/
  hour worst case) while a blip that clears within the backoff window
  recovers the same day. Trade-off: a genuinely broken trigger now makes
  bounded repeated attempts instead of exactly one — that is the
  deliberate price of not skipping a day silently.
- **No linger.** `WantedBy=default.target` starts the service at login;
  at logout it stops. Deliberate for a desktop machine; `loginctl
  enable-linger <user>` is the documented opt-in for headless uptime.
- **Notifications are best-effort** (need the session's display/dbus
  env); a failed notify is logged, never fatal.
- **The sandbox FS hole from last round is closed, the env-level sandbox
  remains env-level**: draft `test.py` files now cannot write outside
  their temp sandbox dir (absolute-path/`..` writes rejected by AST),
  but network egress and OS-level isolation are still aspirational — the
  honest-limits note in `CAPABILITY_GAP_PROOF.md` was updated to match.
- **Nothing about the safety rails changed**: the allowlist, executor
  gates, and the automated approval gate are untouched by this
  deployment. Ambient triggers can still never reach `window.shutdown`,
  shell, or a non-allowlisted primitive.

## Verdict

DEPLOYED AND PROVEN — persistent service running, enabled, restarting on
failure, firing the real gmail trigger to COMPLETED/VERIFIED unattended,
and emitting a real heartbeat over real elapsed time that immediately
caught and fixed its own first-release timing bug. The legacy broken
timer pair is gone. Full suite: **318 tests, 318 passed** (was 284; +34 covering the
fs-scope AST checks incl. os.open (write-flag aware, read-only
os.open not false-flagged) and Path.open(mode=...) keyword writes,
the heartbeat + its boot-clock regression, the sandbox TMPDIR
redirect, the gap-file hermeticity regression, the persisted
fired-state (same-day-restart no-refire, new-day rollover, corrupt/
missing fails safe, daemon-mode persistence), the retry semantics
(failed runs not marked fired and retried, backoff-bounded cadence),
and the build-verify stage (test-passes-but-impl-wrong caught, correct
draft passes both stages, wrong return shape rejected, not-applicable
classes honestly flagged), plus the refused-runs-are-terminal retry
regression.

Operate it: `deploy/RUNBOOK.md`.
