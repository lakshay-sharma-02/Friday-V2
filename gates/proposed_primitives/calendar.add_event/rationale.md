The gap record shows a refusal for `calendar.add_event` when the user asked to 'add a meeting to my calendar tomorrow at 2pm for 1 hour'. The attempted args_shape was `{summary: str:6, start: str:6, end: str:6}` and the refusal_reason was `'primitive calendar.add_event has no registered contract; refusing to call it'`. Looking at `friday/l1/calendar.py`, only `list_upcoming` exists - there is no `add_event` primitive. This is a missing write-capability for calendar operations. The contract declares `calendar.events` scope requirement; users must run `gates/_calendar_oauth_setup.py --scope 'https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/calendar.events'` to enable write access (the current readonly token would return 403 on write attempts).

## Draft status
- generated: 2026-08-14T14:35:55+00:00
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
- run: 2026-08-14T14:36:11+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; add_event() defined; no dead arguments; @contract decorator present; log_transform (if any) defined; no undeclared bare-builtin raises
- registration: PASS - draft registers the contracted name when imported
- sandbox: PASS - sandbox test run PASSED (exit 0)
- build-verify: NOT APPLICABLE for module class 'calendar' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-14T14:36:51+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; add_event() defined; no dead arguments; @contract decorator present; log_transform (if any) defined; no undeclared bare-builtin raises
- registration: PASS - draft registers the contracted name when imported
- sandbox: PASS - sandbox test run PASSED (exit 0)
- build-verify: NOT APPLICABLE for module class 'calendar' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-14T14:37:09+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; add_event() defined; no dead arguments; @contract decorator present; log_transform (if any) defined; no undeclared bare-builtin raises
- registration: PASS - draft registers the contracted name when imported
- sandbox: PASS - sandbox test run PASSED (exit 0)
- build-verify: NOT APPLICABLE for module class 'calendar' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.
