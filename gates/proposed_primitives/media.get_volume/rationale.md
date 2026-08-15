The gap record shows a real executor refusal: attempted_primitive: media.get_volume, attempted_args_shape: {}, goal_context: "what is the current media volume level". The refusal_reason — "primitive media.get_volume has no registered contract; refusing to call it" — confirms this primitive does not exist: friday/l1/media.py defines set_volume, play, play_for, stop, pause, resume, and is_playing, but no get_volume. This is a genuine capability gap, not an allowlist refusal of an existing primitive (an allowlist would block even a registered primitive; a missing-contract refusal means the contract was never registered). Friday needs a read-only volume query to answer the user's natural goal "what is the current media volume level" — set_volume writes but never reads, and _socket_send is private, so no existing primitive serves this. The implementation reuses the module's own _socket_send and _reply_ok helpers (already mocked in the existing test suite, so coverage is consistent), raises no exceptions per the contract, and returns None for every failure path so a missing mpv instance is reported as absence rather than a crash. log_transform is omitted: the volume integer is not secret, and there is no nested redaction need — logging it directly is consistent with how set_volume is logged. The precondition/postcondition shape mirrors is_playing (the closest analog: both reads, both idempotent, both return early/None when no player exists).

## Draft status
- generated: 2026-08-14T12:16:25+00:00
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
- run: 2026-08-14T12:16:30+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; get_volume() defined; no dead arguments; @contract decorator present; log_transform (if any) defined; no undeclared bare-builtin raises
- registration: PASS - draft registers the contracted name when imported
- sandbox: PASS - sandbox test run PASSED (exit 0) - ........ ---------------------------------------------------------------------- Ran 8 tests in 0.018s OK
- build-verify: NOT APPLICABLE for module class 'media' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-14T12:16:36+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; get_volume() defined; no dead arguments; @contract decorator present; log_transform (if any) defined; no undeclared bare-builtin raises
- registration: PASS - draft registers the contracted name when imported
- sandbox: PASS - sandbox test run PASSED (exit 0) - ........ ---------------------------------------------------------------------- Ran 8 tests in 0.017s OK
- build-verify: NOT APPLICABLE for module class 'media' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-14T14:41:17+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; get_volume() defined; no dead arguments; @contract decorator present; log_transform (if any) defined; no undeclared bare-builtin raises
- registration: PASS - draft registers the contracted name when imported
- sandbox: PASS - sandbox test run PASSED (exit 0) - ........ ---------------------------------------------------------------------- Ran 8 tests in 0.017s OK
- build-verify: NOT APPLICABLE for module class 'media' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.
