# Task 9 proof: composite media control (Gate-6-grade)

Goal -> LLM plan -> executor -> verified, on real audio state, unattended.

GOAL: "play the test tone, verify it is playing, pause it and verify it is
      paused, resume it and verify it is playing again, then stop it and
      verify it is stopped"

First full-stack composite over media.pause / media.resume / media.stop
(proven standalone in the remaining primitives bring-up, now executor-driven
from an LLM plan). Audio only - zero window interaction.

The plan composed media.play -> media.pause -> media.resume -> media.stop
exactly as the recipe prescribed (the timed auto-stop pattern explicitly
does not apply to this manual-pause/resume/stop goal). Every step VERIFIED,
and the real end state is media.is_playing() == False.

DoD (checked from the raw L0 trace + real player state):
  1. every step VERIFIED; plan composed play -> pause -> resume -> stop,
  2. the player is stopped at the end (media.is_playing() False).

Raw output from the shipped gate run (run label `task9-media-a`) follows:

---
========================================================================
TASK 9 - composite media control (play -> pause -> resume -> stop)
========================================================================
GOAL: 'play the test tone, verify it is playing, pause it and verify it is paused, resume it and verify it is playing again, then stop it and verify it is stopped'

--- L4: LLM planning ---
LLM-produced plan JSON:
{
  "goal": "play the test tone, verify it is playing, pause it and verify it is paused, resume it and verify it is playing again, then stop it and verify it is stopped",
  "steps": [
    {
      "primitive": "media.play",
      "args": {
        "source": "/home/lakshay/Projects/Friday V2/assets/test_tone.mp3"
      },
      "verify": {
        "check": "checks.media_playing",
        "args": {},
        "expect": true
      }
    },
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
      "primitive": "media.resume",
      "args": {},
      "verify": {
        "check": "checks.media_playing",
        "args": {},
        "expect": true
      }
    },
    {
      "primitive": "media.stop",
      "args": {},
      "verify": {
        "check": "checks.media_playing",
        "args": {},
        "expect": false
      }
    }
  ]
}

--- L3: executor runs the LLM plan (real audio) ---
plan status: COMPLETED
  step 1: media.play                 VERIFIED     attempts=1 verify_actual=True
  step 2: media.pause                VERIFIED     attempts=1 verify_actual=False
  step 3: media.resume               VERIFIED     attempts=1 verify_actual=True
  step 4: media.stop                 VERIFIED     attempts=1 verify_actual=False

[end state] media.is_playing() -> False  (expect False)

=== L0 trace: L4 planning (7 lines, run_id=task9-media-a-plan) ===
[2026-08-08T07:33:15.327+00:00] L4 step=None plan                           -> PENDING
[2026-08-08T07:33:15.328+00:00] L4 step=None plan.attempt                   -> RUNNING
[2026-08-08T07:33:30.565+00:00] L1 step=None dev.run                        -> {'is_error': False, 'duration_api_ms': 10205, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': 'abd7a706-f38b-4bb5-b03f-96e40c32ca4a', 'total_cost_usd': 0.170315, 'usage': {'input_tokens': '<redacted>', 'cache_creation_input_tokens': '<redacted>', 'cache_read_input_tokens': '<redacted>', 'output_tokens': '<redacted>', 'server_tool_use': {'web_search_requests': 0, 'web_fetch_requests': 0}, 'service_tier': 'standard', 'cache_creation': {'ephemeral_1h_input_tokens': '<redacted>', 'ephemeral_5m_input_tokens': '<redacted>'}, 'inference_geo': '', 'iterations': [], 'speed': 'standard'}, 'modelUsage': {'openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free': {'inputTokens': '<redacted>', 'outputTokens': '<redacted>', 'cacheReadInputTokens': '<redacted>', 'cacheCreationInputTokens': '<redacted>', 'webSearchRequests': 0, 'costUSD': 0.170315, 'contextWindow': 200000, 'maxOutputTokens': '<redacted>', 'canonicalModel': 'openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free', 'provider': 'firstParty'}}, 'permission_denials': [], 'terminal_reason': 'completed', 'fast_mode_state': 'off', 'fast_mode_disabled_reason': 'sdk_opt_in_required', 'subtype': 'success', 'api_error_status': None, 'result': '{\n  "goal": "play the test tone, verify it is playing, pause it and verify it is paused, resume it and verify it is playing again, then stop it and verify it is stopped",\n  "steps": [\n    {\n      "primitive": "media.play",\n      "args": {\n        "source": "$facts.test_tone"\n      },\n      "verify": {\n        "check": "checks.media_playing",\n        "args": {},\n        "expect": true\n      }\n    },\n    {\n      "primitive": "checks.media_playing",\n      "args": {},\n      "verify": {\n        "chec...<+1171 chars>', 'ttft_ms': 7436, 'ttft_stream_ms': 1704, 'time_to_request_ms': 137, 'type': 'result', 'duration_ms': 10333}
[2026-08-08T07:33:30.566+00:00] L4 step=None plan.attempt                   -> FAILED EXC: plan failed schema validation: step 2: unknown or unregistered primitive 'checks.media_playing'
[2026-08-08T07:33:30.566+00:00] L4 step=None plan.attempt                   -> RUNNING
[2026-08-08T07:33:44.372+00:00] L1 step=None dev.run                        -> {'is_error': False, 'duration_api_ms': 9508, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': '15749739-7ecb-4e7c-86bf-e65a8221580a', 'total_cost_usd': 0.16211, 'usage': {'input_tokens': '<redacted>', 'cache_creation_input_tokens': '<redacted>', 'cache_read_input_tokens': '<redacted>', 'output_tokens': '<redacted>', 'server_tool_use': {'web_search_requests': 0, 'web_fetch_requests': 0}, 'service_tier': 'standard', 'cache_creation': {'ephemeral_1h_input_tokens': '<redacted>', 'ephemeral_5m_input_tokens': '<redacted>'}, 'inference_geo': '', 'iterations': [], 'speed': 'standard'}, 'modelUsage': {'openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free': {'inputTokens': '<redacted>', 'outputTokens': '<redacted>', 'cacheReadInputTokens': '<redacted>', 'cacheCreationInputTokens': '<redacted>', 'webSearchRequests': 0, 'costUSD': 0.16211, 'contextWindow': 200000, 'maxOutputTokens': '<redacted>', 'canonicalModel': 'openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free', 'provider': 'firstParty'}}, 'permission_denials': [], 'terminal_reason': 'completed', 'fast_mode_state': 'off', 'fast_mode_disabled_reason': 'sdk_opt_in_required', 'subtype': 'success', 'api_error_status': None, 'result': '{\n  "goal": "play the test tone, verify it is playing, pause it and verify it is paused, resume it and verify it is playing again, then stop it and verify it is stopped",\n  "steps": [\n    {\n      "primitive": "media.play",\n      "args": {\n        "source": "$facts.test_tone"\n      },\n      "verify": {\n        "check": "checks.media_playing",\n        "args": {},\n        "expect": true\n      }\n    },\n    {\n      "primitive": "media.pause",\n      "args": {},\n      "verify": {\n        "check": "chec...<+433 chars>', 'ttft_ms': 8353, 'ttft_stream_ms': 1763, 'time_to_request_ms': 212, 'type': 'result', 'duration_ms': 9696}
[2026-08-08T07:33:44.373+00:00] L4 step=None plan                           -> ACCEPTED

=== L0 trace: execution (real audio) (28 lines, run_id=task9-media-a-exec) ===
[2026-08-08T07:33:44.373+00:00] L3 step=None plan                           -> PENDING
[2026-08-08T07:33:44.373+00:00] L3 step=1 step.1                         -> PENDING
[2026-08-08T07:33:44.374+00:00] L3 step=1 step.1                         -> RUNNING extra={'attempt': 1, 'max_attempts': 1}
[2026-08-08T07:33:44.904+00:00] L1 step=1 media.play                     -> {'pid': 127141, 'socket': '/tmp/friday_mpv.sock', 'source': '/home/lakshay/Projects/Friday V2/assets/test_tone.mp3'}
[2026-08-08T07:33:44.910+00:00] L1 step=1 media.is_playing               -> True
[2026-08-08T07:33:44.910+00:00] L2 step=1 checks.media_playing           -> True
[2026-08-08T07:33:44.911+00:00] L3 step=1 step.1                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-08T07:33:44.911+00:00] L3 step=2 step.2                         -> PENDING
[2026-08-08T07:33:44.911+00:00] L3 step=2 step.2                         -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-08T07:33:44.913+00:00] L1 step=2 media.pause                    -> None
[2026-08-08T07:33:44.918+00:00] L1 step=2 media.is_playing               -> False
[2026-08-08T07:33:44.919+00:00] L2 step=2 checks.media_playing           -> False
[2026-08-08T07:33:44.919+00:00] L3 step=2 step.2                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'False'}
[2026-08-08T07:33:44.922+00:00] L3 step=3 step.3                         -> PENDING
[2026-08-08T07:33:44.922+00:00] L3 step=3 step.3                         -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-08T07:33:44.924+00:00] L1 step=3 media.resume                   -> None
[2026-08-08T07:33:44.932+00:00] L1 step=3 media.is_playing               -> True
[2026-08-08T07:33:44.935+00:00] L2 step=3 checks.media_playing           -> True
[2026-08-08T07:33:44.936+00:00] L3 step=3 step.3                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-08T07:33:44.936+00:00] L3 step=4 step.4                         -> PENDING
[2026-08-08T07:33:44.936+00:00] L3 step=4 step.4                         -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-08T07:33:45.059+00:00] L1 step=4 media.stop                     -> None
[2026-08-08T07:33:45.060+00:00] L1 step=4 media.is_playing               -> False
[2026-08-08T07:33:45.060+00:00] L2 step=4 checks.media_playing           -> False
[2026-08-08T07:33:45.060+00:00] L3 step=4 step.4                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'False'}
[2026-08-08T07:33:45.060+00:00] L3 step=None plan                           -> COMPLETED extra={'steps': 4}
[2026-08-08T07:33:45.083+00:00] L1 step=None media.stop                     -> None
[2026-08-08T07:33:45.083+00:00] L1 step=None media.is_playing               -> False

=== TASK 9 DoD (from raw L0 trace + real player state) ===
  OK: every step VERIFIED; plan composed play -> pause -> resume -> stop
  OK: media.is_playing() False at the end - the player is stopped

TASK 9: DONE (goal -> LLM plan -> media control -> verified; player stopped)
