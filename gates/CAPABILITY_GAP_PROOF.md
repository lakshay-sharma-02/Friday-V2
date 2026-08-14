# CAPABILITY_GAP_PROOF - the FULL self-improvement loop, end to end

Status date: 2026-08-10T18:36:27+00:00.

gap -> structured record -> triage -> automated gate (AST + sandbox)
-> human approval -> registration -> re-run-passes. All machinery is
the REAL shipped stack; only the triggering plan is hand-written (the
same convention WATCHER_PROOF uses for deterministic plans), so the
proof is reproducible. Registration is idempotent - re-running the
demo is a no-op on the registered function.

## 1. The refusal (real L3 executor)

```
plan aborted at step 1: "primitive 'files.do_thing' has no registered contract; refusing to call it"
```

`files.do_thing` is a real module with an unregistered function -
`_resolve_primitive` refuses it (`no registered contract`) and the plan
ABORTs exactly as it did before the gap loop existed; the gap record is
additive, never a behavior change.

## 2. The structured capability-gap record

```
{
  "gap_id": "18ca857fd9b0934e29",
  "timestamp": "2026-08-10T18:36:26.365409+00:00",
  "source": "executor",
  "attempted_primitive": "files.do_thing",
  "attempted_args_shape": {
    "name": "str:1",
    "recursive": "bool"
  },
  "goal_context": "locate the missing artifact and report it",
  "refusal_reason": "\"primitive 'files.do_thing' has no registered contract; refusing to call it\"",
  "goal_id": "locate the missing artifact and report it"
}
```

One record per refusal: source, goal_context, attempted_primitive,
attempted_args_shape (type tags only - no values, so secrets and mail
metadata never ride a gap record), and the refusal_reason.

## 3. Triage + human-gate correction

```
files.do_thing: already drafted (gates/proposed_primitives/files.do_thing), gaps consumed
```

Artifacts: `gates/proposed_primitives/files.do_thing/` (contract.json,
impl.py, test.py, rationale.md, APPROVED.md)

The RAW LLM draft for this gap was REJECTED by the human gate - its
defects are documented in APPROVED.md: the contract was emitted as a
Python decorator-source string instead of a JSON object, and the impl
ignored its own `name` argument. The human-corrected proposal is
`files.find_file_exact` - an EXACT (case-insensitive) filename match
returning '' when absent, genuinely distinct from find_file's substring
semantics. This rejection-and-correction IS the gate working.

## 4. The automated gate (AST + sandboxed tests) + the human signature

```
automated gate (AST + sandbox):
  AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; find_file_exact() defined; no dead arguments
  sandbox: PASS - sandbox test run PASSED (exit 0) - .... ---------------------------------------------------------------------- Ran 4 tests in 0.004s OK
  build-verify: PASS - files.* real-target probes: present name -> exact path, absent -> str, bad directory -> FridayError handled
registered files.find_file_exact: files.find_file_exact already registered in /home/lakshay/Projects/Friday V2/friday/l1/files.py (no-op)
registry check: present
```

Gate order: contract schema (plain JSON object, real Contract fields,
idempotency enum) -> impl compiles -> AST checks (imports limited to
what shipped L1 primitives import; no exec/eval/subprocess/os-system
calls; no sandbox-escaping file writes - absolute/.. /~ targets
rejected in impl.py AND test.py; the contracted function defined; no
dead arguments) -> the proposal's own test.py runs in an isolated
subprocess (temp HOME + temp cwd, no credentials, no claude CLI on
PATH, timeout) against the DRAFT impl -> BUILD VERIFY (files.* runs
the draft against REAL temp-dir targets - present name must return
the exact path; other classes are honestly flagged not-applicable)
-> APPROVED.md signature -> register into friday/l1/files.py ->
REGISTRY presence check.
Nothing is registered without the human signature AND a clean automated
gate; a rejected draft changes nothing about the running agent.

## 5. A deliberately BAD draft is blocked before any human review

The demo signs a proposal whose impl calls subprocess.run and asks the
gate to register it. The AST check refuses BEFORE the signature step -
the sandbox is skipped (a rejected draft is never executed) and the
primitive is not registered:

```
REJECTED by the automated gate - never reached the human signature:
automated gate (AST + sandbox):
  AST REJECT: calls subprocess.run() - dangerous/arbitrary execution
  sandbox: SKIPPED - the draft was rejected at AST, so its test was not executed
```

This is the exact class of defect the previous round's human caught
by hand (an impl doing something the executor would treat as
dangerous) now caught mechanically - a person paying attention
became a system property.

## 6. Build-verify catches a draft whose OWN test passes

The draft above is signed anyway, and its self-authored test is NOT
a lie - it passes (the impl does return a str). But the impl returns
the bare NAME, never looking at the target directory. The test-only
gate would have let it through to a human; the build stage runs the
draft against a REAL temp-dir target and demands the exact path:

```
REJECTED by the automated gate - never reached the human signature:
automated gate (AST + sandbox):
  AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; find_file_exact() defined; no dead arguments
  sandbox: PASS - sandbox test run PASSED (exit 0) - . ---------------------------------------------------------------------- Ran 1 test in 0.001s OK
  build-verify: REJECT - PROBE_FAIL 0 expected path '/tmp/friday_buildverify_n4cjzetn/report.pdf', got 'report.pdf' (str)
```

The self-test passing is not the only check - a draft whose author
wrote its own test to trivially pass is caught here, before the
human signature, and nothing is registered (files.py is byte-
identical after both rejected drafts).

## 7. The goal re-run (now completes instead of refusing)

```
plan status: COMPLETED
  step 1: files.find_file_exact    VERIFIED
```

The original goal - 'locate the missing artifact and report it' - now
runs with the approved primitive (files.find_file_exact on README.md)
and completes with every step VERIFIED. The planner catalog auto-
discovers friday/l1/*.py, so the new primitive is also LLM-planable
with no source edit.

## 8. Draft quality is a KNOWN LIMIT

The automated gate catches STRUCTURAL defects mechanically: imports
outside the derived L1 allowlist, exec/eval/subprocess/os-system
calls, a missing contracted function, dead arguments, and a failing
or non-hermetic sandboxed test. It CANNOT catch logically wrong but
syntactically clean code - a draft that uses all its arguments and
passes its own test can still encode a wrong design. That is what
the human signature is still for: the automated gate narrows what
the human must review to intent and design, not syntax. The sandbox
is env-level, not OS-level: it strips credentials, redirects HOME
and cwd to a temp dir, removes the claude CLI from PATH, and rejects
absolute/.. /~ file writes statically - but network egress and file
reads of local paths are NOT hard-blocked (documented limits; full
seccomp/containerization remains aspirational). Build-verify
closes part of the 'wrong but clean' gap for files.* (real temp-dir
targets), but other module classes have NO safe real target this
session and are HONESTLY flagged 'build-verification not applicable,
human review required' - never a pretended pass.

## Verdict

FULL CYCLE PROVEN -
refusal, record, triage, automated gate (AST + sandbox + build-
verify), human approval, registration and re-run all through the
real stack; an AST-bad draft and a test-passing-but-wrong draft are
both blocked without a human having to spot them.

