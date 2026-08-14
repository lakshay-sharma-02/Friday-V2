Goal: show me my upcoming calendar events for the week (real gap record). Refusal: allowlist blocks notify.notify_send when calendar.list_upcoming is invoked, preventing any calendar read primitive from succeeding. Arg shape: days: int. Friday needs a read‑only L1 primitive that returns upcoming calendar events for a given number of days, with no side effects, idempotent, and fails cleanly on auth/API errors rather than raising generic exceptions. Existing code lacks a dedicated calendar.read_upcoming primitive, and the current allowlist prevents the existing notification‑linked call from succeeding, so a new primitive is required.

## Draft status
- generated: 2026-08-11T17:23:12+00:00
- impl compiles: yes
- test compiles: yes
- driving gap records: 1
- APPROVAL: PENDING - this is a DRAFT; nothing is registered. To
  register, run friday/register_proposal.py on this dir: the
  AUTOMATED gate (AST checks + sandboxed test run) runs first and
  rejects structural defects without a human; only then does your
  APPROVED.md signature authorize registration into friday/l1/.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-11T17:25:46+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; list_upcoming() defined; no dead arguments
- sandbox: REJECT - sandbox test run FAILED (exit 1):
Traceback (most recent call last):
  File "/tmp/friday_sandbox_8ivkpq94/runner.py", line 34, in <module>
    sys.exit(main())
             ~~~~^^
  File "/tmp/friday_sandbox_8ivkpq94/runner.py", line 17, in main
    exec(compile(src, impl_path, "exec"), ns)
    ~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/lakshay/Projects/Friday V2/gates/proposed_primitives/calendar.list_upcoming/impl.py", line 2, in <module>
    from friday.l1 import calendar
ImportError: cannot import name 'calendar' from 'friday.l1' (/home/lakshay/Projects/Friday V2/friday/l1/__init__.py)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.
