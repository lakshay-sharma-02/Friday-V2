## Gap Addressed

**Goal context (from the real gap record):** "write the latest digest summary to a notes file"
**Refusal reason:** trigger allowlist ['notify.notify_send'] — the watcher's ambient-gap-probe-file-write trigger only allows `notify.notify_send` on its allowlist, NOT `files.write_text`.
**Attempted primitive & args:** `files.write_text`, args shape `{path: str:20, text: str:11}`.

## Why Friday Needs This Primitive

Friday's L1 `files` module (`friday/l1/files.py`) currently has only **read-side** primitives: `find_file`, `find_file_exact`, `read_text`, and `find_recent_doc`. There is no `write_text`. A goal as simple as writing a digest summary to a notes file has no primitive to express it — the watcher attempted `files.write_text` but it does not exist, so the call was refused.

This is a genuine capability gap, not an allowlist-only issue. While the trigger's allowlist ALSO needs updating (it currently only permits `notify.notify_send`), the root cause is that `files.write_text` was never registered. The new primitive is registered with the `@contract` decorator so it appears in `REGISTRY` and becomes eligible for the allowlist.

## Design Choices

- **Idempotency: commutative-safe** — a write that overwrites is idempotent on the final state; an append is commutative-safe (re-appending the same content does not corrupt the file). This matches the semantics: the executor may retry knowing the file ends up with the right content.
- **No parent-directory creation** — follows the YAGNI principle. The watcher/digest trigger provides a known notes-file path with an existing parent. `mkdir -p` can be a separate primitive when proven needed.
- **Same `_anchor` rule as read_text/find_file** — `~` expands, relative paths anchor at `PROJECT_ROOT`. Consistency across the module.
- **Returns the absolute path** — so downstream plan steps can reference it as `$steps.N.result`.

## What Was Skipped

- `redact_result`: the return is just a path, not sensitive data.
- `log_transform`: not needed; the return value is a filesystem path, not PII.
- Parent directory auto-creation: deferred until a real goal requires writing to a nested path that doesn't exist yet.

## Draft status
- generated: 2026-08-13T03:48:06+00:00
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
- run: 2026-08-13T03:50:07+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; write_text() defined; no dead arguments
- sandbox: REJECT - sandbox test run FAILED (exit 1):
ERROR: test_writes_new_file (__main__.WriteTextBehavior.test_writes_new_file)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/lakshay/Projects/Friday V2/gates/proposed_primitives/files.write_text/test.py", line 37, in test_writes_new_file
    result = files.write_text(str(target), "hello world")
             ^^^^^^^^^^^^^^^^
AttributeError: module 'friday.l1.files' has no attribute 'write_text'

----------------------------------------------------------------------
Ran 9 tests in 0.008s

FAILED (errors=6)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-13T03:51:25+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; write_text() defined; no dead arguments
- sandbox: REJECT - sandbox test run FAILED (exit 1):
  File "/usr/lib/python3.14/pathlib/__init__.py", line 809, in write_text
    with self.open(mode='w', encoding=encoding, errors=errors, newline=newline) as f:
         ~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.14/pathlib/__init__.py", line 771, in open
    return io.open(self, mode, buffering, encoding, errors, newline)
           ~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ValueError: illegal newline value: w

----------------------------------------------------------------------
Ran 9 tests in 0.014s

FAILED (errors=4)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Hand correction (2026-08-13, human gate)

The sandbox caught a REAL runtime bug in the LLM draft: the impl passed
`newline=mode` (mode='w'/'a') to `Path.write_text`, which rejects it
(`ValueError: illegal newline value: w`) - a compile-clean draft that
would crash on first real invocation. A human corrected the write to
`with p.open(mode, encoding='utf-8') as f: f.write(text)` so append mode
actually appends, then re-ran the automated gate (Fix 2 write-family
build-verify, 2026-08-13).

## Automated gate (friday/automated_gate.py)
- run: 2026-08-13T04:03:14+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; write_text() defined; no dead arguments
- sandbox: PASS - sandbox test run PASSED (exit 0) - ......... ---------------------------------------------------------------------- Ran 9 tests in 0.018s OK
- build-verify: PASS - files.* write probes: created+overwrote (and appended, when declared) a real temp file with verified content; missing-parent and empty-path raised FridayError or returned (Fix 2, 2026-08-13)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-13T04:03:33+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; write_text() defined; no dead arguments
- sandbox: PASS - sandbox test run PASSED (exit 0) - ......... ---------------------------------------------------------------------- Ran 9 tests in 0.007s OK
- build-verify: PASS - files.* write probes: created+overwrote (and appended, when declared) a real temp file with verified content; missing-parent raised FridayError or returned (Fix 2, 2026-08-13)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-13T04:07:27+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; write_text() defined; no dead arguments
- sandbox: PASS - sandbox test run PASSED (exit 0) - ......... ---------------------------------------------------------------------- Ran 9 tests in 0.007s OK
- build-verify: PASS - files.* write probes: created+overwrote (and appended, when declared) a real temp file with verified content; missing-parent raised FridayError or returned (Fix 2, 2026-08-13)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-13T04:07:40+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; write_text() defined; no dead arguments
- sandbox: PASS - sandbox test run PASSED (exit 0) - ......... ---------------------------------------------------------------------- Ran 9 tests in 0.008s OK
- build-verify: PASS - files.* write probes: created+overwrote (and appended, when declared) a real temp file with verified content; missing-parent raised FridayError or returned (Fix 2, 2026-08-13)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.
