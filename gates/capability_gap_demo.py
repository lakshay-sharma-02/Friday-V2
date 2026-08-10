#!/usr/bin/env python
"""CAPABILITY-GAP proof - the gap -> draft half of the self-improvement loop.

Runs the REAL refusal machinery end to end on this machine:

  1. The UNMODIFIED L3 executor ABORTs a step whose primitive is unknown
     (files.do_thing - a real module, unregistered function) and records
     ONE structured gap record in var/logs/capability_gaps.jsonl.
  2. gap_triage groups unprocessed gaps by attempted_primitive and makes a
     LIVE LLM call to draft a proposal (contract.json / impl.py / test.py /
     rationale.md) into gates/proposed_primitives/files.do_thing/.
  3. The proof captures the cycle up to the approval gate.

APPROVAL + REGISTRATION are deliberately NOT part of this run: the
meta-engine gate (AST-validation + sandboxed build + dual human approval)
does NOT exist yet - it is aspirational, see gates/PLAN_STATUS.md. Nothing
is auto-registered; the drafted artifacts exist for human review.

The triggering plan is hand-written (the same convention WATCHER_PROOF
uses for deterministic plans) so the proof is reproducible; the refusal,
the gap record, the triage grouping and the LLM draft all run through the
REAL shipped stack.

Run:  ./.venv/bin/python -u gates/capability_gap_demo.py
"""

from __future__ import annotations

import io
import json
import sys
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
    print(f"CAPABILITY-GAP demo - refusal -> record -> triage draft ({datetime.now(timezone.utc).isoformat(timespec='seconds')})")
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

    print("\n--- gap_triage: group unprocessed gaps and LLM-draft a proposal ---")
    print("     (one live LLM call - drafting is a paid, non-deterministic step)")
    buf = io.StringIO()
    with redirect_stdout(buf):
        triage()
    triage_log = buf.getvalue()
    print(triage_log, end="")

    d = proposal_dir(PRIMITIVE)
    rationale = (d / "rationale.md").read_text(encoding="utf-8") if (d / "rationale.md").is_file() else ""
    status_lines = [l for l in rationale.splitlines() if "compiles" in l or "APPROVAL" in l]

    proof = "\n".join([
        "# CAPABILITY_GAP_PROOF - gap -> draft (self-improvement loop, steps 1-2)",
        "",
        f"Status date: {datetime.now(timezone.utc).isoformat(timespec='seconds')}.",
        "",
        "The refusal, the gap record, the triage grouping and the LLM draft all run",
        "through the REAL shipped stack; only the triggering plan is hand-written",
        "(the same convention WATCHER_PROOF uses for deterministic plans), so the",
        "proof is reproducible.",
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
        "## 3. Triage (group + LLM draft)",
        "",
        "```",
        triage_log.strip(),
        "```",
        "",
        f"Artifacts: `gates/proposed_primitives/{PRIMITIVE}/`",
        "",
        "- `contract.json` - the draft Contract following friday/contracts.py",
        "- `impl.py` - a draft @contract-decorated function",
        "- `test.py` - a draft hermetic unittest",
        "- `rationale.md` - which refused goal(s) drove this, in plain language",
        "",
        "Draft status from rationale.md:",
        "",
        "```",
        "\n".join(status_lines),
        "```",
        "",
        "## 4. Draft quality is a KNOWN LIMIT",
        "",
        "The LLM draft is only syntax-checked (compile()) - it is NOT semantic-\n",
        "or safety-validated, and there is no sandboxed build or approval gate\n",
        "(that machinery is aspirational). A real run observed the model emitting\n",
        "the contract as a Python decorator-source string instead of a JSON\n",
        "object, and an impl that hardcoded a filename while ignoring its own\n",
        "name argument. Such a draft compiles yet is wrong - it must be rejected\n",
        "at HUMAN REVIEW, never registered: nothing in this loop self-registers,\n",
        "and a rejected draft changes nothing about the running agent.\n",
        "",
        "## 5. Approval + registration - PENDING BY DESIGN",
        "",
        "The meta-engine gate (AST-validation + sandboxed build + dual human",
        "approval) described in the plan DOES NOT EXIST in this repo yet - it is",
        "aspirational (see gates/PLAN_STATUS.md section 8). Per the session",
        "constraint, no parallel approval flow was invented: **nothing is",
        "auto-registered**. A human must review these draft artifacts and, if",
        "approved, wire the primitive through the REAL registration path:",
        "",
        "1. create friday/l1/<module>.py with the reviewed contract + function,",
        "2. add the module name to planner._L1_MODULES so the registry populates,",
        "3. re-run the original goal that produced the gap - it should now plan",
        "   and execute instead of refusing.",
        "",
        "## Verdict",
        "",
        "Gap -> draft loop proven end to end with real machinery. Approval +",
        "registration await the approval-gate decision.",
        "",
    ])
    (ROOT / PROOF).write_text(proof + "\n", encoding="utf-8")
    print(f"\nproof written to {PROOF}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
