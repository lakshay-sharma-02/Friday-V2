# APPROVED - clipboard.write_text

SIGNED: 2026-08-14 (human gate)

## Human review notes

- **@contract decorator present** - the exact defect that killed earlier
  clipboard drafts is absent here; the draft landed only after the
  `draft_no_register` lesson was reordered into the injected set (it sat
  beyond the 5-lesson cap and the model never saw it - loop-level fix,
  applies to every future draft).
- wl-copy (Wayland) and xclip (X11) fallbacks BOTH implemented - matches
  the contract's precondition, no contract/impl drift.
- Write side uses `input=text` (stdin) with `text=True` for str I/O -
  the read-only bounded subprocess carve-out tolerates the extra kwargs
  (only shell/capture/timeout are gated), so the AST check passes.
- Returns the text echoed back - lets the executor's verify step assert
  the write landed; matches the read_text convention of returning content.
- FridayError family only (PrimitiveError with `state=`) - no bare
  builtins; empty-string write returns '' distinct from a tool failure.
- Test is hermetic: mocks subprocess.run for both tool paths, covers
  tool-failure and missing-tool. Passed the sandbox run.
- build-verify NOT APPLICABLE (clipboard class has no safe real target) -
  documented limit; semantic proof is the live verification below.

## Live verification (real clipboard)

- write_text then read_text round-trip against the real system clipboard
  via wl-copy/wl-paste: text landed and read back identically.

## Correction after live verification (2026-08-14) - write shape deadlock

- **What live verification found**: the registered write used the READ
  subprocess shape (`capture_output=True`) and EVERY write failed with a
  5s timeout. Root cause: `wl-copy` (and `xclip`) fork a daemon that
  inherits the child's pipe fds, so `communicate()` waits forever for EOF.
  The hermetic mock test never exercised the real tool - the classic
  build-verify-NOT-APPLICABLE gap where only live verification catches
  the defect.
- **The fix**: output is DISCARDED, not captured - `stdout=subprocess.DEVNULL,
  stderr=subprocess.DEVNULL` completes in ~0.1s and the clipboard holds
  the content (proven against the real clipboard). Error detail is
  dropped (DEVNULL discards stderr); the returncode check still
  classifies failure as PrimitiveError.
- **Loop-level fix (not just this primitive)**: `_is_safe_subprocess_run`
  now admits the WRITE shape (both stdout and stderr DEVNULL, never mixed
  with capture_output, timeout always required) alongside the READ shape,
  and the triage prompt + `draft_ast` lesson teach it - so future
  write-family drafts (clipboard, any daemon-forking tool) stop shipping
  the deadlocking read shape.
- Shipped `friday/l1/clipboard.py`, the proposal impl/test, and the gate
  rule + tests were all updated together; full suite re-run green.
