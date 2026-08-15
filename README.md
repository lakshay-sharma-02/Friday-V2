# Friday V8

Layered desktop automation with the discipline that every layer ships raw
proof before the next layer starts. Five layers, strict dependency order:

```
L4  Planning     (LLM: goal -> plan JSON)      [Gate 5]
L3  Execution    (deterministic runner)         [Gate 4]
L2  Verification (read-only state checks)       [Gate 3]
L1  Primitives   (window/media/browser/dev/...) [Gate 1]
L0  Observability (structured logging)          [Gate 2]
```

**Status: DONE + hardened + live-verified** (2026-08-15) — every
structural gate G1–G6 shipped raw, captured output; **25 distinct
passing task ids** — the **13 composite tasks**, the `retry-stress` gate,
and **11 live-automation records** (watch/e2e) — are on record in
`var/logs/tasks.jsonl`; every executor-callable L1 primitive has
standalone bring-up proof; the core is hardened (blocked primitives,
protected windows, dangerous-dev gate); a **515-test unit suite** covers
every layer; a **live end-to-end check** runs the real stack against
this machine's real state — including a real gmail summary through the
ambient watch loop — and the watch loop is **deployed as a persistent
systemd service** (`deploy/friday-watcher.service`, starts at login,
restarts on failure) with a `daemon.alive` heartbeat every 60 s; the
**capability-gap loop** is closed end to
end: refused steps become structured records, triage drafts proposed
primitives, an **automated gate** (AST checks + sandboxed test run)
rejects structural defects before any human review, and a human-signed
approval registers them — **10 real primitives registered and re-proven**
through the full loop: `files.find_file_exact` (read-only),
**`gmail.send_document`** (the loop's first SIDE-EFFECTING primitive,
hand-built rather than LLM-drafted after the two rejected drafts for
it), `files.write_text`, `calendar.list_upcoming`, `clipboard.read_text`,
`files.find_newest`, `media.get_volume`, `media.get_playing_title`,
`calendar.add_event` and `clipboard.write_text` (the last two registered
2026-08-14; `clipboard.write_text` needed the gate's WRITE subprocess
shape after its READ-shape first registration deadlocked live), and a deliberately
bad draft is mechanically blocked in the proof; the **lessons loop**
makes the
rejections stick: every mechanical rejection is recorded as a structured
lesson event, `friday/lessons.py` generalizes event clusters into
human-approved lessons (`config/lessons.json`), and the approved lessons
are injected as a bounded KNOWN-MISTAKES block into the triage, planner
and digest prompts; and the **goals-proposal stage**
(`friday/goal_proposals.py`) mines the failure history — recurring
FAILED goals in `tasks.jsonl` plus L0 failure signatures — into INERT,
watcher-validated trigger proposals (`gates/proposed_triggers/`) that a
human approves or rejects, so Friday proposes what deserves a scheduled
goal instead of only executing goals you hand it. The two remaining
primitives
(`window.shutdown`, `vision`) are deferred **by the plan's own terms**,
not by omission. Full completion record: `gates/PLAN_STATUS.md`.

## Layout

```
friday/
  contracts.py      L1 contract registry (pre/post/idempotency/failure)
  errors.py         exception hierarchy (FridayError, PreconditionError, ...)
  observability.py  L0: one structured JSON line per call (redaction + clip +
                    per-primitive log projection + size-based rotation)
  secrets.py        pass-based credential store (friday/<service>)
  l1/               L1 primitives (each contract-registered; see below)
    window.py       hyprctl IPC  (open/close/focus/list/move/shutdown)
    media.py        mpv IPC socket (play/pause/resume/stop/volume; orphan
                    sweep + zombie reaping - lifecycle-fixed and re-proven)
    browser.py      Playwright persistent context (DOM, not screenshots)
    dev.py          claude -p subprocess (bypass is explicit opt-in); digest()
                    LLM-in-primitive cross-project synthesis (Phase C)
    git.py          read-only git log (repo history, no diffs) - Phase C
    digestcheck.py  verify_attribution - MECHANICAL digest attribution check
                    (every "X's <mechanism>" claim must appear in X's own
                    gathered content - the v2.1 confabulation fix)
    files.py        deterministic discovery + bounded reader (find_file /
                    find_file_exact / find_newest / read_text /
                    find_recent_doc / write_text)
    gmail.py        Gmail REST API, OAuth2 (list_unread / get_message /
                    summarize read-only; send_document — the gate-registered
                    first side-effecting primitive; scope gmail.readonly +
                    gmail.send after the 2026-08-11 re-consent)
    calendar.py     Google Calendar API, OAuth2 (list_upcoming read-only;
                    add_event — the loop's first calendar WRITE, registered
                    2026-08-14; refresh-grant auth + summary redaction)
    clipboard.py    gate-registered clipboard primitives (read_text /
                    write_text — wl-paste/wl-copy on Wayland, xclip on X11;
                    the WRITE shape's stdout/stderr=DEVNULL is the
                    daemon-fork fix from the 2026-08-14 deadlock)
    notify.py       desktop notifications (notify-send) - the watch loop's
                    feedback channel
    telegram.py     Telegram Bot API (send_text / send_document)
    discord.py      Discord Bot API (send_text / send_file)
  watcher.py        ambient watch loop (config/ triggers -> goals -> tasks.jsonl;
                    daemon.alive heartbeat; deployed via deploy/friday-watcher.service)
  capability_gaps.py structured refusal records (var/logs/capability_gaps.jsonl)
  gap_triage.py     groups gaps, LLM-drafts proposed primitives (review-only)
  automated_gate.py AST checks (imports/danger/contract-fn/dead-args) +
                    sandboxed test run + build-verify (real targets),
                    before any human review
  register_proposal.py approval gate: automated stage -> APPROVED.md -> register
  lessons.py        the lessons loop: rejection events -> human-approved
                    lessons -> bounded KNOWN-MISTAKES prompt injection
  goal_proposals.py the goals-proposal stage: recurring FAILED goals from
                    tasks.jsonl + L0 failures -> INERT trigger proposals
                    (gates/proposed_triggers/) for human approval
tests/               dependency-free unittest suite (515 tests, all mocked)
  l2/
    checks.py       L2 verification: read-only checks (catalog below)
  l3/
    executor.py     L3 deterministic state machine over a plan
  l4/
    planner.py      L4 LLM planning (goal -> plan JSON, schema-validated)
gates/               every gate/task runner + its raw proof artifact
                     (incl. proposed_primitives/ + proposed_triggers/ - the
                     two human-review queues of the self-improvement loop)
assets/test_tone.mp3  deterministic audio fixture (70s 440Hz)
config/planner_facts.json  editable PROJECT FACTS for the planner
config/lessons.json       human-approved lessons store (the lessons loop's
                    injection source - editing it IS the approval gate)
var/               runtime data (browser profile, logs) - gitignored
```

## L1 primitives

Every primitive carries a registered contract (precondition, postcondition,
idempotency class, failure mode) in `friday/contracts.py`; **L3 refuses to
call any primitive without one**. Idempotency classes: `idempotent`
(read-only, safe to retry), `at-most-once` (a retry could duplicate a side
effect: send/open), `commutative-safe` (retry is harmless once the target
state already matches).

| Module | Primitives |
|--------|-----------|
| `window` | `open_app`, `close_window`, `close_all(exclude_classes=...)`, `focus_window`, `move_to_workspace`, `list_clients`, `get_active_window` (+ `shutdown` — **blocked from the executor** via `EXECUTOR_BLOCKED`; direct script calls only) |
| `media` | `play`, `play_for`, `pause`, `resume`, `stop`, `set_volume`, `is_playing` (read), `get_volume` (read, gate-registered), `get_playing_title` (read, gate-registered) |
| `browser` | `goto`, `read_page_text`, `find_locator`, `click`, `type_text`, `press_key`, `upload_file`, `login`, `credentials` (returns secret — result redacted in the log), `close` |
| `dev` | `run` (claude -p), `run_shell` — **arbitrary shell, requires `FRIDAY_ALLOW_DANGEROUS=1`** (checked before claude runs), `digest(context, instruction)` — LLM-in-primitive cross-project digest synthesis (Phase C, the gmail.summarize exception) |
| `files` | `find_file(name, directory, recursive)`, `find_file_exact(name, directory)` — gate-registered exact-match probe returning `''` when absent, `find_newest(name, directory)` — gate-registered mtime-newest match ('' when none), `read_text(path, max_chars)` — bounded read-only text reader, `find_recent_doc(repo_path)` — most recently modified status/planning doc (PLAN_STATUS/ROADMAP/DEVLOG/STATUS/TODO/CHANGELOG shapes, README fallback), `write_text(path, text, append)` — gate-registered first files.* WRITE primitive (commutative-safe; absolute/`..`/`~` targets rejected by the automated gate's fs-scope checks) |
| `git` | `log(repo_path, count, days)` — read-only recent commit entries (hash/author/date/subject, no diffs), the cross-project digest's eyes (Phase C) |
| `digestcheck` | `verify_attribution(digest, context)` — mechanical per-repo attribution check: every "X's <mechanism>" claim must appear in X's own gathered content, not just anywhere in the combined prompt (Phase C, the v2.1 confabulation fix) |
| `notify` | `notify_send(title, body, timeout_ms)` — desktop notification |
| `gmail` | `list_unread(sender, max_results)`, `get_message(message_id)`, `summarize(message_id)` — OAuth2 read-only, auto token refresh; `send_document(file_path, to=None, subject, body)` — **gate-registered, the loop's first side-effecting primitive** (at-most-once; recipient redacted from the L0 result line); send scope requires the one-time re-consent in `gates/GMAIL_SETUP.md` §6.5 |
| `calendar` | `list_upcoming(days)` — OAuth2 read-only, auto token refresh, summaries redacted in the L0 line (gate-registered; refresh-grant auth fix 2026-08-14); `add_event(summary, start, end)` — **gate-registered first calendar WRITE** (at-most-once; needs the `calendar.events` scope added at consent time — see `gates/_calendar_oauth_setup.py`) |
| `clipboard` | `read_text()` — gate-registered clipboard read (wl-paste/wl-copy Wayland, xclip X11; content redacted in the L0 line), `write_text(text)` — gate-registered clipboard write (echoes text back; DEVNULL subprocess shape so the tool's forked daemon can't block the pipe) |
| `whatsapp` | `get_me`, `upload_document`, `send_document`, `send_text` |
| `telegram` | `get_me`, `send_document`, `send_text` |
| `discord` | `get_me`, `send_file`, `send_text` |

## L2 checks (read-only; the only thing a plan step may verify with)

`friday/l2/checks.py` — pure, side-effect-free functions. Import
discipline enforced by Gate 3: L2 imports only primitives' *read-only*
accessors. Catalog:

- window: `window_client_count`, `window_has_class`, `window_has_title`,
  `active_window_class`, `window_focused`, `window_on_workspace`,
  `window_only_classes`
- media: `media_playing`
- browser: `browser_has_text`, `browser_input_has_value`
- files: `file_exists`
- pure shape checks: `list_nonempty` (a gather step produced a list),
  `text_nonempty` (a read/synthesis step produced text) — Phase C
- messaging: `whatsapp_identity_ok`, `message_sent`
- gmail: `gmail_unread_exists`, `gmail_message_matches`

`checks.window_only_classes` is the **sufficient** check for a
`window.close_all(exclude_classes=...)` step: it asserts that no client
with a class outside the excluded set remains (mirrors `close_all`'s own
class-only loop, vacuous-true on an empty desktop). `window_focused` only
proves where focus landed and must never verify a close-all — the Gate 6
harness refuses such plans.

## L3 executor

`friday/l3/executor.py` — a deterministic state machine, **zero LLM
calls**. Per step:

```
PENDING -> RUNNING -> {VERIFIED, FAILED}
FAILED -> RETRY (bounded, contract-derived backoff) -> RUNNING
FAILED -> RETRY_EXHAUSTED -> ABORT (plan-level, loud, logged)
```

- `run_plan(plan, run_id=...) -> PlanResult` walks `{primitive, args,
  verify}` steps, dispatching generically through the contract registry —
  zero conditionals keyed on primitive or app identity.
- Every verify is an L2 read-only check run *after* the primitive; a
  step's own return value is never trusted as proof.
- Plans may reference prior step results via `$steps.N.result.key`; a
  reference to a *future* step is rejected **before** the primitive runs.
- Every transition writes one L0 line with `run_id` + `step_id`
  correlation.

## L4 planner

`friday/l4/planner.py` — goal string in, plan JSON out, via a live LLM
call (`dev.run`), in the exact schema L3 consumes unmodified.

- **Capability catalog** (`build_catalog`): compact text of every
  contract-registered primitive + every L2 check, auto-derived from the
  registry at call time so it can never drift from what L3 will resolve.
- **Zero goal-specific logic**: no goal-keyed branching, no template
  library. Anti-cheese proven by running two goals through the unmodified
  pipeline (incl. one never seen anywhere before).
- `validate_plan` schema-checks the LLM's output (registered primitives
  only, real checks, `$facts` resolved) **before** it reaches L3; malformed
  plans fail loudly in L4.
- `plan(goal, ...)` — bounded LLM retries; `build_prompt(goal)` for the
  raw prompt. Facts override chain: `facts_file` arg > `$FRIDAY_FACTS_FILE`
  > `config/planner_facts.json` > built-ins.

## Running a goal

```sh
./.venv/bin/python - <<'PY'
import sys; sys.path.insert(0, ".")
from friday.l4.planner import plan
from friday.l3.executor import run_plan

goal = "pause whatever's playing, then close every window except my terminal"
result = run_plan(plan(goal, run_id="demo"))
print(result.status)          # COMPLETED | ABORTED
PY
```

Every layer logs to `var/logs/friday.jsonl` (`$FRIDAY_LOG_FILE`
overrides). The log rotates by size: past `FRIDAY_LOG_MAX_BYTES`
(default 10 MB) it is renamed to `.1`, older backups shift, and
`FRIDAY_LOG_BACKUPS` (default 3) are kept; `FRIDAY_OBSERVABILITY=0`
disables logging entirely. Some primitives project their logged result:
`window.list_clients` / `get_active_window` / `open_app` log a compact
client summary (address/class/title/workspace/pid/mapped), and
`gmail.list_unread` redacts sender/subject while keeping message_id/date -
the real return values are never affected. The same pipeline, run with
zero scaffolding, is what Task 11 (`gates/GATE6_DOD_PROOF.md`) proved
end-to-end.

## Secrets

Credentials live in `pass` at `friday/<service>`:

```sh
pass insert -m friday/github   # store JSON: {"username": "...", "password": "..."}
```

Read via `friday.secrets.get_credentials(service)` — never hardcoded,
never logged in plaintext (whole-result redaction where needed). `pass`
itself is installed via `sudo pacman -S pass` and initialized with
`pass init 41D31F50572982F8`.

Messaging platforms use env vars instead: `WHATSAPP_ACCESS_TOKEN` +
`WHATSAPP_PHONE_NUMBER_ID` (+ optional `WHATSAPP_DEFAULT_PHONE`),
`TELEGRAM_BOT_TOKEN`, `DISCORD_BOT_TOKEN` + `DISCORD_CHANNEL_ID`.

## Planner facts

`config/planner_facts.json` feeds the PROJECT FACTS section of every LLM
planning prompt. Named `file_paths` and named `recipients` are
referenceable from plan args as `$facts.<name>` (e.g. `"file_path":
"$facts.readme"`, `"to": "$facts.whatsapp"`) and are substituted
deterministically before execution, so goals never need hardcoded paths
or recipient ids. Free-form `facts` render as extra bullets (e.g. "my
terminal = kitty windows", the GitHub login recipe). Override the file
with `$FRIDAY_FACTS_FILE`, or pass `facts=` / `file_paths=` /
`recipients=` to `planner.plan()` per call.

When a goal only *describes* a file ("the receipt pdf in my downloads"),
`files.find_file(name, directory)` resolves it to a path deterministically
(`directory` can be a configured folder like `$facts.downloads`); a plan
locates it with one step and sends `"$steps.1.result.path"` with the next.

## Testing

A dependency-free unittest suite lives in `tests/` and covers every layer
and feature: the contract registry, observability (redaction, rotation,
`log_transform`), the executor (ref resolver, retry policy, blocked
primitives), the planner (validate_plan, catalog, facts), all L2 checks,
window protected-classes, the dev dangerous-gate, gmail/notify/secrets,
the watch loop (incl. the per-trigger primitive allowlist and the
daemon.alive heartbeat), the digest attribution checker (correct claims
pass, cross-repo misattributions flagged, typographic-punctuation
normalization), the recency-based status-doc finder, the capability-gap recorder (executor + watcher refusal paths, with the
gap file temp-isolated by default after a real hermeticity leak was
found and fixed), the capability-gap triage drafter, the lessons loop
(recording, candidate generalization with min-example threshold and
coverage tracking, approved-store validation, bounded injection into all
three prompts, and the record sites: gate rejections, digest
misattributions and planner failures each write a lesson event), the
goals-proposal stage (recurring-failed-goal clustering with window +
min-recurrence filters, REFUSED/probe exclusion, existing-trigger
coverage by substring AND significant-token overlap, WATCH-layer L0
evidence attachment, deterministic + LLM drafting with strict
watcher-schema validation and deterministic fallback, inert-proposal
writing, idempotence, and a never-touches-watcher-config assertion),
and the browser locator chain, plus the gate-registered send primitive
(`gmail.send_document`: real MIME assembly with mocked HTTP/token, the
recipient-redaction discipline on the L0 result line, and the
future-import registration hardening). Every side-effect boundary
is mocked — the suite never sends, launches, clicks, or touches the
compositor.

```sh
./.venv/bin/python -m unittest discover -s tests -v   # run directly
./.venv/bin/python gates/test_suite.py                # run + write gates/TESTS_PROOF.md
```

The runner captures the raw output into `gates/TESTS_PROOF.md`, the same
proof discipline as every gate.

## Task counter (the ≥10 mechanism)

`var/logs/tasks.jsonl` — one JSON line per run, from Gate 6 onward:
`{task_id, goal, gate6_passed, timestamp, proof}`. Failures are recorded
honestly (never deleted); tasks 1–7 predate the file and are backfilled
with `backfilled: true`. Current distinct passing ids: **25** — the **13
composite tasks** (task1–task10 + `gate6` + `whatsapp-filesend` +
`gmail-summary`), the `retry-stress` gate, and **11 live-automation
records**: the watcher demos (`watch:demo-time`, `watch:demo-file`), the
live E2E goals (`e2e:files`, `e2e:media`, `e2e:windows`, `e2e:gmail`),
the real watcher triggers `watch:morning-gmail-summary` (a live gmail
summary via `$facts.gmail_sender`), `watch:weekly-cross-project-digest`
(a live cross-project digest over Friday + vivaha + Aether, Phase C v2.2
with the mechanical attribution check), and the three daily-use
triggers added 2026-08-14: `watch:morning-calendar-summary`,
`watch:morning-clipboard-digest` (both live-proven against the real
calendar 2026-08-15) and `watch:new-download-alert`. Per
the Gate 6 prompt's scheme, counting starts at `gate6` from here on.

## Gates, tasks and proofs (all raw output, `gates/`)

| Artifact | What it proves |
|----------|----------------|
| `GATE1_PROOF.md` | L1 bring-up (window/media/browser/dev) |
| `GATE2_PROOF.md` | L0: one structured line per call |
| `GATE3_PROOF.md` | L2 read-only checks + import discipline |
| `GATE4_PROOF.md` | L3 executor on a hardcoded plan, zero LLM |
| `GATE5_PROOF.md` | L4 LLM planning → same executor |
| `GATE5_DOD_PROOF.md` | Anti-cheese: two goals, unmodified pipeline, incl. a never-seen goal (`gate5_devrun_lines.jsonl` holds the model's raw plan output bytes) |
| `GATE6_PROOF.md` | First composite task (messaging), full L0 trace |
| `GATE6_DOD_PROOF.md` | Real spoken-style goal, zero scaffolding; incl. the L2-gap fix and its run history (failed runs kept as data) |
| `TASK1..TASK10_*_PROOF.md` | Composite tasks: receipt→WhatsApp, text→3 platforms, browser open/click/search, media timer + pause/resume, window compose, GitHub login, file upload |
| `TASK_WHATSAPP_FILESEND_PROOF.md` | WhatsApp file-send re-prove on the Cloud API — the historical browser-era "stages but doesn't send" bug has zero recorded instances in the API path (legacy browser automation removed) |
| `BRINGUP_GMAIL_PROOF.md` / `TASK_GMAIL_SUMMARY_PROOF.md` | Gmail primitives bring-up + unread-email summary task (OAuth2 read-only; its 3 honest failed runs exposed executor list-index/bracket-ref gaps, now fixed + unit-tested) |
| `GMAIL_SETUP.md` | From-scratch Google OAuth setup guide incl. the production publish that removes the 7-day testing-mode token expiry |
| `BRINGUP_REMAINING_PROOF.md` | Last unproven primitives: media pause/resume, browser upload, window focus/move/close_all |
| `MPV_LIFECYCLE_FIX_PROOF.md` | mpv orphan-leak + zombie-reap defects fixed and re-proven |
| `RETRY_STRESS_PROOF.md` | Lifecycle holds under repeated invocation + executor retry paths |
| `TESTS_PROOF.md` | The dependency-free unit suite, raw output (regenerated by `gates/test_suite.py`; 515 tests) |
| `CAPABILITIES.md` | Live capability inventory GENERATED from the contract registry — 57 primitives, 17 checks, 10 triggers, 10 gate-registered primitives (regenerate: `./.venv/bin/python gates/generate_capabilities.py`, idempotent) |
| `PORTABILITY.md` | Windows-port analysis + ordered checklist — reference/aspirational, no porting scheduled |
| `WATCHER_PROOF.md` | Watch loop first proof: time + file triggers fire deterministic plans through the real watcher (no LLM, no side effects), recorded in tasks.jsonl, notified |
| `WATCHER_GMAIL_PROOF.md` | The enabled `morning-gmail-summary` trigger runs a REAL gmail summary through the unmodified watcher (`$facts.gmail_sender`, `allow: ["gmail.*"]`, live LLM plan, verified) |
| `E2E_PROOF.md` | Live end-to-end: 4 goals (files/windows/media/gmail) through the real stack with live LLM plans, allowlist refusal, redacted proof |
| `CAPABILITY_GAP_PROOF.md` | Capability-gap loop closed end to end: refusal -> record -> triage -> AUTOMATED gate (AST + sandboxed tests) -> human signature -> registration -> re-run-passes; a deliberately bad draft is blocked before the signature; one real primitive (`files.find_file_exact`) registered |
| `WATCHER_DEPLOY_PROOF.md` | The watch loop **deployed** as a persistent systemd user service replacing the silently-failing July timer pair; real status, real `daemon.alive` heartbeats over real elapsed time (and the heartbeat catching its own first-release timing bug), and the real gmail trigger COMPLETING under the service |
| `PHASE_C_V1_PROOF.md` | **Phase C v1** (narrow, historical): the first digest paired Friday with Agent-Reach — a THIRD-PARTY repo, not Lakshay's — proving the gather→synthesize→deliver pattern mechanically while showing its suggestions were specific-sounding but not actionable |
| `PHASE_C_V2_PROOF.md` | **Phase C v2 → v2.2** (real owned repos): drops Agent-Reach and pairs Friday with **vivaha + Aether** (cloned from GitHub, both owned); v2.1's context experiment found provenance confabulation + invisible true blockers, so v2.2 added a THIRD mechanical check — `digestcheck.verify_attribution` (every "X's <mechanism>" claim must appear in X's own gathered content) — and switched context to recency-based `files.find_recent_doc` status docs; the live digest is 12/12 VERIFIED (executor + real watcher) with all 4 attributed mechanisms confirmed; human is the final judge |

The master completion record with the full task table lives at
`gates/PLAN_STATUS.md`.

## Deferred by design (not gaps)

- **`window.shutdown`** — destructive: it ends the Hyprland session. It is
  now **mechanically blocked** from the executor: the LLM never sees it in
  the catalog, `validate_plan` rejects it, and L3 refuses it
  (`EXECUTOR_BLOCKED` in `friday/contracts.py`). A deliberate script can
  still call `window.shutdown()` directly as a last act on a clear desktop.
- **`vision`** — the plan itself says "skip vision for now"; gated off
  until every structured alternative has failed for a target.

## Safety rail (core-enforced, not harness-enforced)

- **Protected windows**: `window.close_window` / `close_all` refuse to
  close any client whose class is protected — `FRIDAY_PROTECTED_CLASSES`
  (comma-separated, default `kitty`, the user's terminals). The refusal
  happens **before any dispatch**, so a plan can never partially close the
  desktop and then fail.
- **Dangerous dev**: `dev.run_shell` and `dev.run(allow_bypass_permissions=True)`
  raise `PreconditionError` unless `FRIDAY_ALLOW_DANGEROUS=1` is set — the
  flag is the authorization boundary, checked before claude is invoked.
- **Blocked primitives**: `EXECUTOR_BLOCKED` primitives are unreachable
  from any plan path (catalog, validation, executor).

## Watch loop (ambient automation)

`friday/watcher.py` turns goals into background automations. Triggers live
in `config/watcher.json` — inert until you set `enabled: true`. The
`morning-gmail-summary` trigger is **wired in and enabled** (09:00
weekdays); its goal references `$facts.gmail_sender`, so the sender is
edited in `config/planner_facts.json`, never hardcoded in the trigger.
The `weekly-cross-project-digest` trigger is **wired in and enabled**
(Sundays 10:00, Phase C v2.2) — a deterministic plan gathering `git.log`
from Friday + vivaha + Aether, discovering each repo's most recently
modified status doc (`files.find_recent_doc`), reading those docs, then
`dev.digest` synthesizing a weekly digest with one full-tier LLM call,
`digestcheck.verify_attribution` mechanically checking every
"X's <mechanism>" claim against X's own gathered content (the
confabulation fix), and `notify.notify_send` delivering it
(see the Phase C section below). A companion `sunday-digest-reminder`
trigger (10:05 Sundays, 5 minutes after the digest) fires a static
notify-only plan — zero LLM cost, allowlisted to `notify.notify_send`
only, `notify: false` so it never double-pings — nudging the weekly
verdict into `gates/DIGEST_TRACKING.md`, the human judgment log that
decides whether Phase C scales.

The four `ambient-gap-probe-*` triggers were the loop's **deliberate
ambient volume source**: silent (`notify: false`), allowlisted
(`allow: ["notify.notify_send"]`) deterministic probes whose single step
was a genuinely unbuilt primitive. The allowlist refused the step BEFORE
any execution — nothing ever ran — and REFUSED is terminal-for-the-day,
so each probe recorded **exactly one real capability-gap record per day**
for triage to group and LLM-draft. All four are now **RETIRED** (disabled
in `config/watcher.json`) because their primitives completed the loop and
registered — a daily refusal of a solved primitive is noise:
- `ambient-gap-probe-email-send` **RETIRED 2026-08-11** —
  `gmail.send_document` approved and registered (the loop's first
  side-effecting primitive).
- `ambient-gap-probe-file-write` **RETIRED 2026-08-13** — `files.write_text`
  approved and registered through the full loop (self-checked LLM draft,
  automated gate with write-family build-verify, human review).
- `ambient-gap-probe-calendar` **RETIRED 2026-08-13** —
  `calendar.list_upcoming` registered through the loop's second complete
  cycle (LLM-drafted with ZERO hand-correction; needs calendar OAuth
  creds to return real events — without them it returns `[]` and
  verification fails honestly).
- `ambient-gap-probe-clipboard` **RETIRED 2026-08-14 — the same day it
  was created** — `clipboard.read_text` was approved and registered
  through the full loop (contract-aware gate + subprocess-read
  build-verify + human signature), so its daily refusal of a now-solved
  primitive became noise (lifecycle precedent: the three above). No
  probe remains enabled; the loop's ambient volume now comes from REAL
  refusals and the goal-proposals stage (below).

And because registering a send primitive under a `gmail.*` pattern would
have silently armed the LLM-planned morning trigger with send capability,
that trigger's allowlist was tightened to the three read-only primitives
(`gmail.list_unread` / `gmail.get_message` / `gmail.summarize`).

**2026-08-14 — the daily-use layer caught up with the loop.** Three more
triggers are wired in and enabled (all deterministic plans, no L4 LLM
call, each allowlisted to exactly the primitives its plan needs):
- `new-download-alert` — a `file` trigger on `~/Downloads` matching
  `.pdf`: `files.find_newest` locates the newest pdf by mtime (mtime,
  not lexicographic-first — the fix that motivated the primitive) and
  `whatsapp.send_document` delivers it to the configured default phone.
  Fires once per new pdf; never fires for pre-existing files.
- `morning-calendar-summary` (daily 08:00) — one step,
  `calendar.list_upcoming(days=1)`, verified with `checks.list_nonempty`
  and desktop-notified. An empty day is an honest FAIL (same philosophy
  as morning-gmail-summary's empty mailbox).
- `morning-clipboard-digest` (daily 08:05, right after the calendar
  summary) — `calendar.list_upcoming(days=1)` → `dev.digest` composes a
  short plain-text morning digest (the one LLM-in-primitive exception,
  same as gmail.summarize) → `clipboard.write_text` copies it. Both
  were live-proven 2026-08-15 against the real calendar (a real
  add_event test event read back into the digest, and the clipboard
  held the composed digest).

```json
{ "id": "morning-gmail-summary",
  "goal": "find the most recent unread email from $facts.gmail_sender and
    summarize it in at most 5 plain sentences",
  "schedule": {"type": "time", "at": "09:00", "days": ["mon","tue","wed","thu","fri"]},
  "enabled": true, "allow": ["gmail.list_unread", "gmail.get_message",
    "gmail.summarize"] }
```

- `time` triggers fire once per day after `at` (on `days` if given);
  `file` triggers fire once per new file in `directory` matching `name`.
- A trigger may carry an inline deterministic `plan` (no LLM) or a `goal`
  planned through L4 (one LLM call per distinct goal per daemon run, then
  cached).
- **`allow`** (optional) is a per-trigger primitive allowlist: exact names
  or `mod.*` patterns. Any plan step whose primitive is not on the list is
  REFUSED before execution and recorded honestly — a hallucinated
  side-effecting step never acts from an unattended trigger. (L2 verify
  checks are read-only and always permitted.)
- Each firing is recorded in `var/logs/tasks.jsonl` as `watch:<id>` in the
  gate-6 format (`FRIDAY_TASKS_FILE` overrides the path) and pings the
  desktop via `notify_send` (`"notify": false` silences it).
- Triggers run strictly serially — one goal at a time — because the L1
  media/browser state is a single-writer resource. Safety is inherited
  from the core (protected windows, blocked primitives, dangerous-dev gate).

```sh
./.venv/bin/python -m friday.watcher --once      # fire due triggers, exit (cron)
./.venv/bin/python -m friday.watcher --poll 30   # daemon mode
```

**Deployed**: the daemon runs as a persistent systemd **user** service
(`friday-watcher.service`, source in `deploy/`, day-2 ops in
`deploy/RUNBOOK.md`) — starts at login, `Restart=on-failure`, polls every
30 s, and emits a `daemon.alive` heartbeat every 60 s into
`var/logs/friday.jsonl` (`FRIDAY_HEARTBEAT_S` overrides; the heartbeat
carries uptime, the last trigger fired, and the live `capability_gaps`
count — the number to watch for proposals outpacing human review). It
replaced the July `friday-watch.timer` pair, which had been failing every
2 minutes since (it ran a `friday.cli` entry point that no longer
exists). Once-per-day fired state is **persisted**
(`var/state/watcher_fired.json`) so a restart does not re-fire a trigger
that already COMPLETED today — proven live in `gates/WATCHER_DEPLOY_PROOF.md`
§8; a FAILED run stays eligible to retry later the same day, rate-limited
by `RETRY_BACKOFF_S` (600 s) so a transient failure never silently kills
the day's slot, while an allowlist REFUSED run is treated as done for
the day (retrying it would only replan and re-refuse). Without
`loginctl enable-linger` the service stops at logout. Proof:
`gates/WATCHER_DEPLOY_PROOF.md`.

Proofs: `gates/WATCHER_PROOF.md` (time + file triggers, deterministic
plans) and `gates/WATCHER_GMAIL_PROOF.md` (the real gmail trigger through
the unmodified watcher against the live inbox — LLM plan, verified steps,
real summary).

## Live end-to-end check

`gates/e2e_check.py` runs the REAL stack on this machine — not unit tests:
four goals are planned by a live LLM call (L4), executed by the
unmodified executor (L3), verified by real L2 checks against real state,
traced through the real L0 log, recorded in the gate-6 tasks format, and
pinged to the desktop:

- files: find README.md and report its absolute path
- windows: verify a kitty terminal is open (real compositor state)
- media: pause any playing audio (a no-op when nothing plays)
- gmail: summarize the most recent unread email from a sender discovered
  by a read-only pre-probe of the real inbox — `list_unread` →
  `get_message` → `summarize`, all verified; `E2E_GMAIL_SENDER=<email>`
  pins a sender instead of probing

Defense in depth: a read-only allowlist REFUSES any plan containing a
side-effecting primitive before execution — an LLM that hallucinates a
send/open/close step can never act on it during the check (a live run
once caught the model planning a `whatsapp.send_text` report; it was
refused with zero side effects). The probe sender is redacted as
`<redacted>` in the proof transcript, matching `gmail.list_unread`'s L0
`log_transform`.

```sh
./.venv/bin/python -u gates/e2e_check.py     # writes gates/E2E_PROOF.md
```

Live proof: `gates/E2E_PROOF.md` (4/4 goals PASS from live LLM plans).

## Capability-gap loop (gap -> draft -> human gate -> register)

When a plan step is refused because its primitive is unknown, unregistered,
blocked, or not on a trigger's allowlist, `friday/capability_gaps.py`
writes one structured record to `var/logs/capability_gaps.jsonl`
(source, goal_context, attempted_primitive, arg-SHAPE type tags — never
values — and refusal_reason). Three committed `ambient-gap-probe-*`
triggers generated this ambient volume deliberately (all retired after
their primitives registered — see the watch-loop section), so the loop's
volume and draft quality were tested under real continuous operation, not
just by proof runs. `friday/gap_triage.py` groups unprocessed
records by primitive and makes an LLM call to draft a proposal into
`gates/proposed_primitives/<primitive>/` — `contract.json` (the real
Contract schema), `impl.py`, `test.py`, `rationale.md`.

**Nothing self-registers.** A draft becomes a primitive only through the
two-stage approval gate (`friday/register_proposal.py`):

1. **Automated stage** (`friday/automated_gate.py`), before any human
   involvement: contract schema → impl compiles → **AST checks** (imports
   limited to what shipped L1 primitives actually import, no
   exec/eval/os-system calls and no subprocess.* beyond the bounded
   pattern shipped primitives use — the READ shape
   (`subprocess.run([...], capture_output=True, timeout=...)`, which lets
   a read-family primitive like `clipboard.read_text` shell out to
   `wl-paste`/`xclip`) and the WRITE shape (`subprocess.run([...],
   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=...)`,
   required for write-family tools like `wl-copy`/`xclip` whose forked
   daemon inherits pipe fds and would block `capture_output` forever —
   added 2026-08-14 after the first `write_text` deadlocked live), the
   contracted function defined,
   no dead arguments, and no file writes escaping the sandbox —
   absolute/`..`/`~` write targets are rejected in impl.py AND test.py) →
   the proposal's own `test.py` is danger- and fs-scope-checked and runs
   in an **isolated subprocess** (temp HOME + temp cwd, no credential env
   vars, the `claude` CLI removed from PATH, timeout) against the DRAFT
   impl → **build verification**: the draft function runs against REAL
   harmless targets (files.* gets temp-dir probes — a present name must
   return the exact path, catching a draft whose own test passes but
   whose impl is wrong; other classes are honestly flagged
   "not-applicable, human review required", never a pretended pass). A
   failure at any step is written into `rationale.md` and the proposal
   never reaches the signature.
2. **Human signature**: a person reviews AND edits the artifacts, signs
   `APPROVED.md`, and only then the gate registers into the real L1 path
   (an existing `friday/l1/<module>.py` or a new module; the planner
   auto-discovers `friday/l1/*.py`), confirms REGISTRY, and re-runs the
   originally-refused goal.

The proof (`gates/CAPABILITY_GAP_PROOF.md`) shows one real primitive
(`files.find_file_exact`) through the full cycle AND a deliberately bad
draft (subprocess.run, signed anyway) blocked by the AST check before the
signature. Bad LLM drafts (observed in a real run: a decorator-source
string masquerading as a contract; an impl ignoring its own argument)
compile yet are wrong — the dead-argument check now catches that class
mechanically, and build-verify closes part of the
"wrong-but-syntactically-clean" gap for files.* primitives (real-target
probes). **2026-08-11 — the first side-effecting primitive:**
`gmail.send_document` was HAND-BUILT (not LLM-drafted — the two prior
drafts for it were the loop's first confabulation, on record in the
proposal's rationale), passed the automated gate (AST clean, sandboxed
test 6/6, build-verify honestly NOT APPLICABLE for gmail — human review
IS the semantic gate for send-capable code), was human-signed, and
registered. Registration surfaced and fixed a real harness bug: an impl
beginning with `from __future__ import annotations` is a SyntaxError
appended at EOF of an existing module, so `register_proposal` now strips
leading future imports (regression-tested). The automated gate catches
structural defects; logically wrong but syntactically clean code in
classes build-verify cannot safely probe still needs the human reviewer.
The dual-human-approval meta-engine remains aspirational.

```sh
./.venv/bin/python -m friday.gap_triage                    # draft unprocessed gaps
./.venv/bin/python -m friday.register_proposal --proposal \
    gates/proposed_primitives/files.do_thing               # automated gate + human signature
./.venv/bin/python -u gates/capability_gap_demo.py          # live proof -> gates/CAPABILITY_GAP_PROOF.md
```

## Lessons loop (rejections → remembered behavior)

The gap loop DRAFTS new primitives; the lessons loop makes rejections
STICK — the missing second half of self-improvement. Without it, a
rejected draft leaves its rejection in one proposal's `rationale.md` and
nothing ever consumes it; the planner fails a schema check and the reason
dies in the L0 log. `friday/lessons.py` closes that:

1. **Record** — every mechanical rejection writes one structured event to
   `var/logs/lessons.jsonl` (best-effort, additive, never breaks the
   caller). Sites: the automated gate (`draft_ast` / `draft_test_fail` /
   `draft_build_verify_fail`), the approval gate's earlier stages
   (`draft_schema` / `draft_impl_syntax`), the digest attribution check
   (`digest_misattribution`), and the planner's retry failures
   (`planner_unparseable` / `planner_schema` /
   `planner_unknown_primitive` / `planner_blocked_primitive` /
   `planner_facts_ref` / `planner_llm_error`). Human-observed categories
   with no mechanical detector (`draft_confabulation` /
   `draft_dead_arg` / `draft_wrapper_dodge`) are recorded via
   `--record`.
2. **Generalize** — a lesson is a CATEGORY, not one event: `generalize()`
   groups events by category and writes a reviewable candidate to
   `gates/proposed_lessons/<category>.md` when a category has ≥2 events
   (idempotent — new evidence extends a candidate, never duplicates
   it).
3. **Human gate** — a lesson is a PROPOSAL until you add it to
   `config/lessons.json`; editing that file IS the approval, same
   philosophy as `APPROVED.md` for primitives. Nothing auto-absorbs — a
   wrong lesson injected everywhere is worse than none.
4. **Inject (bounded)** — approved lessons render as a small
   KNOWN-MISTAKES block (capped at 5) into the prompt for their target:
   the triage drafting prompt, the planner prompt, or the digest prompt.
   The seed lessons in `config/lessons.json` are the verified findings
   earned in Phase B/C: the confabulation pattern (both sides),
   dead-argument impls, allowlist-dodging wrappers, the contract-name
   schema failure, and digest misattribution.

```sh
./.venv/bin/python -m friday.lessons            # generalize: candidates for event clusters
./.venv/bin/python -m friday.lessons --list     # the injected set (approved lessons)
./.venv/bin/python -m friday.lessons --events   # raw recorded events
./.venv/bin/python -m friday.lessons --record --category draft_confabulation \
    --detail "a real observed instance"          # human-observed event
```

Honest limits: a lesson is plain-language prompt guidance — it can stop a
RECOGNIZED failure class from recurring, but it cannot catch a
clean-but-subtly-wrong draft (that remains a human reading problem), and
it shapes the next attempt, it never gates it.

## Goals-proposal stage (Friday proposes what deserves a trigger)

Friday executing goals you hand it is automation; the goals-proposal
stage is the first step toward it proposing work itself. `friday/goal_proposals.py`
mines the failure history and turns recurring FAILED goals into
reviewable, INERT trigger proposals:

1. **Mine** — `tasks.jsonl` records with `gate6_passed: false`, EXCLUDING
   allowlist REFUSED records (a refusal is a deliberate terminal outcome —
   the probes generate them on purpose) and the `ambient-gap-probe-*`
   ids. Goals group by normalized text; a cluster needs ≥2 failed runs
   in the window (default 14 days) to become a candidate — one-off
   proof-run failures are not a pattern.
2. **Dedupe** — a cluster whose goal is already covered by an existing
   trigger in `config/watcher.json` is SKIPPED (normalized substring
   containment OR significant-token overlap ≥0.5 — the gmail-summary
   failures are covered by the enabled morning-gmail-summary trigger even
   though the sender text differs), and a cluster with an existing
   proposal dir is covered (idempotent).
3. **Draft (verbatim goal, inert trigger)** — the goal is the QUOTED
   evidence, never an LLM rewrite (that is the provenance-confabulation
   risk). `trigger.json` is always `enabled: false` with `allow: []` by
   default — NOTHING can run until a human grants scope — and is
   validated through the watcher's real trigger loader. The optional
   `--llm` flag drafts id/schedule/allowlist only; a strict validator
   falls back to deterministic defaults (daily 09:00, mon–fri) on any
   failure. The L0 log contributes WATCH-layer failures for the same
   goal as direct evidence and a global failure-signature summary as
   context.
4. **Human gate** — the rationale carries a prominent "this goal has
   FAILED N times — review why before enabling" warning; approval is
   copying `trigger.json` into `config/watcher.json`, expanding the
   allowlist, and flipping `enabled: true`. Nothing here ever writes the
   config.

The first real run proposed exactly two candidates — the `gate6`
pause-and-close goal (2 failures) and the `retry-stress` mpv goal
(2 failures) — both inert, both waiting on your judgment (watch, fix, or
reject: deleting the proposal dir lets the cluster re-candidate on new
failures).

```sh
./.venv/bin/python -m friday.goal_proposals            # mine + propose
./.venv/bin/python -m friday.goal_proposals --dry-run  # preview, write nothing
./.venv/bin/python -m friday.goal_proposals --llm      # LLM-drafted schedules (cost)
```

## Phase C — cross-project digest (v2, real owned repos)

Friday now reads **across** repos it owns, not just inside a goal you
hand it. The enabled `weekly-cross-project-digest` trigger
(`config/watcher.json`, Sundays 10:00) runs a **deterministic plan** (no
L4 planning call) through the real executor:

1. `git.log(~/Projects/Friday V2)` → verified `checks.list_nonempty`
2. `git.log(~/Projects/vivaha)` → verified `checks.list_nonempty`
3. `git.log(~/Projects/Aether)` → verified `checks.list_nonempty`
4. `files.find_recent_doc(~/Projects/Friday V2)` → verified `checks.file_exists`
5. `files.find_recent_doc(~/Projects/vivaha)` → verified `checks.file_exists`
6. `files.find_recent_doc(~/Projects/Aether)` → verified `checks.file_exists`
7. `files.read_text($steps.4.result)` → verified `checks.text_nonempty`
8. `files.read_text($steps.5.result)` → verified `checks.text_nonempty`
9. `files.read_text($steps.6.result)` → verified `checks.text_nonempty`
10. `dev.digest({labels → the six gathered results})` → verified
    `checks.text_nonempty` — **the one live full-tier LLM call** (~$0.17,
    weekly), the same documented LLM-in-primitive exception as
    `gmail.summarize` (a digest is a terminal read-only artifact)
11. `digestcheck.verify_attribution(digest, per-repo content)` → verified
    `checks.text_nonempty` — **mechanical attribution check**: every
    "X's <mechanism>" claim must appear in X's own gathered content, not
    just anywhere in the combined prompt; unconfirmed claims are flagged,
    never silently delivered as confident
12. `notify.notify_send(body=$steps.11.result)` → verified on the returned
    body — the digest text is DELIVERED to the desktop

The v2 primitives (`git.log`, `files.read_text`, `dev.digest`,
`notify.notify_send`) are unchanged from v1; only the target repos
changed. The v2.2 round added `files.find_recent_doc` (recency-based
status-doc discovery — no hand-maintained note) and
`digestcheck.verify_attribution` (the mechanical attribution check).
`vivaha` + `Aether` were chosen for real recent activity
(pushed 2026-07-18 / 2026-07-13) and because they are Lakshay's own —
v1's defect was pairing Friday with **Agent-Reach**, a third-party repo
he doesn't control, so its suggestions were specific-sounding but not
actionable. Agent-Reach is now dropped entirely. Jarvis is excluded as
dormant; Friday-V3 is excluded this round by design (flagged in
PLAN_STATUS for a dedicated look at its earlier correlation engine —
not mined here); Psyche Space and ChangelogAI remain absent (no GitHub
copy) and excluded pending a separate decision.

The v2.2 proof (`gates/PHASE_C_V2_PROOF.md`) applies **three mechanical
checks** to the real digest — specific-vs-generic (do the suggestions
name mechanisms that verifiably exist in the gathered sources),
targets-owned (no off-scope repo references), and attribution
(every "X's <mechanism>" claim appears in X's own gathered content) —
and the human remains the final judge of whether the suggestions are
worth acting on.

**v2.1 context experiment (2026-08-11):** v2 fed only git log +
boilerplate READMEs (Vivaha's is create-next-app default), so both
suggestions were 0-for-2 under human judgment — S1 was unconnected to
Vivaha's real needs, S2 (`sync.sh`) was a WSL↔Windows shim irrelevant
on CachyOS. The experiment fed **current-priority docs** (Vivaha
roadmap + payment system, Aether devlog) instead of the READMEs:
relevance improved (suggestions touch real roadmap items) but
actionability stays partial — the digest re-attributed the
target repo's own mechanisms as transfers (provenance confabulation),
and true blockers (unimplemented Razorpay, Supabase key rotation,
broken admin verification) live only in Lakshay's head, not in any
repo doc.

**v2.2 — attribution check + recency-based context (2026-08-11):** the
confabulation is a fabrication problem, not a missing-input problem —
the digest asserted something false about Lakshay's own codebase,
confidently, in a suggestion meant to be trusted — so it got a
**mechanical gate**, not a better prompt. `digestcheck.verify_attribution`
runs on every digest before delivery: each "X's <mechanism>" claim is
name-matched against X's own gathered content, and unconfirmed claims
are flagged in the delivered digest, never silently dropped. Context
gathering also switched from hardcoded priority docs to
`files.find_recent_doc` — each repo's most recently modified
status-shaped file (PLAN_STATUS/ROADMAP/DEVLOG/STATUS/TODO/CHANGELOG,
README fallback), no hand-maintained note. The live digest (12/12
VERIFIED through executor AND the real watcher) named two concrete,
attribution-confirmed suggestions — Friday's per-trigger allowlist →
Vivaha's admin dashboard (roadmap Q4), Friday's systemd heartbeat →
Aether's kernel service — and the check reported "All 4 attributed
mechanisms confirmed". Honest limits: the check is name-match only —
a claim with no concrete mechanism is 'not confirmed', never 'false' —
and the true blockers still live only in Lakshay's head.

```sh
./.venv/bin/python -u gates/phase_c_v2_demo.py   # live proof -> gates/PHASE_C_V2_PROOF.md
```

## Gate 1 bring-up (historical runner)

```sh
./.venv/bin/python gates/bringup_gate1.py all   # real side effects: opens Firefox,
                                                # plays audio ~1 min, launches a browser
```

The output is captured to `gates/GATE1_PROOF.md` as the gate's raw proof
artifact. A gate is not green until that artifact shows the DoD lines.
