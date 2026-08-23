# Rationale for git.status primitive

## Capability Gap

Based on the self-improvement loop's findings, there's no `git.status` primitive. Users need to check repository state (clean/dirty, branch name, staged files) for automation workflows.

## Why Friday Needs This Primitive

1. **Pre-commit Checks**: Goals like "only push if repo is clean" require knowing the repo state
2. **Branch-based Automation**: Different behaviors based on current branch
3. **File Change Detection**: Know what files were modified since last commit
4. **Integration with Messaging**: "Report uncommitted changes" goals

## Design Decisions

- **Read-only**: Uses `git status --porcelain -b` which is safe and fast
- **Idempotent**: Can be called multiple times safely
- **Structured Output**: Returns dict with branch, staged list, conflicts list, uncommitted list, and is_clean flag
- **Graceful Error Handling**: Returns structured data even for empty repos

## Use Cases

1. "Check if Friday V2 repo has uncommitted changes before running tests"
2. "List all modified files in the vivaha repo"
3. "Report current branch and whether there are pending changes"

---

## Manual Draft Status

- generated: 2026-08-18
- APPROVAL: PENDING - this is a DRAFT; nothing is registered. To register, run friday/register_proposal.py on this dir: the AUTOMATED gate (AST checks + sandboxed test run) runs first and rejects structural defects without a human; only then does your APPROVED.md signature authorize registration into friday/l1/.

**Next steps:**
1. Run `friday/automated_gate.py` on this proposal
2. If gate passes, human review and sign APPROVED.md
3. Run `friday/register_proposal.py` to register the primitive
## Automated gate (friday/automated_gate.py)
- run: 2026-08-18T04:59:24+00:00
- AST REJECT: calls subprocess.run() - dangerous/arbitrary execution
- AST REJECT: calls subprocess.run() - dangerous/arbitrary execution
- sandbox: SKIPPED - the draft was rejected at AST, so its test was not executed

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-18T05:01:48+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; status() defined; no dead arguments; @contract decorator present; log_transform (if any) defined; no undeclared bare-builtin raises
- registration: PASS - draft registers the contracted name when imported
- test.py AST REJECT: calls subprocess.run() - dangerous/arbitrary execution
- test.py AST REJECT: calls subprocess.run() - dangerous/arbitrary execution
- test.py AST REJECT: calls subprocess.run() - dangerous/arbitrary execution
- test.py AST REJECT: calls subprocess.run() - dangerous/arbitrary execution
- sandbox: SKIPPED - the test file itself was rejected at AST

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-18T05:02:16+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; status() defined; no dead arguments; @contract decorator present; log_transform (if any) defined; no undeclared bare-builtin raises
- registration: PASS - draft registers the contracted name when imported
- sandbox: PASS - sandbox test run PASSED (exit 0) - ..... ---------------------------------------------------------------------- Ran 5 tests in 2.756s OK
- build-verify: NOT APPLICABLE for module class 'git' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.

## Automated gate (friday/automated_gate.py)
- run: 2026-08-18T05:02:43+00:00
- AST checks: passed - imports allowed; no dangerous calls; no sandbox-escaping writes; status() defined; no dead arguments; @contract decorator present; log_transform (if any) defined; no undeclared bare-builtin raises
- registration: PASS - draft registers the contracted name when imported
- sandbox: PASS - sandbox test run PASSED (exit 0) - ..... ---------------------------------------------------------------------- Ran 5 tests in 2.085s OK
- build-verify: NOT APPLICABLE for module class 'git' - no safe real target for this class this session; human review required (documented limit)

The automated gate catches STRUCTURAL defects only - it does not
validate design or safety intent. Review the impl against its
contract, then sign APPROVED.md to register.
