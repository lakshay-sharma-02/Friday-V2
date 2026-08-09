# E2E_PROOF — live end-to-end check of Friday

Status date: 2026-08-09T19:22:55+00:00.

A LIVE run on this machine - not unit tests. Three goals were planned by a real LLM call
(L4), executed by the unmodified executor (L3), verified by real L2 checks, traced through
the real L0 log, recorded in the gate-6 tasks.jsonl format, and pinged to the desktop.
All goals are read-only, or a no-op when nothing is playing; plans containing any
side-effecting primitive were mechanically refused by an allowlist before execution.

## Verdict: PASS

## Raw output

```
========================================================================
FRIDAY E2E - live end-to-end check on this machine (not unit tests)
========================================================================
date: 2026-08-09T19:20:06+00:00
compositor: Hyprland via hyprctl (live)   claude CLI: live LLM planning
allowlist (read-only primitives only): ['files.find_file', 'media.is_playing', 'media.pause', 'window.get_active_window', 'window.list_clients']
tasks file: /home/lakshay/Projects/Friday V2/var/logs/tasks.jsonl

========================================================================
GOAL 1 - files: 'find the file named README.md in this project and report its absolute path'
========================================================================

--- L4: live LLM planning ---
plan JSON returned by the LLM:
{
  "goal": "find the file named README.md in this project and report its absolute path",
  "steps": [
    {
      "primitive": "files.find_file",
      "args": {
        "name": "README.md",
        "directory": "/home/lakshay/Projects/Friday V2",
        "recursive": false
      },
      "verify": {
        "check": "checks.file_exists",
        "args": {
          "path": "$steps.1.result.path"
        },
        "expect": true
      }
    }
  ]
}

--- L3: executor runs the LLM plan ---
plan status: COMPLETED
  step 1: files.find_file          VERIFIED     attempts=1 verify_actual=True

=== L0 trace: L4 planning goal 1 (4 lines, run_id=e2e-20260810T005006-g1-plan) ===
[2026-08-09T19:20:06.211+00:00] L4 step=None plan                         -> PENDING
[2026-08-09T19:20:06.211+00:00] L4 step=None plan.attempt                 -> RUNNING
[2026-08-09T19:20:51.787+00:00] L1 step=None dev.run                      -> {'is_error': False, 'duration_api_ms': 41083, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': '7132ddd3-ed41-4223-8cef-9477923e655c', 'total_cost_usd': 0.16666499999999998, 'usage': {'input_tokens': '<redacted>'...
[2026-08-09T19:20:51.788+00:00] L4 step=None plan                         -> ACCEPTED

=== L0 trace: execution goal 1 (7 lines, run_id=e2e-20260810T005006-g1-exec) ===
[2026-08-09T19:20:51.789+00:00] L3 step=None plan                         -> PENDING
[2026-08-09T19:20:51.789+00:00] L3 step=1 step.1                       -> PENDING
[2026-08-09T19:20:51.790+00:00] L3 step=1 step.1                       -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-09T19:20:51.791+00:00] L1 step=1 files.find_file              -> {'path': '/home/lakshay/Projects/Friday V2/README.md', 'name': 'README.md', 'matches': ['/home/lakshay/Projects/Friday V2/README.md']}
[2026-08-09T19:20:51.791+00:00] L2 step=1 checks.file_exists           -> True
[2026-08-09T19:20:51.792+00:00] L3 step=1 step.1                       -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-09T19:20:51.792+00:00] L3 step=None plan                         -> COMPLETED extra={'steps': 1}
[tasks.jsonl] appended e2e:files gate6_passed=True
GOAL 1: PASS

========================================================================
GOAL 2 - windows: "verify that a terminal window with window class 'kitty' is currently open, and report the classes of the open windows"
========================================================================

--- L4: live LLM planning ---
plan JSON returned by the LLM:
{
  "goal": "verify that a terminal window with window class 'kitty' is currently open, and report the classes of the open windows",
  "steps": [
    {
      "primitive": "window.list_clients",
      "args": {},
      "verify": {
        "check": "checks.window_has_class",
        "args": {
          "cls": "kitty"
        },
        "expect": true
      }
    }
  ]
}

--- L3: executor runs the LLM plan ---
plan status: COMPLETED
  step 1: window.list_clients      VERIFIED     attempts=1 verify_actual=True

=== L0 trace: L4 planning goal 2 (7 lines, run_id=e2e-20260810T005006-g2-plan) ===
[2026-08-09T19:20:51.886+00:00] L4 step=None plan                         -> PENDING
[2026-08-09T19:20:51.887+00:00] L4 step=None plan.attempt                 -> RUNNING
[2026-08-09T19:22:22.641+00:00] L1 step=None dev.run                      -> {'is_error': False, 'duration_api_ms': 87183, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': '60d6c191-5eae-4a51-968f-8fd90225bff9', 'total_cost_usd': 0.167695, 'usage': {'input_tokens': '<redacted>', 'cache_cr...
[2026-08-09T19:22:22.642+00:00] L4 step=None plan.attempt                 -> FAILED EXC: plan failed schema validation: step 1: unknown or unregistered primitive 'checks.window_has_class'
[2026-08-09T19:22:22.642+00:00] L4 step=None plan.attempt                 -> RUNNING
[2026-08-09T19:22:46.549+00:00] L1 step=None dev.run                      -> {'is_error': False, 'duration_api_ms': 20079, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': '6dfb0180-c199-45e9-9121-7526eba196d0', 'total_cost_usd': 0.16655999999999999, 'usage': {'input_tokens': '<redacted>'...
[2026-08-09T19:22:46.549+00:00] L4 step=None plan                         -> ACCEPTED

=== L0 trace: execution goal 2 (8 lines, run_id=e2e-20260810T005006-g2-exec) ===
[2026-08-09T19:22:46.550+00:00] L3 step=None plan                         -> PENDING
[2026-08-09T19:22:46.551+00:00] L3 step=1 step.1                       -> PENDING
[2026-08-09T19:22:46.551+00:00] L3 step=1 step.1                       -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-09T19:22:46.561+00:00] L1 step=1 window.list_clients          -> [{'address': '0x55f0adb9c000', 'class': 'kitty', 'title': '✳ Claude Code', 'workspace_id': 1, 'pid': 2825, 'mapped': True}, {'address': '0x55f0ad3ffb40', 'class': 'brave-browser', 'title': 'lakshay-sharma-02/Friday-V2 - ...
[2026-08-09T19:22:46.575+00:00] L1 step=1 window.list_clients          -> [{'address': '0x55f0adb9c000', 'class': 'kitty', 'title': '✳ Claude Code', 'workspace_id': 1, 'pid': 2825, 'mapped': True}, {'address': '0x55f0ad3ffb40', 'class': 'brave-browser', 'title': 'lakshay-sharma-02/Friday-V2 - ...
[2026-08-09T19:22:46.576+00:00] L2 step=1 checks.window_has_class      -> True
[2026-08-09T19:22:46.576+00:00] L3 step=1 step.1                       -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-09T19:22:46.576+00:00] L3 step=None plan                         -> COMPLETED extra={'steps': 1}
[tasks.jsonl] appended e2e:windows gate6_passed=True
GOAL 2: PASS

========================================================================
GOAL 3 - media: 'pause any playing audio'
========================================================================

--- L4: live LLM planning ---
plan JSON returned by the LLM:
{
  "goal": "pause any playing audio",
  "steps": [
    {
      "primitive": "media.pause",
      "args": {},
      "verify": {
        "check": "checks.media_playing",
        "args": {},
        "expect": false
      }
    }
  ]
}

--- L3: executor runs the LLM plan ---
plan status: COMPLETED
  step 1: media.pause              VERIFIED     attempts=1 verify_actual=False

=== L0 trace: L4 planning goal 3 (4 lines, run_id=e2e-20260810T005006-g3-plan) ===
[2026-08-09T19:22:46.650+00:00] L4 step=None plan                         -> PENDING
[2026-08-09T19:22:46.650+00:00] L4 step=None plan.attempt                 -> RUNNING
[2026-08-09T19:22:55.045+00:00] L1 step=None dev.run                      -> {'is_error': False, 'duration_api_ms': 4708, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': 'ea8b0612-c3ff-47cd-a582-caac0fee3417', 'total_cost_usd': 0.16533, 'usage': {'input_tokens': '<redacted>', 'cache_crea...
[2026-08-09T19:22:55.046+00:00] L4 step=None plan                         -> ACCEPTED

=== L0 trace: execution goal 3 (8 lines, run_id=e2e-20260810T005006-g3-exec) ===
[2026-08-09T19:22:55.047+00:00] L3 step=None plan                         -> PENDING
[2026-08-09T19:22:55.047+00:00] L3 step=1 step.1                       -> PENDING
[2026-08-09T19:22:55.047+00:00] L3 step=1 step.1                       -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-09T19:22:55.047+00:00] L1 step=1 media.pause                  -> None
[2026-08-09T19:22:55.048+00:00] L1 step=1 media.is_playing             -> False
[2026-08-09T19:22:55.048+00:00] L2 step=1 checks.media_playing         -> False
[2026-08-09T19:22:55.048+00:00] L3 step=1 step.1                       -> VERIFIED extra={'attempts': 1, 'verify_actual': 'False'}
[2026-08-09T19:22:55.048+00:00] L3 step=None plan                         -> COMPLETED extra={'steps': 1}
[tasks.jsonl] appended e2e:media gate6_passed=True
GOAL 3: PASS

========================================================================
=== E2E VERDICT ===
  OK: all goals COMPLETED with every step VERIFIED, from live LLM plans
========================================================================
[notify] desktop notification sent
```
