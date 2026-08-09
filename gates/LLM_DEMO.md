========================================================================
LIVE LLM DEMO - do the LLM planning calls work?
========================================================================
GOAL: 'pause any playing audio'

--- L4: LLM planning ---
LLM-produced plan JSON:
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
steps: 1

--- L3: executor runs the LLM plan ---
plan status: COMPLETED
  step 1: media.pause            VERIFIED     attempts=1 verify_actual=False

=== L0 trace: L4 planning (4 lines, run_id=llm-demo) ===
[2026-08-07T15:26:44.677+00:00] L4 step=None plan                       -> PENDING
[2026-08-07T15:26:44.677+00:00] L4 step=None plan.attempt               -> RUNNING
[2026-08-07T15:27:12.812+00:00] L1 step=None dev.run                    -> {'is_error': False, 'duration_api_ms': 20767, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': 'b5785d56-ad2b-4237-a5aa-c299d9ec4897', 'total_cost_usd': 0.14479, 'usage': {'input_tokens': '<redacted>', 'cache_creation_input_tokens': '<redacted>', 'cache_read_input_tokens': '<redacted>', 'output_tokens': '<redacted>', 'server_tool_use': {'web_search_requests': 0, 'web_fetch_requests': 0}, 'service_tier': 'standard', 'cache_creation': {'ephemeral_1h_input_tokens': '<redacted>', 'ephemeral_5m_input_tokens': '<redacted>'}, 'inference_geo': '', 'iterations': [], 'speed': 'standard'}, 'modelUsage': {'openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free': {'inputTokens': '<redacted>', 'outputTokens': '<redacted>', 'cacheReadInputTokens': '<redacted>', 'cacheCreationInputTokens': '<redacted>', 'webSearchRequests': 0, 'costUSD': 0.14479, 'contextWindow': 200000, 'maxOutputTokens': '<redacted>', 'canonicalModel': 'openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free', 'provider': 'firstParty'}}, 'permission_denials': [], 'terminal_reason': 'completed', 'fast_mode_state': 'off', 'fast_mode_disabled_reason': 'sdk_opt_in_required', 'subtype': 'success', 'api_error_status': None, 'result': '{\n  "goal": "pause any playing audio",\n  "steps": [\n    {\n      "primitive": "media.pause",\n      "args": {},\n      "verify": {\n        "check": "checks.media_playing",\n        "args": {},\n        "expect": false\n      }\n    }\n  ]\n}', 'ttft_ms': 21088, 'ttft_stream_ms': 3868, 'time_to_request_ms': 1887, 'type': 'result', 'duration_ms': 22328}
[2026-08-07T15:27:12.819+00:00] L4 step=None plan                       -> ACCEPTED

=== L0 trace: execution (8 lines, run_id=llm-demo-exec) ===
[2026-08-07T15:27:12.820+00:00] L3 step=None plan                       -> PENDING
[2026-08-07T15:27:12.821+00:00] L3 step=1 step.1                     -> PENDING
[2026-08-07T15:27:12.822+00:00] L3 step=1 step.1                     -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-07T15:27:12.824+00:00] L1 step=1 media.pause                -> None
[2026-08-07T15:27:12.825+00:00] L1 step=1 media.is_playing           -> False
[2026-08-07T15:27:12.826+00:00] L2 step=1 checks.media_playing       -> False
[2026-08-07T15:27:12.826+00:00] L3 step=1 step.1                     -> VERIFIED extra={'attempts': 1, 'verify_actual': 'False'}
[2026-08-07T15:27:12.826+00:00] L3 step=None plan                       -> COMPLETED extra={'steps': 1}

DEMO: OK - LLM calls work end-to-end
