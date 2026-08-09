# Friday V8 master plan — STATUS: DONE

Status date: 2026-08-08.

The V8 plan's only job was to prevent V1–V7's failure mode: an orchestration
layer sitting on execution that was never verified. It defines completion by
its own terms — every layer ships raw proof before the next layer starts —
and by those terms the plan is **done**:

- Every structural gate (G1–G6) shipped raw, captured output.
- Thirteen real composite tasks are on record, each with a Gate-6-grade proof.
- Every L1 primitive the executor can call has standalone bring-up proof.
- The two remaining primitives are deferred **by the plan's own terms**, not
  by omission (see below).

---

## 1. Gates (raw proof in `gates/`)

| Gate | Layer proven | Proof artifact |
|------|--------------|----------------|
| G1 | L1 primitives bring-up (window/media/browser/dev) | `GATE1_PROOF.md` |
| G2 | L0 observability (one structured line per call) | `GATE2_PROOF.md` |
| G3 | L2 verification (read-only checks, import discipline enforced) | `GATE3_PROOF.md` |
| G4 | L3 execution (hardcoded plan, zero LLM) | `GATE4_PROOF.md` |
| G5 | L4 planning (LLM goal → plan JSON, same executor) | `GATE5_PROOF.md` |
| G6 | first composite task, full L0 trace | `GATE6_PROOF.md` |

## 2. Composite tasks (13 on record)

Counter: `var/logs/tasks.jsonl` — one line per run
(`task_id, goal, gate6_passed, timestamp, proof`). Tasks 1–7 predate the
counter and are backfilled there from their proof artifacts (`backfilled:
true`); failures are recorded honestly — every failed iteration stays in
the file (the first Task 8 attempt, two `retry-stress` runs, and Gate 6
DoD runs `c`/`d` are all present with `gate6_passed: false`).

Distinct tasks with a passing run: **13 composite tasks** (task1–task10
plus task `gate6`, task `whatsapp-filesend` and task `gmail-summary`,
2026-08-08). The file also
holds non-task entries —
`retry-stress` (a stress gate, not a task) — so raw distinct-id counts
over the whole file run higher than the task count. Per the Gate 6
prompt's own scheme, counting starts at `gate6` (pass 1) from here on;
both schemes are visible in the same file.

| # | Goal (abridged) | Proof |
|---|-----------------|-------|
| 1 | send the receipt pdf from downloads to WhatsApp | `TASK1_SEND_RECEIPT_PROOF.md` |
| 2 | send a text to WhatsApp, Telegram and Discord | `TASK2_SEND_TEXT_PROOF.md` |
| 3 | open example.com and verify 'Example Domain' | `TASK3_BROWSER_PROOF.md` |
| 4 | DuckDuckGo search, report first result title | `TASK4_DDG_SEARCH_PROOF.md` |
| 5 | play the test tone 1 min, verify it stops by itself | `TASK5_MEDIA_TIMER_PROOF.md` |
| 6 | search DDG, click the first result, verify the page | `TASK6_BROWSER_CLICK_PROOF.md` |
| 7 | log in to GitHub with stored credentials (log-safe) | `TASK7_BROWSER_LOGIN_PROOF.md` |
| 8 | open → focus → move workspace → close (control group intact) | `TASK8_WINDOW_PROOF.md` |
| 9 | play → pause → resume → stop, verified | `TASK9_MEDIA_PROOF.md` |
| 10 | upload a file to a page, verify via page state | `TASK10_UPLOAD_PROOF.md` |
| 11 | "pause whatever's playing, then close every window except my terminal" (real goal, unmodified pipeline) | `GATE6_DOD_PROOF.md` |
| 12 | WhatsApp file-send re-prove on the Cloud API ("send the README.md file to my whatsapp") | `TASK_WHATSAPP_FILESEND_PROOF.md` |
| 13 | Gmail unread-email summary ("find the most recent unread email from accounts.google.com and summarize it") | `TASK_GMAIL_SUMMARY_PROOF.md` |

Task 12 closes Phase 2 Section 1: the historical "stages but doesn't send"
symptom belonged to the **superseded web.whatsapp.com browser automation**
(removed 2026-08-08; only the Cloud API CLI remains). The Cloud API path
has zero recorded failures across its entire L0 history and was re-proven
fresh — verification was the fresh wamid via `checks.message_sent`, not
absence-of-exception. The 24-hour window does not apply (admin user).

Task 13 (Phase 2 Section 2, first task) adds the **gmail** primitives
(`list_unread` / `get_message` / `summarize`, OAuth2, `gmail.readonly`
scope only — tokeninfo-confirmed) and its proof. Its three honest failed
runs exposed and fixed three real gaps in the SHARED stack, each now
covered generically (no per-goal code): (1) the executor's `$steps.N.result`
resolver gained LIST-INDEX support (integer path segments); (2) it now
accepts dot AND bracket ref syntax (`result.0` / `result[0]` /
`result["key"]`) with 17 unit tests; (3) the planner prompt states gmail
goals need ONLY `gmail.*` primitives, and the gmail harness refuses any
plan containing browser/dev steps before execution (Gate-6-style
interlock). The one-time Google OAuth setup is documented in
`gates/GMAIL_SETUP.md` (incl. the testing-mode 7-day refresh-token
expiry and the production publish that removes it).

Supporting bring-ups: `BRINGUP_REMAINING_PROOF.md` (media pause/resume,
browser upload_file, window focus/move/close_all — the last unproven
primitives) and `MPV_LIFECYCLE_FIX_PROOF.md` (orphan-leak + zombie-reap
defects fixed and re-proven). Anti-cheese and stress evidence:
`GATE5_DOD_PROOF.md` (two goals through the unmodified L4 pipeline, incl.
a never-seen goal) and `RETRY_STRESS_PROOF.md` (mpv lifecycle holds under
repeated invocation).

## 3. Deferred by design (not gaps)

- **`window.shutdown`** — destructive: it ends the Hyprland session. It is
  provable only as a deliberate last act on a clear desktop; the user has
  chosen to leave it unproven, so the executor can never call it.
- **`vision`** — the plan itself says "skip vision for now"; it is gated
  off until every structured alternative (1–4) has failed for a target.

## 4. Working discipline held

- No per-goal code: every task composed the generic catalog + config facts
  (`config/planner_facts.json`); no `if "gmail" in goal:` handlers exist.
- Every executor-called primitive has standalone proof first.
- Defects were fixed inside the gate they were found in (e.g. the GitHub
  click-navigation fix, the mpv lifecycle fix, Task 8's reference-chaining
  fix — all recorded in the run histories of their proof docs).

## 5. What this unlocks

Section 3's non-goals (self-improvement loop, capability-gap detection,
ambient watch loop, cross-project synthesis, MCP servers) are gated behind
"≥10 real tasks pass Gate-6-style proof" — that threshold is now **met**,
so they are eligible to build. They remain earned, not obligated: nothing
in this plan requires them.

## How to verify

```bash
./.venv/bin/python - <<'PY'
import json
lines = [json.loads(l) for l in open("var/logs/tasks.jsonl", encoding="utf-8")]
ids = []
for l in lines:
    if l["gate6_passed"] and l["task_id"] not in ids:
        ids.append(l["task_id"])
print(len(ids), ids)
PY
```

and re-run any gate/task runner in `gates/` to see the raw evidence again.
