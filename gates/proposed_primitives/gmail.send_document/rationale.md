# gmail.send_document - hand-built proposal

Real gap: refusal of `gmail.send_document` (gap_id 18cacf6e171e840d26,
2026-08-11T17:11:13Z, source watcher, trigger_id ambient-gap-probe-email-send,
goal_context "email the newest receipt pdf to myself", refusal_reason trigger
allowlist ['notify.notify_send']). The probe fires daily and the allowlist
refuses the step BEFORE execution - a deliberate, zero-side-effect volume
source for the self-improvement loop.

## Prior drafts - REJECTED, on record

The two LLM drafts for this gap were rejected by the automated gate; this
proposal replaces both:

1. **The confabulated wrapper** (rejected at contract schema 2026-08-11
   17:26 UTC): the draft named its contract `friday.l1.gmail.send_receipt`
   (an invalid qualified name - `register_proposal` requires `<module>.<fn>`)
   and its impl was a wrapper around `friday.l1.gmail.send_document` - a
   function that DOES NOT EXIST. The model fabricated a route around a
   boundary it couldn't satisfy instead of reporting the constraint: exactly
   the confabulation failure mode the lessons loop records
   (`draft_confabulation`).
2. **The broken-schema predecessor** (calendar sandbox ImportError, same
   session): structurally broken imports.

The gate's job was done correctly: both were rejected MECHANICALLY, before
any human time was spent. This is the first side-effecting primitive the
loop has ever produced, so it is deliberately HAND-BUILT (not LLM-drafted)
and reviewed slowly by the human gate.

## This proposal (hand-built)

- primitive: `gmail.send_document(file_path, to=None, subject=None, body=None)`
- Gmail REST API `messages.send` with a base64url MIME multipart message
  (attachment encoded via stdlib `email`), authenticated by the module's
  existing `_access_token()` refresh machinery.
- contract: `at-most-once` (sending is a side effect; retry can duplicate),
  `log_transform=_log_redact_send_meta` keeps the RECIPIENT out of the L0
  log while message_id/filename stay visible - the same mail-metadata
  redaction discipline as `gmail.list_unread`.
- test: hermetic unittest (mocked token + HTTP; real MIME assembly).
- build-verify: NOT APPLICABLE for the gmail module class (no safe real
  target - a live send has real side effects); human review required.

## Scope note (the one deliberate trust decision)

The current refresh token in pass was minted for `gmail.readonly` ONLY.
Sending requires the `gmail.send` scope, which is fixed at consent time -
so the human must re-run the OAuth consent flow with BOTH scopes
(`gates/_gmail_oauth_setup.py --scope "gmail.readonly gmail.send"`) before
the live proof can run. The new token REPLACES the readonly token in pass
and keeps every existing read primitive working. Approving this proposal
expands Friday's gmail surface from read-only to side-effecting.

## Draft status

- generated: 2026-08-11 (hand-written; the LLM drafts it replaces were rejected)
- contract schema: to be validated by the automated gate
- impl: to be AST-checked + sandboxed-test-run by the automated gate
- APPROVAL: PENDING - nothing is registered until the human signs APPROVED.md.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-11T18:28:36+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; send_document() defined; no dead arguments
- sandbox: REJECT - sandbox test run FAILED (exit 1):
FAIL: test_api_error_surfaces_primitive_error (__main__.TestSendDocument.test_api_error_surfaces_primitive_error)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/lakshay/Projects/Friday V2/gates/proposed_primitives/gmail.send_document/test.py", line 83, in test_api_error_surfaces_primitive_error
    self.assertIn("403", str(ctx.exception))
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: '403' not found in 'gmail credentials missing: set GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET and GMAIL_REFRESH_TOKEN, or store them in pass at friday/gmail'

----------------------------------------------------------------------
Ran 6 tests in 0.080s

FAILED (failures=1, errors=2)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-11T18:29:31+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; send_document() defined; no dead arguments
- sandbox: REJECT - sandbox test run FAILED (exit 1):
FAIL: test_api_error_surfaces_primitive_error (__main__.TestSendDocument.test_api_error_surfaces_primitive_error)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/lakshay/Projects/Friday V2/gates/proposed_primitives/gmail.send_document/test.py", line 110, in test_api_error_surfaces_primitive_error
    self.assertIn("403", str(ctx.exception))
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: '403' not found in 'gmail credentials missing: set GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET and GMAIL_REFRESH_TOKEN, or store them in pass at friday/gmail'

----------------------------------------------------------------------
Ran 6 tests in 0.089s

FAILED (failures=1, errors=2)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-11T18:30:03+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; send_document() defined; no dead arguments
- sandbox: REJECT - sandbox test run FAILED (exit 1):
FAIL: test_api_error_surfaces_primitive_error (__main__.TestSendDocument.test_api_error_surfaces_primitive_error)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/lakshay/Projects/Friday V2/gates/proposed_primitives/gmail.send_document/test.py", line 110, in test_api_error_surfaces_primitive_error
    self.assertIn("403", str(ctx.exception))
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: '403' not found in 'gmail credentials missing: set GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET and GMAIL_REFRESH_TOKEN, or store them in pass at friday/gmail'

----------------------------------------------------------------------
Ran 6 tests in 0.080s

FAILED (failures=1, errors=2)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-11T18:30:45+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; send_document() defined; no dead arguments
- sandbox: REJECT - sandbox test run FAILED (exit 1):
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/lakshay/Projects/Friday V2/friday/observability.py", line 276, in wrapper
    result = fn(*args, **kwargs)
  File "/home/lakshay/Projects/Friday V2/gates/proposed_primitives/gmail.send_document/impl.py", line 111, in send_document
    f"gmail send failed ({resp.status_code}): {resp.text[:300]}",
                                               ~~~~~~~~~^^^^^^
TypeError: 'Mock' object is not subscriptable

----------------------------------------------------------------------
Ran 6 tests in 0.073s

FAILED (errors=1)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-11T18:30:57+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; send_document() defined; no dead arguments
- sandbox: PASS - sandbox test run PASSED (exit 0) - ...... ---------------------------------------------------------------------- Ran 6 tests in 0.030s OK
- build-verify: NOT APPLICABLE for module class 'gmail' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-11T18:35:00+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; send_document() defined; no dead arguments
- sandbox: PASS - sandbox test run PASSED (exit 0) - ...... ---------------------------------------------------------------------- Ran 6 tests in 0.039s OK
- build-verify: NOT APPLICABLE for module class 'gmail' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-11T18:36:25+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; send_document() defined; no dead arguments
- sandbox: PASS - sandbox test run PASSED (exit 0) - ...... ---------------------------------------------------------------------- Ran 6 tests in 0.239s OK
- build-verify: NOT APPLICABLE for module class 'gmail' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.
