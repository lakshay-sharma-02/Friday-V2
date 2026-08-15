# Rationale for files.find_newest primitive

## Gap record
- **Gap ID**: 18cbad97bc9e3df432
- **Timestamp**: 2026-08-14T13:02:24.398713+00:00
- **Source**: executor
- **Attempted primitive**: `files.find_newest` (DOES NOT EXIST)
- **Attempted args**: `{"name": "str:5", "directory": "str:5"}`
- **Goal context**: "send the newest pdf in my downloads to my whatsapp"
- **Refusal reason**: `'primitive files.find_newest has no registered contract; refusing to call it'`

## Why this primitive is needed
The user goal "send the newest pdf in my downloads to my whatsapp" requires finding the most recently modified PDF file in a directory when the exact filename is unknown. The existing `files.find_file` finds *first* match by name ordering, not by modification time. A `files.find_newest` primitive is necessary for time-based file discovery.

## Why previous primitives don't suffice
- `files.find_file`: Returns the lexicographically first match, not the newest by mtime
- `files.find_file_exact`: Requires exact filename match, not helpful for unknown filenames
- `files.find_recent_doc`: Only matches status/planning docs (README, ROADMAP, etc.), not general files like PDFs

## Design decisions
- Returns empty dict `{}` instead of raising when no file matches (consistent with `files.find_recent_doc` pattern)
- Non-recursive search (consistent with `files.find_file` default)
- Case-insensitive name matching (consistent with `files.find_file`)
- Returns `matches` list for debugging/verification in plans
- `log_transform` to redact matches list in logs (privacy-preserving)

## Draft status
- generated: 2026-08-14T13:33:11+00:00
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
- run: 2026-08-14T13:33:17+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; find_newest() defined; no dead arguments; @contract decorator present; log_transform (if any) defined; no undeclared bare-builtin raises
- registration: PASS - draft registers the contracted name when imported
- sandbox: PASS - sandbox test run PASSED (exit 0)
- build-verify: REJECT - PROBE_FAIL 0 expected path '/tmp/friday_buildverify_gih5fvg_/report.pdf', got {'path': '/tmp/friday_buildverify_gih5fvg_/report.pdf', 'name': 'report.pdf', 'mtime': 1786714397.2287, 'matches': ['/tmp/friday_buildverify_gih5fvg_/report.pdf']} (dict)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-14T13:34:33+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; find_newest() defined; no dead arguments; @contract decorator present; log_transform (if any) defined; no undeclared bare-builtin raises
- registration: PASS - draft registers the contracted name when imported
- sandbox: PASS - sandbox test run PASSED (exit 0) - ....... ---------------------------------------------------------------------- Ran 7 tests in 0.009s OK
- build-verify: PASS - files.* real-target probes: present name -> exact path, absent -> str, bad directory -> FridayError handled

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-14T13:34:49+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; find_newest() defined; no dead arguments; @contract decorator present; log_transform (if any) defined; no undeclared bare-builtin raises
- registration: PASS - draft registers the contracted name when imported
- sandbox: PASS - sandbox test run PASSED (exit 0) - ....... ---------------------------------------------------------------------- Ran 7 tests in 0.009s OK
- build-verify: PASS - files.* real-target probes: present name -> exact path, absent -> str, bad directory -> FridayError handled

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.
