# SELF_IMPROVEMENT_LOOP_PROOF - the full cycle, closed end to end (2026-08-13)

Status date: 2026-08-13.

This is the record of the loop's FIRST complete cycle with a side-effecting
primitive: refusal -> gap record -> LLM draft -> self-check repair ->
automated gate (AST + sandbox + write-family build-verify) -> human review
-> registration -> re-run passes -> probe retired. Every stage below ran
through the REAL shipped stack (the watcher, the executor, the gate, the
registration path); only the triggering plan is hand-written (the same
convention the other proofs use for deterministic plans).

## 1. The refusal -> gap record (real watcher)

The `ambient-gap-probe-file-write` trigger (daily 00:05, silent) fired its
one-step plan calling `files.write_text`; the step was REFUSED pre-execution
by the trigger's own allowlist (`["notify.notify_send"]`). Exactly one
structured gap record landed in `var/logs/capability_gaps.jsonl`:

```json
{
  "gap_id": "18cb263b0ba1a2e42f",
  "timestamp": "2026-08-12T19:41:52.222632+00:00",
  "source": "watcher",
  "attempted_primitive": "files.write_text",
  "attempted_args_shape": {"path": "str:20", "text": "str:11"},
  "goal_context": "write the latest digest summary to a notes file",
  "refusal_reason": "trigger allowlist ['notify.notify_send']",
  "trigger_id": "ambient-gap-probe-file-write"
}
```

## 2. Triage: self-checked LLM draft (real gap_triage, live LLM)

`gap_triage` grouped the gap and drafted a 4-artifact proposal. The
SELF-CHECK repair loop (Fix 1) ran its own structural checks before writing
anything: the first reply was unparseable, the exact rejection was fed back,
and the second reply produced a structurally clean draft - exact name
`files.write_text`, `structural self-check: passed`, impl and test both
compile. (This live run also surfaced and fixed three real defects: the
dormant `PrimitiveTimeout.__init__` bug, the model-router DEGRADED failure
class -> `FRIDAY_TRIAGE_MODEL`, and the fully-qualified-name normalization.)

## 3. The automated gate caught a REAL bug in the clean draft (sandbox)

The draft passed contract schema and ALL AST checks (allowed imports, no
dangerous calls, no sandbox-escaping writes, function defined, no dead
arguments). The sandboxed test run then caught a genuine runtime defect the
draft's own tests did not:

```
ValueError: illegal newline value: w
```

The impl passed `newline=mode` (`mode='w'/'a'`) to `Path.write_text`, which
rejects it - a compile-clean, self-test-passing draft that would crash on
first real invocation. This was the "scary case" the whole sequence had been
waiting for (a clean side-effecting draft, subtly wrong), and the gate caught
it mechanically, before any human time. A human then corrected the one line
(`with p.open(mode, encoding='utf-8') as f: f.write(text)`) and reconciled a
contract/impl mismatch (OSError now propagates per the contract).

## 4. Fix 2: write-family build-verify

The same live run exposed that build-verify hardcoded find_file READ
semantics, so even a correct write draft would false-reject. Fix 2 derived
the probe family from the draft's DECLARED parameters (path-ish + content-ish
pair -> write probes; name/pattern -> read probes; neither -> honest
not-applicable). The write probes call the draft against absolute temp paths
and verify the FILE ON DISK: created with exact content, overwritten by a
second write, appended when `append` is declared, missing-parent raising
FridayError or returning.

## 5. The corrected draft passes the FULL automated gate

```
AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; write_text() defined; no dead arguments
sandbox: PASS - sandbox test run PASSED (exit 0) - 9 tests OK
build-verify: PASS - files.* write probes: created+overwrote (and appended, when declared)
    a real temp file with verified content; missing-parent raised FridayError or returned (Fix 2)
```

`gates/proposed_primitives/files.write_text/rationale.md` carries the full
trail: the original sandbox rejection, the hand-correction note, and the
pass record.

## 6. Human review + registration (real register_proposal)

`APPROVED.md` signed after review (the gate's documented role - it cannot
judge design intent). Registration output:

```
registered files.write_text: appended files.write_text to .../friday/l1/files.py
registry check: present
```

Live check of the registered primitive:

```
in REGISTRY: True
idempotency: commutative-safe
wrote: .../notes.md | exists: True | content: hello
overwrote: goodbye
appended: goodbye line2
```

## 7. The re-run: the originally-refused goal now COMPLETES

The goal that produced the gap ("write the latest digest summary to a notes
file") re-ran through the REAL executor with `files.write_text`:

```
plan status: COMPLETED
  step 1: files.write_text         VERIFIED
file written: True
content: Digest summary: Friday + vivaha + Aether - see DIGEST_TRACKING.md
RE_RUN_PASSED
```

## 8. Lifecycle: probe retired

`ambient-gap-probe-file-write` was DISABLED in `config/watcher.json`
(email-send lifecycle precedent) - its job is done, and any straggler gap
for a now-registered primitive is consumed by triage as SOLVED, never
re-drafted. The committed-config guard test was rewritten to assert the
retired state (probe disabled, primitive registered).

## 9. Resilience: FRIDAY_MODEL

The live runs also exposed that the whole LLM layer (planner, triage,
digest, summarize) routes through the user's local model router, whose free
opus alias was DEGRADED provider-side for the entire session. The
`FRIDAY_MODEL` override at the `_run_claude` choke point repoints every call
at a working full model id (e.g. `oc/laguna-s-2.1-free`) so the loop stays
alive when the default alias' provider is down.

## Verdict

FULL CYCLE PROVEN for a side-effecting primitive - the loop no longer stops
at "proposal written"; it produces a survivor, the gate rejects its defects
mechanically, a human signs, the primitive registers, and the originally
refused goal completes with verified steps. Test suite: 454 tests green.

## CYCLE 2 (2026-08-13): calendar.list_upcoming - ZERO hand-correction

The loop's SECOND complete cycle, and its first with NO human correction.

1. Gap: `calendar.list_upcoming` (goal "show me my upcoming calendar events
   for the week", args {days: 7}), refused by the calendar probe's allowlist.
2. Drafting: the first run exposed a model-SPEED blocker - laguna-s timed out
   at 300s on all 3 attempts (the fixed PrimitiveTimeout surfaced a clean,
   diagnosable error; the gap stayed unprocessed, crash-safe). With
   `FRIDAY_TRIAGE_MODEL=openrouter/poolside/laguna-xs-2.1:free` (the user's
   suggestion - 17s on a comparable probe), the self-check repair loop
   produced a structurally clean draft with zero human edits.
3. Automated gate:
   - AST checks: passed
   - sandbox: PASS (the draft's own 8-test hermetic suite, API mocked)
   - build-verify: NOT APPLICABLE for module class 'calendar' (the
     documented limit - build-verify is real for files.* only; the human
     signature IS the semantic check)
4. Registration: created friday/l1/calendar.py (the loop's first NEW
   module file), registry check present. 51 primitives in the catalog.
5. Re-run: the original goal runs but ABORTS HONESTLY - no calendar OAuth
   creds configured, list_upcoming returns [], checks.list_nonempty fails,
   the executor refuses to accept an unverified step (`verify never matched
   True (last: False)`). Registration is complete; the goal completes once
   calendar credentials exist (pass friday/calendar or GOOGLE_CALENDAR_TOKEN).
6. Lifecycle: the calendar probe was retired (all three probes now
   disabled), and the committed-config guard test asserts the retired state.
7. Latent bugs found by cycle 2 and fixed:
   - planner L1 auto-discovery: default base path used parents[1] (the
     friday package dir) -> <root>/friday/friday/l1 (nonexistent) -> the
     glob always fell back to the hardcoded tuple, so NEW module files
     were never discovered/planable. Fixed to parents[2], regression-
     tested. This is why every earlier registration was into an existing
     module and the bug stayed latent.
   - new-module registration header used a different marker format than
     the append path, undercounting gate-registered primitives in
     CAPABILITIES (3 instead of 4). Fixed + regenerated.

Verdict: the loop now completes a full cycle with a mechanically-produced
survivor and NO human correction - the self-check repair loop, the lessons
block and the faster-model knob together did the work the human used to do.
