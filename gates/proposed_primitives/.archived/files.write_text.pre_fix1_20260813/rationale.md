The gap record shows a refusal of `files.write_text` due to allowlist `notify.notify_send` while attempting to write the latest digest summary to a notes file (goal_context). The attempted args were a path string and a text string (arg shape). No existing `files.write_text` primitive exists in friday/l1/, and the allowlist blocks file writes that could trigger notifications. Friday needs a new primitive that can write text to an approved location, enabling digest summaries to be saved without violating the allowlist. This primitive will be named `write_notes` in `friday.l1.files`, with a precondition that the path is within an allowed notes directory, and will return a confirmation string.

## Draft status
- generated: 2026-08-12T19:26:18+00:00
- impl compiles: no
- test compiles: no
- driving gap records: 1
- APPROVAL: PENDING - this is a DRAFT; nothing is registered. To
  register, run friday/register_proposal.py on this dir: the
  AUTOMATED gate (AST checks + sandboxed test run) runs first and
  rejects structural defects without a human; only then does your
  APPROVED.md signature authorize registration into friday/l1/.

## Gate rejection (2026-08-12 19:26 UTC)
REJECTED: contract name must be '<module>.<fn>', got 'friday.l1.files.write_notes'
