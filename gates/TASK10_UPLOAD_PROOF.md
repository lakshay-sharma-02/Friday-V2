# Task 10 proof: composite browser upload (Gate-6-grade)

Goal -> LLM plan -> executor -> verified, on real page state, unattended.

GOAL: "open the upload test page served by the harness, upload the file
      named 'friday_upload_test.txt' to it, and report whether the upload
      succeeded by reading the page text"

First full-stack composite over browser.upload_file (proven standalone in
the remaining primitives bring-up, now executor-driven from an LLM plan).
The harness served a throwaway local page with a file input whose JS change
handler reports the selected filename in the page text - the upload's
real-world effect is readable state, exactly what the L2 checks read. No
external service involved.

The plan composed browser.goto -> browser.upload_file -> browser.read_page_text.
The upload_file result in the trace reports input_count=1, and the final
page read reports "selected: friday_upload_test.txt" - the upload really
landed.

DoD (checked from the raw L0 trace):
  1. every step VERIFIED; plan used browser.goto + browser.upload_file,
  2. upload_file reported input_count >= 1,
  3. the final page read reports the uploaded filename.

Raw output from the shipped gate run (run label `task10-upload-a`) follows:

---
========================================================================
TASK 10 - composite browser upload (goto -> upload_file -> report)
========================================================================
GOAL: "open the upload test page served by the harness, upload the file named 'friday_upload_test.txt' to it, and report whether the upload succeeded by reading the page text"

--- L4: LLM planning ---
LLM-produced plan JSON:
{
  "goal": "open the upload test page served by the harness, upload the file named 'friday_upload_test.txt' to it, and report whether the upload succeeded by reading the page text",
  "steps": [
    {
      "primitive": "browser.goto",
      "args": {
        "url": "http://127.0.0.1:46887/index.html"
      },
      "verify": {
        "check": "checks.browser_has_text",
        "args": {
          "substring": "friday upload test"
        },
        "expect": true
      }
    },
    {
      "primitive": "browser.upload_file",
      "args": {
        "what": null,
        "path": "/home/lakshay/Projects/Friday V2/var/logs/upload_tmp/friday_upload_test.txt"
      },
      "verify": {
        "check": "checks.browser_has_text",
        "args": {
          "substring": "selected: friday_upload_test.txt"
        },
        "expect": true
      }
    },
    {
      "primitive": "browser.read_page_text",
      "args": {},
      "verify": {
        "check": "checks.browser_has_text",
        "args": {
          "substring": "selected: friday_upload_test.txt"
        },
        "expect": true
      }
    }
  ]
}

--- L3: executor runs the LLM plan (real browser upload) ---
plan status: COMPLETED
  step 1: browser.goto               VERIFIED     attempts=1 verify_actual=True
  step 2: browser.upload_file        VERIFIED     attempts=1 verify_actual=True
  step 3: browser.read_page_text     VERIFIED     attempts=1 verify_actual=True

=== L0 trace: L4 planning (4 lines, run_id=task10-upload-a-plan) ===
[2026-08-08T07:34:16.430+00:00] L4 step=None plan                           -> PENDING
[2026-08-08T07:34:16.431+00:00] L4 step=None plan.attempt                   -> RUNNING
[2026-08-08T07:34:29.202+00:00] L1 step=None dev.run                        -> {'is_error': False, 'duration_api_ms': 8458, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': '8f93f9f1-9ed9-4c7a-82a7-3d09abf1a6df', 'total_cost_usd': 0.16298999999999997, 'usage': {'input_tokens': '<redacted>', 'cache_creation_input_tokens': '<redacted>', 'cache_read_input_tokens': '<redacted>', 'output_tokens': '<redacted>', 'server_tool_use': {'web_search_requests': 0, 'web_fetch_requests': 0}, 'service_tier': 'standard', 'cache_creation': {'ephemeral_1h_input_tokens': '<redacted>', 'ephemeral_5m_input_tokens': '<redacted>'}, 'inference_geo': '', 'iterations': [], 'speed': 'standard'}, 'modelUsage': {'openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free': {'inputTokens': '<redacted>', 'outputTokens': '<redacted>', 'cacheReadInputTokens': '<redacted>', 'cacheCreationInputTokens': '<redacted>', 'webSearchRequests': 0, 'costUSD': 0.16298999999999997, 'contextWindow': 200000, 'maxOutputTokens': '<redacted>', 'canonicalModel': 'openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free', 'provider': 'firstParty'}}, 'permission_denials': [], 'terminal_reason': 'completed', 'fast_mode_state': 'off', 'fast_mode_disabled_reason': 'sdk_opt_in_required', 'subtype': 'success', 'api_error_status': None, 'result': '{\n  "goal": "open the upload test page served by the harness, upload the file named \'friday_upload_test.txt\' to it, and report whether the upload succeeded by reading the page text",\n  "steps": [\n    {\n      "primitive": "browser.goto",\n      "args": {\n        "url": "http://127.0.0.1:46887/index.html"\n      },\n      "verify": {\n        "check": "checks.browser_has_text",\n        "args": {\n          "substring": "friday upload test"\n        },\n        "expect": true\n      }\n    },\n    {\n      "p...<+565 chars>', 'ttft_ms': 7182, 'ttft_stream_ms': 2495, 'time_to_request_ms': 677, 'type': 'result', 'duration_ms': 8663}
[2026-08-08T07:34:29.203+00:00] L4 step=None plan                           -> ACCEPTED

=== L0 trace: execution (real browser upload) (21 lines, run_id=task10-upload-a-exec) ===
[2026-08-08T07:34:29.203+00:00] L3 step=None plan                           -> PENDING
[2026-08-08T07:34:29.204+00:00] L3 step=1 step.1                         -> PENDING
[2026-08-08T07:34:29.204+00:00] L3 step=1 step.1                         -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-08T07:34:33.668+00:00] L1 step=1 browser.goto                   -> {'url': 'http://127.0.0.1:46887/index.html', 'title': ''}
[2026-08-08T07:34:33.723+00:00] L1 step=1 browser.read_page_text         -> friday upload test
no file
[2026-08-08T07:34:33.723+00:00] L2 step=1 checks.browser_has_text        -> True
[2026-08-08T07:34:33.724+00:00] L3 step=1 step.1                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-08T07:34:33.725+00:00] L3 step=2 step.2                         -> PENDING
[2026-08-08T07:34:33.725+00:00] L3 step=2 step.2                         -> RUNNING extra={'attempt': 1, 'max_attempts': 1}
[2026-08-08T07:34:34.202+00:00] L1 step=2 browser.upload_file            -> {'path': '/home/lakshay/Projects/Friday V2/var/logs/upload_tmp/friday_upload_test.txt', 'input_count': 1}
[2026-08-08T07:34:34.209+00:00] L1 step=2 browser.read_page_text         -> friday upload test
selected: friday_upload_test.txt
[2026-08-08T07:34:34.209+00:00] L2 step=2 checks.browser_has_text        -> True
[2026-08-08T07:34:34.210+00:00] L3 step=2 step.2                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-08T07:34:34.211+00:00] L3 step=3 step.3                         -> PENDING
[2026-08-08T07:34:34.214+00:00] L3 step=3 step.3                         -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-08T07:34:34.230+00:00] L1 step=3 browser.read_page_text         -> friday upload test
selected: friday_upload_test.txt
[2026-08-08T07:34:34.236+00:00] L1 step=3 browser.read_page_text         -> friday upload test
selected: friday_upload_test.txt
[2026-08-08T07:34:34.236+00:00] L2 step=3 checks.browser_has_text        -> True
[2026-08-08T07:34:34.237+00:00] L3 step=3 step.3                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-08T07:34:34.237+00:00] L3 step=None plan                           -> COMPLETED extra={'steps': 3}
[2026-08-08T07:34:34.797+00:00] L1 step=None browser.close                  -> None

=== TASK 10 DoD (from raw L0 trace) ===
  OK: every step VERIFIED; plan used goto -> upload_file -> read_page_text
  OK: upload_file attached to 1 file input(s)
  OK: final page read reports the uploaded file: 'selected: friday_upload_test.txt'

TASK 10: DONE (goal -> LLM plan -> upload -> verified page state)
