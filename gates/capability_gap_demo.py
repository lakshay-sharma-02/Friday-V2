#!/usr/bin/env python
"""CAPABILITY-GAP proof - the FULL self-improvement loop, end to end.

Runs the REAL machinery on this machine:

  1. The UNMODIFIED L3 executor ABORTs a step whose primitive is unknown
     (files.do_thing - a real module, unregistered function) and records
     ONE structured gap record in var/logs/capability_gaps.jsonl.
  2. gap_triage groups unprocessed gaps and drafts a proposal into
     gates/proposed_primitives/files.do_thing/. The artifacts in that dir
     are the HUMAN-CORRECTED versions: the raw LLM draft was rejected by
     the human gate (defects documented in APPROVED.md) and replaced with
     files.find_file_exact.
  3. The automated gate (friday/automated_gate.py: AST checks + sandboxed
     test run + build-verify against real targets) blocks structural
     defects BEFORE any human review; the human then signs APPROVED.md,
     register_proposal registers files.find_file_exact into
     friday/l1/files.py, and REGISTRY is confirmed.
  4. A deliberately BAD draft (subprocess.run, signed anyway) is blocked
     by the automated gate - the AST catches it before the signature
     step and nothing is registered. A SECOND bad draft - whose own test
     PASSES but whose impl returns the bare name instead of the real
     path - is caught by build-verify's real-target probe.
  5. The original goal is re-run with the approved primitive: COMPLETED
     with every step VERIFIED instead of refusing.

The triggering plan is hand-written (the same convention WATCHER_PROOF
uses for deterministic plans) so the proof is reproducible; the refusal,
the gap record, the triage, the gate and the re-run all go through the
REAL shipped stack. Registration is idempotent - re-running the demo is a
no-op on the registered function.

Run:  ./.venv/bin/python -u gates/capability_gap_demo.py
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.capability_gaps import all_gaps  # noqa: E402
from friday.errors import FridayError  # noqa: E402
from friday.gap_triage import proposal_dir, triage  # noqa: E402
from friday.l3.executor import run_plan  # noqa: E402

PROOF = "gates/CAPABILITY_GAP_PROOF.md"
PRIMITIVE = "files.do_thing"

# A plan whose step primitive is genuinely unregistered. Hand-written on
# purpose (deterministic proof), but the executor path is the real one.
PLAN = {
    "goal": "locate the missing artifact and report it",
    "steps": [{
        "primitive": PRIMITIVE,
        "args": {"name": "x", "recursive": False},
        "verify": {"check": "checks.file_exists", "args": {}, "expect": True},
        "verify_wait_s": 0.1, "backoff_s": 0.05,
    }],
}


def main() -> int:
    out: list[str] = []
    print("=" * 72)
    print(f"CAPABILITY-GAP demo - refusal -> record -> draft -> gate -> re-run ({datetime.now(timezone.utc).isoformat(timespec='seconds')})")
    print("=" * 72)

    print("\n--- L3 executor refuses an unknown primitive (real stack) ---")
    refusal = ""
    try:
        run_plan(PLAN, run_id="cap-gap-demo")
        print("ERROR: the plan unexpectedly completed")
        return 1
    except FridayError as exc:
        refusal = str(exc)
        print(f"plan ABORTed as designed: {refusal}")

    print("\n--- the structured gap record (real var/logs/capability_gaps.jsonl) ---")
    recs = [g for g in all_gaps() if g.get("attempted_primitive") == PRIMITIVE]
    if not recs:
        print("ERROR: no gap record found for", PRIMITIVE)
        return 1
    rec = recs[-1]
    print(json.dumps(rec, indent=2))
    out.append(json.dumps(rec, indent=2))

    print("\n--- gap_triage: group unprocessed gaps and draft a proposal ---")
    print("     (artifacts in gates/proposed_primitives/ are the HUMAN-CORRECTED")
    print("      version - the raw LLM draft was rejected by the human gate)")
    buf = io.StringIO()
    with redirect_stdout(buf):
        triage()
    triage_log = buf.getvalue()
    print(triage_log, end="")

    d = proposal_dir(PRIMITIVE)

    print("\n--- the automated gate + the human signature (register_proposal.py) ---")
    from friday.register_proposal import approve_and_register  # noqa: E402

    gate_log: list[str] = []
    ok, msg = approve_and_register(d)
    gate_log.append(msg)
    print(msg)

    print("\n--- a deliberately BAD draft is blocked by the automated gate ---")
    print("     (impl calls subprocess.run; APPROVED.md is signed anyway -")
    print("      the AST check must refuse before the signature step)")
    bad_root = Path(tempfile.mkdtemp(prefix="friday_bad_proposal_"))
    bad_contract = {
        "name": "files.bad_prim",
        "precondition": "p",
        "postcondition": "q",
        "idempotency": "idempotent",
        "failure_mode": "f",
        "returns": "bool",
    }
    (bad_root / "contract.json").write_text(json.dumps(bad_contract, indent=2), encoding="utf-8")
    (bad_root / "impl.py").write_text(
        "import subprocess\n\n"
        "def bad_prim(name: str) -> bool:\n"
        '    return subprocess.run(["echo", name]).returncode == 0\n',
        encoding="utf-8",
    )
    (bad_root / "test.py").write_text(
        "import unittest\n"
        "from friday.l1.files import bad_prim\n"
        "class T(unittest.TestCase):\n"
        "    def test_ok(self):\n"
        "        self.assertTrue(bad_prim('x'))\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n",
        encoding="utf-8",
    )
    (bad_root / "APPROVED.md").write_text(
        "APPROVED\nsigned anyway - the automated gate must still refuse\n", encoding="utf-8"
    )
    bad_ok, bad_msg = approve_and_register(bad_root)
    bad_log = bad_msg
    print(bad_msg)
    files_src = (ROOT / "friday" / "l1" / "files.py").read_text(encoding="utf-8")
    bad_blocked = (not bad_ok) and "subprocess.run" in bad_msg and "def bad_prim" not in files_src

    print("\n--- a draft whose OWN test passes but whose impl is wrong is blocked by build-verify ---")
    print("     (the self-authored test asserts isinstance str and PASSES; the impl returns")
    print("      the bare NAME instead of the real path - the real-target probe catches it)")
    bv_root = Path(tempfile.mkdtemp(prefix="friday_bv_proposal_"))
    bv_contract = {
        "name": "files.find_file_exact",
        "precondition": "name is a non-empty string; directory (if given) exists.",
        "postcondition": "Returns the absolute path of the first exact filename match, or '' when absent.",
        "idempotency": "idempotent",
        "failure_mode": "PreconditionError for a missing directory.",
        "returns": "str",
    }
    (bv_root / "contract.json").write_text(json.dumps(bv_contract, indent=2), encoding="utf-8")
    (bv_root / "impl.py").write_text(
        "def find_file_exact(name: str, directory: str | None = None) -> str:\n"
        '    base = directory or "."\n'
        "    return name  # wrong: returns the input, never looks at the target\n",
        encoding="utf-8",
    )
    (bv_root / "test.py").write_text(
        "import unittest\n"
        "import tempfile\n"
        "from pathlib import Path\n"
        "from friday.l1.files import find_file_exact\n"
        "class T(unittest.TestCase):\n"
        "    def test_ok(self):\n"
        "        d = tempfile.mkdtemp()\n"
        "        Path(d, 'report.pdf').write_text('x')\n"
        "        self.assertIsInstance(find_file_exact('report.pdf', d), str)\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n",
        encoding="utf-8",
    )
    (bv_root / "APPROVED.md").write_text(
        "APPROVED\nsigned anyway - build-verify must still refuse\n", encoding="utf-8"
    )
    bv_ok, bv_msg = approve_and_register(bv_root)
    bv_log = bv_msg
    print(bv_msg)
    build_blocked = (not bv_ok) and "build-verify: REJECT" in bv_msg

    print("\n--- re-run the original goal with the approved primitive ---")
    rerun = {
        "goal": "locate the missing artifact and report it",
        "steps": [{
            "primitive": "files.find_file_exact",
            "args": {"name": "README.md", "directory": str(ROOT)},
            "verify": {"check": "checks.file_exists", "args": {"path": "$steps.1.result"}, "expect": True},
            "verify_wait_s": 0.1, "backoff_s": 0.05,
        }],
    }
    if not bad_blocked:
        print("ERROR: the bad draft was NOT blocked by the automated gate")
        return 1
    if not build_blocked:
        print("ERROR: the wrong-but-self-test-passing draft was NOT blocked by build-verify")
        return 1
    if files_src != (ROOT / "friday" / "l1" / "files.py").read_text(encoding="utf-8"):
        print("ERROR: files.py changed during the demo's rejected drafts - a bad draft registered")
        return 1
    rerun_log: list[str] = []
    result = run_plan(rerun, run_id="cap-gap-rerun")
    rerun_log.append(f"plan status: {result.status}")
    for sr in result.steps:
        rerun_log.append(f"  step {sr.step_id}: {sr.primitive:24s} {sr.status}")
    print("\n".join(rerun_log))
    rerun_passed = result.status == "COMPLETED" and all(s.status == "VERIFIED" for s in result.steps)

    proof = "\n".join([
        "# CAPABILITY_GAP_PROOF - the FULL self-improvement loop, end to end",
        "",
        f"Status date: {datetime.now(timezone.utc).isoformat(timespec='seconds')}.",
        "",
        "gap -> structured record -> triage -> automated gate (AST + sandbox)",
        "-> human approval -> registration -> re-run-passes. All machinery is",
        "the REAL shipped stack; only the triggering plan is hand-written (the",
        "same convention WATCHER_PROOF uses for deterministic plans), so the",
        "proof is reproducible. Registration is idempotent - re-running the",
        "demo is a no-op on the registered function.",
        "",
        "## 1. The refusal (real L3 executor)",
        "",
        "```",
        refusal,
        "```",
        "",
        "`files.do_thing` is a real module with an unregistered function -",
        "`_resolve_primitive` refuses it (`no registered contract`) and the plan",
        "ABORTs exactly as it did before the gap loop existed; the gap record is",
        "additive, never a behavior change.",
        "",
        "## 2. The structured capability-gap record",
        "",
        "```",
        out[0],
        "```",
        "",
        "One record per refusal: source, goal_context, attempted_primitive,",
        "attempted_args_shape (type tags only - no values, so secrets and mail",
        "metadata never ride a gap record), and the refusal_reason.",
        "",
        "## 3. Triage + human-gate correction",
        "",
        "```",
        triage_log.strip(),
        "```",
        "",
        f"Artifacts: `gates/proposed_primitives/{PRIMITIVE}/` (contract.json,",
        "impl.py, test.py, rationale.md, APPROVED.md)",
        "",
        "The RAW LLM draft for this gap was REJECTED by the human gate - its",
        "defects are documented in APPROVED.md: the contract was emitted as a",
        "Python decorator-source string instead of a JSON object, and the impl",
        "ignored its own `name` argument. The human-corrected proposal is",
        "`files.find_file_exact` - an EXACT (case-insensitive) filename match",
        "returning '' when absent, genuinely distinct from find_file's substring",
        "semantics. This rejection-and-correction IS the gate working.",
        "",
        "## 4. The automated gate (AST + sandboxed tests) + the human signature",
        "",
        "```",
        "\n".join(gate_log),
        "```",
        "",
        "Gate order: contract schema (plain JSON object, real Contract fields,",
        "idempotency enum) -> impl compiles -> AST checks (imports limited to",
        "what shipped L1 primitives import; no exec/eval/subprocess/os-system",
        "calls; no sandbox-escaping file writes - absolute/.. /~ targets",
        "rejected in impl.py AND test.py; the contracted function defined; no",
        "dead arguments) -> the proposal's own test.py runs in an isolated",
        "subprocess (temp HOME + temp cwd, no credentials, no claude CLI on",
        "PATH, timeout) against the DRAFT impl -> BUILD VERIFY (files.* runs",
        "the draft against REAL temp-dir targets - present name must return",
        "the exact path; other classes are honestly flagged not-applicable)",
        "-> APPROVED.md signature -> register into friday/l1/files.py ->",
        "REGISTRY presence check.",
        "Nothing is registered without the human signature AND a clean automated",
        "gate; a rejected draft changes nothing about the running agent.",
        "",
        "## 5. A deliberately BAD draft is blocked before any human review",
        "",
        "The demo signs a proposal whose impl calls subprocess.run and asks the",
        "gate to register it. The AST check refuses BEFORE the signature step -",
        "the sandbox is skipped (a rejected draft is never executed) and the",
        "primitive is not registered:",
        "",
        "```",
        bad_log,
        "```",
        "",
        "This is the exact class of defect the previous round's human caught",
        "by hand (an impl doing something the executor would treat as",
        "dangerous) now caught mechanically - a person paying attention",
        "became a system property.",
        "",
        "## 6. Build-verify catches a draft whose OWN test passes",
        "",
        "The draft above is signed anyway, and its self-authored test is NOT",
        "a lie - it passes (the impl does return a str). But the impl returns",
        "the bare NAME, never looking at the target directory. The test-only",
        "gate would have let it through to a human; the build stage runs the",
        "draft against a REAL temp-dir target and demands the exact path:",
        "",
        "```",
        bv_log,
        "```",
        "",
        "The self-test passing is not the only check - a draft whose author",
        "wrote its own test to trivially pass is caught here, before the",
        "human signature, and nothing is registered (files.py is byte-",
        "identical after both rejected drafts).",
        "",
        "## 7. The goal re-run (now completes instead of refusing)",
        "",
        "```",
        "\n".join(rerun_log),
        "```",
        "",
        "The original goal - 'locate the missing artifact and report it' - now",
        "runs with the approved primitive (files.find_file_exact on README.md)",
        "and completes with every step VERIFIED. The planner catalog auto-",
        "discovers friday/l1/*.py, so the new primitive is also LLM-planable",
        "with no source edit.",
        "",
        "## 8. Draft quality is a KNOWN LIMIT",
        "",
        "The automated gate catches STRUCTURAL defects mechanically: imports",
        "outside the derived L1 allowlist, exec/eval/subprocess/os-system",
        "calls, a missing contracted function, dead arguments, and a failing",
        "or non-hermetic sandboxed test. It CANNOT catch logically wrong but",
        "syntactically clean code - a draft that uses all its arguments and",
        "passes its own test can still encode a wrong design. That is what",
        "the human signature is still for: the automated gate narrows what",
        "the human must review to intent and design, not syntax. The sandbox",
        "is env-level, not OS-level: it strips credentials, redirects HOME",
        "and cwd to a temp dir, removes the claude CLI from PATH, and rejects",
        "absolute/.. /~ file writes statically - but network egress and file",
        "reads of local paths are NOT hard-blocked (documented limits; full",
        "seccomp/containerization remains aspirational). Build-verify",
        "closes part of the 'wrong but clean' gap for files.* (real temp-dir",
        "targets), but other module classes have NO safe real target this",
        "session and are HONESTLY flagged 'build-verification not applicable,",
        "human review required' - never a pretended pass.",
        "",
        "## Verdict",
        "",
        f"{'FULL CYCLE PROVEN' if rerun_passed and bad_blocked and build_blocked else 'GATE FAILED'} -",
        "refusal, record, triage, automated gate (AST + sandbox + build-",
        "verify), human approval, registration and re-run all through the",
        "real stack; an AST-bad draft and a test-passing-but-wrong draft are",
        "both blocked without a human having to spot them.",
        "",
    ])
    (ROOT / PROOF).write_text(proof + "\n", encoding="utf-8")
    print(f"\nproof written to {PROOF}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
