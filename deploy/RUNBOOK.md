# RUNBOOK — Friday watcher service

The watcher runs as a persistent systemd **user** service
(`friday-watcher.service`) on this machine (CachyOS + Hyprland). It polls
`config/watcher.json` every 30 s, fires due triggers (currently only
`morning-gmail-summary`, 09:00 weekdays), and emits a `daemon.alive`
heartbeat every 60 s. All structured lines land in the standard L0 log,
`var/logs/friday.jsonl`.

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
{"layer":"WATCH","primitive":"daemon.alive","result":"ALIVE","args":{"uptime_s":300,"last_trigger":"none","last_trigger_at":"","capability_gaps":6},...}
```

- `uptime_s` — seconds since the daemon started.
- `last_trigger` / `last_trigger_at` — the last trigger that fired (UTC).
- `capability_gaps` — how many gap records exist right now. **This is the
  number to watch**: if it grows faster than proposals get reviewed, the
  triage loop is outrunning the human gate and the meta-engine
  (dual-approval / sandboxed-build) should move up the list.

### Stop / start / restart

```sh
systemctl --user stop friday-watcher.service
systemctl --user start friday-watcher.service
systemctl --user restart friday-watcher.service
```

Stopping sends SIGINT, which the watcher handles as a clean stop (a `STOP`
event is written to the L0 log).

### Turn it off entirely (undo the deployment)

```sh
systemctl --user disable --now friday-watcher.service
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
- **The 09:00 gmail trigger makes a live LLM call** (plan + summarize)
  through the local model router (~$0.17/run — flat router fee, not model
  cost). One call per distinct goal per daemon run, cached thereafter.
- **Linger**: the service starts at login (`WantedBy=default.target`).
  To also start it at boot without login (headless), run
  `loginctl enable-linger <user>` once — deliberately not enabled by
  default for a desktop machine.
- **The allowlist and executor gates are untouched** by this deployment;
  the watcher inherits them, so a trigger can never reach
  `window.shutdown`, shell, or a non-allowlisted primitive.
