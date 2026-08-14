# PHASE_C_V1_PROOF - weekly cross-project digest (narrow v1)

Status date: 2026-08-10T19:04:29+00:00.

The ENABLED `weekly-cross-project-digest` trigger's plan
(config/watcher.json, Sundays 10:00) run through the REAL executor
(run_plan): the exact plan the watcher will run on Sunday - same
primitives, same verifies, same allowlist. The watcher-wrapping path
(record -> notify) is proven by WATCHER_DEPLOY_PROOF + the committed-
trigger unit test; this run proves the real gather -> synthesize ->
verify cycle on the real repos. The L0 log was pointed at a temp file
for this run; the digest text comes from the StepResult the executor
now carries (the log clips results to 500 chars).

## The plan (deterministic - no L4 LLM call)

```
{
  "goal": "produce a weekly cross-project digest: summarize recent git activity and planning docs across Friday and Agent-Reach, with 1-2 concrete cross-project suggestions",
  "steps": [
    {
      "primitive": "git.log",
      "args": {
        "repo_path": "/home/lakshay/Projects/Friday V2",
        "count": 10
      },
      "verify": {
        "check": "checks.list_nonempty",
        "args": {
          "value": "$steps.1.result"
        },
        "expect": true
      }
    },
    {
      "primitive": "git.log",
      "args": {
        "repo_path": "/home/lakshay/Projects/Agent-Reach",
        "count": 10
      },
      "verify": {
        "check": "checks.list_nonempty",
        "args": {
          "value": "$steps.2.result"
        },
        "expect": true
      }
    },
    {
      "primitive": "files.read_text",
      "args": {
        "path": "/home/lakshay/Projects/Agent-Reach/CHANGELOG.md",
        "max_chars": 6000
      },
      "verify": {
        "check": "checks.text_nonempty",
        "args": {
          "value": "$steps.3.result.text"
        },
        "expect": true
      }
    },
    {
      "primitive": "dev.digest",
      "args": {
        "context": {
          "friday git log": "$steps.1.result",
          "agent-reach git log": "$steps.2.result",
          "agent-reach CHANGELOG": "$steps.3.result.text"
        }
      },
      "verify": {
        "check": "checks.text_nonempty",
        "args": {
          "value": "$steps.4.result"
        },
        "expect": true
      }
    },
    {
      "primitive": "notify.notify_send",
      "args": {
        "title": "Friday: weekly cross-project digest",
        "body": "$steps.4.result"
      },
      "verify": {
        "check": "checks.text_nonempty",
        "args": {
          "value": "$steps.5.result.body"
        },
        "expect": true
      }
    }
  ]
}
```

Primitives: `git.log` (new, read-only), `files.read_text` (new, bounded
reader), `dev.digest` (new - the ONE live full-tier LLM call per run,
~$0.17, the same documented LLM-in-primitive exception as
gmail.summarize; a digest is a terminal read-only artifact), and
`notify.notify_send` (step 5 - the digest text is DELIVERED to the
desktop as the notification body, verified by checks.text_nonempty on
the notify envelope's returned body: the strongest honest claim about
a fire-and-forget action, the same spirit as message_sent verifying a
returned id). The trigger allowlist is exactly these four, so the plan
can never reach for anything side-effecting.

## Plan result (every step VERIFIED)

```
step 1: git.log VERIFIED (attempts=1)
step 2: git.log VERIFIED (attempts=1)
step 3: files.read_text VERIFIED (attempts=1)
step 4: dev.digest VERIFIED (attempts=1)
step 5: notify.notify_send VERIFIED (attempts=1)
```

## What git.log gathered (from the temp L0 trace)

```
/home/lakshay/Projects/Friday V2:
  2026-08-10 lakshay-sharma-02: Capability-gap loop: refusal -> record -> LLM triage draft (approval pending) (b728b4f)
  2026-08-10 lakshay-sharma-02: gmail.summarize in E2E + watcher wired into real gmail + docs to latest (8c95ff0)
  2026-08-10 lakshay-sharma-02: TESTS_PROOF: refresh status date (214/214 re-verified) (5982321)
  2026-08-10 lakshay-sharma-02: E2E: fourth live goal - gmail.list_unread against the real inbox (704385d)
  2026-08-10 lakshay-sharma-02: Close remaining coverage gaps + live E2E check (2c07f53)
  2026-08-10 lakshay-sharma-02: Test everything: 200-test unittest suite + TESTS_PROOF gate (ed83f9d)
  2026-08-10 lakshay-sharma-02: Harden core (P0) + ambient watch loop (P1) (079f1a0)
  2026-08-10 lakshay-sharma-02: Log hygiene: rotation, compact window lines, gmail redaction, duplicate observe fix (3dde00e)
  2026-08-09 lakshay-sharma-02: Initial commit: Friday V8 - layered desktop automation (L0-L4) with all gates/tasks proofs (1a58e38)
/home/lakshay/Projects/Agent-Reach:
  2026-07-25 Pnant: Merge pull request #530 from Panniantong/codex/p0-hardening-20260725 (b4d52c4)
  2026-07-25 Pnant: fix(xiaohongshu): resolve OpenCLI status at check time (fb1a898)
  2026-07-25 Pnant: docs(auth): enforce explicit cookie guidance (18cce85)
  2026-07-25 Pnant: fix(transcribe): reject oversized media before processing (f3fef51)
  2026-07-25 Pnant: fix(cli): fail closed on credential setup errors (ec4c696)
  2026-07-25 Pnant: fix(security): make diagnostics provably read-only (b336726)
  2026-07-25 Pnant: fix(security): enforce least-privilege credential boundaries (fe58c3f)
  2026-07-25 Pnant: fix(doctor): make health checks truthful and read-only (6d67d70)
  2026-07-25 Pnant: test: isolate pytest from user home (be51421)
  2026-07-25 Pnant: fix(youtube): install required default dependencies (bb55cc6)
```

## The digest (real LLM output)

```
Friday – In the last two days the team merged a capability‑gap loop that records refusals and produces LLM triage drafts, completed E2E Gmail integration with summarize and live unread checks, closed remaining test coverage, hardened core components, and refined log hygiene with rotation and de‑duplication.  

Agent‑reach – On July 25 the repository received a series of security‑focused updates, including a merged hardening PR, enforced least‑privilege credential boundaries, read‑only diagnostics, truthful health checks, pytest isolation, and YouTube dependency fixes.  

Suggestion 1 – Adopt Friday’s log‑rotation and de‑duplication logic (e.g., rotate logs after 7 days and suppress duplicate “observe” entries) in Agent‑reach to keep logs lean and easier to audit.  

Suggestion 2 – Extend Agent‑reach’s security model by adding a refusal‑recording triage step (similar to Friday’s loop) that logs denied credential attempts and auto‑generates a triage summary for review, reinforcing the least‑privilege enforcement.
```

## Honest quality assessment

```
SPECIFIC - the digest names concrete things from the gathered sources (concrete references found: ['gmail', 'Friday', 'capability', 'security', 'hardening'])
```

## The real watcher run (record + notify delivery)

Beyond the executor run above, the SAME committed trigger was fired
through the REAL watcher (`run_watcher(once=True)`, schedule moved to
00:00 only, temp fired-state so the real `var/state/watcher_fired.json`
is untouched) with the REAL `var/logs/tasks.jsonl` and desktop
notification. The recorded line:

```
{
  "task_id": "watch:weekly-cross-project-digest",
  "goal": "produce a weekly cross-project digest: summarize recent git activity and planning docs across Friday and Agent-Reach, with 1-2 concrete cross-project suggestions",
  "gate6_passed": true,
  "timestamp": "2026-08-10T19:05:25+00:00",
  "proof": "{\"trigger\": \"weekly-cross-project-digest\", \"status\": \"COMPLETED\", \"steps\": [{\"step_id\": 1, \"primitive\": \"git.log\", \"status\": \"VERIFIED\", \"attempts\": 1}, {\"step_id\": 2, \"primitive\": \"git.log\", \"status\": \"VERIFIED\", \"attempts\": 1}, {\"step_id\": 3, \"primitive\": \"files.read_text\", \"status\": \"VERIFIED\", \"attempts\": 1}, {\"step_id\": 4, \"primitive\": \"dev.digest\", \"status\": \"VERIFIED\", \"attempts\": 1}, {\"step_id\": 5, \"primitive\": \"notify.notify_send\", \"status\": \"VERIFIED\", \"attempts\": 1}]}"
}
```

This is the 22nd distinct passing task id. The digest text reached the
desktop as the notify step's body (the watcher's `_notify_outcome` also
pings on completion, like the gmail digest).

## Verdict

PASS - the ambient pattern (watcher trigger ->
read-only gather primitives -> LLM synthesis -> notify delivery ->
record) extends cleanly to reading ACROSS repos. The digest above is
REAL output from the real repos on this machine (Friday V2 +
Agent-Reach - the only two repos present under ~/Projects). Whether the
suggestions are worth acting on is judged in the quality assessment:
both name concrete mechanisms that exist (log rotation + dedup, the
refusal-recording triage loop), so the specific-vs-generic signal is
favorable for v1 - and the human remains the judge of whether 2-repo
synthesis is useful enough to scale to more repos.

## Cost

One full-tier LLM call per digest run (~$0.17) - the suggestion-drafting
call itself, weekly. No L4 planning call (deterministic plan). If cost
matters, the read/summarize split (cheap tier for gathering, full tier
for the final suggestion) is the documented next step.

