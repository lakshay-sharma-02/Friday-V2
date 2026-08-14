# PHASE_C_V2_PROOF - weekly cross-project digest over real owned repos

Status date: 2026-08-11T16:13:33+00:00.



v1 proved the gather -> synthesize -> deliver pattern works mechanically
but paired Friday with Agent-Reach - a THIRD-PARTY repo, not Lakshay's -
so the suggestions were specific-sounding yet not actionable. v2 drops
Agent-Reach entirely and pairs Friday with **vivaha + Aether**, two repos
Lakshay owns with real recent activity (vivaha last pushed 2026-07-18,
Aether 2026-07-13). Jarvis is excluded as dormant (1 commit in 90 days);
Friday-V3 is excluded THIS ROUND by design - it is flagged in PLAN_STATUS
as containing an earlier correlation-engine implementation worth a
dedicated future look, and is NOT mined here. Psyche Space and
ChangelogAI are excluded pending a separate decision (no GitHub copy
under lakshay-sharma-02).

The ENABLED `weekly-cross-project-digest` trigger's plan
(config/watcher.json, Sundays 10:00) runs through the REAL executor
(run_plan): the exact plan the watcher will run on Sunday - same
primitives, same verifies, same allowlist. The L0 log is pointed at a
temp file; the digest text comes from the StepResult the executor
carries (the log clips results to 500 chars).

## The plan (deterministic - no L4 LLM call)

```
{
  "goal": "produce a weekly cross-project digest: summarize recent git activity and current priorities across Friday, vivaha and Aether, with 1-2 concrete cross-project suggestions tied to each repo's actual priorities",
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
        "repo_path": "/home/lakshay/Projects/vivaha",
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
      "primitive": "git.log",
      "args": {
        "repo_path": "/home/lakshay/Projects/Aether",
        "count": 10
      },
      "verify": {
        "check": "checks.list_nonempty",
        "args": {
          "value": "$steps.3.result"
        },
        "expect": true
      }
    },
    {
      "primitive": "files.find_recent_doc",
      "args": {
        "repo_path": "/home/lakshay/Projects/Friday V2"
      },
      "verify": {
        "check": "checks.file_exists",
        "args": {
          "path": "$steps.4.result"
        },
        "expect": true
      }
    },
    {
      "primitive": "files.find_recent_doc",
      "args": {
        "repo_path": "/home/lakshay/Projects/vivaha"
      },
      "verify": {
        "check": "checks.file_exists",
        "args": {
          "path": "$steps.5.result"
        },
        "expect": true
      }
    },
    {
      "primitive": "files.find_recent_doc",
      "args": {
        "repo_path": "/home/lakshay/Projects/Aether"
      },
      "verify": {
        "check": "checks.file_exists",
        "args": {
          "path": "$steps.6.result"
        },
        "expect": true
      }
    },
    {
      "primitive": "files.read_text",
      "args": {
        "path": "$steps.4.result",
        "max_chars": 10000
      },
      "verify": {
        "check": "checks.text_nonempty",
        "args": {
          "value": "$steps.7.result.text"
        },
        "expect": true
      }
    },
    {
      "primitive": "files.read_text",
      "args": {
        "path": "$steps.5.result",
        "max_chars": 6000
      },
      "verify": {
        "check": "checks.text_nonempty",
        "args": {
          "value": "$steps.8.result.text"
        },
        "expect": true
      }
    },
    {
      "primitive": "files.read_text",
      "args": {
        "path": "$steps.6.result",
        "max_chars": 6000
      },
      "verify": {
        "check": "checks.text_nonempty",
        "args": {
          "value": "$steps.9.result.text"
        },
        "expect": true
      }
    },
    {
      "primitive": "dev.digest",
      "args": {
        "context": {
          "friday git log": "$steps.1.result",
          "vivaha git log": "$steps.2.result",
          "aether git log": "$steps.3.result",
          "friday status doc": "$steps.7.result.text",
          "vivaha status doc": "$steps.8.result.text",
          "aether status doc": "$steps.9.result.text"
        }
      },
      "verify": {
        "check": "checks.text_nonempty",
        "args": {
          "value": "$steps.10.result"
        },
        "expect": true
      }
    },
    {
      "primitive": "digestcheck.verify_attribution",
      "args": {
        "digest": "$steps.10.result",
        "context": {
          "friday": [
            "$steps.1.result",
            "$steps.7.result.text"
          ],
          "vivaha": [
            "$steps.2.result",
            "$steps.8.result.text"
          ],
          "aether": [
            "$steps.3.result",
            "$steps.9.result.text"
          ]
        }
      },
      "verify": {
        "check": "checks.text_nonempty",
        "args": {
          "value": "$steps.11.result"
        },
        "expect": true
      }
    },
    {
      "primitive": "notify.notify_send",
      "args": {
        "title": "Friday: weekly cross-project digest",
        "body": "$steps.11.result"
      },
      "verify": {
        "check": "checks.text_nonempty",
        "args": {
          "value": "$steps.12.result.body"
        },
        "expect": true
      }
    }
  ]
}
```

Primitives: `git.log` (gather), `files.find_recent_doc` (recency-
based status-doc discovery: most recently modified PLAN_STATUS/ROADMAP/
DEVLOG/STATUS/TODO/CHANGELOG-shaped file, README fallback), `files.read_text`
(the status docs), `dev.digest` (the ONE live full-tier LLM call per run,
~$0.17, the same documented LLM-in-primitive exception as gmail.summarize),
`digestcheck.verify_attribution` (the MECHANICAL attribution check - every
"X's <mechanism>" claim must appear in X's OWN gathered content, not just
anywhere in the combined prompt), and `notify.notify_send` (the digest text
is DELIVERED to the desktop as the notification body, verified by
checks.text_nonempty on the returned envelope body). The trigger
allowlist is exactly these six - the plan can never reach for anything
side-effecting.

## Plan result (every step VERIFIED)

```
step 1: git.log VERIFIED (attempts=1)
step 2: git.log VERIFIED (attempts=1)
step 3: git.log VERIFIED (attempts=1)
step 4: files.find_recent_doc VERIFIED (attempts=1)
step 5: files.find_recent_doc VERIFIED (attempts=1)
step 6: files.find_recent_doc VERIFIED (attempts=1)
step 7: files.read_text VERIFIED (attempts=1)
step 8: files.read_text VERIFIED (attempts=1)
step 9: files.read_text VERIFIED (attempts=1)
step 10: dev.digest VERIFIED (attempts=1)
step 11: digestcheck.verify_attribution VERIFIED (attempts=1)
step 12: notify.notify_send VERIFIED (attempts=1)
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
/home/lakshay/Projects/vivaha:
  2026-07-18 lakshay-sharma-02: retheme: all remaining pages to Indian wedding palette (3fecc69)
  2026-07-18 lakshay-sharma-02: Image of register page changed (8994a05)
  2026-07-18 lakshay-sharma-02: fix: prerender error on /login — wrap useSearchParams in Suspense boundary (70b1205)
  2026-07-18 lakshay-sharma-02: fix: functional gaps + Indian wedding visual retheme (d7d5320)
  2026-07-13 lakshay-sharma-02: Observation test (6325a25)
  2026-07-05 lakshay-sharma-02: Fixed issues (b6eed2b)
  2026-07-05 lakshay-sharma-02: fix: cast supabase to any to properly bypass typescript method chaining checks (9cb81ed)
  2026-07-05 lakshay-sharma-02: fix: ignore ts errors for new supabase tables until types are generated (db7810a)
  2026-07-05 lakshay-sharma-02: fix: incorrect supabase server import in navbar actions (542ab49)
  2026-07-05 lakshay-sharma-02: feat: add Mega Menu Navbar with dynamic categories and Supabase migration (836afd8)
/home/lakshay/Projects/Aether:
  2026-07-13 lakshay-sharma-02: Restarting the project (34012dc)
  2026-05-31 lakshay-sharma-02: The updates are completed and the commit message is as follows: (8098181)
  2026-05-31 lakshay-sharma-02: finished updates: might leave the project (58464a9)
  2026-05-17 lakshay-sharma-02: fix: remove code-model=kernel (causes bootloader PageAlreadyMapped panic); fix serial target (d713d89)
  2026-05-17 lakshay-sharma-02: fix: Makefile uses WSL qemu with curses/serial, cargo bootimage via full path (ab71156)
  2026-05-17 lakshay-sharma-02: fix: workspace .cargo/config.toml to prevent duplicate _start; add Makefile (3576498)
  2026-05-17 lakshay-sharma-02: feat: add sync.sh workspace synchronization helper (0df4ab5)
  2026-05-17 lakshay-sharma-02: chore: automate windows qemu via bootimage run-command (73403ed)
  2026-05-17 lakshay-sharma-02: chore: move workspace profiles to root Cargo.toml (06604cb)
  2026-05-17 lakshay-sharma-02: fix: wrap rust-toolchain.toml keys in [toolchain] table (0aa2124)
```

## The digest (real LLM output)

```
Friday: The team hardened the core, added a 343‑test stdlib suite, wired the ambient watch loop to real Gmail and deployed it as a systemd service with a daemon.alive heartbeat, and completed Phase C v2 which now synthesizes weekly cross‑project digests from Friday, Vivaha and Aether.  
Vivaha: Recent commits retheme the UI to an Indian wedding palette, fix prerender and functional issues, update the register page image, and add a Mega Menu Navbar with dynamic categories.  
Aether: The project was initialized in May 2026, scaffolded a Linux‑based kernel with VexFS and Jarvis, and has been testing kernel boot in QEMU; activity has been dormant since that initial setup.  

Suggestions: Adopt Friday’s systemd service + daemon.alive heartbeat pattern to monitor and auto‑restart Aether’s kernel service for reliable uptime; and apply Friday’s per‑trigger allowlist (e.g., `"allow": ["gmail.*"]`) to Vivaha’s admin dashboard to restrict API calls and prevent unintended side effects.
```

> Note: the digest above is the frozen LLM output from this run; the
> "343-test" it quotes reflects the docs at that moment - the suite is
> now 366 tests.

## Attribution check (digestcheck.verify_attribution - mechanical)

Every "X's <mechanism>" claim in the digest is name-matched against
the gathered content fetched FOR that repo; unconfirmed claims are
flagged below instead of being delivered as fact (the v2.1
confabulation fix - Vivaha's Cloudflare-Worker pattern was once
described as if it were Friday's).

```
All 4 attributed mechanism(s) confirmed in the named repo's own gathered content.

Mechanical name-match check only: absence means 'not confirmed', never 'false'; paraphrases and synonyms cannot be verified mechanically.
```

## Honest quality assessment

```
SPECIFIC - the digest names concrete things from the gathered sources (concrete references found: ['gmail', 'vivaha', 'aether', 'navbar']); targets stay within owned repos
```

Three mechanical checks this round: (a) does each suggestion name a
mechanism that actually exists in the gathered sources (specific vs
filler), (b) do the transfer targets stay within repos Lakshay owns -
the exact defect v1 had (suggestions aimed at a repo he didn't
control) - and (c) does every "X's <mechanism>" claim actually appear
in X's OWN gathered content (digestcheck.verify_attribution, the v2.1
confabulation fix). The final bar - 'would I act on this' - remains a
human judgment, reported honestly below.

## Verdict

PASS - the ambient pattern (watcher trigger ->
read-only gather primitives -> LLM synthesis -> notify delivery ->
record) works over repos Lakshay actually owns. Whether the suggestions
are worth ACTING on is the real signal of this round and is judged by a
human against the two checks above - the digest's quality assessment
makes the evidence explicit rather than assumed.

## The real watcher run (record + notify delivery)

The SAME committed trigger fired through the REAL watcher
(run_watcher(once=True), schedule moved to 00:00 only, temp
fired-state so the real var/state/watcher_fired.json is
untouched) with the REAL var/logs/tasks.jsonl and desktop
notification. The latest recorded line (12/12 VERIFIED,
COMPLETED):

```
{
  "task_id": "watch:weekly-cross-project-digest",
  "goal": "produce a weekly cross-project digest: summarize recent git activity and current priorities across Friday, vivaha and Aether, with 1-2 concrete cross-project suggestions tied to each repo's actual priorities",
  "gate6_passed": true,
  "timestamp": "2026-08-11T16:14:15.447891+00:00",
  "proof": "{\"trigger\": \"weekly-cross-project-digest\", \"status\": \"COMPLETED\", \"steps\": [{\"step_id\": 1, \"primitive\": \"git.log\", \"status\": \"VERIFIED\", \"attempts\": 1}, {\"step_id\": 2, \"primitive\": \"git.log\", \"status\": \"VERIFIED\", \"attempts\": 1}, {\"step_id\": 3, \"primitive\": \"git.log\", \"status\": \"VERIFIED\", \"attempts\": 1}, {\"step_id\": 4, \"primitive\": \"files.find_recent_doc\", \"status\": \"VERIFIED\", \"attempts\": 1}, {\"step_id\": 5, \"primitive\": \"files.find_recent_doc\", \"status\": \"VERIFIED\", \"attempts\": 1}, {\"step_id\": 6, \"primitive\": \"files.find_recent_doc\", \"status\": \"VERIFIED\", \"attempts\": 1}, {\"step_id\": 7, \"primitive\": \"files.read_text\", \"status\": \"VERIFIED\", \"attempts\": 1}, {\"step_id\": 8, \"primitive\": \"files.read_text\", \"status\": \"VERIFIED\", \"attempts\": 1}, {\"step_id\": 9, \"primitive\": \"files.read_text\", \"status\": \"VERIFIED\", \"attempts\": 1}, {\"step_id\": 10, \"primitive\": \"dev.digest\", \"status\": \"VERIFIED\", \"attempts\": 1}, {\"step_id\": 11, \"primitive\": \"digestcheck.verify_attribution\", \"status\": \"VERIFIED\", \"attempts\": 1}, {\"step_id\": 12, \"primitive\": \"notify.notify_send\", \"status\": \"VERIFIED\", \"attempts\": 1}]}"
}
```

The digest text reached the desktop as the notify step's body.


## Verdict on the context experiment (v2.1)

The v2.1 experiment (2026-08-11) asked: does feeding the digest
CURRENT-PRIORITY context (vivaha roadmap + payment system, aether
devlog) instead of git log + boilerplate READMEs produce suggestions
worth acting on? The v2.1 context WAS promoted into the committed
trigger at the time (8/8 VERIFIED - strictly better than the create-
next-app boilerplate READMEs it replaced, same cost, same allowlist);
v2.2 later replaced the hardcoded priority docs with recency-based
files.find_recent_doc discovery plus the digestcheck.verify_attribution
mechanical check (the committed trigger is now the 12-step v2.2 plan).

Relevance: IMPROVED. Both suggestions touched real roadmap items
(Vivaha admin dashboard [Q4], moderation microservice + bundle size
[Q1/Q4]) and the digest correctly described the payment flow from the
payment doc - versus v2 where the Vivaha suggestion was unconnected
to anything the repo needs.

Ceiling confirmed - two failure modes survive better context:
(a) PROVENANCE CONFABULATION: the digest re-attributed Vivaha's OWN
roadmap mechanism (Cloudflare Worker for moderation) to Friday as if
it were a Friday pattern - the transfer claim is partially false
even when the suggestion is roadmap-accurate.
(b) TRUE BLOCKERS ARE INVISIBLE: the actual current priorities
(unimplemented Razorpay flow, Supabase key rotation, broken admin
verification UI) live in Lakshay's head and past conversations, not
in any repo doc; the roadmap is a FUTURE roadmap, not a current-
state doc.

Decision: SCALING IS DEFERRED - the pattern has not yet produced a
suggestion worth acting on. The next improvement needs a source of
TRUE current priorities (e.g. a maintained per-repo status note) -
a maintenance decision, not a config change.

## Cost

One full-tier LLM call per digest run (~$0.17) - the suggestion-drafting
call itself, weekly. No L4 planning call (deterministic plan). If cost
matters, the read/summarize split (cheap tier for gathering, full tier
for the final suggestion) is the documented next step.

