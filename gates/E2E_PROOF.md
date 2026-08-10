# E2E_PROOF — live end-to-end check of Friday

Status date: 2026-08-10T03:53:10+00:00.

A LIVE run on this machine - not unit tests. Four goals were planned by a real LLM call
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
date: 2026-08-10T03:51:46+00:00
compositor: Hyprland via hyprctl (live)   claude CLI: live LLM planning
allowlist (read-only primitives only): ['files.find_file', 'gmail.get_message', 'gmail.list_unread', 'media.is_playing', 'media.pause', 'window.get_active_window', 'window.list_clients']
tasks file: /home/lakshay/Projects/Friday V2/var/logs/tasks.jsonl

--- gmail pre-probe: which sender has unread mail right now? ---
[gmail] pre-probe: unread mail from '<redacted>'

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
        "directory": "/home/lakshay/Projects/Friday V2"
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

=== L0 trace: L4 planning goal 1 (4 lines, run_id=e2e-20260810T092146-g1-plan) ===
[2026-08-10T03:51:48.031+00:00] L4 step=None plan                         -> PENDING
[2026-08-10T03:51:48.031+00:00] L4 step=None plan.attempt                 -> RUNNING
[2026-08-10T03:52:05.171+00:00] L1 step=None dev.run                      -> {'is_error': False, 'duration_api_ms': 12874, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': 'f8726df0-dc79-44e5-863d-ae7b6e7eb544', 'total_cost_usd': 0.16647, 'usage': {'input_tokens': '<redacted>', 'cache_cre...
[2026-08-10T03:52:05.172+00:00] L4 step=None plan                         -> ACCEPTED

=== L0 trace: execution goal 1 (7 lines, run_id=e2e-20260810T092146-g1-exec) ===
[2026-08-10T03:52:05.173+00:00] L3 step=None plan                         -> PENDING
[2026-08-10T03:52:05.174+00:00] L3 step=1 step.1                       -> PENDING
[2026-08-10T03:52:05.174+00:00] L3 step=1 step.1                       -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-10T03:52:05.175+00:00] L1 step=1 files.find_file              -> {'path': '/home/lakshay/Projects/Friday V2/README.md', 'name': 'README.md', 'matches': ['/home/lakshay/Projects/Friday V2/README.md']}
[2026-08-10T03:52:05.176+00:00] L2 step=1 checks.file_exists           -> True
[2026-08-10T03:52:05.176+00:00] L3 step=1 step.1                       -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-10T03:52:05.176+00:00] L3 step=None plan                         -> COMPLETED extra={'steps': 1}
[tasks.jsonl] appended e2e:files gate6_passed=True
GOAL 1: PASS

========================================================================
GOAL 2 - windows: "verify that a terminal window with window class 'kitty' is currently open, and state the classes of the open windows"
========================================================================

--- L4: live LLM planning ---
plan JSON returned by the LLM:
{
  "goal": "verify that a terminal window with window class 'kitty' is currently open, and state the classes of the open windows",
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

=== L0 trace: L4 planning goal 2 (4 lines, run_id=e2e-20260810T092146-g2-plan) ===
[2026-08-10T03:52:05.257+00:00] L4 step=None plan                         -> PENDING
[2026-08-10T03:52:05.258+00:00] L4 step=None plan.attempt                 -> RUNNING
[2026-08-10T03:52:39.866+00:00] L1 step=None dev.run                      -> {'is_error': False, 'duration_api_ms': 30631, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': 'b9993c2c-241d-46c2-99ed-290cf70cd868', 'total_cost_usd': 0.16615, 'usage': {'input_tokens': '<redacted>', 'cache_cre...
[2026-08-10T03:52:39.867+00:00] L4 step=None plan                         -> ACCEPTED

=== L0 trace: execution goal 2 (8 lines, run_id=e2e-20260810T092146-g2-exec) ===
[2026-08-10T03:52:39.867+00:00] L3 step=None plan                         -> PENDING
[2026-08-10T03:52:39.868+00:00] L3 step=1 step.1                       -> PENDING
[2026-08-10T03:52:39.868+00:00] L3 step=1 step.1                       -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-10T03:52:39.879+00:00] L1 step=1 window.list_clients          -> [{'address': '0x55f0adb9c000', 'class': 'kitty', 'title': '✳ Claude Code', 'workspace_id': 1, 'pid': 2825, 'mapped': True}, {'address': '0x55f0ad3ffb40', 'class': 'brave-browser', 'title': '24Online Client - Brave', 'wor...
[2026-08-10T03:52:39.896+00:00] L1 step=1 window.list_clients          -> [{'address': '0x55f0adb9c000', 'class': 'kitty', 'title': '✳ Claude Code', 'workspace_id': 1, 'pid': 2825, 'mapped': True}, {'address': '0x55f0ad3ffb40', 'class': 'brave-browser', 'title': '24Online Client - Brave', 'wor...
[2026-08-10T03:52:39.897+00:00] L2 step=1 checks.window_has_class      -> True
[2026-08-10T03:52:39.897+00:00] L3 step=1 step.1                       -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-10T03:52:39.897+00:00] L3 step=None plan                         -> COMPLETED extra={'steps': 1}
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

=== L0 trace: L4 planning goal 3 (4 lines, run_id=e2e-20260810T092146-g3-plan) ===
[2026-08-10T03:52:39.972+00:00] L4 step=None plan                         -> PENDING
[2026-08-10T03:52:39.972+00:00] L4 step=None plan.attempt                 -> RUNNING
[2026-08-10T03:52:55.715+00:00] L1 step=None dev.run                      -> {'is_error': False, 'duration_api_ms': 11816, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': '3b8d8b09-4129-4c65-b746-e7fcd05bff7d', 'total_cost_usd': 0.165305, 'usage': {'input_tokens': '<redacted>', 'cache_cr...
[2026-08-10T03:52:55.715+00:00] L4 step=None plan                         -> ACCEPTED

=== L0 trace: execution goal 3 (8 lines, run_id=e2e-20260810T092146-g3-exec) ===
[2026-08-10T03:52:55.716+00:00] L3 step=None plan                         -> PENDING
[2026-08-10T03:52:55.716+00:00] L3 step=1 step.1                       -> PENDING
[2026-08-10T03:52:55.716+00:00] L3 step=1 step.1                       -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-10T03:52:55.717+00:00] L1 step=1 media.pause                  -> None
[2026-08-10T03:52:55.718+00:00] L1 step=1 media.is_playing             -> False
[2026-08-10T03:52:55.718+00:00] L2 step=1 checks.media_playing         -> False
[2026-08-10T03:52:55.718+00:00] L3 step=1 step.1                       -> VERIFIED extra={'attempts': 1, 'verify_actual': 'False'}
[2026-08-10T03:52:55.719+00:00] L3 step=None plan                         -> COMPLETED extra={'steps': 1}
[tasks.jsonl] appended e2e:media gate6_passed=True
GOAL 3: PASS

========================================================================
GOAL 4 - gmail: 'list the most recent unread email from <redacted> and return its sender, subject and date (read-only)'
========================================================================

--- L4: live LLM planning ---
plan JSON returned by the LLM:
{
  "goal": "list the most recent unread email from <redacted> and return its sender, subject and date (read-only)",
  "steps": [
    {
      "primitive": "gmail.list_unread",
      "args": {
        "sender": "<redacted>",
        "max_results": 1
      },
      "verify": {
        "check": "checks.gmail_unread_exists",
        "args": {
          "sender": "<redacted>"
        },
        "expect": true
      }
    },
    {
      "primitive": "gmail.get_message",
      "args": {
        "message_id": "$steps.1.result.0.message_id"
      },
      "verify": {
        "check": "checks.gmail_message_matches",
        "args": {
          "message_id": "$steps.1.result.0.message_id",
          "expected_sender_substring": "<redacted>"
        },
        "expect": true
      }
    }
  ]
}

--- L3: executor runs the LLM plan ---
plan status: COMPLETED
  step 1: gmail.list_unread        VERIFIED     attempts=1 verify_actual=True
  step 2: gmail.get_message        VERIFIED     attempts=1 verify_actual=True

=== L0 trace: L4 planning goal 4 (4 lines, run_id=e2e-20260810T092146-g4-plan) ===
[2026-08-10T03:52:55.797+00:00] L4 step=None plan                         -> PENDING
[2026-08-10T03:52:55.797+00:00] L4 step=None plan.attempt                 -> RUNNING
[2026-08-10T03:53:08.112+00:00] L1 step=None dev.run                      -> {'is_error': False, 'duration_api_ms': 8426, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': '96d5905a-f8ed-45a1-aca2-fbea22c3b876', 'total_cost_usd': 0.16948, 'usage': {'input_tokens': '<redacted>', 'cache_crea...
[2026-08-10T03:53:08.113+00:00] L4 step=None plan                         -> ACCEPTED

=== L0 trace: execution goal 4 (14 lines, run_id=e2e-20260810T092146-g4-exec) ===
[2026-08-10T03:53:08.113+00:00] L3 step=None plan                         -> PENDING
[2026-08-10T03:53:08.113+00:00] L3 step=1 step.1                       -> PENDING
[2026-08-10T03:53:08.114+00:00] L3 step=1 step.1                       -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-10T03:53:09.059+00:00] L1 step=1 gmail.list_unread            -> [{'message_id': '19fe663ba2d76ce3', 'sender': '<redacted>', 'subject': '<redacted>', 'date': 'Sun, 9 Aug 2026 11:58:43 +0000'}]
[2026-08-10T03:53:09.987+00:00] L1 step=1 gmail.list_unread            -> [{'message_id': '19fe663ba2d76ce3', 'sender': '<redacted>', 'subject': '<redacted>', 'date': 'Sun, 9 Aug 2026 11:58:43 +0000'}]
[2026-08-10T03:53:09.987+00:00] L2 step=1 checks.gmail_unread_exists   -> True
[2026-08-10T03:53:09.987+00:00] L3 step=1 step.1                       -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-10T03:53:09.987+00:00] L3 step=2 step.2                       -> PENDING
[2026-08-10T03:53:09.988+00:00] L3 step=2 step.2                       -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-10T03:53:10.409+00:00] L1 step=2 gmail.get_message            -> <redacted>
[2026-08-10T03:53:10.826+00:00] L1 step=2 gmail.get_message            -> <redacted>
[2026-08-10T03:53:10.826+00:00] L2 step=2 checks.gmail_message_matches -> True
[2026-08-10T03:53:10.827+00:00] L3 step=2 step.2                       -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-10T03:53:10.827+00:00] L3 step=None plan                         -> COMPLETED extra={'steps': 2}
[tasks.jsonl] appended e2e:gmail gate6_passed=True
GOAL 4: PASS

========================================================================
=== E2E VERDICT ===
  OK: all goals COMPLETED with every step VERIFIED, from live LLM plans
========================================================================
[notify] desktop notification sent
```
