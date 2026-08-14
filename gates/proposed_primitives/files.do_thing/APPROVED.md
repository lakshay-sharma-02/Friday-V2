APPROVED

Reviewed and corrected by the human gate on 2026-08-10 (session with the
capability-gap loop).

The RAW LLM draft for this gap was REJECTED. Its defects, on record:
- contract.json was emitted as a Python @contract(...) decorator-source
  string, not a plain JSON Contract object (rejected by validate_contract);
- the impl ignored its own `name` argument and hardcoded the literal
  filename 'artifact';
- its semantics duplicated files.find_file's substring search.

The corrected, approved proposal:
- primitive: files.find_file_exact(name, directory) -> str
- EXACT (case-insensitive) filename match - genuinely distinct from
  find_file's substring semantics - returning '' when absent instead of
  raising, i.e. an exact-match probe.
- contract schema: validated against friday/contracts.py.
- impl: appends to the existing friday/l1/files.py (uses its _anchor /
  PROJECT_ROOT / PreconditionError helpers).
- test: hermetic unittest over temp dirs.

This APPROVED.md is the human signature required by the minimal approval
gate (friday/register_proposal.py). Signing authorizes registration: the
primitive becomes executor-callable and appears in the planner catalog.
