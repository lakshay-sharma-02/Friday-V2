# E2E_PROOF — live end-to-end check of Friday

Status date: 2026-08-10T04:07:24+00:00.

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
date: 2026-08-10T04:05:58+00:00
compositor: Hyprland via hyprctl (live)   claude CLI: live LLM planning
allowlist (read-only primitives only): ['files.find_file', 'gmail.get_message', 'gmail.list_unread', 'gmail.summarize', 'media.is_playing', 'media.pause', 'window.get_active_window', 'window.list_clients']
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

=== L0 trace: L4 planning goal 1 (4 lines, run_id=e2e-20260810T093558-g1-plan) ===
[2026-08-10T04:06:00.206+00:00] L4 step=None plan                         -> PENDING
[2026-08-10T04:06:00.206+00:00] L4 step=None plan.attempt                 -> RUNNING
[2026-08-10T04:06:11.643+00:00] L1 step=None dev.run                      -> {'is_error': False, 'duration_api_ms': 6960, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': 'c843ae5c-45ee-4eed-ad62-885009fb253c', 'total_cost_usd': 0.16278499999999999, 'usage': {'input_tokens': '<redacted>',...
[2026-08-10T04:06:11.644+00:00] L4 step=None plan                         -> ACCEPTED

=== L0 trace: execution goal 1 (7 lines, run_id=e2e-20260810T093558-g1-exec) ===
[2026-08-10T04:06:11.644+00:00] L3 step=None plan                         -> PENDING
[2026-08-10T04:06:11.645+00:00] L3 step=1 step.1                       -> PENDING
[2026-08-10T04:06:11.645+00:00] L3 step=1 step.1                       -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-10T04:06:11.646+00:00] L1 step=1 files.find_file              -> {'path': '/home/lakshay/Projects/Friday V2/README.md', 'name': 'README.md', 'matches': ['/home/lakshay/Projects/Friday V2/README.md']}
[2026-08-10T04:06:11.646+00:00] L2 step=1 checks.file_exists           -> True
[2026-08-10T04:06:11.646+00:00] L3 step=1 step.1                       -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-10T04:06:11.647+00:00] L3 step=None plan                         -> COMPLETED extra={'steps': 1}
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

=== L0 trace: L4 planning goal 2 (4 lines, run_id=e2e-20260810T093558-g2-plan) ===
[2026-08-10T04:06:11.730+00:00] L4 step=None plan                         -> PENDING
[2026-08-10T04:06:11.730+00:00] L4 step=None plan.attempt                 -> RUNNING
[2026-08-10T04:06:31.780+00:00] L1 step=None dev.run                      -> {'is_error': False, 'duration_api_ms': 15852, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': 'ec4dc62e-0baa-46df-8330-794a13b31985', 'total_cost_usd': 0.16259, 'usage': {'input_tokens': '<redacted>', 'cache_cre...
[2026-08-10T04:06:31.781+00:00] L4 step=None plan                         -> ACCEPTED

=== L0 trace: execution goal 2 (8 lines, run_id=e2e-20260810T093558-g2-exec) ===
[2026-08-10T04:06:31.782+00:00] L3 step=None plan                         -> PENDING
[2026-08-10T04:06:31.782+00:00] L3 step=1 step.1                       -> PENDING
[2026-08-10T04:06:31.783+00:00] L3 step=1 step.1                       -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-10T04:06:31.792+00:00] L1 step=1 window.list_clients          -> [{'address': '0x55f0adb9c000', 'class': 'kitty', 'title': '✳ Claude Code', 'workspace_id': 1, 'pid': 2825, 'mapped': True}, {'address': '0x55f0ad3ffb40', 'class': 'brave-browser', 'title': '24Online Client - Brave', 'wor...
[2026-08-10T04:06:31.805+00:00] L1 step=1 window.list_clients          -> [{'address': '0x55f0adb9c000', 'class': 'kitty', 'title': '✳ Claude Code', 'workspace_id': 1, 'pid': 2825, 'mapped': True}, {'address': '0x55f0ad3ffb40', 'class': 'brave-browser', 'title': '24Online Client - Brave', 'wor...
[2026-08-10T04:06:31.805+00:00] L2 step=1 checks.window_has_class      -> True
[2026-08-10T04:06:31.806+00:00] L3 step=1 step.1                       -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-10T04:06:31.806+00:00] L3 step=None plan                         -> COMPLETED extra={'steps': 1}
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
        "expect": false,
        "verify_wait_s": 5
      }
    }
  ]
}

--- L3: executor runs the LLM plan ---
plan status: COMPLETED
  step 1: media.pause              VERIFIED     attempts=1 verify_actual=False

=== L0 trace: L4 planning goal 3 (4 lines, run_id=e2e-20260810T093558-g3-plan) ===
[2026-08-10T04:06:31.882+00:00] L4 step=None plan                         -> PENDING
[2026-08-10T04:06:31.882+00:00] L4 step=None plan.attempt                 -> RUNNING
[2026-08-10T04:06:46.554+00:00] L1 step=None dev.run                      -> {'is_error': False, 'duration_api_ms': 10607, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': '017c8d7c-3ff9-47aa-92ce-1b741a22a745', 'total_cost_usd': 0.16563999999999998, 'usage': {'input_tokens': '<redacted>'...
[2026-08-10T04:06:46.554+00:00] L4 step=None plan                         -> ACCEPTED

=== L0 trace: execution goal 3 (8 lines, run_id=e2e-20260810T093558-g3-exec) ===
[2026-08-10T04:06:46.555+00:00] L3 step=None plan                         -> PENDING
[2026-08-10T04:06:46.555+00:00] L3 step=1 step.1                       -> PENDING
[2026-08-10T04:06:46.556+00:00] L3 step=1 step.1                       -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-10T04:06:46.556+00:00] L1 step=1 media.pause                  -> None
[2026-08-10T04:06:46.556+00:00] L1 step=1 media.is_playing             -> False
[2026-08-10T04:06:46.557+00:00] L2 step=1 checks.media_playing         -> False
[2026-08-10T04:06:46.558+00:00] L3 step=1 step.1                       -> VERIFIED extra={'attempts': 1, 'verify_actual': 'False'}
[2026-08-10T04:06:46.558+00:00] L3 step=None plan                         -> COMPLETED extra={'steps': 1}
[tasks.jsonl] appended e2e:media gate6_passed=True
GOAL 3: PASS

========================================================================
GOAL 4 - gmail: 'list the most recent unread email from <redacted> and return a short plain-text summary of it (read-only)'
========================================================================

--- L4: live LLM planning ---
plan JSON returned by the LLM:
{
  "goal": "list the most recent unread email from <redacted> and return a short plain-text summary of it (read-only)",
  "steps": [
    {
      "primitive": "gmail.list_unread",
      "args": {
        "sender": "<redacted>",
        "max_results": 5
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
    },
    {
      "primitive": "gmail.summarize",
      "args": {
        "message_id": "$steps.2.result.message_id"
      },
      "verify": {
        "check": "checks.gmail_message_matches",
        "args": {
          "message_id": "$steps.2.result.message_id",
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
  step 3: gmail.summarize          VERIFIED     attempts=1 verify_actual=True

=== L0 trace: L4 planning goal 4 (4 lines, run_id=e2e-20260810T093558-g4-plan) ===
[2026-08-10T04:06:46.648+00:00] L4 step=None plan                         -> PENDING
[2026-08-10T04:06:46.648+00:00] L4 step=None plan.attempt                 -> RUNNING
[2026-08-10T04:07:07.788+00:00] L1 step=None dev.run                      -> {'is_error': False, 'duration_api_ms': 17217, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': '1c916637-c23d-4391-8374-2fa410185249', 'total_cost_usd': 0.17207, 'usage': {'input_tokens': '<redacted>', 'cache_cre...
[2026-08-10T04:07:07.788+00:00] L4 step=None plan                         -> ACCEPTED

=== L0 trace: execution goal 4 (21 lines, run_id=e2e-20260810T093558-g4-exec) ===
[2026-08-10T04:07:07.789+00:00] L3 step=None plan                         -> PENDING
[2026-08-10T04:07:07.789+00:00] L3 step=1 step.1                       -> PENDING
[2026-08-10T04:07:07.789+00:00] L3 step=1 step.1                       -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-10T04:07:12.328+00:00] L1 step=1 gmail.list_unread            -> [{'message_id': '19fe663ba2d76ce3', 'sender': '<redacted>', 'subject': '<redacted>', 'date': 'Sun, 9 Aug 2026 11:58:43 +0000'}, {'message_id': '19fe128143855161', 'sender': '<redacted>', 'subject': '<redacted>', 'date': ...
[2026-08-10T04:07:13.660+00:00] L1 step=1 gmail.list_unread            -> [{'message_id': '19fe663ba2d76ce3', 'sender': '<redacted>', 'subject': '<redacted>', 'date': 'Sun, 9 Aug 2026 11:58:43 +0000'}]
[2026-08-10T04:07:13.660+00:00] L2 step=1 checks.gmail_unread_exists   -> True
[2026-08-10T04:07:13.661+00:00] L3 step=1 step.1                       -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-10T04:07:13.661+00:00] L3 step=2 step.2                       -> PENDING
[2026-08-10T04:07:13.661+00:00] L3 step=2 step.2                       -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-10T04:07:14.172+00:00] L1 step=2 gmail.get_message            -> <redacted>
[2026-08-10T04:07:14.702+00:00] L1 step=2 gmail.get_message            -> <redacted>
[2026-08-10T04:07:14.703+00:00] L2 step=2 checks.gmail_message_matches -> True
[2026-08-10T04:07:14.703+00:00] L3 step=2 step.2                       -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-10T04:07:14.704+00:00] L3 step=3 step.3                       -> PENDING
[2026-08-10T04:07:14.704+00:00] L3 step=3 step.3                       -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-10T04:07:15.195+00:00] L1 step=3 gmail.get_message            -> <redacted>
[2026-08-10T04:07:23.473+00:00] L1 step=3 gmail.summarize              -> From Snapchat, addressed to Lakshay, the email reminds him of an event that occurred on 30 December 2025 and includes a link to view the content in Snapchat. It contains a promotional header image and a “View in Snapchat...
[2026-08-10T04:07:23.897+00:00] L1 step=3 gmail.get_message            -> <redacted>
[2026-08-10T04:07:23.897+00:00] L2 step=3 checks.gmail_message_matches -> True
[2026-08-10T04:07:23.898+00:00] L3 step=3 step.3                       -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-10T04:07:23.898+00:00] L3 step=None plan                         -> COMPLETED extra={'steps': 3}
[tasks.jsonl] appended e2e:gmail gate6_passed=True
GOAL 4: PASS

========================================================================
=== E2E VERDICT ===
  OK: all goals COMPLETED with every step VERIFIED, from live LLM plans
========================================================================
[notify] desktop notification sent
```
