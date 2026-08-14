## Gap Addressed

**Goal context (from the real gap record):** "show me my upcoming calendar events for the week"
**Refusal reason:** `trigger allowlist ['notify.notify_send']` - MISLEADING. The actual refusal was for `calendar.list_upcoming` which does NOT exist as a registered primitive. The allowlist message is incorrect - the primitive simply has no contract registered.
**Attempted primitive & args:** `calendar.list_upcoming`, args shape `{days: int}`.

## Why Friday Needs This Primitive

Friday's L1 primitives include `gmail`, `files`, `browser`, `notify`, etc., but there is no `calendar` module. A user goal to "show me my upcoming calendar events for the week" has no way to express it - the watcher attempted `calendar.list_upcoming(days=7)` but it was refused because no contract exists.

This is a GENUINE CAPABILITY GAP, NOT an allowlist-only issue. The trigger's allowlist appears to be checking for `calendar.list_upcoming` but the primitive was never registered. Friday needs calendar integration for goals like:
- Show upcoming meetings for the day
- Verify event attendance
- Generate weekly agenda summaries
- Check for scheduling conflicts between browser-based and local events

## Design Choices

- **Idempotency: idempotent** - a read operation, safe to retry without side effects
- **Default days: 7** - matches the goal context "for the week"; users can override
- **Google Calendar API** - follows the Gmail OAuth pattern (credentials via GOOGLE_CALENDAR_TOKEN env var or pass entry)
- **Returns empty list when no events** - never raises Exception for 'no events' (consistent with gmail.list_unread)
- **ISO 8601 timestamps** - standard datetime format, parseable by downstream L2 checks

## What Was Skipped

- `redact_result`: not needed; event summaries are generally safe to log (they're already visible to the user)
- `log_transform`: event summaries could be redacted but current implementation keeps them visible for debugging
- `local .ics file parsing`: deferred until there's a real goal requiring it; API-first design matches the Gmail pattern

## Draft status
- generated: 2026-08-13T04:15:00+00:00
- structural self-check: pending
- impl compiles: pending
- test compiles: pending
- driving gap records: 1
- APPROVAL: PENDING - this is a DRAFT; nothing is registered. To
  register, run friday/register_proposal.py on this dir: the
  AUTOMATED gate (AST checks + sandboxed test run) runs first and
  rejects structural defects without a human; only then does your
  APPROVED.md signature authorize registration into friday/l1/.

## Draft status
- generated: 2026-08-13T04:51:16+00:00
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
- run: 2026-08-13T04:51:53+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; list_upcoming() defined; no dead arguments
- sandbox: PASS - sandbox test run PASSED (exit 0) - ........ ---------------------------------------------------------------------- Ran 8 tests in 0.213s OK
- build-verify: NOT APPLICABLE for module class 'calendar' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-13T04:52:42+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; list_upcoming() defined; no dead arguments
- sandbox: PASS - sandbox test run PASSED (exit 0) - ........ ---------------------------------------------------------------------- Ran 8 tests in 0.209s OK
- build-verify: NOT APPLICABLE for module class 'calendar' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.
