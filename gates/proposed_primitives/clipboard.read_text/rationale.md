The gap record shows a refusal of clipboard.read_text due to the allowlist notify.notify_send, indicating the primitive does not exist in friday/l1. This primitive is needed so the desktop‑automation agent can read clipboard text without triggering the allowlist. It provides a safe, idempotent way to retrieve clipboard content using only stdlib and a subprocess call to wl-paste, matching the contract schema.

## Draft status
- generated: 2026-08-14T04:34:30+00:00
- structural self-check: passed
- impl compiles: yes
- test compiles: yes
- driving gap records: 1
- APPROVAL: PENDING - this is a DRAFT; nothing is registered. To
  register, run friday/register_proposal.py on this dir: the
  AUTOMATED gate (AST checks + sandboxed test run) runs first and
  rejects structural defects without a human; only then does your
  APPROVED.md signature authorize registration into friday/l1/.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-14T04:35:03+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; read_text() defined; no dead arguments
- test.py AST REJECT: calls subprocess.CompletedProcess() - dangerous/arbitrary execution
- test.py AST REJECT: calls subprocess.CompletedProcess() - dangerous/arbitrary execution
- sandbox: SKIPPED - the test file itself was rejected at AST

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Human review (2026-08-14) - hand-corrected before re-gating

The LLM draft passed the structural self-check but was NOT registerable:

1. **Missing @contract(...) decorator** - registration writes impl.py as-is
   into friday/l1/; without the decorator the primitive never enters the
   REGISTRY and the executor keeps refusing it.
2. **contract.json declared log_transform="_log_redact_clipboard_meta"**
   but impl.py never defined that function - NameError at import time.
3. **Test defects**: imported `friday.clipboard` (no l1 segment - the
   module will be friday/l1/clipboard.py) and built its mock return via
   `subprocess.CompletedProcess(...)`, which the gate's test.py AST check
   rejects; the shipped convention is `mock.Mock(returncode=..., stdout=...)`.
4. **Bare RuntimeError** instead of PrimitiveError (the contract's own
   failure_mode), so the executor's FridayError-derived retry policy
   would not see it.
5. **wl-paste only, no xclip fallback** despite the contract claiming
   "wl-paste or xclip".

All five corrected by hand; re-gated below.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-14T04:36:40+00:00
- AST REJECT: calls subprocess.run() - dangerous/arbitrary execution
- sandbox: SKIPPED - the draft was rejected at AST, so its test was not executed

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-14T04:37:06+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; read_text() defined; no dead arguments
- test.py AST REJECT: calls __import__() - arbitrary-execution builtin
- sandbox: SKIPPED - the test file itself was rejected at AST

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-14T04:37:28+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; read_text() defined; no dead arguments
- test.py AST REJECT: calls subprocess.TimeoutExpired() - dangerous/arbitrary execution
- sandbox: SKIPPED - the test file itself was rejected at AST

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-14T04:38:04+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; read_text() defined; no dead arguments
- sandbox: PASS - sandbox test run PASSED (exit 0) - ......... ---------------------------------------------------------------------- Ran 9 tests in 0.010s OK
- build-verify: NOT APPLICABLE for module class 'clipboard' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-14T04:38:10+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; read_text() defined; no dead arguments
- sandbox: PASS - sandbox test run PASSED (exit 0) - ......... ---------------------------------------------------------------------- Ran 9 tests in 0.009s OK
- build-verify: NOT APPLICABLE for module class 'clipboard' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-14T04:38:28+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; read_text() defined; no dead arguments
- sandbox: PASS - sandbox test run PASSED (exit 0) - ......... ---------------------------------------------------------------------- Ran 9 tests in 0.012s OK
- build-verify: NOT APPLICABLE for module class 'clipboard' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.
