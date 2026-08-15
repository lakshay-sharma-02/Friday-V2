## Why Friday needs `clipboard.write_text`

The real gap record shows the running desktop-automation agent tried to satisfy the goal **"copy the summary text to my clipboard"** by calling `clipboard.write_text` with args `{text: str:6}`, and was refused:

> `'primitive clipboard.write_text has no registered contract; refusing to call it'`

The agent needs to put text onto the user's clipboard (the natural write counterpart to the already-registered `clipboard.read_text`). The primitive simply does not exist in `friday/l1/`, so the executor refuses it before any work happens. This is a genuinely missing primitive, **not** an allowlist refusal of something that already exists - the fix is to draft and register it.

## Design

- **Idempotent**: writing the same `text` repeatedly converges the clipboard to that value; retries are harmless.
- **Bounded subprocess, read-or-write**: writes shell out to `wl-copy` (Wayland) or `xclip -selection clipboard` (X11) - the only way to mutate the Linux clipboard - through the gate's exact `subprocess.run([<literal list>], capture_output=True, text=True, timeout=5)` shape. Text is piped via stdin (`input=`), never a shell string.
- **Failure class**: `PrimitiveError` on a missing tool or non-zero exit (distinct from a successful empty-string write), so the executor's FridayError-keyed retry policy classifies it correctly - no bare `RuntimeError`.
- **No log_transform / no redaction extras** declared; the contract is exactly the 6 `Contract` fields, so there is no undefined function to trip the import.

Both fallbacks (wl-copy and xclip) are implemented exactly as the contract claims, and the test mocks `subprocess.run` (no real compositor, no `__import__`, no `exec`) to verify both platform paths, the tool-failure path, and the missing-tool path all raise `PrimitiveError`.

## Draft status
- generated: 2026-08-14T15:25:59+00:00
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
- run: 2026-08-14T15:26:22+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; write_text() defined; no dead arguments; @contract decorator present; log_transform (if any) defined; no undeclared bare-builtin raises
- registration: PASS - draft registers the contracted name when imported
- sandbox: PASS - sandbox test run PASSED (exit 0) - .... ---------------------------------------------------------------------- Ran 4 tests in 0.012s OK
- build-verify: NOT APPLICABLE for module class 'clipboard' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-14T15:26:46+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; write_text() defined; no dead arguments; @contract decorator present; log_transform (if any) defined; no undeclared bare-builtin raises
- registration: PASS - draft registers the contracted name when imported
- sandbox: PASS - sandbox test run PASSED (exit 0) - .... ---------------------------------------------------------------------- Ran 4 tests in 0.011s OK
- build-verify: NOT APPLICABLE for module class 'clipboard' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.
