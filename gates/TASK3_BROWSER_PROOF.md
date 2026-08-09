========================================================================
TASK 3 (Gate-6-grade proof) - first full-stack browser task
========================================================================
GOAL: "open example.com in the browser and verify it shows 'Example Domain'"
  - first time the browser primitive ran through LLM plan -> executor -> verify
  - single-step plan: browser.goto("https://example.com") verified via
    checks.browser_has_text("Example Domain") -> True (DOM-based, no screenshots)
  - iteration history (defects fixed inside the gate, per master plan):
      attempt 1: url "example.com" (no scheme) + redundant window.open_app(firefox)
                -> executor ABORTed loudly: goto requires an http(s) URL
      attempt 2: correct https URL; verify asked for hostname "example.com",
                which is NOT in the visible page text -> verify never matched
      attempt 3 (this run): clean single-step plan, VERIFIED, no stray app open
    -> prompt now teaches: full http(s):// URLs; verify a phrase you expect
       to SEE on the page, not the bare hostname.
Raw run output (goal -> LLM plan -> browser -> verified):
========================================================================
TASK 3 - first full-stack browser task: open + verify example.com
========================================================================
GOAL: "open example.com in the browser and verify it shows 'Example Domain'"

--- L4: LLM planning ---
LLM-produced plan JSON:
{
  "goal": "open example.com in the browser and verify it shows 'Example Domain'",
  "steps": [
    {
      "primitive": "browser.goto",
      "args": {
        "url": "https://example.com"
      },
      "verify": {
        "check": "checks.browser_has_text",
        "args": {
          "substring": "Example Domain"
        },
        "expect": true
      }
    }
  ]
}

--- L3: executor runs the LLM plan (real browser) ---
plan status: COMPLETED
  step 1: browser.goto               VERIFIED     attempts=1 verify_actual=True

=== L0 trace: L4 planning (4 lines, run_id=task3-final-plan) ===
[2026-08-07T18:48:18.944+00:00] L4 step=None plan                           -> PENDING
[2026-08-07T18:48:18.945+00:00] L4 step=None plan.attempt                   -> RUNNING
[2026-08-07T18:48:30.995+00:00] L1 step=None dev.run                        -> {'is_error': False, 'duration_api_ms': 6366, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': 'a874462c-4765-49bb-8b0e-73152ac2790c', 'total_cost_usd': 0.15107, 'usage': {'input_tokens': '<redacted>', 'cache_creation_input_tokens': '<redacted>', 'cache_read_input_tokens': '<redacted>', 'output_tokens': '<redacted>', 'server_tool_use': {'web_search_requests': 0, 'web_fetch_requests': 0}, 'service_tier': 'standard', 'cache_creation': {'ephemeral_1h_input_tokens': '<redacted>', 'ephemeral_5m_input_tokens': '<redacted>'}, 'inference_geo': '', 'iterations': [], 'speed': 'standard'}, 'modelUsage': {'openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free': {'inputTokens': '<redacted>', 'outputTokens': '<redacted>', 'cacheReadInputTokens': '<redacted>', 'cacheCreationInputTokens': '<redacted>', 'webSearchRequests': 0, 'costUSD': 0.15107, 'contextWindow': 200000, 'maxOutputTokens': '<redacted>', 'canonicalModel': 'openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free', 'provider': 'firstParty'}}, 'permission_denials': [], 'terminal_reason': 'completed', 'fast_mode_state': 'off', 'fast_mode_disabled_reason': 'sdk_opt_in_required', 'subtype': 'success', 'api_error_status': None, 'result': '{\n  "goal": "open example.com in the browser and verify it shows \'Example Domain\'",\n  "steps": [\n    {\n      "primitive": "browser.goto",\n      "args": {\n        "url": "https://example.com"\n      },\n      "verify": {\n        "check": "checks.browser_has_text",\n        "args": {\n          "substring": "Example Domain"\n        },\n        "expect": true\n      }\n    }\n  ]\n}', 'ttft_ms': 5915, 'ttft_stream_ms': 2829, 'time_to_request_ms': 247, 'type': 'result', 'duration_ms': 6605}
[2026-08-07T18:48:30.996+00:00] L4 step=None plan                           -> ACCEPTED

=== L0 trace: execution (real browser) (8 lines, run_id=task3-final-exec) ===
[2026-08-07T18:48:30.996+00:00] L3 step=None plan                           -> PENDING
[2026-08-07T18:48:30.997+00:00] L3 step=1 step.1                         -> PENDING
[2026-08-07T18:48:30.997+00:00] L3 step=1 step.1                         -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-07T18:48:34.923+00:00] L1 step=1 browser.goto                   -> {'url': 'https://example.com/', 'title': 'Example Domain'}
[2026-08-07T18:48:35.016+00:00] L1 step=1 browser.read_page_text         -> Example Domain

This domain is for use in documentation examples without needing permission. Avoid use in operations.

Learn more
[2026-08-07T18:48:35.020+00:00] L2 step=1 checks.browser_has_text        -> True
[2026-08-07T18:48:35.035+00:00] L3 step=1 step.1                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-07T18:48:35.035+00:00] L3 step=None plan                           -> COMPLETED extra={'steps': 1}

TASK 3: DONE (goal -> LLM plan -> browser -> verified; trace above)
EXIT_CODE=0
