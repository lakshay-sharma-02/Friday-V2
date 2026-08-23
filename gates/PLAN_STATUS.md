# Friday — current state (handoff for planning the next phase)

Status date: 2026-08-14.

Friday is a **layered desktop-automation agent** whose defining discipline is
that every layer ships raw proof before the next layer starts — and that
nothing an LLM plans is ever trusted without mechanical verification.
The original V8 plan (gates G1–G6 + 13 composite tasks) is **done**;since then the core was hardened, a 537-test unit suite was added, a live
end-to-end check now runs the real stack against real state, the
ambient watch loop has been wired into real gmail, and it is now
**deployed** as a persistent systemd service with a `daemon.alive`
heartbeat. Phase C v2.2 (cross-project digest) is live: the watcher now
gathers `git.log` across Friday + vivaha + Aether — three real repos
Lakshay owns — reads each repo's most recently modified status doc,
synthesizes a weekly digest with one full-tier LLM call, and
**mechanically verifies every attribution claim** before delivery. The
self-improvement loop's other halves are closed too: the **lessons
loop** (`friday/lessons.py`) records every mechanical rejection as a
structured event, generalizes event clusters into human-approved
lessons (`config/lessons.json`), and injects them as a bounded
KNOWN-MISTAKES block into the triage / planner / digest prompts — the
gap loop drafts new arms, the lessons loop makes rejections stick —
and the **goals-proposal stage** (`friday/goal_proposals.py`) mines
recurring FAILED goals from `tasks.jsonl` + L0 failure signatures into
INERT, watcher-validated trigger proposals (`gates/proposed_triggers/`)
for a human to approve or reject, so Friday proposes what deserves a
scheduled goal instead of only executing goals you hand it. This document is the
single source of truth for what exists, what is proven, what is knowingly
left out, and what the next plan could build.

---

## 1. Architecture (five layers + the watch loop)

```
L4  Planning     (LLM: goal -> plan JSON, schema-validated, $facts resolved)
L3  Execution    (deterministic state machine, zero LLM, $steps refs, retries)
L2  Verification (read-only state checks; the only thing a step may verify with)
L1  Primitives   (window/media/browser/dev/files/git/digestcheck/gmail/notify/whatsapp/telegram/discord)
                 (git.log + git.status + files.find_recent_doc + files.read_text + dev.digest
                 + digestcheck.verify_attribution = Phase C v2.2 cross-project
                 gather/synthesize/VERIFY over Friday + vivaha + Aether; the LLM
                 call lives inside dev.digest, the gmail.summarize exception)
L0  Observability (one structured JSON line per call; redaction + clip +
                   per-primitive projection + size-based rotation)
WATCH  friday/watcher.py   ambient loop: config triggers -> goals -> tasks.jsonl -> notify
                          (fired-state persisted; FAILED runs retry same-day,
                          backoff-limited)
GAPS   friday/capability_gaps.py + gap_triage.py + automated_gate.py
                          + register_proposal.py
                          refusal -> structured record (capability_gaps.jsonl)
                          -> grouped -> LLM-drafted proposal
                          (gates/proposed_primitives/, review-only)
                          -> AUTOMATED gate (AST + sandboxed tests + build-verify)
                          -> human signature -> registered into L1
LESSONS friday/lessons.py   rejection events (lessons.jsonl) -> categorized
                          candidates (gates/proposed_lessons/) -> human
                          approval (config/lessons.json) -> bounded
                          KNOWN-MISTAKES block injected into the triage /
                          planner / digest prompts
GOALS  friday/goal_proposals.py  recurring FAILED goals (tasks.jsonl,
                          REFUSED/probes excluded, deduped vs existing
                          triggers) + L0 failure signatures -> INERT
                          trigger proposals (gates/proposed_triggers/,
                          enabled:false, allow:[]) -> human approval
                          (copy into config/watcher.json, grant scope,
                          flip enabled)
```

- **L1** — every primitive carries a registered contract (pre/post/idempotency/
  failure mode) in `friday/contracts.py`; L3 refuses to call anything without
  one. Idempotency classes: `idempotent` / `at-most-once` / `commutative-safe`.
- **L3** — `PENDING -> RUNNING -> {VERIFIED, FAILED}`, bounded retries with
  contract-derived backoff, `$steps.N.result` refs (dot + bracket + list-index),
  refuses `EXECUTOR_BLOCKED` primitives, rejects future-step refs before running.
- **L4** — capability catalog auto-derived from the registry (can never drift
  from what L3 resolves), zero goal-specific logic, `validate_plan` catches
  malformed output before execution and feeds the reason back into a retry.
- **L0** — `var/logs/friday.jsonl`; redaction (`<redacted>` for secrets and
  mail bodies), clipping of huge values, per-primitive log projection
  (`window.list_clients` compact, `gmail.list_unread` redacts sender/subject
  while keeping message_id/date), size-based rotation past 10 MB keeping 3 backups.

## 2. Hardened core (post-V8, all mechanically proven)

| Rail | Mechanism | Proven by |
|------|-----------|-----------|
| `window.shutdown` unreachable | `EXECUTOR_BLOCKED` in contracts — hidden from the LLM catalog, rejected by `validate_plan`, refused by L3 | unit tests + gate proofs |
| Arbitrary shell gated | `dev.run_shell` / `dev.run(allow_bypass_permissions=True)` raise unless `FRIDAY_ALLOW_DANGEROUS=1` (checked before claude runs) | `tests/test_dev.py` |
| Protected windows | `close_window`/`close_all` refuse protected classes (`FRIDAY_PROTECTED_CLASSES`, default `kitty`) **before any dispatch** — no partial close | `tests/test_window.py` |
| Per-trigger allowlist (NEW) | watcher triggers may carry `"allow": ["gmail.*"]`; any plan step whose primitive is not on the list is REFUSED before execution, recorded honestly, and popped from the plan cache | `tests/test_watcher.py` (47 tests) |
| Persistent deployment + heartbeat (NEW) | `friday-watcher.service` (systemd user unit, source `deploy/`): starts at login, restarts on failure, `daemon.alive` heartbeat every `FRIDAY_HEARTBEAT_S` (60 s) carrying uptime + last trigger + live capability-gap count; replaces the July timer pair that ran a now-nonexistent `friday.cli` and failed every 2 minutes | `gates/WATCHER_DEPLOY_PROOF.md`, `deploy/RUNBOOK.md`, heartbeat tests in `tests/test_watcher.py` |
| Draft impls gated before review (NEW) | capability-gap proposals pass an automated gate before any human signature: AST checks (imports limited to the derived L1 allowlist, no exec/eval/os-system calls and no subprocess.* beyond the bounded pattern shipped primitives use - the READ shape (subprocess.run([...], capture_output=True, timeout=...)) and the WRITE shape (subprocess.run([...], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=...), added 2026-08-14 after the first clipboard.write_text deadlocked live: wl-copy/xclip fork a daemon that inherits pipe fds, so capture_output blocks EOF forever - never mixed, timeout always required), contracted function defined, no dead arguments, **@contract decorator required, every contract-named log_transform defined, no bare-builtin raises the contract never declares**) + a **REGISTRATION check** (the DRAFT is exec'd in an isolated subprocess and the contracted name must actually land in REGISTRY - a draft that compiles and passes its own test can still be dead on arrival) + the proposal's own test run in an isolated subprocess (temp HOME, no credentials, timeout) against the DRAFT impl + **build-verify extended to the subprocess-read family** (clipboard-class drafts get mocked-tool probes: success -> str, tool failure/timeout -> FridayError, never a bare builtin) | `tests/test_automated_gate.py`, `tests/test_register_proposal.py` |

## 3. Proof ledger (all raw output in `gates/`)

Structural gates: `GATE1_PROOF` (L1 bring-up) … `GATE6_PROOF` (first
composite task) plus `GATE5_DOD_PROOF` (anti-cheese: never-seen goal
through the unmodified pipeline) and `GATE6_DOD_PROOF` (real spoken-style
goal). Bring-ups: `BRINGUP_GMAIL_PROOF`, `BRINGUP_REMAINING_PROOF`,
`MPV_LIFECYCLE_FIX_PROOF`, `RETRY_STRESS_PROOF`.

**13 composite tasks**, each with a Gate-6-grade proof: receipt→WhatsApp,
text→3 platforms, browser open/click/search, media timer + pause/resume,
window compose, GitHub login (log-safe), file upload, WhatsApp file-send on
the Cloud API, gmail unread-email summary, and the task-table in
`gates/TASK*_PROOF.md` files.

**Post-V8 artifacts (this phase):**

| Artifact | What it proves |
|----------|----------------|
| `TESTS_PROOF.md` | 537-test dependency-free unit suite, all side-effect boundaries mocked (regenerated by `gates/test_suite.py`) |
| `CAPABILITIES.md` | Live capability inventory GENERATED from the registry (59 primitives / 17 checks / 10 triggers / 12 gate-registered) — `gates/generate_capabilities.py`, idempotent |
| `PORTABILITY.md` | Windows-port analysis + ordered checklist — REFERENCE ONLY, aspirational, nothing scheduled |
| `E2E_PROOF.md` | **Live** end-to-end on this machine: 4 goals (files/windows/media/gmail) planned by real LLM calls, executed by the unmodified executor, verified by real L2 checks against real state, traced in the real log, recorded in tasks.jsonl, desktop-notified. Read-only allowlist refused hallucinated side-effecting plans (a live run caught a `whatsapp.send_text`); probe sender redacted in the proof |
| `WATCHER_PROOF.md` | Watch loop first proof: time + file triggers, deterministic plans, no LLM, recorded + notified |
| `WATCHER_GMAIL_PROOF.md` | The **enabled** `morning-gmail-summary` trigger through the unmodified watcher against the live inbox: `$facts.gmail_sender`, `allow: ["gmail.*"]`, LLM plan → verified steps → real summary → tasks.jsonl → notify |
| `CAPABILITY_GAP_PROOF.md` | Capability-gap loop closed end to end: refusal -> record -> triage -> automated gate (AST + sandboxed tests) -> human signature -> registration -> re-run-passes; a deliberately bad draft (subprocess.run, signed anyway) is blocked before the signature (`files.find_file_exact` registered) |
| `WATCHER_DEPLOY_PROOF.md` | Watch loop **deployed** as a persistent systemd user service (replacing the silently-failing July timer pair): real `systemctl` status, the real gmail trigger COMPLETING under the service, real `daemon.alive` heartbeats over real elapsed time — incl. the heartbeat catching its own first-release timing bug — and the first ambient capability-gap reading (15 records, all from prior proof runs; zero from ambient operation) |
| `PHASE_C_V1_PROOF.md` | **Phase C v1** (narrow, historical): proved the gather→synthesize→deliver pattern mechanically, but paired Friday with Agent-Reach (a THIRD-PARTY repo) — suggestions specific-sounding, not actionable; the lesson that drove v2 |
| `PHASE_C_V2_PROOF.md` | **Phase C v2 → v2.2**: drops Agent-Reach, pairs Friday with **vivaha + Aether** (both owned); v2's suggestions were 0-for-2 under human judgment (S1 unconnected, S2 `sync.sh` is a WSL shim); v2.1's context experiment improved relevance but exposed **provenance confabulation** + invisible true blockers. v2.2 fixes the fabrication mechanically: `digestcheck.verify_attribution` flags any "X's <mechanism>" claim not in X's own gathered content, and context is now discovered by recency (`files.find_recent_doc` — no hand-maintained note). Live digest 12/12 VERIFIED (executor + real watcher): all 4 attributed mechanisms confirmed |

## 4. Test suite

`tests/` — 571 tests, stdlib `unittest`, zero dependencies, ~37 s on
Windows. (2026-08-18: +19 from the Windows port - secrets env backend,
PowerShell notify, tasklist browser sweep, win32 window tests, gate sandbox
- and +15 from the MCP server tests.) Covers
the registry, observability (redaction/rotation/log_transform), executor
(ref resolver incl. list-index + bracket syntax, retry policy, blocked
primitives), planner (validate_plan, catalog, facts, `$facts` substitution),
every L2 check, protected windows, the dev dangerous-gate, browser locator
fallback chain + the credential-logging regression, media `_launch`/
`_wait_socket`, gmail summarize flow + body-never-logged regression, the
watcher (config validation, time/file triggers, LLM plan caching, **allowlist
refusal**, honest failure recording, the **daemon.alive heartbeat** incl.
the boot-relative-clock regression, and the **persisted fired-state**:
same-day restart never re-fires, new-day rollover fires, corrupt/missing
state fails safe, FAILED runs not marked fired + backoff-bounded
retry cadence, REFUSED runs terminal for the day), the BUILD-VERIFY
stage (test-passes-but-impl-wrong caught, correct draft passes both
stages, wrong return shape rejected, not-applicable classes honestly
flagged, and Fix 2's write-family probes: correct write draft passes,
an always-append draft caught by the overwrite probe's content
mismatch, append probed only when declared, family detection
read/write/none), and the capability-gap loop (one record
per unknown/blocked/allowlist-refused primitive; triage drafting, idempotent
processed-tracking, compile-status honesty) and its closure (approval-gate
signature/schema/impl checks, idempotent registration, planner L1
auto-discovery, the registered `files.find_file_exact` primitive, and the
AUTOMATED gate: one draft per AST failure mode - bad import, exec/
eval/subprocess/os.system, missing contract fn, dead argument, plus the
fs-scope checks rejecting absolute-path/`..` writes in drafted test files
- a clean draft passing through untouched, sandboxed test pass/fail,
draft-over-registered-module injection IN ALL IMPORT STYLES (incl. the
package-level `from friday.l1 import files` regression that
false-rejected the first clean write draft, 2026-08-13), env
sanitization), and the triage SELF-CHECK repair loop (broken draft
repaired on retry with the exact rejection fed back, renamed primitive
caught by the exact-name check, uncompilable impl/test caught, dead
arg caught, bounded-termination returns None and leaves the group
unprocessed, written proposals record their self-check status), plus
`FRIDAY_TRIAGE_MODEL` (a full model id overriding the opus alias when
its provider is DEGRADED) and the default-alias test), and
PHASE C: `git.log` against a hermetic temp git repo (newest-first,
count/days filters, empty-repo-is-empty-list, not-a-repo errors,
registry idempotent), `files.read_text` (bounded reads, truncation flag,
missing-file errors), `files.find_recent_doc` (recency wins over name,
README fallback when no status-shaped doc exists, missing-repo error,
case-insensitive doc-shape matching), `dev.digest` (labeled context
prompt, empty context/result errors, bypass never set), the pure
`list_nonempty` / `text_nonempty` checks, `digestcheck.verify_attribution`
(correct claim passes, cross-repo misattribution flagged — a
reproduction of the real Vivaha/Friday confabulation case, no-claim
honest skip, idempotent, and smart-punctuation normalization so
U+2019/U+2011 typographic characters still match), and a committed-config
test pinning the digest trigger's plan to the REAL planner registry (a
primitive rename or schema drift fails the suite, not Sunday), and the
LESSONS LOOP: event recording (well-formed + append-order + detail
truncation + malformed-line resilience), approved-store validation
(fail-open on invalid entries / malformed file, target filtering,
bounded injection at INJECT_LIMIT), candidate generalization
(min-example threshold, idempotent coverage via the events sidecar,
new-evidence extension, unregistered categories never candidate), the
real record sites (a schema rejection writes `draft_schema`, a signed
subprocess impl writes `draft_ast`, a clean proposal writes nothing, a
digest misattribution writes `digest_misattribution`, an unparseable
plan writes `planner_unparseable`), and injection into all three
prompts (triage / planner / digest carry their own target's approved
block), and the GOALS-PROPOSAL stage (clustering with window +
min-recurrence, REFUSED/probe exclusion, existing-trigger coverage by
substring AND significant-token overlap, WATCH-layer L0 evidence,
deterministic + LLM drafting with strict watcher-schema validation and
deterministic fallback, inert proposals, idempotence, and the
never-touches-watcher-config assertion). Hermetic: `EnvTestCase` points
`FRIDAY_LOG_FILE`, `FRIDAY_GAPS_FILE`, `FRIDAY_PROPOSALS_DIR`,
`FRIDAY_LESSONS_FILE` and `FRIDAY_APPROVED_LESSONS` at per-test
temp paths, so the suite never writes into the real log, gap file,
`gates/proposed_primitives/`, `var/logs/lessons.jsonl`, or the real
`config/lessons.json`. The **gate-registered send primitive**
(`gmail.send_document`, 2026-08-11) is covered hermetic too: real MIME
assembly with mocked HTTP + token refresh, recipient redacted from the
L0 result line while message_id stays visible, Precondition/Primitive
error paths, the default-recipient env, and the registration hardening
(future imports stripped when appending to an existing module).

## 5. Task counter

`var/logs/tasks.jsonl` — one honest JSON line per run (`task_id, goal,
gate6_passed, timestamp, proof`); failures are never deleted. **25 distinct
passing ids**: the 13 composite tasks, the `retry-stress` gate, and 11
live-automation records (`watch:demo-time`, `watch:demo-file`, `e2e:files`,
`e2e:media`, `e2e:windows`, `e2e:gmail`, `watch:morning-gmail-summary`,
`watch:weekly-cross-project-digest`, `watch:morning-calendar-summary`,
`watch:morning-clipboard-digest`, `watch:new-download-alert` — the last
three are the daily-use triggers added 2026-08-14, live-proven
2026-08-15).

## 6. Known limits / honest caveats

- **LLM plan variance**: plans come from a live LLM and occasionally
  hallucinate — wrong window counts, extra side-effecting steps, even a
  `whatsapp.send_text` in a gmail goal. Every such plan is caught
  mechanically (L2 verify fails → ABORT; allowlist/allow refuse → REFUSED)
  and recorded honestly. This is the design working, not a defect.
- **Empty mailbox is a false verdict, never an error**: an absent unread
  email from the configured sender makes `gmail_unread_exists` return False
  and the goal honestly FAILs. The watcher's `morning-gmail-summary` fires
  at 09:00 weekdays against `$facts.gmail_sender` (currently
  `accounts.google.com`); change the sender in `config/planner_facts.json`
  to one you reliably receive unread mail from.
- **Mail privacy**: sender/subject are redacted in L0 and in committed
  proofs; the gmail *summary* text (an LLM-generated artifact) is shown
  truncated in proofs. `gmail.summarize` internally calls the LLM
  (unlogged by design — the mail body never reaches the log).
- **`summarize` costs money**: it is the one primitive that makes a live LLM
  call per invocation (~$0.17 per the last run); the E2E and watcher both
  call it once per run.
- **Capability-gap drafts are unvalidated LLM output — but the
  structurally-catchable "clean but wrong" classes are now mechanically
  caught (2026-08-14)**: the clipboard.read_text round produced a
  self-check-clean draft with FIVE defects a human had to hand-correct
  (missing @contract decorator; contract-named log_transform never defined;
  test importing a wrong module path; bare RuntimeError vs PrimitiveError;
  contract claiming "wl-paste or xclip" but impl handling only wl-paste).
  Four of the five are now rejected mechanically: the @contract decorator
  is REQUIRED (a missing one means the primitive never enters REGISTRY),
  every contract-named log_transform must be defined (NameError at import),
  explicit bare-builtin raises the contract never declares are rejected
  (the executor's retry policy keys on FridayError), and a REGISTRATION
  check execs the DRAFT in isolation and requires the contracted name to
  actually land in REGISTRY - plus build-verify now probes clipboard-class
  drafts with a MOCKED tool (success -> str, failure/timeout ->
  FridayError, never a bare builtin) instead of honestly reporting
  NOT APPLICABLE. The triage self-check mirrors all the static checks +
  the test.py AST checks, so the LLM repairs these at DRAFT time, not at
  human review (the clipboard draft's test was gate-rejected THREE times
  in a row before this - subprocess.CompletedProcess -> __import__ ->
  TimeoutExpired - because the self-check only compiled it). Remaining
  human items after this round: tool-fallback drift (contract says
  "wl-paste or xclip", impl does only one) is still a human-read finding,
  and semantic intent stays human - but the structural "dead on arrival"
  and "wrong error class"  classes no longer reach the reviewer. All new
  checks are covered in the suite; the corrected clipboard draft passed
  the full automated gate including the new stages and was **REGISTERED
  2026-08-14** (re-verified live: the driving goal "read the current
  clipboard text" re-ran through the real planner + executor and
  COMPLETED with a VERIFIED step).
- **The first CLEAN draft was caught by the sandbox, live (2026-08-13)**:
  with the self-check repair loop + name normalization + model override
  all landed, triage finally produced a structural survivor
  (`files.write_text` - exact name, self-check passed, AST clean). The
  gate then mechanically caught a REAL runtime bug in it at the sandbox
  stage: the impl passed `newline="w"` to `Path.write_text`
  (`ValueError: illegal newline value: w`) - a compile-clean,
  self-test-passing draft that would crash on first real invocation. This
  is the "scary case" (clean side-effecting draft, subtly wrong) finally
  occurring AND being caught by the gate, not a human. The draft was then
  HAND-CORRECTED (one line: `with p.open(mode) as f: f.write(text)` instead
  of the illegal `newline=mode`), **Fix 2** (write-family build-verify)
  generalized the probes, and the corrected draft passed the FULL
  automated gate and was **REGISTERED 2026-08-13** - the loop's FIRST
  side-effecting primitive through the complete cycle. The original
  goal ("write the latest digest summary to a notes file") re-ran through
  the REAL executor and COMPLETED with a VERIFIED step. The
  ambient-gap-probe-file-write trigger that generated the gap was RETIRED
  (disabled) the same day - email-send lifecycle precedent; any straggler
  gaps are consumed as SOLVED. Honest note: the OSError-vs-contract
  mismatch was reconciled at review (wrapper removed - OSError now
  propagates per the contract); the gate itself cannot judge such
  semantic drift, which is why the human step remains.
- **The daily-use layer caught up with the infrastructure (2026-08-14)**:
  the gap loop's machinery was applied to two real routines.  (a)
  `calendar.list_upcoming`'s original auth read a RAW access token that
  expires in ~1 hour with no refresh path — it could never have served a
  persistent trigger. The fix mirrors gmail.py's proven pattern
  (client_id/client_secret/refresh_token in pass friday/calendar or
  CALENDAR_* env, refresh grant, cached token, 401 -> refresh + retry),
  auth failure now raises PrimitiveError (DISTINCT from 'no events', per
  the registered contract — an unconfigured calendar can no longer
  masquerade as a free week), and the review also found the contract
  defined `_log_redact_calendar_meta` but never wired it in — event
  summaries were reaching the L0 log raw; both fixed with 8 hermetic
  tests (new tests/test_calendar.py) + the env-var leak guard for
  CALENDAR_* in tests/helpers.py. The one-time consent flow
  (gates/_calendar_oauth_setup.py) was RUN successfully 2026-08-14 — the
  refresh token now lives in pass friday/calendar and a live
  `list_upcoming()` call authenticates against the real Calendar API
  (returns [] for an empty week — a valid result, distinct from auth
  failure). (b) `new-download-alert` is now ENABLED with a deterministic
  plan — `files.find_newest` (built + registered through the loop the
  same day: the LLM draft returned a dict, the build-verify read probes
  rejected it against the files.* str convention, corrected at human
  review) locates the newest pdf by MTIME (find_file is lexicographic-
  first, wrong for 'newest'), whatsapp.send_document delivers it to the
  configured default phone, allowlisted, no LLM per firing. (c) The
  clipboard family's first real daily routine is ENABLED:
  `morning-clipboard-digest` (daily 08:05, right after
  morning-calendar-summary) pushes a plain-text morning digest of today's
  calendar to the system clipboard. Deterministic plan, no L4 LLM:
  calendar.list_upcoming(days=1) -> dev.digest composes the digest (the
  ONE live LLM call per firing, ~$0.17 — same cost class as the existing
  morning-gmail-summary) -> clipboard.write_text copies it. Allowlist
  pins the three primitives; empty calendar = honest FAIL. Live-proven
  end-to-end the day it was added: the real plan ran COMPLETED against
  the real calendar (the add_event test event read back into the digest),
  and the clipboard held the composed digest. clipboard.write_text's
  write-shape deadlock fix (capture_output -> stdout/stderr=DEVNULL, see
  §6) is what made this trigger possible — the write now completes in
  ~0.1s instead of timing out on every firing.
- **The loop was re-tested live on a NEW gap (2026-08-14) and the
  model-router escape hatch carried it**: after clipboard registered, a
  fresh gap (`media.get_volume` — set_volume exists, no getter) was
  recorded and triaged. The default opus alias failed it — 300s
  timeouts and unparseable replies on the big draft shape — and with no
  `FRIDAY_TRIAGE_FALLBACK_MODELS` configured the loop could not
  complete. The codebase's own documented escape hatch worked:
  `FRIDAY_TRIAGE_MODEL=oc/laguna-s-2.1-free` (alive, ~11s on probe)
  drafted a self-check-clean proposal in one attempt, and the automated
  gate passed every stage (AST + registration + 8-test sandbox),
  stopping only at the human signature — the designed terminal state
  for a draft. The draft itself is high quality: it reuses the module's
  own `_socket_send`/`_reply_ok` helpers, returns None on absence (no
  bare exceptions, mirroring is_playing), and matches its contract
  exactly. The three new clipboard-round lessons (draft_no_register,
  draft_error_class, draft_contract_drift) were also approved into
  `config/lessons.json` the same day (9 valid, 0 problems), so the
  triage prompt now carries them. The model chain is now configured on
  this machine (`~/.zshrc`): `FRIDAY_TRIAGE_MODEL=oc/laguna-s-2.1-free`
  as the drafting primary, `FRIDAY_TRIAGE_FALLBACK_MODELS=opus` as the
  timeout/hard-failure fallback (the watcher daemon already pins
  `FRIDAY_MODEL` in its unit). Proven live the same day: the configured
  chain drafted `media.get_playing_title` clean on the first attempt and
  the gate passed every stage (AST + registration + 6-test sandbox),
  stopping only at the human signature — no manual override needed
  (deploy/RUNBOOK.md documents both configs). the opus alias routes through the user's local proxy to
  a free provider model that was DEGRADED for the whole session
  (`DEGRADED function cannot be invoked`, openrouter/nvidia/...) - the
  watcher's planner calls and triage drafting both failed the same way.
  Two escape hatches, both documented: `FRIDAY_TRIAGE_MODEL` (per-run
  draft-model override for gap_triage) and **`FRIDAY_MODEL` (the
  WHOLE-AGENT override at the `_run_claude` choke point - planner,
  triage, digest and summarize all flow through it; a full model id like
  `oc/laguna-s-2.1-free` repoints every call). The MODEL FALLBACK
  CHAIN is now built (2026-08-14): triage drafts with a chain - primary
  FRIDAY_TRIAGE_MODEL (or the opus alias), then each entry of
  `FRIDAY_TRIAGE_FALLBACK_MODELS` (comma-separated full model ids) after
  a TIMEOUT or HARD FAILURE of the LLM call, so a DEGRADED or too-slow
  provider is handled automatically instead of burning every attempt on
  a dead model. The chain advances ONLY on timeout/hard failure - a
  structural rejection is a working model's defect and is fed back to
  the SAME model for repair (7 new tests pin this, incl. the env-var
  leak fix: FRIDAY_TRIAGE_MODEL / FRIDAY_TRIAGE_FALLBACK_MODELS /
  FRIDAY_MODEL are now in the test suite's ENV_KEYS so one test's
  override can never leak into the next). Model
  SPEED matters as much as availability: cycle 2's calendar draft (a
  genuinely NEW module - the largest triage prompt shape) timed out at
  300s on all 3 attempts with laguna-s, then drafted in ~2 min with
  `openrouter/poolside/laguna-xs-2.1:free` (17s on a comparable probe).
  The per-attempt budget (300s) is not env-configurable yet - a
  candidate.
- **The automated gate is real, the meta-engine is PARTIAL**: proposals
  now pass AST validation (import allowlist derived from shipped L1
  primitives, no exec/eval/os-system calls and no subprocess.* beyond the read-only bounded pattern (subprocess.run([...], capture_output=True, timeout=...)), contracted
  function defined, no dead arguments) and a sandboxed test run (temp
  HOME, no credential env vars, timeout, DRAFT impl injected) BEFORE a
  human signs APPROVED.md; one primitive (`files.find_file_exact`) is
  registered through it and a bad draft is mechanically blocked
  (`CAPABILITY_GAP_PROOF.md`). Still aspirational: sandboxed-BUILD
  isolation and dual-human approval. Documented limits: the sandbox does
  not hard-block network (no credentials are present to use it), and the
  gate cannot catch logically-wrong-but-syntactically-clean code - that
  is still the human reviewer's job.
- **Build-verify is now family-derived, not read-only (Fix 2,
  2026-08-13)**: the probes no longer assume find_file semantics. The
  probe family is derived from the DRAFT's declared parameters - a
  path-ish+content-ish pair (files.write_text(path, text)) gets WRITE
  probes (real temp file created+overwritten with verified content,
  appended when the fn declares `append`, missing-parent raising
  FridayError or returning); a name/pattern arg gets the original READ
  probes; neither -> honest not-applicable. A draft that returns a
  non-str, writes nothing, writes the wrong content, or appends when it
  should overwrite is now caught mechanically regardless of what its
  self-authored test asserted. Honest limit: write probes verify the
  file on disk but cannot judge design intent (e.g. the corrected
  write_text draft maps OSError -> PreconditionError against its own
  contract - a human-reconciliation item, not a gate failure).
- **Sandbox injection fixed (2026-08-13)**: the draft-impl injection
  previously replaced `sys.modules` only - bypassable by the common
  import styles `from friday.l1 import files` and `import ... as`, which
  bind the package ATTRIBUTE (set by the earlier real import) and never
  consult `sys.modules`. The first clean draft exposed it live
  (false-rejected with 'module friday.l1.files has no attribute
  write_text'). The runner now execs the draft IN PLACE into the module's
  own namespace (the sandbox is a throwaway subprocess) and keeps the
  package attribute in sync, so every import style exercises the draft.
  Regression-tested with the exact package-level style that failed.
- **The lessons loop is real, and it is prompt-guidance, not a gate
  (2026-08-11)**: `friday/lessons.py` records rejection events
  mechanically (gate AST/sandbox/build-verify rejects, approval-gate
  schema/impl rejects, digest attribution flags, planner retry failures)
  and injects human-approved lessons as a bounded KNOWN-MISTAKES block
  into the triage / planner / digest prompts. Honest limits: (a) a
  lesson can stop a RECOGNIZED failure class from recurring — it CANNOT
  catch a clean-but-subtly-wrong draft (that remains a human reading
  problem, unchanged); (b) lessons shape the next attempt, they never
  gate it — a lesson is advice, not an enforced check; (c) the
  mechanical record sites cover the mechanical rejections only — the
  semantic categories (draft_confabulation, draft_dead_arg,
  draft_wrapper_dodge) have no detector and are recorded via `--record`
  or seeded by a human, so the event log under-reports exactly the
  scariest class of draft; (d) approved lessons accumulate — stale ones
  must be pruned by editing `config/lessons.json`, and injection is
  capped at 5 per prompt so the store can never bloat a prompt; (e)
  generalization needs ≥2 events per category, so a brand-new category
  produces no candidate until a second instance lands; (f)  injected statements are LLM-prompt text — an over-general or wrong approved
  lesson would steer future drafts, which is precisely why approval is a
  human edit, not an automated promote.
- **The goals-proposal stage is real, and it proposes FAILURES, not
  opportunities (2026-08-11)**: `friday/goal_proposals.py` mines
  recurring FAILED goals into inert trigger proposals. Honest limits:
  (a) it mines what FAILED — it does not yet mine what you do repeatedly
  but never schedule, or what the repos' own state suggests (that is
  still the cross-project/digest problem, deliberately not merged); (b)
  L0 contributes evidence and context but cannot produce a standalone
  proposal class yet — a "reliability watch" trigger would need a new
  primitive (no check exists for 'has X failed again'), which is the gap
  loop's job, so the top L0 signatures are reported as context, not
  proposed; (c) the dedupe is text/token-based — a goal that differs in
  intent from an existing trigger but shares tokens can be skipped (0.5
  threshold, deliberately conservative) and a genuinely new goal that
  fails 2x will be proposed; (d) every proposal is INERT
  (`enabled: false`, `allow: []`) but if a human approves one without
  expanding the allowlist it becomes a refusal-only trigger that records
  gap records per firing — the rationale warns about this; (e) the
  default schedule is a generic daily 09:00 mon–fri that a human must
  sanity-check; (f) min-recurrence 2 means a genuinely important goal
  that failed once is invisible until it fails again (deliberate —
  one-off failures are not a pattern).
- **A test-hermeticity leak was found and fixed (2026-08-10)**: the watcher
  allowlist-refusal unit test (trigger `allow-x`) set `FRIDAY_TASKS_FILE`
  but not `FRIDAY_GAPS_FILE`, and `tests/helpers.py` did not isolate the
  gap file by default — so repeated runs of that test wrote 5 real records
  into `var/logs/capability_gaps.jsonl` (timestamps match the test runs;
  the deployed watcher itself generated zero ambient gaps). Fix:
  `FRIDAY_GAPS_FILE`/`FRIDAY_PROPOSALS_DIR`/`FRIDAY_L1_DIR` added to
  `EnvTestCase.ENV_KEYS` + the gap file is temp-isolated by default, with
  a regression assertion; the real gap file is now byte-identical before
  and after the suite. The 5 leaked records (allowlist-refusals of the
  EXISTING `whatsapp.send_text`) were consumed by inspection into
  `capability_gaps.done` — triage must never LLM-draft an existing
  primitive; the real fix for that class is the trigger's allowlist
  (`WATCHER_DEPLOY_PROOF.md` §6).
- **The first side-effecting primitive is real, and the LIVE send proof
  is gated on a user-only step (2026-08-11)**: `gmail.send_document` is
  registered, executor-callable, and covered by hermetic tests — but its
  live end-to-end proof awaits the OAuth re-consent with the `gmail.send`
  scope ADDED (Google fixes scopes at consent time). The definitive check
  at approval time (`tokeninfo` on a fresh access token) showed the token
  still carrying ONLY `gmail.readonly`, so the live proof is honestly
  PENDING the browser re-consent (`gates/GMAIL_SETUP.md` §6.5 — must keep
  readonly too, the token is shared with the morning digest). Known limits
  of the primitive itself: build-verify is NOT APPLICABLE for the gmail
  class (no safe real target — a live send has real side effects), so the
  human signature IS the semantic gate for this code; the recipient
  address appears in the L0 args line (consistent with every other send
  primitive — whatsapp/telegram/discord log `to`) but is REDACTED in the
  result line via `log_transform`; and `at-most-once` means a lost
  response must be verified, never blind-retried.
- **Watch loop IS deployed — one honest behavior left**: the daemon runs
  as a persistent systemd user service (`deploy/friday-watcher.service`,
  `gates/WATCHER_DEPLOY_PROOF.md`) with a 60 s `daemon.alive` heartbeat,
  and once-per-day fired state is **persisted**
  (`var/state/watcher_fired.json`): the restart-re-fire bug (23:32 restart
  re-sent the 23:29 digest) is fixed and proven live — a restart now
  produces zero new actions (`WATCHER_DEPLOY_PROOF.md` §8). Fired-state
  is recorded on genuine SUCCESS or a deliberate ALLOWLIST REFUSAL (the
  safe terminal outcome — a refusal never retries into a replan-refuse
  loop of LLM calls + gap records); a FAILED/ABORTed run stays eligible
  to retry later the same day, rate-limited by `RETRY_BACKOFF_S` (600 s,
  ~6 attempts/hour worst case) — a transient failure no longer silently
  skips the day. Remaining behavior: no linger — the service stops at
  logout (`loginctl enable-linger` is the documented opt-in). The four
  `ambient-gap-probe-*` triggers were the loop's DELIBERATE ambient
  volume source: silent (notify:false), allowlisted deterministic probes
  whose single step was a genuinely UNBUILT primitive — refused by the
  allowlist BEFORE any execution (nothing ever runs) and
  terminal-for-the-day, so exactly ONE real gap record per probe per day
  (the first real test of volume + draft quality under continuous
  operation; the gate honestly flags the non-`files` drafts human-review-only).
  All four are now **RETIRED** — each after its primitive completed the
  loop and registered: `ambient-gap-probe-email-send` **2026-08-11**
  (`gmail.send_document`), `ambient-gap-probe-file-write` **2026-08-13**
  (`files.write_text`), `ambient-gap-probe-calendar` **2026-08-13**
  (`calendar.list_upcoming`), and `ambient-gap-probe-clipboard`
  **2026-08-14 — same day it was created** (`clipboard.read_text`). No
  probe remains enabled; the loop's ambient volume now comes from REAL
  refusals + the goals-proposal stage, and `morning-gmail-summary`'s
  allowlist was tightened from `"gmail.*"` to the three read-only
  primitives so the LLM-planned morning trigger can never reach the send
  primitive. The heartbeat's `capability_gaps` count is the remaining
  signal to watch (2026-08-15: the heartbeat now ALSO carries
  `gaps_pending_triage` — the UNPROCESSED backlog, the actionable number
  — alongside the monotonic total, so 'proposals outpacing human review'
  is visible from one log line instead of a growing total that never
  shrinks). The `sunday-digest-reminder` trigger (10:05 Sundays, notify-only,
  zero LLM) nudges the weekly verdict into `gates/DIGEST_TRACKING.md`
  (delivery-neutral wording - it never claims the digest succeeded; keep
  its 10:05 schedule in sync with the digest trigger's if that ever changes).
- **Phase C v2 (cross-project digest) — REAL OWNED REPOS, with honest
  limits**: v1 paired Friday with Agent-Reach (a THIRD-PARTY repo, not
  Lakshay's), so its suggestions were specific-sounding but not
  actionable. v2 drops Agent-Reach and pairs Friday with **vivaha +
  Aether** — both cloned from GitHub (lakshay-sharma-02), both owned,
  chosen for real recent activity (pushed 2026-07-18 / 2026-07-13;
  Jarvis excluded as dormant). The v2 proof applies two mechanical
  checks (specific-vs-generic; targets stay within owned repos) and the
  real run's suggestions named mechanisms verifiably present in the
  gathered sources with owned targets — but "would I act on this"
  remains the human's call. v2.1 experiment (2026-08-11): feeding the
  digest current-priority docs (vivaha roadmap + payment, aether devlog)
  instead of boilerplate READMEs improved relevance (suggestions touch
  real roadmap items) but did NOT clear the actionability bar — the
  digest re-attributes the target repo's own mechanisms as transfers
  (provenance confabulation), and true current blockers (unimplemented
  Razorpay, Supabase key rotation, broken admin verification UI) exist
  only in Lakshay's head/past conversations, not in any repo doc.
  SCALING IS DEFERRED; the improved context is shipped (strictly better
  than boilerplate, same cost). **v2.2 (2026-08-11) — attribution check +
  recency-based context**: the confabulation is a FABRICATION problem
  (the digest asserted something false about Lakshay's own codebase,
  confidently, in a suggestion meant to be trusted) — a different class
  than the missing-input problem — so it got a mechanical gate, not a
  better prompt: `digestcheck.verify_attribution` runs on every digest
  before delivery (each "X's <mechanism>" claim name-matched against X's
  own gathered content; unconfirmed claims flagged, never silently
  dropped), and context is discovered by RECENCY via `files.find_recent_doc`
  (each repo's most recently modified status-shaped file, README
  fallback — no hand-maintained note; the v2.1 hardcoded priority docs
  are replaced). The live digest (12/12 VERIFIED through executor AND
  the real watcher) named two concrete suggestions — Friday's per-trigger
  allowlist → Vivaha's admin dashboard (roadmap Q4), Friday's systemd
  heartbeat → Aether's kernel service — with "All 4 attributed
  mechanisms confirmed". Honest limits of the check itself: it is
  name-match only — a claim naming no concrete mechanism is 'not
  confirmed', never 'false' — and it cannot verify the transfer makes
  SENSE (S2 `sync.sh` was mechanically confirmed AND wrong for the
  target), so the human stays the final judge of actionability — each
  weekly run's verdict is logged by hand in `gates/DIGEST_TRACKING.md`,
  and scaling stays deferred until that table shows an 'acted' verdict
  or a clear pattern. Still
  open: (a) only 3 of the master-plan's
  repos are in the loop — Friday-V3 is excluded THIS round by design
  and FLAGGED: its source contains an earlier correlation-engine
  implementation worth a dedicated future look (NOT mined here); Psyche
  Space and ChangelogAI have no GitHub copy under lakshay-sharma-02 and
  are excluded pending a separate decision; (b) `dev.digest` costs one
  full-tier LLM call (~$0.17) per weekly run — the read/summarize cost
  split is the documented next step; (c) repo paths are hardcoded in
  the trigger config; (d) `dev.digest` is idempotent, so a failed-step
  retry is a fresh paid call; (e) digest text is a generated artifact,
  not guaranteed identical across runs.
- **A live-only defect slipped past the hermetic gate and was caught by
  live verification (2026-08-14, clipboard.write_text)**: the first
  registered write_text shipped the READ subprocess shape
  (`capture_output=True`) and EVERY write failed with a 5s timeout —
  `wl-copy`/`xclip` fork a daemon that inherits the child's pipe fds, so
  `communicate()` waits forever for EOF. The hermetic mock test never
  exercised the real tool, and build-verify is honestly NOT APPLICABLE
  for the clipboard class (no safe real target), so only the live
  round-trip caught it. Fixed to the WRITE shape (`stdout=subprocess.DEVNULL,
  stderr=subprocess.DEVNULL`) which completes in ~0.1s and was re-verified
  live (write→read round-trip on the real clipboard OK). **Loop-level
  fix, not just this primitive**: `_is_safe_subprocess_run` now admits
  BOTH shapes (never mixed, timeout always required) with new gate tests,
  and the triage prompt + `draft_ast` lesson teach the write shape — so
  future write-family drafts stop shipping the deadlocking read shape.
  This is the documented build-verify-NOT-APPLICABLE limit doing its
  job: the gate can't prove semantics for untargetable classes, so the
  human + live verification remain the last line — and they caught it.

## 7. Deferred by design (not gaps)

- **`window.shutdown`** — destructive; mechanically blocked from every plan
  path. A deliberate script may still call it directly.
- **`vision`** — the plan itself said "skip vision for now"; gated off until
  every structured alternative fails for a target.

## 8. What the next plan could build (threshold met)

The original plan's non-goals — self-improvement loop, capability-gap
detection, ambient watch loop, cross-project synthesis, MCP servers — were
gated behind "≥10 real tasks pass Gate-6-grade proof". That threshold is
**met and exceeded** (13 composite tasks + the retry-stress gate + 11
live-automation records = 25 distinct passing ids), so these are
eligible. Concrete candidates, roughly in dependency order:

0. **Capability-gap approval gate — RESOLVED (automated + human)**: the
   automated gate (AST validation + sandboxed test run + BUILD VERIFY
   against real targets) is built and runs BEFORE the human signature;
   FOUR real primitives are registered + re-proven: `files.find_file_exact`
   (read-only), **`gmail.send_document` (2026-08-11 — the loop's first
   side-effecting primitive, HAND-BUILT after the two LLM drafts for it
   were rejected on record)**, **`files.write_text` (2026-08-13 — the
   loop's first LLM-drafted primitive through the entire cycle, needing
   ONE hand-corrected line the sandbox caught)**, and
   **`calendar.list_upcoming` (2026-08-13 — the loop's SECOND complete
   cycle with ZERO hand-correction: the LLM draft passed the self-check
   repair loop and every automated gate unchanged, then registered)**, and
   **`clipboard.read_text` (2026-08-14 — the first primitive whose draft
   went through the CONTRACT-AWARE gate: the five hand-corrected defects
   of the earlier draft are now mechanical checks — @contract required,
   log_transform defined, registration verified by exec, error class
   probed — and the corrected draft passed all stages and registered,
   driving goal re-run COMPLETED)**, and   **`files.find_newest`
   (2026-08-14 — the newest-by-mtime finder the download alert needed;
   the LLM draft's dict return was corrected at human review to the
   files.* read convention (str path, '' when none) — the build-verify
   read probes rejected the dict shape, exactly the kind of
   convention-drift the gate is for — and the corrected draft passed
   every stage and registered)**, and **`calendar.add_event`
   (2026-08-14 — the loop's first WRITE-capable calendar primitive: the
   LLM draft was corrected at human review (end<=start was a STRING
   comparison — wrong across mixed timezone offsets and no format
   validation — now parsed via datetime.fromisoformat with tests),
   registered, and verified LIVE: a real event was created on the
   primary calendar and   read back through the API; the consent was
   re-run with the calendar.events scope added so the shared refresh
   token now serves both read and write; 2026-08-15 added the scope
   GUARD: a readonly-only token's 403 'Insufficient Permission' is now
   surfaced as an actionable PrimitiveError naming the consent re-run
   (`_calendar_oauth_setup.py --scope "...readonly ...events"`) instead
   of a generic API failure — the latent footgun (module SCOPE was
   readonly while add_event is write-capable) now fails loudly with the
   fix)**, **`media.get_volume` and
   `media.get_playing_title` (2026-08-14 — the loop's first media READ
   probes, read-only idempotent counterparts to set_volume/play that
   return None instead of raising when no player is reachable; drafted
   through the model-router escape hatch after the opus alias DEGRADED,
   gate-clean, human-signed, registered)**, and **`clipboard.write_text`
   (2026-08-14 — the loop's first WRITE-family clipboard primitive; its
   first registration shipped the READ subprocess shape and EVERY write
   deadlocked live — wl-copy/xclip fork a daemon inheriting the pipe
   fds, so capture_output blocks EOF forever — fixed by the WRITE shape
   (stdout/stderr=DEVNULL, completes in ~0.1s), which the gate now
   enforces as the only allowed write-family subprocess call)**. That is
   **12 gate-registered primitives** in total (2026-08-18 added
   `git.status` — the status query enables goals like "check if repo has
   uncommitted changes" or "report staged files"; 2026-08-15 added
   `screenshot.capture` — the capture half of "send me a screenshot"
   goals, hand-built through the gate's new CAPTURE subprocess shape
   (literal allowlisted tool binary + runtime args, the same class of
   extension as the WRITE shape): full / active-window / selector
   capture via grim + the shipped window geometry, live-verified
   end-to-end 2026-08-15 — a real goal "send a screenshot of my
   terminal to my whatsapp" COMPLETED through the real planner +
   executor, screenshot delivered to WhatsApp).
   Cycle 2 also exposed and fixed two latent registration bugs: the
   planner's L1 auto-discovery default path was off-by-one
   (`parents[1]` = the friday package dir, so the glob always fell back
   to the hardcoded tuple — new module files were NEVER discovered;
   fixed + regression-tested), and the new-module registration header
   used a different marker format than the append path, undercounting
   gate-registered primitives in CAPABILITIES (fixed). Honest cycle-2
   caveat: build-verify is NOT APPLICABLE for the calendar class (the
   documented limit), so the signature was the semantic check; the
   primitive is read-only and degrades to [] without calendar OAuth
   creds, and the probe's original goal still fails verification
   honestly until creds exist (`pass friday/calendar` or
   `GOOGLE_CALENDAR_TOKEN`). Registration of
   the send primitive surfaced + fixed a real harness bug: an impl
   beginning with `from __future__ import annotations` is a SyntaxError
   appended at EOF of an existing module, so `register_proposal` now
   strips leading future imports (regression-tested). The corresponding
   probe was retired and the morning trigger's allowlist tightened to
   read-only gmail primitives (see §6). Open option: dual-human approval
   for the full meta-engine.
1. **Deploy the watch loop — RESOLVED**: persistent systemd user service
   (`deploy/friday-watcher.service`, `WATCHER_DEPLOY_PROOF.md`) + 60 s
   heartbeat; replaces the failing July timer pair; once-per-day fired
   state persisted (`var/state/watcher_fired.json`, `WATCHER_DEPLOY_PROOF.md`
   §8). Open option: `loginctl enable-linger` for boot-without-login
   uptime.
2. **More ambient triggers**: other gmail senders, a daily planner-facts
   report, download alerts (already in config, disabled), desktop-status
   notifications on schedule.
3. **Capability-gap detection — DONE** (structured records + triage
   drafts + minimal approval gate; `CAPABILITY_GAP_PROOF.md`), and the
   two committed `ambient-gap-probe-*` triggers now feed it real ambient
   volume (~2 gap records/day, all safe allowlist refusals of genuinely
   unbuilt primitives) — the loop's first test under continuous
   operation. Triage now consumes gaps whose primitive is REGISTERED
   without drafting (the post-approval lifecycle: a probe keeps refusing
   a solved primitive, and the loop must never re-propose it).
   **First ambient triage (2026-08-11):** both proposals were drafted
   and the automated gate REJECTED both before any human review — the
   calendar draft imports a nonexistent `friday.l1.calendar` (sandbox
   ImportError); the gmail draft fails contract schema (name with three
   dots) AND confabulated the existence of a `gmail.send_document` to
   wrap ("the existing primitive is disallowed, so a new wrapper with a
   non-conflicting name…") — the digest's provenance failure appearing
   in the code-generation loop, the exact risk class to watch for
   send-capable drafts (a draft that compiles and passes its own mocked
   test is human-gate-only). Both rationales now carry their gate
   rejection records — schema/impl-stage rejections were previously NOT
   annotated (left a false APPROVAL: PENDING), now fixed + tested. The
   rejected proposal dirs act as tombstones: new probe gaps for these
   primitives are consumed without re-drafting until the dirs are
   deleted or the primitives registered.   On approval, RETIRE the
   corresponding probe (disable/repoint — its allowlist never changes);
   approving `gmail.send_document` expands gmail from read-only to
   side-effecting, a deliberate trust decision.
   **DONE 2026-08-11**: `gmail.send_document` was hand-built, gated
   (AST clean, sandbox 6/6, build-verify honestly NOT APPLICABLE for
   gmail), human-signed, and registered; `ambient-gap-probe-email-send`
   is now DISABLED per this lifecycle; `morning-gmail-summary`'s
   allowlist is tightened to `gmail.list_unread` / `gmail.get_message` /
   `gmail.summarize`. The calendar probe + its tombstoned drafts remain.

   STANDING PATTERN (recorded 2026-08-11, not a one-off bug): the gmail
   draft's confabulation is the same general failure mode as the digest's
   provenance misattribution — the model, asked to satisfy a constraint it
   cannot actually satisfy (an allowlist boundary, a mechanism that does
   not exist), fabricates a route around it instead of reporting the
   constraint. It has now appeared on BOTH sides of the system (digest
   synthesis + code generation), on the very first side-effecting draft.
   Expect it to recur; a prompt tweak is not the fix — a human reading the
   artifact is.

   PRECISE SCOPE OF THIS ROUND'S PROOF: the gate has proven it rejects
   STRUCTURALLY broken drafts (wrong imports, syntax errors, nonexistent
   symbols, contract-schema violations) quickly and before any human
   review. The first side-effecting primitive was therefore HAND-BUILT
   (not LLM-drafted) and human-signed — the human gate was the semantic
   check for the send-capable code, with build-verify honestly flagged
   NOT APPLICABLE for the gmail class. It has NOT yet been tested on the
   scarier case: a send-capable LLM DRAFT that compiles cleanly and
   passes its own mocked test while being subtly wrong or unauthorized.
   When such a draft appears — from a REAL gap, not the probes — that is
   a test of the human review process, not of the mechanical gate.
4. **Self-improvement loop — ALL STAGES CLOSED (2026-08-11)**: gap →
   draft → register was already closed; the **lessons loop** now closes
   the other half — rejections become remembered behavior. Every
   mechanical rejection is recorded as a structured lesson event
   (`var/logs/lessons.jsonl`): the automated gate's AST / sandbox /
   build-verify rejections, the approval gate's schema / impl-syntax
   rejections, the digest attribution check's flags, and the planner's
   retry-loop failures. `friday/lessons.py generalize` turns event
   clusters (≥2 per category) into reviewable candidates in
   `gates/proposed_lessons/` (idempotent, coverage-tracked); approval is
   editing `config/lessons.json` (human-edited like planner_facts.json —
   the file edit IS the human gate, same philosophy as APPROVED.md);
   approved lessons render as a bounded (≤5) KNOWN-MISTAKES block into
   the triage drafting prompt, the planner prompt, and the digest
   prompt. The seed lessons are the verified findings earned in Phase
   B/C: draft_confabulation, draft_dead_arg, draft_wrapper_dodge,
   draft_schema, digest_misattribution. The two real first-ambient-triage
   rejections (calendar sandbox ImportError → draft_test_fail; gmail
   contract-schema → draft_schema) are backfilled into the event log as
   labeled evidence. **THE GOALS-PROPOSAL STAGE (2026-08-11) closes the
   last open half**: `friday/goal_proposals.py` mines recurring FAILED
   goals from `tasks.jsonl` (REFUSED/probe records excluded, window +
   min-recurrence ≥2, deduped against existing triggers by substring +
   significant-token overlap) plus L0 failure signatures, and writes
   INERT, watcher-validated trigger proposals to
   `gates/proposed_triggers/<id>/` (`enabled: false`, `allow: []` —
   nothing can run until a human grants scope; the goal is quoted
   evidence, never LLM-rewritten; `--llm` drafts only schedule/allowlist
   with strict validation and deterministic fallback). Approval = copy
   into config/watcher.json + grant the allowlist + flip enabled. The
   first real run proposed exactly two candidates (the `gate6`
   pause-and-close goal ×2 and the `retry-stress` mpv goal ×2), both
   inert, both awaiting human judgment. Open: measuring plan-vs-reality
   drift.
5. **Cross-project synthesis — v2.2 SHIPPED (owned repos), SCALING DEFERRED**:
   the weekly digest over Friday + vivaha + Aether is live and proven end
   to end (`PHASE_C_V2_PROOF.md`); v1's third-party-target defect is
   fixed (Agent-Reach dropped, targets verified owned). v2.2 added the
   **mechanical attribution check** (`digestcheck.verify_attribution` —
   the v2.1 provenance-confabulation fix, now a gate on every digest)
   and switched context to **recency-based status docs**
   (`files.find_recent_doc`, no hand-maintained note). The live digest
   passed all three mechanical checks (specific-vs-generic, targets-
   owned, attribution — all 4 mechanisms confirmed) yet the human
   actionability bar still awaits one suggestion worth acting on, so
   scaling, the cost split, and V3 mining are ALL deferred. The full
   correlation engine (recency weighting, ingestion producer, confidence
   thresholds) remains open, and **Friday-V3 is flagged as containing an
   earlier correlation-engine implementation worth mining for that**.
6. **MCP servers — SHIPPED (2026-08-18)**: `friday/mcp_server.py` exposes
   every contract-registered, executor-accessible primitive (57 tools) as
   an MCP tool server over stdio (MCP 2024-11-05 subset), zero new
   dependencies (stdlib JSON-RPC 2.0 only - the project stays on
   requests/playwright/Pillow). Each tool call routes through the
   executor's `_resolve_primitive` boundary, so an unproven or blocked
   primitive (window.shutdown) is refused exactly like a plan step would
   be; L0 logging is automatic via the existing @contract -> @observe
   wrap. Tool schemas derive from the primitives' real signatures at
   list time. Run `python -m friday.mcp_server` or the `friday-mcp`
   console script; 15 hermetic tests in tests/test_mcp_server.py.

## How to verify anything in this document

```bash
./.venv/bin/python gates/test_suite.py            # 571 tests -> TESTS_PROOF.md
python -m friday.mcp_server                      # MCP tool server (stdio; see friday/mcp_server.py)
./.venv/bin/python -m friday.goal_proposals       # mine failures -> inert trigger proposals
./.venv/bin/python -m friday.goal_proposals --dry-run   # preview, write nothing
systemctl --user status friday-watcher.service    # deployed daemon (see deploy/RUNBOOK.md)
./.venv/bin/python -u gates/e2e_check.py          # live 4-goal check -> E2E_PROOF.md
./.venv/bin/python -u gates/watcher_gmail_demo.py # live gmail trigger -> WATCHER_GMAIL_PROOF.md
./.venv/bin/python gates/watcher_demo.py          # deterministic triggers -> WATCHER_PROOF.md
./.venv/bin/python -u gates/capability_gap_demo.py # gap -> gate -> re-run -> CAPABILITY_GAP_PROOF.md
./.venv/bin/python -u gates/phase_c_v1_demo.py     # Phase C v1 (historical) proof
./.venv/bin/python -u gates/phase_c_v2_demo.py     # Phase C v2 (owned repos) -> PHASE_C_V2_PROOF.md
./.venv/bin/python -m friday.lessons --list       # the injected KNOWN-MISTAKES set
./.venv/bin/python -m friday.lessons              # generalize recorded events into candidates
./.venv/bin/python -m friday.watcher --once       # the real watcher, current config
```

Raw evidence: `var/logs/friday.jsonl` (L0), `var/logs/tasks.jsonl`
(counter). All proof files are raw captured output, not summaries.
