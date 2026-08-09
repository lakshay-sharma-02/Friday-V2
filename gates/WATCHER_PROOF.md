# WATCHER_PROOF — ambient watch loop, first end-to-end proof

Status date: 2026-08-09T18:52:01+00:00.

Two deterministic triggers (inline plans - no LLM, no sends, no
window/media/browser side effects) run through the real watcher:

- `watch:demo-time`: a time trigger already due at 00:00, planning a
  `files.find_file` on a pre-created file, verified by
  `checks.file_exists` on the returned path.
- `watch:demo-file`: a file trigger watching a temp directory; a new
  file is dropped AFTER the watcher starts, detection fires the same
  find + verify.

Each firing: L3 executes the plan, the outcome is recorded in
`var/logs/tasks.jsonl` as `watch:demo-*` with the gate-6 format, and a
desktop notification is sent via the new `notify_send` primitive.

## Recorded tasks

```
watch:demo-time gate6_passed=True  proof={"trigger": "demo-time", "status": "COMPLETED", "steps": [{"step_id": 1, "primitive": "files.find_file", "status": "VERIFIED", "attempts": 1}]}
watch:demo-file gate6_passed=True  proof={"trigger": "demo-file", "status": "COMPLETED", "steps": [{"step_id": 1, "primitive": "files.find_file", "status": "VERIFIED", "attempts": 1}]}
watch:demo-time gate6_passed=True  proof={"trigger": "demo-time", "status": "COMPLETED", "steps": [{"step_id": 1, "primitive": "files.find_file", "status": "VERIFIED", "attempts": 1}]}
watch:demo-file gate6_passed=True  proof={"trigger": "demo-file", "status": "COMPLETED", "steps": [{"step_id": 1, "primitive": "files.find_file", "status": "VERIFIED", "attempts": 1}]}
watch:demo-time gate6_passed=True  proof={"trigger": "demo-time", "status": "COMPLETED", "steps": [{"step_id": 1, "primitive": "files.find_file", "status": "VERIFIED", "attempts": 1}]}
watch:demo-file gate6_passed=True  proof={"trigger": "demo-file", "status": "COMPLETED", "steps": [{"step_id": 1, "primitive": "files.find_file", "status": "VERIFIED", "attempts": 1}]}
```

Result: 6/6 demo triggers passed.

## What this proves

- The watch loop loads and validates config, evaluates time and file
  triggers, and fires each at most once.
- Goals run through the same L3 executor as every other task, with the
  same L0 tracing (layer=WATCH + layer=L3/L2/L1 in var/logs/friday.jsonl).
- Outcomes land in the tasks counter in the honest gate-6 format.
- `notify_send` works end-to-end (a real desktop notification appears).
- Serial execution: the two triggers never overlap.

## Raw proof

See `var/logs/friday.jsonl` (layer=WATCH lines with run_id `watch-*`)
for the full L0 trace of this run.

