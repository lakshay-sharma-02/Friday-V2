# TASK whatsapp-filesend — WhatsApp file-send re-prove (Phase 2 Section 1)

Status date: 2026-08-08.

## 1. The board item, restated

Phase 2 Section 1 asked to fix "files stage correctly in the WhatsApp Web
upload flow but the send action fails silently." The diagnostic protocol
that came with it (DOM locators, disabled send buttons, click races,
stale locators) was written for the **Playwright/web.whatsapp.com path**.

That path does not exist in the current stack.

## 2. Confirmed root cause (the DoD's "not just it works now")

- The current L1 primitive `friday/l1/whatsapp.py` is the official
  WhatsApp Business **Cloud API** — a two-step REST flow
  (`POST /{phone_number_id}/media` -> `media_id`, then
  `POST /{phone_number_id}/messages` -> `wamid`), with no DOM, no
  staging, no send button. There is nothing to race, go stale, or
  silently swallow.
- The "stages but doesn't send" symptom belonged to the **superseded
  browser automation** (`gates/send_file_whatsapp.py`,
  `send_readme_whatsapp.py`, `_send_whatsapp_decisive.py`,
  `_diag_whatsapp_account.py`), which was **removed on 2026-08-08**
  after the Cloud API migration made it dead code. Only the Cloud API
  CLI (`gates/send_file_whatsapp_api.py`) remains.
- The L0 log holds every WhatsApp call this stack has ever made:
  **7 calls (2026-08-07), 0 exceptions, all VERIFIED** — including the
  `upload_document -> send_document` pairs from `gate6-exec` and
  `task1-receipt-exec`. No silent failure has ever been recorded in the
  Cloud API path.
- Non-2xx responses are raised loudly: both primitives raise
  `PrimitiveError` with the response body, and L0 logs every exception.
  An error body cannot be swallowed by this code.
- The 24-hour customer-service window is not a factor: Friday is a
  registered **admin user** on the WhatsApp Business account, so the
  out-of-window rejection class does not apply to these sends.

Conclusion: there was no bug to fix in the current architecture — the
symptom was a phantom carried over from an era of the project that no
longer exists. Section 1 is therefore closed as **re-proven**, not
patched.

## 3. What this run proves (fresh, stronger than absence-of-exception)

The goal was run through the **unmodified** pipeline (L4 LLM plan -> L3
executor -> L2 verify -> L0 log) with zero scaffolding, same as Task 11:

- GOAL (verbatim): `"send the README.md file to my whatsapp"`
- The send step's verify is `checks.message_sent(platform="whatsapp",
  message_id="$steps.2.result.message_id")` — the fresh wamid itself is
  the asserted state, not "no exception."
- Fresh artifacts, raw in the trace below: media_id `1304998864816975`,
  wamid `wamid.HBgMOTE4Mzk2MDIwODA3FQIAERgSRUE4NkNERjg2RDEwNDQyRDAzAA==`.
- Bonus evidence: the L4 planning trace shows the first attempt rejected
  by `validate_plan` (the LLM emitted `checks.whatsapp_identity_ok` as a
  *primitive*), regenerated, and accepted — the schema-validation layer
  firing exactly as designed, before L3 ever saw the malformed plan.

Registered in `var/logs/tasks.jsonl` as `whatsapp-filesend`,
`gate6_passed: true`.

## 4. Raw run output

================================================================
========================================================================
TASK whatsapp-filesend - WhatsApp file-send re-prove (Cloud API, unmodified pipeline)
========================================================================
GOAL: 'send the README.md file to my whatsapp'

--- L4: LLM planning ---
LLM-produced plan JSON:
{
  "goal": "send the README.md file to my whatsapp",
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
    },
    {
      "primitive": "whatsapp.send_document",
      "args": {
        "file_path": "$steps.1.result.path",
        "to": "918396020807"
      },
      "verify": {
        "check": "checks.message_sent",
        "args": {
          "platform": "whatsapp",
          "message_id": "$steps.2.result.message_id"
        },
        "expect": true
      }
    }
  ]
}

--- L3: executor runs the LLM plan (real send) ---
plan status: COMPLETED
  step 1: files.find_file            VERIFIED     attempts=1 verify_actual=True
  step 2: whatsapp.send_document     VERIFIED     attempts=1 verify_actual=True

=== L0 trace: L4 planning (7 lines, run_id=whatsapp-filesend-plan) ===
[2026-08-08T09:45:30.009+00:00] L4 step=None plan                           -> PENDING
[2026-08-08T09:45:30.010+00:00] L4 step=None plan.attempt                   -> RUNNING
[2026-08-08T09:45:55.304+00:00] L1 step=None dev.run                        -> {'is_error': False, 'duration_api_ms': 19901, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': 'd6ce2107-bfd8-4a1a-b8e0-64dbf1e42218', 'total_cost_usd': 0.16231, 'usage': {'input_tokens': '<redacted>', 'cache_creation_input_tokens': '<redacted>', 'cache_read_input_tokens': '<redacted>', 'output_tokens': '<redacted>', 'server_tool_use': {'web_search_requests': 0, 'web_fetch_requests': 0}, 'service_tier': 'standard', 'cache_creation': {'ephemeral_1h_input_tokens': '<redacted>', 'ephemeral_5m_input_tokens': '<redacted>'}, 'inference_geo': '', 'iterations': [], 'speed': 'standard'}, 'modelUsage': {'openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free': {'inputTokens': '<redacted>', 'outputTokens': '<redacted>', 'cacheReadInputTokens': '<redacted>', 'cacheCreationInputTokens': '<redacted>', 'webSearchRequests': 0, 'costUSD': 0.16231, 'contextWindow': 200000, 'maxOutputTokens': '<redacted>', 'canonicalModel': 'openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free', 'provider': 'firstParty'}}, 'permission_denials': [], 'terminal_reason': 'completed', 'fast_mode_state': 'off', 'fast_mode_disabled_reason': 'sdk_opt_in_required', 'subtype': 'success', 'api_error_status': None, 'result': '{\n  "goal": "send the README.md file to my whatsapp",\n  "steps": [\n    {\n      "primitive": "files.find_file",\n      "args": {\n        "name": "README.md",\n        "directory": "$facts.project",\n        "recursive": false\n      },\n      "verify": {\n        "check": "checks.file_exists",\n        "args": {\n          "path": "$steps.1.result.path"\n        },\n        "expect": true\n      }\n    },\n    {\n      "primitive": "checks.whatsapp_identity_ok",\n      "args": {},\n      "verify": {\n        "che...<+463 chars>', 'ttft_ms': 15873, 'ttft_stream_ms': 7578, 'time_to_request_ms': 196, 'type': 'result', 'duration_ms': 20078}
[2026-08-08T09:45:55.304+00:00] L4 step=None plan.attempt                   -> FAILED EXC: plan failed schema validation: step 2: unknown or unregistered primitive 'checks.whatsapp_identity_ok'
[2026-08-08T09:45:55.305+00:00] L4 step=None plan.attempt                   -> RUNNING
[2026-08-08T09:46:24.896+00:00] L1 step=None dev.run                        -> {'is_error': False, 'duration_api_ms': 25799, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': 'd67ba7bf-e8dc-48ab-b907-8bb131c37b9c', 'total_cost_usd': 0.165215, 'usage': {'input_tokens': '<redacted>', 'cache_creation_input_tokens': '<redacted>', 'cache_read_input_tokens': '<redacted>', 'output_tokens': '<redacted>', 'server_tool_use': {'web_search_requests': 0, 'web_fetch_requests': 0}, 'service_tier': 'standard', 'cache_creation': {'ephemeral_1h_input_tokens': '<redacted>', 'ephemeral_5m_input_tokens': '<redacted>'}, 'inference_geo': '', 'iterations': [], 'speed': 'standard'}, 'modelUsage': {'openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free': {'inputTokens': '<redacted>', 'outputTokens': '<redacted>', 'cacheReadInputTokens': '<redacted>', 'cacheCreationInputTokens': '<redacted>', 'webSearchRequests': 0, 'costUSD': 0.165215, 'contextWindow': 200000, 'maxOutputTokens': '<redacted>', 'canonicalModel': 'openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free', 'provider': 'firstParty'}}, 'permission_denials': [], 'terminal_reason': 'completed', 'fast_mode_state': 'off', 'fast_mode_disabled_reason': 'sdk_opt_in_required', 'subtype': 'success', 'api_error_status': None, 'result': '{\n  "goal": "send the README.md file to my whatsapp",\n  "steps": [\n    {\n      "primitive": "files.find_file",\n      "args": {\n        "name": "README.md",\n        "directory": "$facts.project",\n        "recursive": false\n      },\n      "verify": {\n        "check": "checks.file_exists",\n        "args": {\n          "path": "$steps.1.result.path"\n        },\n        "expect": true\n      }\n    },\n    {\n      "primitive": "whatsapp.send_document",\n      "args": {\n        "file_path": "$steps.1.result...<+265 chars>', 'ttft_ms': 22520, 'ttft_stream_ms': 2157, 'time_to_request_ms': 143, 'type': 'result', 'duration_ms': 25928}
[2026-08-08T09:46:24.896+00:00] L4 step=None plan                           -> ACCEPTED

=== L0 trace: execution (real send) (13 lines, run_id=whatsapp-filesend-exec) ===
[2026-08-08T09:46:24.897+00:00] L3 step=None plan                           -> PENDING
[2026-08-08T09:46:24.897+00:00] L3 step=1 step.1                         -> PENDING
[2026-08-08T09:46:24.898+00:00] L3 step=1 step.1                         -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-08T09:46:24.898+00:00] L1 step=1 files.find_file                -> {'path': '/home/lakshay/Projects/Friday V2/README.md', 'name': 'README.md', 'matches': ['/home/lakshay/Projects/Friday V2/README.md']}
[2026-08-08T09:46:24.899+00:00] L2 step=1 checks.file_exists             -> True
[2026-08-08T09:46:24.899+00:00] L3 step=1 step.1                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-08T09:46:24.899+00:00] L3 step=2 step.2                         -> PENDING
[2026-08-08T09:46:24.899+00:00] L3 step=2 step.2                         -> RUNNING extra={'attempt': 1, 'max_attempts': 1}
[2026-08-08T09:46:26.859+00:00] L1 step=2 whatsapp.upload_document       -> 1304998864816975
[2026-08-08T09:46:29.624+00:00] L1 step=2 whatsapp.send_document         -> {'message_id': 'wamid.HBgMOTE4Mzk2MDIwODA3FQIAERgSRUE4NkNERjg2RDEwNDQyRDAzAA==', 'to': '918396020807', 'filename': 'README.md', 'api': {'messaging_product': 'whatsapp', 'contacts': [{'input': '<too deep>', 'wa_id': '<too deep>'}], 'messages': [{'id': '<too deep>'}]}}
[2026-08-08T09:46:29.624+00:00] L2 step=2 checks.message_sent            -> True
[2026-08-08T09:46:29.624+00:00] L3 step=2 step.2                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-08T09:46:29.625+00:00] L3 step=None plan                           -> COMPLETED extra={'steps': 2}

=== TASK DoD (fresh wamid + checks.message_sent + raw trace) ===
  OK: fresh wamid returned by whatsapp.send_document: True (wamid.HBgMOTE4Mzk2MDIwODA3FQIAERgSRUE4Nk...)
  OK: checks.message_sent on that id -> True: True
  OK: all steps VERIFIED: True
  OK: raw L0 trace captured above (media_id + wamid, not summarized): True

TASK whatsapp-filesend: DONE - registered in var/logs/tasks.jsonl as gate6_passed=True
