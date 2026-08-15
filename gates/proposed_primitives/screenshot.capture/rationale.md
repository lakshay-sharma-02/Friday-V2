# screenshot.capture - proposal rationale

**Requested by the human (2026-08-15)**: "it should be able to send me
screenshots on whatsapp/telegram/discord - send screenshot of what's on
the terminal or send the browser screen."

## Why Friday needs this

The SEND half already exists: `whatsapp.send_document`,
`telegram.send_document` and `discord.send_file` ship any file to the
user's platforms. The missing half is CAPTURE: nothing in L1 can turn
"what's on the terminal" into a PNG path for a send primitive to attach.
A goal like "send a screenshot of my terminal to whatsapp" was therefore
impossible even though every step except the capture exists.

## The primitive

`screenshot.capture(target, output_path)`:
- `target="full"` captures the whole desktop (grim, no geometry).
- `target="active"` captures the focused window (geometry resolved via
  the shipped `window.get_active_window`).
- `target=<selector>` captures the first window matching a class/title
  substring or address (geometry via the shipped `window.list_clients`).
- Returns the absolute path of the saved PNG so a plan can hand it to a
  send primitive (`$steps.N.result`).

## Why the gate needed the CAPTURE shape

The automated gate previously allowed only fully-literal subprocess argv
(READ shape) or the DEVNULL WRITE shape. A window-targeted capture
inherently needs a RUNTIME geometry string ("x,y WxH" from hyprctl) in
the grim argv - a fully-literal command cannot express it, so the draft
would be AST-rejected before any human saw it. The CAPTURE shape
(2026-08-15) admits `subprocess.run([<literal tool>, ...runtime args],
capture_output=True, timeout=...)` where the TOOL BINARY is a literal
string constant from a small allowlist (`grim`, `slurp`, `import` -
screenshot/capture binaries whose args are DATA, never code that can be
made to execute, unlike a shell/interpreter). `bash -c <runtime>` stays
rejected - the first element must be a literal allowlisted tool. This is
the same class of extension as the WRITE shape added 2026-08-14 for
clipboard.write_text.

## Hand-built, not LLM-drafted

Like `gmail.send_document` (the loop's first side-effecting primitive),
this was hand-built by the human side: the LLM is a drafting aid, and a
screenshot primitive's geometry-resolution logic (hyprctl client
matching mirroring window.py) is exactly the kind of detail that matters
and is reviewable here. The impl is small, read-only (it creates one
PNG file and changes nothing else), and every external boundary is
mocked in the hermetic test.

## Safety review notes

- **Read-only**: capture writes ONE PNG to the caller's path and changes
  nothing else on the system. Idempotency = idempotent (re-capture is
  harmless; the file is overwritten).
- **Tool allowlist**: only grim/slurp/import are reachable through the
  CAPTURE shape - no shell, no interpreter, no variable tool name.
- **Protected windows are irrelevant here**: capturing a window never
  modifies it.
- **Privacy**: the screenshot CONTENT (what's on screen) is not logged -
  only the returned path rides the L0 line. A plan that sends it should
  be explicit (a send primitive is a deliberate side effect).

## Draft status

- APPROVAL: PENDING - this is a DRAFT; nothing is registered until the
  automated gate passes and APPROVED.md is signed.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-15T05:17:20+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; capture() defined; no dead arguments; @contract decorator present; log_transform (if any) defined; no undeclared bare-builtin raises
- registration: PASS - draft registers the contracted name when imported
- sandbox: REJECT - sandbox test run FAILED (exit 1):
    result = _enter(cm)
  File "/usr/lib/python3.14/unittest/mock.py", line 1494, in __enter__
    self.target = self.getter()
                  ~~~~~~~~~~~^^
  File "/usr/lib/python3.14/pkgutil.py", line 473, in resolve_name
    result = getattr(result, p)
AttributeError: module 'friday.l1.screenshot' has no attribute 'window'

----------------------------------------------------------------------
Ran 14 tests in 0.128s

FAILED (errors=4)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-15T05:17:41+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; capture() defined; no dead arguments; @contract decorator present; log_transform (if any) defined; no undeclared bare-builtin raises
- registration: PASS - draft registers the contracted name when imported
- sandbox: REJECT - sandbox test run FAILED (exit 1):
           ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.14/unittest/mock.py", line 1180, in _mock_call
    return self._execute_mock_call(*args, **kwargs)
           ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.14/unittest/mock.py", line 1241, in _execute_mock_call
    raise effect
TimeoutError: grim timed out

----------------------------------------------------------------------
Ran 14 tests in 0.062s

FAILED (errors=1)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-15T05:18:02+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; capture() defined; no dead arguments; @contract decorator present; log_transform (if any) defined; no undeclared bare-builtin raises
- registration: PASS - draft registers the contracted name when imported
- sandbox: PASS - sandbox test run PASSED (exit 0) - .............. ---------------------------------------------------------------------- Ran 14 tests in 0.093s OK
- build-verify: NOT APPLICABLE for module class 'screenshot' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-15T05:18:33+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; capture() defined; no dead arguments; @contract decorator present; log_transform (if any) defined; no undeclared bare-builtin raises
- registration: PASS - draft registers the contracted name when imported
- sandbox: PASS - sandbox test run PASSED (exit 0) - .............. ---------------------------------------------------------------------- Ran 14 tests in 0.042s OK
- build-verify: NOT APPLICABLE for module class 'screenshot' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-15T05:23:50+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; capture() defined; no dead arguments; @contract decorator present; log_transform (if any) defined; no undeclared bare-builtin raises
- registration: PASS - draft registers the contracted name when imported
- sandbox: PASS - sandbox test run PASSED (exit 0) - .............. ---------------------------------------------------------------------- Ran 14 tests in 0.119s OK
- build-verify: NOT APPLICABLE for module class 'screenshot' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.
