========================================================================
TASK 4 (Gate-6-grade proof) - first click/type browser interaction
========================================================================
GOAL: "search for 'example domain' on DuckDuckGo and report the first result title"
  - first full-stack proof of browser INTERACTION (type + key + verify)
  - plan: goto -> type_text("search privately", ...) -> press_key(Enter)
  - report = verified assertion that the first result title "Example Domain"
    is on the results page (browser_has_text polls False->True as it loads)
  - machinery built/fixed inside this gate:
      * checks.browser_input_has_value (new L2 read-only check) - the only
        honest way to verify typed text landed; reads a contained input
        when the handle resolves to a wrapper
      * find_locator attribute matching is now case-insensitive (was
        missing DDG placeholders like "Search privately")
      * prompt now requires REAL page handles (a made-up one like
        "search box" fails loudly at the step - shown in iteration 1)
  - iteration: task4-a used a non-existent handle and ABORTed loudly;
    task4-b (this run) is green.
Raw run output (goal -> LLM plan -> browser interaction -> verified):
========================================================================
TASK 4 - first click/type interaction: DuckDuckGo search
========================================================================
GOAL: "search for 'example domain' on DuckDuckGo and report the first result title"

--- L4: LLM planning ---
LLM-produced plan JSON:
{
  "goal": "search for 'example domain' on DuckDuckGo and report the first result title",
  "steps": [
    {
      "primitive": "browser.goto",
      "args": {
        "url": "https://duckduckgo.com/"
      },
      "verify": {
        "check": "checks.browser_has_text",
        "args": {
          "substring": "DuckDuckGo"
        },
        "expect": true
      }
    },
    {
      "primitive": "browser.type_text",
      "args": {
        "what": "search privately",
        "text": "example domain",
        "timeout_ms": 10000
      },
      "verify": {
        "check": "checks.browser_input_has_value",
        "args": {
          "what": "search privately",
          "value": "example domain"
        },
        "expect": true
      }
    },
    {
      "primitive": "browser.press_key",
      "args": {
        "what": null,
        "key": "Enter"
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
  step 2: browser.type_text          VERIFIED     attempts=1 verify_actual=True
  step 3: browser.press_key          VERIFIED     attempts=1 verify_actual=True

=== L0 trace: L4 planning (4 lines, run_id=task4-b-plan) ===
[2026-08-07T19:05:10.565+00:00] L4 step=None plan                           -> PENDING
[2026-08-07T19:05:10.565+00:00] L4 step=None plan.attempt                   -> RUNNING
[2026-08-07T19:06:04.780+00:00] L1 step=None dev.run                        -> {'is_error': False, 'duration_api_ms': 49194, 'num_turns': 1, 'stop_reason': 'end_turn', 'session_id': '10ca5019-3f6d-46ce-aec9-c03793a784eb', 'total_cost_usd': 0.16012, 'usage': {'input_tokens': '<redacted>', 'cache_creation_input_tokens': '<redacted>', 'cache_read_input_tokens': '<redacted>', 'output_tokens': '<redacted>', 'server_tool_use': {'web_search_requests': 0, 'web_fetch_requests': 0}, 'service_tier': 'standard', 'cache_creation': {'ephemeral_1h_input_tokens': '<redacted>', 'ephemeral_5m_input_tokens': '<redacted>'}, 'inference_geo': '', 'iterations': [], 'speed': 'standard'}, 'modelUsage': {'openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free': {'inputTokens': '<redacted>', 'outputTokens': '<redacted>', 'cacheReadInputTokens': '<redacted>', 'cacheCreationInputTokens': '<redacted>', 'webSearchRequests': 0, 'costUSD': 0.16012, 'contextWindow': 200000, 'maxOutputTokens': '<redacted>', 'canonicalModel': 'openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free', 'provider': 'firstParty'}}, 'permission_denials': [], 'terminal_reason': 'completed', 'fast_mode_state': 'off', 'fast_mode_disabled_reason': 'sdk_opt_in_required', 'subtype': 'success', 'api_error_status': None, 'result': '{\n  "goal": "search for \'example domain\' on DuckDuckGo and report the first result title",\n  "steps": [\n    {\n      "primitive": "browser.goto",\n      "args": {\n        "url": "https://duckduckgo.com/"\n      },\n      "verify": {\n        "check": "checks.browser_has_text",\n        "args": {\n          "substring": "DuckDuckGo"\n        },\n        "expect": true\n      }\n    },\n    {\n      "primitive": "browser.type_text",\n      "args": {\n        "what": "search privately",\n        "text": "example d...<+544 chars>', 'ttft_ms': 43855, 'ttft_stream_ms': 2203, 'time_to_request_ms': 101, 'type': 'result', 'duration_ms': 49297}
[2026-08-07T19:06:04.780+00:00] L4 step=None plan                           -> ACCEPTED

=== L0 trace: execution (real browser) (27 lines, run_id=task4-b-exec) ===
[2026-08-07T19:06:04.781+00:00] L3 step=None plan                           -> PENDING
[2026-08-07T19:06:04.781+00:00] L3 step=1 step.1                         -> PENDING
[2026-08-07T19:06:04.781+00:00] L3 step=1 step.1                         -> RUNNING extra={'attempt': 1, 'max_attempts': 3}
[2026-08-07T19:06:10.953+00:00] L1 step=1 browser.goto                   -> {'url': 'https://duckduckgo.com/', 'title': 'DuckDuckGo - Protection. Privacy. Peace of mind.'}
[2026-08-07T19:06:11.119+00:00] L1 step=1 browser.read_page_text         -> Duck.ai
Main navigation menu closed
Menu
DuckDuckGo
DuckDuckGo
Search
Duck.ai
Protection. Privacy. Peace of mind.
AI Settings
Protect your personal information on all your devices.

DESKTOP & MOBILE BROWSER

Mac

Windows

iOS

Android

DESKTOP BROWSER EXTENSION

Chrome

Edge

Firefox

Opera

Discover more from DuckDuckGo.

Private Search

Duck.ai

Subscription

Email

Search or enter address
Search Privately

Evade scams & data-hungry companies

PROTECTION

Block most ads & cookie pop-ups

PRIVA...<+6316 chars>
[2026-08-07T19:06:11.122+00:00] L2 step=1 checks.browser_has_text        -> True
[2026-08-07T19:06:11.125+00:00] L3 step=1 step.1                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-07T19:06:11.126+00:00] L3 step=2 step.2                         -> PENDING
[2026-08-07T19:06:11.130+00:00] L3 step=2 step.2                         -> RUNNING extra={'attempt': 1, 'max_attempts': 1}
[2026-08-07T19:06:15.216+00:00] L1 step=2 browser.find_locator           -> <Locator frame=<Frame name= url='https://duckduckgo.com/'> selector='[placeholder*="search privately" i] >> nth=0'>
[2026-08-07T19:06:15.499+00:00] L1 step=2 browser.type_text              -> {'typed_into': 'search privately', 'length': 14}
[2026-08-07T19:06:19.531+00:00] L1 step=2 browser.find_locator           -> <Locator frame=<Frame name= url='https://duckduckgo.com/'> selector='[placeholder*="search privately" i] >> nth=0'>
[2026-08-07T19:06:19.543+00:00] L2 step=2 checks.browser_input_has_value -> True
[2026-08-07T19:06:19.543+00:00] L3 step=2 step.2                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-07T19:06:19.544+00:00] L3 step=3 step.3                         -> PENDING
[2026-08-07T19:06:19.545+00:00] L3 step=3 step.3                         -> RUNNING extra={'attempt': 1, 'max_attempts': 1}
[2026-08-07T19:06:19.596+00:00] L1 step=3 browser.press_key              -> {'key': 'Enter'}
[2026-08-07T19:06:19.621+00:00] L1 step=3 browser.read_page_text         -> Duck.ai
Main navigation menu closed
Menu
DuckDuckGo
DuckDuckGo
Search
Duck.ai
Protection. Privacy. Peace of mind.
AI Settings
Protect your personal information on all your devices.

DESKTOP & MOBILE BROWSER

Mac

Windows

iOS

Android

DESKTOP BROWSER EXTENSION

Chrome

Edge

Firefox

Opera

Discover more from DuckDuckGo.

Private Search

Duck.ai

Subscription

Email

Search or enter address
Search Privately

Evade scams & data-hungry companies

PROTECTION

Block most ads & cookie pop-ups

PRIVA...<+6316 chars>
[2026-08-07T19:06:19.623+00:00] L2 step=3 checks.browser_has_text        -> False
[2026-08-07T19:06:20.315+00:00] L1 step=3 browser.read_page_text         -> 
[2026-08-07T19:06:20.318+00:00] L2 step=3 checks.browser_has_text        -> False
[2026-08-07T19:06:21.292+00:00] L1 step=3 browser.read_page_text         -> DuckDuckGo
Close menu
SEARCH
Homepage
Themes
Settings
SHARE FEEDBACK
DOWNLOADS
iOS Browser
Android Browser
Mac Browser
Windows Browser
Browser Extensions
MORE FROM DUCKDUCKGO
Duck.ai
Email Protection
Newsletter
Blog
Podcast
Collaborations
LEARN MORE
What’s New
Compare Privacy
About Our Browser
About DuckDuckGo
OTHER RESOURCES
Help
Community
Careers
Privacy Policy
Terms of Service
Press Kit
Advertise on Search

Switch to DuckDuckGo and take back your privacy!

1
We don't store your personal info....<+94 chars>
[2026-08-07T19:06:21.297+00:00] L2 step=3 checks.browser_has_text        -> False
[2026-08-07T19:06:22.114+00:00] L1 step=3 browser.read_page_text         -> DuckDuckGo
 All
Images
Videos
News
Maps
Search Assist
 Duck.ai
Search Settings
Protected
India (en)
Safe search: moderate
Any time

Example Domain

www.example.com

Example Domain
This domain is for use in illustrative examples in documents and literature without prior coordination or permission.
Entrar

This domain is for use in illustrative examples in documents and literature without prior coordination or permission.

Wikipedia

https://en.wikipedia.org › wiki › Example.com

example.com - Wik...<+4117 chars>
[2026-08-07T19:06:22.118+00:00] L2 step=3 checks.browser_has_text        -> True
[2026-08-07T19:06:22.120+00:00] L3 step=3 step.3                         -> VERIFIED extra={'attempts': 1, 'verify_actual': 'True'}
[2026-08-07T19:06:22.120+00:00] L3 step=None plan                           -> COMPLETED extra={'steps': 3}

TASK 4: DONE (goal -> LLM plan -> type/press -> verified; first result title in trace)
EXIT_CODE=0
