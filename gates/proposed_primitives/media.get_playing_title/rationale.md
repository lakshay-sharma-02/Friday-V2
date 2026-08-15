The real gap record (2026-08-14T12:30:13+00:00) shows an executor refusal with attempted_primitive: media.get_playing_title, attempted_args_shape: {}, goal_context: "what song is currently playing", and refusal_reason: "'primitive media.get_playing_title has no registered contract; refusing to call it'". This is a genuine capability gap, not an allowlist refusal of an existing primitive: friday/l1/media.py defines is_playing, set_volume, play, play_for, stop, pause, and resume (plus the approved get_volume draft), but NO get_playing_title. An allowlist refusal would block even a registered primitive; a missing-contract refusal means the contract was never registered, which is exactly what happened here.

Friday needs a read-only title query to answer the user's natural goal "what song is currently playing". The existing media.py already drives mpv over its IPC socket at /tmp/friday_mpv.sock via the private _socket_send and _reply_ok helpers, and mpv exposes the current media title as the 'media-title' property - the same get_property mechanism used by is_playing (core-idle) and the approved get_volume (volume). No new external tool, subprocess, or dependency is needed: this reuses the module's own socket infrastructure exactly as is_playing and get_volume do.

The implementation mirrors is_playing and the get_volume draft precisely - both are idempotent reads that return None (not an exception) when no player is reachable, use _socket_send + _reply_ok, and make no state changes. mpv's 'media-title' property returns either an explicit title or a fallback derived from the file name, so the result is meaningful for both tagged tracks and plain audio files. The contract declares no arguments (matching attempted_args_shape: {}), no log_transform (the title string is not secret and has no nested redaction need, consistent with how get_volume logs its integer directly), and raises no FridayError-family exceptions per the contract's failure_mode - this is the correct design because the goal "what song is currently playing" is a best-effort query where absence (no player) should not crash the agent.

## Draft status
- generated: 2026-08-14T12:34:22+00:00
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
- run: 2026-08-14T12:34:29+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; get_playing_title() defined; no dead arguments; @contract decorator present; log_transform (if any) defined; no undeclared bare-builtin raises
- registration: PASS - draft registers the contracted name when imported
- sandbox: PASS - sandbox test run PASSED (exit 0) - ...... ---------------------------------------------------------------------- Ran 6 tests in 0.012s OK
- build-verify: NOT APPLICABLE for module class 'media' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-14T12:34:34+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; get_playing_title() defined; no dead arguments; @contract decorator present; log_transform (if any) defined; no undeclared bare-builtin raises
- registration: PASS - draft registers the contracted name when imported
- sandbox: PASS - sandbox test run PASSED (exit 0) - ...... ---------------------------------------------------------------------- Ran 6 tests in 0.013s OK
- build-verify: NOT APPLICABLE for module class 'media' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-14T14:41:18+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; get_playing_title() defined; no dead arguments; @contract decorator present; log_transform (if any) defined; no undeclared bare-builtin raises
- registration: PASS - draft registers the contracted name when imported
- sandbox: PASS - sandbox test run PASSED (exit 0) - ...... ---------------------------------------------------------------------- Ran 6 tests in 0.012s OK
- build-verify: NOT APPLICABLE for module class 'media' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.
