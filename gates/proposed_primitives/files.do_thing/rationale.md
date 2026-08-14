# files.find_file_exact — proposal rationale (human-corrected, APPROVED)

Driven by the real refused goal:

> "locate the missing artifact and report it"

The recorded refusals (gap_ids 18ca581d7f2b0f2a29, 18ca582f77a351d829,
18ca58326015f70b29, plus the demo re-runs since) all attempted the
primitive `files.do_thing` with arg shape `{name: str:1, recursive: bool}`
and were refused with: "primitive 'files.do_thing' has no registered
contract; refusing to call it".

## What the RAW LLM draft proposed — and why it was REJECTED

The LLM's draft was rejected at the human gate, defects on record in
APPROVED.md:

- `contract.json` was emitted as a Python `@contract(...)` decorator-source
  string instead of a plain JSON Contract object;
- the impl ignored its own `name` argument and hardcoded the literal
  filename 'artifact';
- its semantics duplicated `files.find_file`'s substring search.

Nothing from the raw draft was registered — the rejection-and-correction
IS the gate working.

## The corrected proposal

`files.find_file_exact(name, directory) -> str`:

- EXACT (case-insensitive) filename match — genuinely distinct from
  `find_file`'s substring semantics.
- Returns `''` when no file matches exactly: an absent file is a RESULT,
  never an exception — an exact-match probe a plan can branch on.
- Read-only and idempotent (safe to retry by contract).
- Impl lives in the existing `friday/l1/files.py` (reuses its `_anchor` /
  `PROJECT_ROOT` / `PreconditionError` helpers) — no new module needed.
- Hermetic stdlib unittest over temp dirs.

## Status

- APPROVED by the human gate on 2026-08-10 (signature in APPROVED.md).
- Registered through the minimal approval gate (friday/register_proposal.py):
  contract schema validated against friday/contracts.py → impl compiles +
  defines the function → appended to friday/l1/files.py → present in
  REGISTRY.
- The original goal was re-run with the approved primitive and now
  COMPLETES with every step VERIFIED instead of refusing
  (gates/CAPABILITY_GAP_PROOF.md).
- Registration is idempotent — re-running the gate is a no-op.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-10T17:42:53+00:00
- AST checks: passed - imports allowed; no dangerous calls; find_file_exact() defined; no dead arguments
- sandbox: PASS - sandbox test run PASSED (exit 0) - .... ---------------------------------------------------------------------- Ran 4 tests in 0.006s OK

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-10T17:45:44+00:00
- AST checks: passed - imports allowed; no dangerous calls; find_file_exact() defined; no dead arguments
- test.py AST REJECT: imports 'tempfile' - top-level 'tempfile' is not in the derived L1 import allowlist
- test.py AST REJECT: imports 'unittest' - top-level 'unittest' is not in the derived L1 import allowlist
- sandbox: SKIPPED - the test file itself was rejected at AST

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-10T17:46:41+00:00
- AST checks: passed - imports allowed; no dangerous calls; find_file_exact() defined; no dead arguments
- sandbox: PASS - sandbox test run PASSED (exit 0) - .... ---------------------------------------------------------------------- Ran 4 tests in 0.006s OK

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-10T18:09:51+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; find_file_exact() defined; no dead arguments
- sandbox: PASS - sandbox test run PASSED (exit 0) - .... ---------------------------------------------------------------------- Ran 4 tests in 0.005s OK

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-10T18:36:26+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; find_file_exact() defined; no dead arguments
- sandbox: PASS - sandbox test run PASSED (exit 0) - .... ---------------------------------------------------------------------- Ran 4 tests in 0.004s OK
- build-verify: PASS - files.* real-target probes: present name -> exact path, absent -> str, bad directory -> FridayError handled

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.
