# Approval: files.write_text

APPROVED

## Review record (2026-08-13)

The automated gate passed every stage before this signature:
- contract schema: PASS (name `files.write_text`, exactly `<module>.<fn>`)
- AST: PASS (allowed imports; no dangerous calls; no sandbox-escaping writes;
  `write_text()` defined; no dead arguments)
- sandbox: PASS (the draft's own 9-test suite, exercising the DRAFT via the
  in-place injection)
- build-verify (Fix 2, write-family probes): PASS - created + overwrote +
  appended a real temp file with verified on-disk content; missing-parent
  raised FridayError

Human review performed (the gate's documented role - it cannot judge
design intent):
1. The first LLM draft was REJECTED by the sandbox: `newline=mode` with
   `mode='w'/'a'` is illegal for `Path.write_text` (`ValueError: illegal
   newline value: w`) - a compile-clean draft that would crash on first
   real invocation. Corrected by a human to `with p.open(mode) as f:
   f.write(text)` so append mode actually appends.
2. The draft's contract/impl mismatch on failure_mode was reconciled: the
   impl wrapped disk/read-only OSErrors into PreconditionError, but the
   contract says "OSError propagated". The wrapper was removed - OSError
   now propagates as the contract declares (a disk-full or read-only
   filesystem is not a caller bug).

Remaining semantic notes (accepted for a file-write primitive):
- The impl anchors relative paths at PROJECT_ROOT and expands `~` (same
  rule as find_file/read_text) - a plan step should pass an absolute path
  or a path relative to the project root.
- Idempotency `commutative-safe` is accurate: overwriting is idempotent on
  final state; appending the same content twice is harmless.

## Why this primitive exists

Driven by the real gap record from `ambient-gap-probe-file-write`:
goal_context "write the latest digest summary to a notes file",
attempted_primitive `files.write_text` (args shape {path: str:20,
text: str:11}), refused because no write primitive was registered. This is
the loop's FIRST side-effecting primitive registered through the full
self-improvement cycle: refusal -> gap record -> LLM draft -> self-check
repair loop -> automated gate (AST + sandbox + write-family build-verify)
-> human review -> registration.
