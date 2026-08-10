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

**Status: DONE + hardened + live-verified** (2026-08-10) — every
structural gate G1–G6 shipped raw, captured output; **13 composite tasks**
plus **7 live-automation records** (watch/e2e) are on record in
`var/logs/tasks.jsonl`; every executor-callable L1 primitive has
standalone bring-up proof; the core is hardened (blocked primitives,
protected windows, dangerous-dev gate); a **217-test unit suite** covers
every layer; and a **live end-to-end check** runs the real stack against
this machine's real state — including a real gmail summary through the
ambient watch loop. The two remaining primitives (`window.shutdown`,
`vision`) are deferred **by the plan's own terms**, not by omission. Full
completion record: `gates/PLAN_STATUS.md`.

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
    dev.py          claude -p subprocess (bypass is explicit opt-in)
    files.py        deterministic file discovery (find_file by name)
    gmail.py        Gmail REST API, OAuth2 read-only (list_unread /
                    get_message / summarize; scope gmail.readonly only)
    notify.py       desktop notifications (notify-send) - the watch loop's
                    feedback channel
    telegram.py     Telegram Bot API (send_text / send_document)
    discord.py      Discord Bot API (send_text / send_file)
  watcher.py        ambient watch loop (config/ triggers -> goals -> tasks.jsonl)
tests/               dependency-free unittest suite (217 tests, all mocked)
  l2/
    checks.py       L2 verification: read-only checks (catalog below)
  l3/
    executor.py     L3 deterministic state machine over a plan
  l4/
    planner.py      L4 LLM planning (goal -> plan JSON, schema-validated)
gates/               every gate/task runner + its raw proof artifact
assets/test_tone.mp3  deterministic audio fixture (70s 440Hz)
config/planner_facts.json  editable PROJECT FACTS for the planner
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
| `media` | `play`, `play_for`, `pause`, `resume`, `stop`, `set_volume`, `is_playing` (read) |
| `browser` | `goto`, `read_page_text`, `find_locator`, `click`, `type_text`, `press_key`, `upload_file`, `login`, `credentials` (returns secret — result redacted in the log), `close` |
| `dev` | `run` (claude -p), `run_shell` — **arbitrary shell, requires `FRIDAY_ALLOW_DANGEROUS=1`** (checked before claude runs) |
| `files` | `find_file(name, directory, recursive)` |
| `notify` | `notify_send(title, body, timeout_ms)` — desktop notification |
| `gmail` | `list_unread(sender, max_results)`, `get_message(message_id)`, `summarize(message_id)` — OAuth2, `gmail.readonly` only, auto token refresh; one-time setup in `gates/GMAIL_SETUP.md` |
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
the watch loop (incl. the per-trigger primitive allowlist), and the
browser locator chain. Every side-effect boundary is mocked — the suite
never sends, launches, clicks, or touches the compositor.

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
with `backfilled: true`. Current distinct passing ids: **21** — the **13
composite tasks** (task1–task10 + `gate6` + `whatsapp-filesend` +
`gmail-summary`), the `retry-stress` gate, and **7 live-automation
records**: the watcher demos (`watch:demo-time`, `watch:demo-file`), the
live E2E goals (`e2e:files`, `e2e:media`, `e2e:windows`, `e2e:gmail`)
and the real watcher trigger `watch:morning-gmail-summary` (a live gmail
summary via `$facts.gmail_sender`). Per the Gate 6 prompt's scheme,
counting starts at `gate6` from here on.

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
| `TESTS_PROOF.md` | The dependency-free unit suite, raw output (regenerated by `gates/test_suite.py`; 217 tests) |
| `WATCHER_PROOF.md` | Watch loop first proof: time + file triggers fire deterministic plans through the real watcher (no LLM, no side effects), recorded in tasks.jsonl, notified |
| `WATCHER_GMAIL_PROOF.md` | The enabled `morning-gmail-summary` trigger runs a REAL gmail summary through the unmodified watcher (`$facts.gmail_sender`, `allow: ["gmail.*"]`, live LLM plan, verified) |
| `E2E_PROOF.md` | Live end-to-end: 4 goals (files/windows/media/gmail) through the real stack with live LLM plans, allowlist refusal, redacted proof |

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
edited in `config/planner_facts.json`, never hardcoded in the trigger:

```json
{ "id": "morning-gmail-summary",
  "goal": "find the most recent unread email from $facts.gmail_sender and
    summarize it in at most 5 plain sentences",
  "schedule": {"type": "time", "at": "09:00", "days": ["mon","tue","wed","thu","fri"]},
  "enabled": true, "allow": ["gmail.*"] }
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

## Gate 1 bring-up (historical runner)

```sh
./.venv/bin/python gates/bringup_gate1.py all   # real side effects: opens Firefox,
                                                # plays audio ~1 min, launches a browser
```

The output is captured to `gates/GATE1_PROOF.md` as the gate's raw proof
artifact. A gate is not green until that artifact shows the DoD lines.
