# RUNBOOK — Friday watcher service

The watcher runs as a persistent systemd **user** service
(`friday-watcher.service`) on this machine (CachyOS + Hyprland). It polls
`config/watcher.json` every 30 s, fires due triggers (currently six
enabled: `morning-gmail-summary` 09:00 weekdays, the `weekly-cross-
project-digest` + `sunday-digest-reminder` pair Sundays, and the
2026-08-14 daily-use layer — `new-download-alert` on new pdfs in
~/Downloads, `morning-calendar-summary` 08:00 and `morning-clipboard-
digest` 08:05 daily), and emits a `daemon.alive` heartbeat every 60 s.
All structured lines land in the standard L0 log, `var/logs/friday.jsonl`.

This service **replaces** the legacy `friday-watch.timer` +
`friday-watch.service` pair (July 2026) that ran `python -m friday.cli
watch --run-once` — an entry point that no longer exists — and had been
failing every 2 minutes since. The legacy units were disabled and removed;
`deploy/friday-watcher.service` is the source of truth.

---

## Day-2 operations

### Is it running?

```sh
systemctl --user status friday-watcher.service     # Active: active (running)
systemctl --user is-active friday-watcher.service  # -> active
systemctl --user is-enabled friday-watcher.service # -> enabled (starts at login)
```

### Live logs

```sh
# the structured L0 log (heartbeats, trigger runs, executor events):
tail -f var/logs/friday.jsonl

# heartbeat lines only:
grep daemon.alive var/logs/friday.jsonl | tail -5

# systemd journal for the service's own lifecycle (starts, restarts, stops):
journalctl --user -u friday-watcher.service -f
```

A healthy heartbeat looks like:

```json
{"layer":"WATCH","primitive":"daemon.alive","result":"ALIVE","args":{"uptime_s":300,"last_trigger":"none","last_trigger_at":"","capability_gaps":6,"gaps_pending_triage":4},...}
```

- `uptime_s` — seconds since the daemon started.
- `last_trigger` / `last_trigger_at` — the last trigger that fired (UTC).
- `capability_gaps` — TOTAL gap records ever recorded (a monotonic count
  of refused steps).
- `gaps_pending_triage` — the UNPROCESSED gap records still awaiting
  triage (added 2026-08-15). **This is the number to watch**: it is the
  real backlog signal — if it grows faster than proposals get reviewed
  and drafted, the triage loop is outrunning the human gate and the
  meta-engine (dual-approval / sandboxed-build) should move up the list.
  (The total count alone is not actionable — consumed gaps are never
  deleted, so it only grows.)

### Stop / start / restart

```sh
systemctl --user stop friday-watcher.service
systemctl --user start friday-watcher.service
systemctl --user restart friday-watcher.service
```

Stopping sends SIGINT, which the watcher handles as a clean stop (a `STOP`
event is written to the L0 log).

### LLM provider degraded (the morning trigger keeps failing)

The watcher's LLM calls (plan + gmail.summarize) go through the local
router's default model alias, which can be DEGRADED for hours (observed
2026-08-13: `morning-gmail-summary` failed 10x in a row with `claude
rc=1` / 300s timeouts before the provider recovered). The escape hatch is
`FRIDAY_MODEL` in the unit file: a full model id that overrides EVERY
LLM consumer (planner, triage, digest, summarize), not just the watcher.

```sh
# 1. edit deploy/friday-watcher.service -> Environment=FRIDAY_MODEL=<working model id>
# 2. reinstall + restart (below)
# 3. confirm the next trigger run uses the new model:
#    grep '"primitive": "dev.run"' var/logs/friday.jsonl | tail -2
```

The default value pinned in the unit (`oc/laguna-s-2.1-free`) is the one
that recovered from the Aug-13 incident. Delete the `Environment=` line
entirely to fall back to the default alias. Failures are retried the same
day (`RETRY_BACKOFF_S`, 600s) but a dead provider keeps failing until it
recovers or the model is flipped - the heartbeat's `capability_gaps` and
the `planner_llm_error` lesson events are the tell.

### Manual runs (triage / planner from a terminal) use their own model chain

The watcher unit only covers the daemon. When you run the capability-gap
loop by hand (`python -m friday.gap_triage`), the drafting model chain is
configured in `~/.zshrc` (this machine's shell config):

```sh
export FRIDAY_TRIAGE_MODEL="oc/laguna-s-2.1-free"    # primary drafting model
 export FRIDAY_TRIAGE_FALLBACK_MODELS="opus"          # tried after a timeout/hard failure
```

`gap_triage` drafts with `FRIDAY_TRIAGE_MODEL` (or the default alias if
unset), and advances to each `FRIDAY_TRIAGE_FALLBACK_MODELS` entry after
the current model times out or hard-fails - a slow/DEGRADED primary is
absorbed automatically instead of burning all 3 repair attempts on a dead
model (observed 2026-08-14: the opus alias failed the `media.get_volume`
draft 3x with 300s timeouts + unparseable replies; the configured chain
drafted `media.get_playing_title` clean on the first attempt). `FRIDAY_MODEL`
still overrides EVERYTHING at `_run_claude` when set - the unit pins it
for the daemon, so the daemon never reads these triage vars.

### Turn it off entirely (undo the deployment)

```sh
systemctl --user disable --now friday-watcher.service
```

---

## Windows deployment (Task Scheduler)

The watcher code is identical on Windows - only the deployment mechanism
differs. `deploy/install-windows.ps1` registers a scheduled task that
starts the daemon at logon (the systemd-user equivalent):

```powershell
powershell -ExecutionPolicy Bypass -File deploy\install-windows.ps1
# undo:
powershell -ExecutionPolicy Bypass -File deploy\install-windows.ps1 -Uninstall
```

Day-2 operations map 1:1:

| Linux (systemd) | Windows (Task Scheduler) |
|---|---|
| `systemctl --user status` | `Get-ScheduledTask -TaskName friday-watcher` |
| `systemctl --user restart` | `Restart-ScheduledTask -TaskName friday-watcher` |
| `systemctl --user stop` | `Stop-ScheduledTask -TaskName friday-watcher` |
| `journalctl --user -u` | `var/logs/friday.jsonl` (same L0 log, `tail -f`) |
| `Environment=FRIDAY_MODEL=...` | `[Environment]::SetEnvironmentVariable("FRIDAY_MODEL", "oc/laguna-s-2.1-free", "User")` |

Differences to know:
- Task Scheduler restarts the task up to 3x on failure, then waits for
the next logon; the watcher's own `RETRY_BACKOFF_S` retry logic absorbs
provider outages within a session, so this is not a regression.
- `config/watcher.json` paths (digest repo dirs, facts file paths) are
machine-specific data - edit for the Windows layout.

```

### What happened today (gaps / proposals / tasks)

```sh
# gaps recorded today (unprocessed ones feed the triage loop):
grep -c '"timestamp": "2026-08-10' var/logs/capability_gaps.jsonl
./.venv/bin/python -m friday.gap_triage        # draft proposals for new gaps

# task runs (watch:<id> records, one line each):
grep '"task_id": "watch:' var/logs/tasks.jsonl | tail -5

# proposals awaiting your review + signature:
ls -1 gates/proposed_primitives/ 2>/dev/null
```

### Reinstall after a unit-file change

```sh
cp deploy/friday-watcher.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user restart friday-watcher.service
```

---

## Notes / known behaviors

- **Fired-state persistence**: `var/state/watcher_fired.json` records
  which triggers already COMPLETED today (`{trigger_id: YYYY-MM-DD}`),
  so a service restart does NOT re-fire a trigger that already succeeded
  today (proven live in `gates/WATCHER_DEPLOY_PROOF.md` §8). A FAILED
  run is NOT marked fired — it stays eligible to retry later the same
  day, rate-limited by `RETRY_BACKOFF_S` (600 s; at most ~6 attempts/
  hour on a persistent failure). Deleting the state file resets it: the
  next start treats every trigger as not-yet-fired, so a past-due
  trigger fires once (that is the fail-safe direction).
- **Notifications are best-effort.** `notify_send` needs the desktop
  session's display/dbus env, which a login-started user service usually
  has but a headless session may not; a failed notify is caught and
  logged, never fatal.
- **Live LLM calls are limited**: the 09:00 gmail trigger makes one (plan
  + summarize) through the local model router (~$0.17/run — flat router
  fee, not model cost), cached per distinct goal per daemon run; the
  08:05 morning-clipboard-digest makes one `dev.digest` call per firing;
  the Sunday digest makes one full-tier call (~$0.17/week). Everything
  else fires deterministic plans with zero LLM cost.
- **Linger**: the service starts at login (`WantedBy=default.target`).
  To also start it at boot without login (headless), run
  `loginctl enable-linger <user>` once — deliberately not enabled by
  default for a desktop machine.
- **The allowlist and executor gates are untouched** by this deployment;
  the watcher inherits them, so a trigger can never reach
  `window.shutdown`, shell, or a non-allowlisted primitive.
