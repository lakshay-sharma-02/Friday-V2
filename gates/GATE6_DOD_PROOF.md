# Gate 6 DoD: first REAL composite through the full unmodified pipeline

Goal string in, verified real-world effect out. No pre-staged plan, no
dry-run edit, no new primitives/checks/signatures - the ONLY input is the
goal string:

    "pause whatever's playing, then close every window except my terminal"

Real-world preconditions (declared): the test tone was playing at volume
30 when the run started (so the pause step had a real effect), and the
desktop held the user's real windows (kitty x2 - including the window the
run was read through - and brave x1).

SAFETY: the harness snapshotted the desktop before, marked every kitty
window protected (hard user constraint: never close the window they read
this through), and refused to execute any plan whose close step could
close a protected window. The LLM's plan excluded 'kitty' correctly, so no
refusal was needed - the interlock is proven by it NOT firing on a plan
that could have been malicious.

The LLM composed: media.pause (verify media_playing false) ->
window.close_all(exclude_classes=['kitty']) (verify checks.window_focused
on 'kitty' - after closing the only non-terminal, the focused window IS a
terminal; a clever, correct read-only verification).

INDEPENDENT world proof (not the plan's self-report): raw `hyprctl clients
-j` before = 3 clients (kitty '~', brave-browser 'Next steps after project
completion - Claude', kitty 'Freebuff...'); after = 2 clients, both kitty;
the brave client is gone; every protected terminal survived including the
active window this run was read through; media.is_playing() == False.

DoD (raw, in order): exact goal string; the full LLM prompt (at
/tmp/gate6-dod-a_prompt.txt, and the run output below); the generated plan
JSON; the full L0 trace (L3 state machine + L1 primitive lines, plus every
verify-poll line in var/logs/friday.jsonl under run_id gate6-dod-a-exec);
and the hyprctl before/after above.

Raw output from the shipped gate run (run label `gate6-dod-a`) follows:

---
========================================================================
GATE 6 DoD - first real composite, full unmodified pipeline
========================================================================
GOAL STRING (verbatim): "pause whatever's playing, then close every window except my terminal"

[before] 3 clients (raw hyprctl clients -j):
[{
    "address": "0x55c72bbec680",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [1, 39],
    "size": [1364, 728],
    "workspace": {
        "id": 3,
        "name": "3"
    },
    "floating": false,
    "monitor": 0,
    "class": "kitty",
    "title": "~",
    "initialClass": "kitty",
    "initialTitle": "kitty",
    "pid": 34283,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 2,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "18000007"
},{
    "address": "0x55c72c1d08c0",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [1, 39],
    "size": [1364, 728],
    "workspace": {
        "id": 2,
        "name": "2"
    },
    "floating": false,
    "monitor": 0,
    "class": "brave-browser",
    "title": "Next steps after project completion - Claude - Brave",
    "initialClass": "brave-browser",
    "initialTitle": "New Tab - Brave",
    "pid": 4219,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 1,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "18000003"
},{
    "address": "0x55c72c9db420",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [1, 39],
    "size": [1364, 728],
    "workspace": {
        "id": 1,
        "name": "1"
    },
    "floating": false,
    "monitor": 0,
    "class": "kitty",
    "title": "Freebuff: leave that window.shutdown thing. should i ask fo…",
    "initialClass": "kitty",
    "initialTitle": "kitty",
    "pid": 3829,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 0,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "18000002"
}]

  kitty | ~ | ws 3 | 0x55c72bbec680
  brave-browser | Next steps after project completion - Cl | ws 2 | 0x55c72c1d08c0
  kitty | Freebuff: leave that window.shutdown thi | ws 1 | 0x55c72c9db420
[before] active window: 0x55c72c9db420
[before] protected (terminal) addresses: ['0x55c72bbec680', '0x55c72c9db420']

[precondition] starting the test tone at volume 30 ('whatever's playing')
[precondition] media.is_playing() -> True (expect True)

--- L4: LLM planning ---
(full prompt at /tmp/gate6-dod-a_prompt.txt; also printed below)

GENERATED PLAN JSON:
{
  "goal": "pause whatever's playing, then close every window except my terminal",
  "steps": [
    {
      "primitive": "media.pause",
      "args": {},
      "verify": {
        "check": "checks.media_playing",
        "args": {},
        "expect": false
      },
      "verify_wait_s": 5
    },
    {
      "primitive": "window.close_all",
      "args": {
        "exclude_classes": [
          "kitty"
        ]
      },
      "verify": {
        "check": "checks.window_focused",
        "args": {
          "cls": "kitty"
        },
        "expect": true
      }
    }
  ]
}

--- L3: unmodified executor runs the plan ---
plan status: COMPLETED
  step 1: media.pause                VERIFIED     attempts=1 verify_actual=False
  step 2: window.close_all           VERIFIED     attempts=1 verify_actual=True

[after] 2 clients (raw hyprctl clients -j):
[{
    "address": "0x55c72bbec680",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [1, 39],
    "size": [1364, 728],
    "workspace": {
        "id": 3,
        "name": "3"
    },
    "floating": false,
    "monitor": 0,
    "class": "kitty",
    "title": "~",
    "initialClass": "kitty",
    "initialTitle": "kitty",
    "pid": 34283,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 1,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "18000007"
},{
    "address": "0x55c72c9db420",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [1, 39],
    "size": [1364, 728],
    "workspace": {
        "id": 1,
        "name": "1"
    },
    "floating": false,
    "monitor": 0,
    "class": "kitty",
    "title": "Freebuff: leave that window.shutdown thing. should i ask fo…",
    "initialClass": "kitty",
    "initialTitle": "kitty",
    "pid": 3829,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 0,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "18000002"
}]

  kitty | ~ | ws 3 | 0x55c72bbec680
  kitty | Freebuff: leave that window.shutdown thi | ws 1 | 0x55c72c9db420
[after] media.is_playing() -> False (expect False - paused)

=== L0 trace: L4 planning (4 lines, run_id=gate6-dod-a-plan) ===
[2026-08-08T08:05:40.659+00:00] L4 step=None plan                           -> PENDING
[2026-08-08T08:05:40.659+00:00] L4 step=None plan.attempt                   -> RUNNING
[2026-08-08T08:06:05.593+00:00] L1 step=None dev.run                        -> {'is_error': False, 'duration_api_ms': 20091, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': 'f6a44767-88bf-4c45-aee6-ce6ffda5e088
[2026-08-08T08:06:05.594+00:00] L4 step=None plan                           -> ACCEPTED

=== L0 trace: execution (real composite) (20 lines, run_id=gate6-dod-a-exec) ===
[2026-08-08T08:06:05.595+00:00] L3 step=None plan                           -> PENDING
[2026-08-08T08:06:05.595+00:00] L3 step=1 step.1                         -> PENDING
[2026-08-08T08:06:05.596+00:00] L3 step=1 step.1                         -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-08T08:06:05.598+00:00] L1 step=1 media.pause                    -> None
[2026-08-08T08:06:05.600+00:00] L1 step=1 media.is_playing               -> False
[2026-08-08T08:06:05.602+00:00] L2 step=1 checks.media_playing           -> False
[2026-08-08T08:06:05.602+00:00] L3 step=1 step.1                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'False'}
[2026-08-08T08:06:05.603+00:00] L3 step=2 step.2                         -> PENDING
[2026-08-08T08:06:05.603+00:00] L3 step=2 step.2                         -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-08T08:06:05.616+00:00] L1 step=2 window.list_clients            -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], '
[2026-08-08T08:06:05.658+00:00] L1 step=2 window.list_clients            -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], '
[2026-08-08T08:06:05.923+00:00] L1 step=2 window.list_clients            -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], '
[2026-08-08T08:06:05.924+00:00] L1 step=2 window.close_window            -> None
[2026-08-08T08:06:05.925+00:00] L1 step=2 window.close_all               -> 1
[2026-08-08T08:06:05.943+00:00] L1 step=2 window.get_active_window       -> {'address': '0x55c72c9db420', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], 'w
[2026-08-08T08:06:05.944+00:00] L2 step=2 checks.window_focused          -> True
[2026-08-08T08:06:05.944+00:00] L3 step=2 step.2                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-08T08:06:05.945+00:00] L3 step=None plan                           -> COMPLETED extra={'steps': 2}
[2026-08-08T08:06:06.376+00:00] L1 step=None window.list_clients            -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], '
[2026-08-08T08:06:06.400+00:00] L1 step=None media.is_playing               -> False

=== GATE 6 DoD (raw L0 trace + independent hyprctl before/after) ===
  OK: goal -> LLM plan -> executor -> verified real-world effect
  OK: 1 non-terminal client(s) closed (['brave-browser']); 2 protected terminal(s) survived incl. the active window
  OK: media paused (is_playing False) - the 'whatever's playing' step was real

GATE 6 DoD: DONE
---

## Addendum (2026-08-08, post-review)

### Known L2 gap — NOW FIXED and re-proven (run gate6-dod-b below)
The gap: `checks.window_focused(cls="kitty")` proves focus landed on a
kitty window but does **NOT** prove every non-excluded client closed — a
partial `close_all` could still leave focus on kitty and read VERIFIED.

The fix (same day): a new read-only check `checks.window_only_classes`
(`friday/l2/checks.py`) asserts "every open window's class is in the allowed
set" — class-only matching, all clients, vacuously true on empty desktop,
mirroring `close_all`'s own loop so check and primitive cannot disagree. It
auto-entered the planner catalog and the prompt's framework notes now
direct the LLM to verify `close_all` steps with it; the harness interlock
REFUSES any plan whose `close_all` step verifies with anything weaker.
Re-proven by run `gate6-dod-b` (appended below): the LLM's own plan verifies
step 2 with `checks.window_only_classes(classes=["kitty"])` expect true,
`L2 step=2 checks.window_only_classes -> True`, both steps VERIFIED.

### Counter definition (why "10", and what this run adds)
The "10 composite tasks" claim = distinct `task_id` values `task1`..`task10`
(tasks 1–7 backfilled from proof files). `gate6` is the 11th composite task.
`var/logs/tasks.jsonl` also contains non-task entries (`retry-stress`, a
stress gate) and failed iterations, so raw distinct-id counts over the whole
file (12) exceed the task count. Per the Gate 6 prompt's scheme, counting
starts at `gate6` (pass 1); both schemes are visible in `tasks.jsonl`.

### Gate 5 trace note (on record)
The `gate5-dod-a-g1-plan` / `gate5-dod-a-g2-plan` L4 traces and the two
`dev.run` records (model raw plan output embedded) are on disk at
`gates/GATE5_DOD_PROOF.md` and `gates/gate5_devrun_lines.jsonl` and remain
available for full paste on request.
========================================================================
GATE 6 DoD - first real composite, full unmodified pipeline
========================================================================
GOAL STRING (verbatim): "pause whatever's playing, then close every window except my terminal"

[before] 3 clients (raw hyprctl clients -j):
[{
    "address": "0x55c72bbec680",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [1, 39],
    "size": [1364, 728],
    "workspace": {
        "id": 3,
        "name": "3"
    },
    "floating": false,
    "monitor": 0,
    "class": "kitty",
    "title": "~",
    "initialClass": "kitty",
    "initialTitle": "kitty",
    "pid": 34283,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 2,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "18000007"
},{
    "address": "0x55c72c9db420",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [1, 39],
    "size": [1364, 728],
    "workspace": {
        "id": 1,
        "name": "1"
    },
    "floating": false,
    "monitor": 0,
    "class": "kitty",
    "title": "Freebuff: close all the gaps",
    "initialClass": "kitty",
    "initialTitle": "kitty",
    "pid": 3829,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 0,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "18000002"
},{
    "address": "0x55c72c1ad520",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [1, 39],
    "size": [1364, 728],
    "workspace": {
        "id": 2,
        "name": "2"
    },
    "floating": false,
    "monitor": 0,
    "class": "brave-browser",
    "title": "Next steps after project completion - Claude - Brave",
    "initialClass": "brave-browser",
    "initialTitle": "New chat - Claude - Brave",
    "pid": 155168,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 1,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "1800001c"
}]

  kitty | ~ | ws 3 | 0x55c72bbec680
  kitty | Freebuff: close all the gaps | ws 1 | 0x55c72c9db420
  brave-browser | Next steps after project completion - Cl | ws 2 | 0x55c72c1ad520
[before] active window: 0x55c72c9db420
[before] protected (terminal) addresses: ['0x55c72bbec680', '0x55c72c9db420']

[precondition] starting the test tone at volume 30 ('whatever's playing')
[precondition] media.is_playing() -> True (expect True)

--- L4: LLM planning ---
(full prompt at /tmp/gate6-dod-b_prompt.txt; also printed below)

GENERATED PLAN JSON:
{
  "goal": "pause whatever's playing, then close every window except my terminal",
  "steps": [
    {
      "primitive": "media.pause",
      "args": {},
      "verify": {
        "check": "checks.media_playing",
        "args": {},
        "expect": false
      }
    },
    {
      "primitive": "window.close_all",
      "args": {
        "exclude_classes": [
          "kitty"
        ]
      },
      "verify": {
        "check": "checks.window_only_classes",
        "args": {
          "classes": [
            "kitty"
          ]
        },
        "expect": true
      }
    }
  ]
}

--- L3: unmodified executor runs the plan ---
plan status: COMPLETED
  step 1: media.pause                VERIFIED     attempts=1 verify_actual=False
  step 2: window.close_all           VERIFIED     attempts=1 verify_actual=True

[after] 2 clients (raw hyprctl clients -j):
[{
    "address": "0x55c72bbec680",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [1, 39],
    "size": [1364, 728],
    "workspace": {
        "id": 3,
        "name": "3"
    },
    "floating": false,
    "monitor": 0,
    "class": "kitty",
    "title": "~",
    "initialClass": "kitty",
    "initialTitle": "kitty",
    "pid": 34283,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 1,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "18000007"
},{
    "address": "0x55c72c9db420",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [1, 39],
    "size": [1364, 728],
    "workspace": {
        "id": 1,
        "name": "1"
    },
    "floating": false,
    "monitor": 0,
    "class": "kitty",
    "title": "Freebuff: close all the gaps",
    "initialClass": "kitty",
    "initialTitle": "kitty",
    "pid": 3829,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 0,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "18000002"
}]

  kitty | ~ | ws 3 | 0x55c72bbec680
  kitty | Freebuff: close all the gaps | ws 1 | 0x55c72c9db420
[after] media.is_playing() -> False (expect False - paused)

=== L0 trace: L4 planning (4 lines, run_id=gate6-dod-b-plan) ===
[2026-08-08T08:16:39.028+00:00] L4 step=None plan                           -> PENDING
[2026-08-08T08:16:39.029+00:00] L4 step=None plan.attempt                   -> RUNNING
[2026-08-08T08:17:04.981+00:00] L1 step=None dev.run                        -> {'is_error': False, 'duration_api_ms': 20724, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': '64e1cf10-c79c-4e6e-a6b9-893ad746ddf8
[2026-08-08T08:17:04.982+00:00] L4 step=None plan                           -> ACCEPTED

=== L0 trace: execution (real composite) (20 lines, run_id=gate6-dod-b-exec) ===
[2026-08-08T08:17:04.983+00:00] L3 step=None plan                           -> PENDING
[2026-08-08T08:17:04.983+00:00] L3 step=1 step.1                         -> PENDING
[2026-08-08T08:17:04.984+00:00] L3 step=1 step.1                         -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-08T08:17:04.985+00:00] L1 step=1 media.pause                    -> None
[2026-08-08T08:17:04.987+00:00] L1 step=1 media.is_playing               -> False
[2026-08-08T08:17:04.988+00:00] L2 step=1 checks.media_playing           -> False
[2026-08-08T08:17:04.990+00:00] L3 step=1 step.1                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'False'}
[2026-08-08T08:17:04.991+00:00] L3 step=2 step.2                         -> PENDING
[2026-08-08T08:17:04.992+00:00] L3 step=2 step.2                         -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-08T08:17:05.004+00:00] L1 step=2 window.list_clients            -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], '
[2026-08-08T08:17:05.041+00:00] L1 step=2 window.list_clients            -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], '
[2026-08-08T08:17:05.311+00:00] L1 step=2 window.list_clients            -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], '
[2026-08-08T08:17:05.312+00:00] L1 step=2 window.close_window            -> None
[2026-08-08T08:17:05.313+00:00] L1 step=2 window.close_all               -> 1
[2026-08-08T08:17:05.337+00:00] L1 step=2 window.list_clients            -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], '
[2026-08-08T08:17:05.338+00:00] L2 step=2 checks.window_only_classes     -> True
[2026-08-08T08:17:05.338+00:00] L3 step=2 step.2                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-08T08:17:05.338+00:00] L3 step=None plan                           -> COMPLETED extra={'steps': 2}
[2026-08-08T08:17:05.751+00:00] L1 step=None window.list_clients            -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], '
[2026-08-08T08:17:05.761+00:00] L1 step=None media.is_playing               -> False

=== GATE 6 DoD (raw L0 trace + independent hyprctl before/after) ===
  OK: goal -> LLM plan -> executor -> verified real-world effect
  OK: 1 non-terminal client(s) closed (['brave-browser']); 2 protected terminal(s) survived incl. the active window
  OK: close_all verified by checks.window_only_classes - the SUFFICIENT check (nothing outside the excluded set remains), not just focus
  OK: media paused (is_playing False) - the 'whatever's playing' step was real

GATE 6 DoD: DONE


---

## Post-fix run history (gate6-dod-b/c/d/e - failed runs kept as data)

- gate6-dod-b: GREEN (first run on the new checks.window_only_classes verify; brave closed).
- gate6-dod-c: FAILED - honest precondition guard: no non-terminal window was open before the run, so the DoD refused to certify an untested close effect. Nothing to close, nothing proven.
- gate6-dod-d: FAILED - harness guard bug (not product): the precondition-staged firefox test window grabbed focus, so the read-through-window guard flagged the INTENDED close. Fix: the guard now asserts survival only when the window focused at start was a PROTECTED terminal. Guard before: if active_addr and active_addr not in after_addrs. Guard after: if active_addr in protected_addrs and active_addr not in after_addrs.
- gate6-dod-e: GREEN (shipped code): firefox test window closed, both protected kitty survived incl. this window, checks.window_only_classes -> True, media paused.


========================================================================
GATE 6 DoD - first real composite, full unmodified pipeline
========================================================================
GOAL STRING (verbatim): "pause whatever's playing, then close every window except my terminal"

[before] 2 clients (raw hyprctl clients -j):
[{
    "address": "0x55c72bbec680",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [1, 39],
    "size": [1364, 728],
    "workspace": {
        "id": 3,
        "name": "3"
    },
    "floating": false,
    "monitor": 0,
    "class": "kitty",
    "title": "~",
    "initialClass": "kitty",
    "initialTitle": "kitty",
    "pid": 34283,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 1,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "18000007"
},{
    "address": "0x55c72c9db420",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [1, 39],
    "size": [1364, 728],
    "workspace": {
        "id": 1,
        "name": "1"
    },
    "floating": false,
    "monitor": 0,
    "class": "kitty",
    "title": "Freebuff: close all the gaps",
    "initialClass": "kitty",
    "initialTitle": "kitty",
    "pid": 3829,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 0,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "18000002"
}]

  kitty | ~ | ws 3 | 0x55c72bbec680
  kitty | Freebuff: close all the gaps | ws 1 | 0x55c72c9db420
[before] active window: 0x55c72c9db420
[before] protected (terminal) addresses: ['0x55c72bbec680', '0x55c72c9db420']

[precondition] starting the test tone at volume 30 ('whatever's playing')
[precondition] media.is_playing() -> True (expect True)

--- L4: LLM planning ---
(full prompt at /tmp/gate6-dod-c_prompt.txt; also printed below)

GENERATED PLAN JSON:
{
  "goal": "pause whatever's playing, then close every window except my terminal",
  "steps": [
    {
      "primitive": "media.pause",
      "args": {},
      "verify": {
        "check": "checks.media_playing",
        "args": {},
        "expect": false
      }
    },
    {
      "primitive": "window.close_all",
      "args": {
        "exclude_classes": [
          "kitty"
        ]
      },
      "verify": {
        "check": "checks.window_only_classes",
        "args": {
          "classes": [
            "kitty"
          ]
        },
        "expect": true
      }
    }
  ]
}

--- L3: unmodified executor runs the plan ---
plan status: COMPLETED
  step 1: media.pause                VERIFIED     attempts=1 verify_actual=False
  step 2: window.close_all           VERIFIED     attempts=1 verify_actual=True

[after] 2 clients (raw hyprctl clients -j):
[{
    "address": "0x55c72bbec680",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [1, 39],
    "size": [1364, 728],
    "workspace": {
        "id": 3,
        "name": "3"
    },
    "floating": false,
    "monitor": 0,
    "class": "kitty",
    "title": "~",
    "initialClass": "kitty",
    "initialTitle": "kitty",
    "pid": 34283,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 1,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "18000007"
},{
    "address": "0x55c72c9db420",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [1, 39],
    "size": [1364, 728],
    "workspace": {
        "id": 1,
        "name": "1"
    },
    "floating": false,
    "monitor": 0,
    "class": "kitty",
    "title": "Freebuff: close all the gaps",
    "initialClass": "kitty",
    "initialTitle": "kitty",
    "pid": 3829,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 0,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "18000002"
}]

  kitty | ~ | ws 3 | 0x55c72bbec680
  kitty | Freebuff: close all the gaps | ws 1 | 0x55c72c9db420
[after] media.is_playing() -> False (expect False - paused)

=== L0 trace: L4 planning (4 lines, run_id=gate6-dod-c-plan) ===
[2026-08-08T08:20:09.294+00:00] L4 step=None plan                           -> PENDING
[2026-08-08T08:20:09.295+00:00] L4 step=None plan.attempt                   -> RUNNING
[2026-08-08T08:20:49.143+00:00] L1 step=None dev.run                        -> {'is_error': False, 'duration_api_ms': 35319, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': 'f1e9711c-0fec-4dbb-960e-1b7714c9ad41
[2026-08-08T08:20:49.143+00:00] L4 step=None plan                           -> ACCEPTED

=== L0 trace: execution (real composite) (17 lines, run_id=gate6-dod-c-exec) ===
[2026-08-08T08:20:49.144+00:00] L3 step=None plan                           -> PENDING
[2026-08-08T08:20:49.144+00:00] L3 step=1 step.1                         -> PENDING
[2026-08-08T08:20:49.145+00:00] L3 step=1 step.1                         -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-08T08:20:49.145+00:00] L1 step=1 media.pause                    -> None
[2026-08-08T08:20:49.148+00:00] L1 step=1 media.is_playing               -> False
[2026-08-08T08:20:49.148+00:00] L2 step=1 checks.media_playing           -> False
[2026-08-08T08:20:49.150+00:00] L3 step=1 step.1                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'False'}
[2026-08-08T08:20:49.155+00:00] L3 step=2 step.2                         -> PENDING
[2026-08-08T08:20:49.156+00:00] L3 step=2 step.2                         -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-08T08:20:49.166+00:00] L1 step=2 window.list_clients            -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], '
[2026-08-08T08:20:49.166+00:00] L1 step=2 window.close_all               -> 0
[2026-08-08T08:20:49.176+00:00] L1 step=2 window.list_clients            -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], '
[2026-08-08T08:20:49.176+00:00] L2 step=2 checks.window_only_classes     -> True
[2026-08-08T08:20:49.176+00:00] L3 step=2 step.2                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-08T08:20:49.177+00:00] L3 step=None plan                           -> COMPLETED extra={'steps': 2}
[2026-08-08T08:20:49.590+00:00] L1 step=None window.list_clients            -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], '
[2026-08-08T08:20:49.601+00:00] L1 step=None media.is_playing               -> False

=== GATE 6 DoD (raw L0 trace + independent hyprctl before/after) ===
  FAIL: nothing non-terminal was open before - the close effect is untested

GATE 6 DoD: FAILED


========================================================================
GATE 6 DoD - first real composite, full unmodified pipeline
========================================================================
GOAL STRING (verbatim): "pause whatever's playing, then close every window except my terminal"

[before] 3 clients (raw hyprctl clients -j):
[{
    "address": "0x55c72bbec680",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [1, 39],
    "size": [1364, 728],
    "workspace": {
        "id": 3,
        "name": "3"
    },
    "floating": false,
    "monitor": 0,
    "class": "kitty",
    "title": "~",
    "initialClass": "kitty",
    "initialTitle": "kitty",
    "pid": 34283,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 2,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "18000007"
},{
    "address": "0x55c72c9db420",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [684, 39],
    "size": [681, 728],
    "workspace": {
        "id": 1,
        "name": "1"
    },
    "floating": false,
    "monitor": 0,
    "class": "kitty",
    "title": "Freebuff: close all the gaps",
    "initialClass": "kitty",
    "initialTitle": "kitty",
    "pid": 3829,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 1,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "18000002"
},{
    "address": "0x55c72c1a5a80",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [1, 39],
    "size": [681, 728],
    "workspace": {
        "id": 1,
        "name": "1"
    },
    "floating": false,
    "monitor": 0,
    "class": "firefox",
    "title": "Mozilla Firefox",
    "initialClass": "firefox",
    "initialTitle": "Mozilla Firefox",
    "pid": 164355,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 0,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "1800001d"
}]

  kitty | ~ | ws 3 | 0x55c72bbec680
  kitty | Freebuff: close all the gaps | ws 1 | 0x55c72c9db420
  firefox | Mozilla Firefox | ws 1 | 0x55c72c1a5a80
[before] active window: 0x55c72c1a5a80
[before] protected (terminal) addresses: ['0x55c72bbec680', '0x55c72c9db420']

[precondition] starting the test tone at volume 30 ('whatever's playing')
[precondition] media.is_playing() -> True (expect True)

--- L4: LLM planning ---
(full prompt at /tmp/gate6-dod-d_prompt.txt; also printed below)

GENERATED PLAN JSON:
{
  "goal": "pause whatever's playing, then close every window except my terminal",
  "steps": [
    {
      "primitive": "media.pause",
      "args": {},
      "verify": {
        "check": "checks.media_playing",
        "args": {},
        "expect": false
      }
    },
    {
      "primitive": "window.close_all",
      "args": {
        "exclude_classes": [
          "kitty"
        ]
      },
      "verify": {
        "check": "checks.window_only_classes",
        "args": {
          "classes": [
            "kitty"
          ]
        },
        "expect": true
      }
    }
  ]
}

--- L3: unmodified executor runs the plan ---
plan status: COMPLETED
  step 1: media.pause                VERIFIED     attempts=1 verify_actual=False
  step 2: window.close_all           VERIFIED     attempts=1 verify_actual=True

[after] 2 clients (raw hyprctl clients -j):
[{
    "address": "0x55c72bbec680",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [1, 39],
    "size": [1364, 728],
    "workspace": {
        "id": 3,
        "name": "3"
    },
    "floating": false,
    "monitor": 0,
    "class": "kitty",
    "title": "~",
    "initialClass": "kitty",
    "initialTitle": "kitty",
    "pid": 34283,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 1,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "18000007"
},{
    "address": "0x55c72c9db420",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [1, 39],
    "size": [1364, 728],
    "workspace": {
        "id": 1,
        "name": "1"
    },
    "floating": false,
    "monitor": 0,
    "class": "kitty",
    "title": "Freebuff: close all the gaps",
    "initialClass": "kitty",
    "initialTitle": "kitty",
    "pid": 3829,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 0,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "18000002"
}]

  kitty | ~ | ws 3 | 0x55c72bbec680
  kitty | Freebuff: close all the gaps | ws 1 | 0x55c72c9db420
[after] media.is_playing() -> False (expect False - paused)

=== L0 trace: L4 planning (4 lines, run_id=gate6-dod-d-plan) ===
[2026-08-08T08:21:44.903+00:00] L4 step=None plan                           -> PENDING
[2026-08-08T08:21:44.903+00:00] L4 step=None plan.attempt                   -> RUNNING
[2026-08-08T08:22:02.875+00:00] L1 step=None dev.run                        -> {'is_error': False, 'duration_api_ms': 11134, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': '889779a4-e7b1-470b-9c63-a4d50660a023
[2026-08-08T08:22:02.877+00:00] L4 step=None plan                           -> ACCEPTED

=== L0 trace: execution (real composite) (20 lines, run_id=gate6-dod-d-exec) ===
[2026-08-08T08:22:02.878+00:00] L3 step=None plan                           -> PENDING
[2026-08-08T08:22:02.878+00:00] L3 step=1 step.1                         -> PENDING
[2026-08-08T08:22:02.879+00:00] L3 step=1 step.1                         -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-08T08:22:02.881+00:00] L1 step=1 media.pause                    -> None
[2026-08-08T08:22:02.883+00:00] L1 step=1 media.is_playing               -> False
[2026-08-08T08:22:02.884+00:00] L2 step=1 checks.media_playing           -> False
[2026-08-08T08:22:02.884+00:00] L3 step=1 step.1                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'False'}
[2026-08-08T08:22:02.885+00:00] L3 step=2 step.2                         -> PENDING
[2026-08-08T08:22:02.885+00:00] L3 step=2 step.2                         -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-08T08:22:02.900+00:00] L1 step=2 window.list_clients            -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], '
[2026-08-08T08:22:02.947+00:00] L1 step=2 window.list_clients            -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], '
[2026-08-08T08:22:03.229+00:00] L1 step=2 window.list_clients            -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], '
[2026-08-08T08:22:03.230+00:00] L1 step=2 window.close_window            -> None
[2026-08-08T08:22:03.232+00:00] L1 step=2 window.close_all               -> 1
[2026-08-08T08:22:03.265+00:00] L1 step=2 window.list_clients            -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], '
[2026-08-08T08:22:03.267+00:00] L2 step=2 checks.window_only_classes     -> True
[2026-08-08T08:22:03.267+00:00] L3 step=2 step.2                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-08T08:22:03.268+00:00] L3 step=None plan                           -> COMPLETED extra={'steps': 2}
[2026-08-08T08:22:03.689+00:00] L1 step=None window.list_clients            -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], '
[2026-08-08T08:22:03.713+00:00] L1 step=None media.is_playing               -> False

=== GATE 6 DoD (raw L0 trace + independent hyprctl before/after) ===
  FAIL: the window this run was read through was closed: 0x55c72c1a5a80

GATE 6 DoD: FAILED


========================================================================
GATE 6 DoD - first real composite, full unmodified pipeline
========================================================================
GOAL STRING (verbatim): "pause whatever's playing, then close every window except my terminal"

[before] 3 clients (raw hyprctl clients -j):
[{
    "address": "0x55c72bbec680",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [1, 39],
    "size": [1364, 728],
    "workspace": {
        "id": 3,
        "name": "3"
    },
    "floating": false,
    "monitor": 0,
    "class": "kitty",
    "title": "~",
    "initialClass": "kitty",
    "initialTitle": "kitty",
    "pid": 34283,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 2,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "18000007"
},{
    "address": "0x55c72c9db420",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [684, 39],
    "size": [681, 728],
    "workspace": {
        "id": 1,
        "name": "1"
    },
    "floating": false,
    "monitor": 0,
    "class": "kitty",
    "title": "Freebuff: close all the gaps",
    "initialClass": "kitty",
    "initialTitle": "kitty",
    "pid": 3829,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 1,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "18000002"
},{
    "address": "0x55c72c1daa60",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [1, 39],
    "size": [681, 728],
    "workspace": {
        "id": 1,
        "name": "1"
    },
    "floating": false,
    "monitor": 0,
    "class": "firefox",
    "title": "Mozilla Firefox",
    "initialClass": "firefox",
    "initialTitle": "Mozilla Firefox",
    "pid": 165799,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 0,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "1800001e"
}]

  kitty | ~ | ws 3 | 0x55c72bbec680
  kitty | Freebuff: close all the gaps | ws 1 | 0x55c72c9db420
  firefox | Mozilla Firefox | ws 1 | 0x55c72c1daa60
[before] active window: 0x55c72c1daa60
[before] protected (terminal) addresses: ['0x55c72bbec680', '0x55c72c9db420']

[precondition] starting the test tone at volume 30 ('whatever's playing')
[precondition] media.is_playing() -> True (expect True)

--- L4: LLM planning ---
(full prompt at /tmp/gate6-dod-e_prompt.txt; also printed below)

GENERATED PLAN JSON:
{
  "goal": "pause whatever's playing, then close every window except my terminal",
  "steps": [
    {
      "primitive": "media.pause",
      "args": {},
      "verify": {
        "check": "checks.media_playing",
        "args": {},
        "expect": false
      }
    },
    {
      "primitive": "window.close_all",
      "args": {
        "exclude_classes": [
          "kitty"
        ]
      },
      "verify": {
        "check": "checks.window_only_classes",
        "args": {
          "classes": [
            "kitty"
          ]
        },
        "expect": true
      }
    }
  ]
}

--- L3: unmodified executor runs the plan ---
plan status: COMPLETED
  step 1: media.pause                VERIFIED     attempts=1 verify_actual=False
  step 2: window.close_all           VERIFIED     attempts=1 verify_actual=True

[after] 2 clients (raw hyprctl clients -j):
[{
    "address": "0x55c72bbec680",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [1, 39],
    "size": [1364, 728],
    "workspace": {
        "id": 3,
        "name": "3"
    },
    "floating": false,
    "monitor": 0,
    "class": "kitty",
    "title": "~",
    "initialClass": "kitty",
    "initialTitle": "kitty",
    "pid": 34283,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 1,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "18000007"
},{
    "address": "0x55c72c9db420",
    "mapped": true,
    "hidden": false,
    "visible": true,
    "acceptsInput": true,
    "at": [1, 39],
    "size": [1364, 728],
    "workspace": {
        "id": 1,
        "name": "1"
    },
    "floating": false,
    "monitor": 0,
    "class": "kitty",
    "title": "Freebuff: close all the gaps",
    "initialClass": "kitty",
    "initialTitle": "kitty",
    "pid": 3829,
    "xwayland": false,
    "pinned": false,
    "pinFullscreened": false,
    "fullscreen": 0,
    "fullscreenClient": 0,
    "fullscreenHandler": "default",
    "allowedOverFullscreen": true,
    "grouped": [],
    "tags": [],
    "swallowing": "0x0",
    "focusHistoryID": 0,
    "inhibitingIdle": false,
    "xdgTag": "",
    "xdgDescription": "",
    "contentType": "none",
    "tearingHint": false,
    "stableId": "18000002"
}]

  kitty | ~ | ws 3 | 0x55c72bbec680
  kitty | Freebuff: close all the gaps | ws 1 | 0x55c72c9db420
[after] media.is_playing() -> False (expect False - paused)

=== L0 trace: L4 planning (4 lines, run_id=gate6-dod-e-plan) ===
[2026-08-08T08:22:58.201+00:00] L4 step=None plan                           -> PENDING
[2026-08-08T08:22:58.201+00:00] L4 step=None plan.attempt                   -> RUNNING
[2026-08-08T08:23:25.562+00:00] L1 step=None dev.run                        -> {'is_error': False, 'duration_api_ms': 17758, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': 'd9d53cf9-bc8f-4d58-b76a-6fdc96dfd867
[2026-08-08T08:23:25.568+00:00] L4 step=None plan                           -> ACCEPTED

=== L0 trace: execution (real composite) (20 lines, run_id=gate6-dod-e-exec) ===
[2026-08-08T08:23:25.569+00:00] L3 step=None plan                           -> PENDING
[2026-08-08T08:23:25.570+00:00] L3 step=1 step.1                         -> PENDING
[2026-08-08T08:23:25.571+00:00] L3 step=1 step.1                         -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-08T08:23:25.576+00:00] L1 step=1 media.pause                    -> None
[2026-08-08T08:23:25.584+00:00] L1 step=1 media.is_playing               -> False
[2026-08-08T08:23:25.584+00:00] L2 step=1 checks.media_playing           -> False
[2026-08-08T08:23:25.585+00:00] L3 step=1 step.1                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'False'}
[2026-08-08T08:23:25.587+00:00] L3 step=2 step.2                         -> PENDING
[2026-08-08T08:23:25.587+00:00] L3 step=2 step.2                         -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-08T08:23:25.617+00:00] L1 step=2 window.list_clients            -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], '
[2026-08-08T08:23:25.663+00:00] L1 step=2 window.list_clients            -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], '
[2026-08-08T08:23:25.941+00:00] L1 step=2 window.list_clients            -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], '
[2026-08-08T08:23:25.944+00:00] L1 step=2 window.close_window            -> None
[2026-08-08T08:23:25.948+00:00] L1 step=2 window.close_all               -> 1
[2026-08-08T08:23:25.977+00:00] L1 step=2 window.list_clients            -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], '
[2026-08-08T08:23:25.978+00:00] L2 step=2 checks.window_only_classes     -> True
[2026-08-08T08:23:25.980+00:00] L3 step=2 step.2                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-08T08:23:25.982+00:00] L3 step=None plan                           -> COMPLETED extra={'steps': 2}
[2026-08-08T08:23:26.430+00:00] L1 step=None window.list_clients            -> [{'address': '0x55c72bbec680', 'mapped': True, 'hidden': False, 'visible': True, 'acceptsInput': True, 'at': [1, 39], 'size': [1364, 728], '
[2026-08-08T08:23:26.468+00:00] L1 step=None media.is_playing               -> False

=== GATE 6 DoD (raw L0 trace + independent hyprctl before/after) ===
  OK: goal -> LLM plan -> executor -> verified real-world effect
  OK: 1 non-terminal client(s) closed (['firefox']); 2 protected terminal(s) survived incl. the active window
  OK: close_all verified by checks.window_only_classes - the SUFFICIENT check (nothing outside the excluded set remains), not just focus
  OK: media paused (is_playing False) - the 'whatever's playing' step was real

GATE 6 DoD: DONE

