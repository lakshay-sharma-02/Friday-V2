"""register_proposal - the approval gate for capability gaps.

A drafted proposal (gates/proposed_primitives/<prim>/) is NEVER registered
automatically. The gate runs in two stages:

  STAGE 1 - the AUTOMATED gate (friday/automated_gate.py), BEFORE any
  human involvement:
      a. contract.json is validated against the REAL Contract schema
         (friday/contracts.py: name/precondition/postcondition/
         idempotency/failure_mode/returns + optional redact_result/
         log_transform),
      b. impl.py is AST-checked: imports limited to what the shipped L1
         primitives actually import, no exec/eval/os-system calls and no
         subprocess.* beyond the read-only bounded pattern shipped
         primitives use (subprocess.run([...], capture_output=True,
         timeout=...) - the carve-out that lets a read-family primitive
         like clipboard.read_text shell out to wl-paste/xclip), the
         contracted function defined, no dead arguments,
      c. the proposal's own test.py runs in an isolated subprocess
         (temp HOME, no credentials, timeout) against the DRAFT impl.
  A failure at any automated step is written into rationale.md and the
  proposal NEVER reaches the human signature - no AST- or sandbox-caught
  defect waits for a person to spot it by eye.

  STAGE 2 - the human signature. A person reviews AND edits the
  artifacts (LLM drafts are reviewed code, not trusted code), then signs
  approval by creating APPROVED.md containing the line "APPROVED". Only
  then does the gate register:
      1. registers: writes friday/l1/<module>.py (new module) or appends
         the function to the existing module file (module comes from the
         contract's qualified name), idempotent - re-running is a no-op,
      2. confirms the primitive is in REGISTRY (reloads the module if it
         was already imported in this process),
      3. optionally re-runs the goal that originally produced the gap
         (--goal) through the LIVE planner + executor to prove the goal
         now completes instead of refusing.

The automated gate catches structural defects; the human reviews intent
and design. What remains aspirational (gates/PLAN_STATUS.md sec 8) is
only the sandboxed-BUILD + dual-human-approval meta-engine - the AST
validation and sandboxed TEST run are real and shipped.

Run:  ./.venv/bin/python -m friday.register_proposal \\
          --proposal gates/proposed_primitives/files.do_thing \\
          [--goal 'the original goal string']
"""

from __future__ import annotations

import argparse
import ast
import importlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from friday import automated_gate
from friday.contracts import Idempotency
from friday.lessons import record_lesson_event

ROOT = Path(__file__).resolve().parents[1]
L1_DIR = ROOT / "friday" / "l1"
APPROVED_TOKEN = "APPROVED"

_CONTRACT_KEYS = ("name", "precondition", "postcondition", "idempotency", "failure_mode", "returns")
_IDEMPOTENCY_VALUES = {e.value for e in Idempotency}
_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$")


def _l1_dir() -> Path:
    return Path(os.environ.get("FRIDAY_L1_DIR", str(L1_DIR)))


# ------------------------------------------------------------------ gate


def require_approval(proposal_dir: Path) -> tuple[bool, str]:
    """The human signature: APPROVED.md must exist and contain a line with
    the token APPROVED. Absent/wrong -> (False, reason)."""
    marker = proposal_dir / "APPROVED.md"
    if not marker.is_file():
        return False, f"no APPROVED.md in {proposal_dir} - the human gate has not signed this proposal"
    try:
        text = marker.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"cannot read {marker}: {exc}"
    if APPROVED_TOKEN not in text:
        return False, f"{marker} does not contain '{APPROVED_TOKEN}'"
    return True, ""


def validate_contract(c: Any) -> tuple[bool, str]:
    """contract.json must be a plain JSON object matching the REAL Contract
    schema - a decorator-source string (a defect seen in a real draft) is
    rejected outright."""
    if not isinstance(c, dict):
        return False, "contract must be a plain JSON object (not source text)"
    missing = [k for k in _CONTRACT_KEYS if not isinstance(c.get(k), str) or not c[k].strip()]
    if missing:
        return False, f"contract missing non-empty field(s): {missing}"
    if c["idempotency"] not in _IDEMPOTENCY_VALUES:
        return False, f"idempotency must be one of {sorted(_IDEMPOTENCY_VALUES)}, got {c['idempotency']!r}"
    if not _NAME_RE.match(c["name"]):
        return False, f"contract name must be '<module>.<fn>', got {c['name']!r}"
    for extra in ("redact_result", "log_transform"):
        if extra in c and not isinstance(c[extra], (bool, str)):
            return False, f"contract field {extra!r} must be bool or str"
    return True, ""


def validate_impl(impl: str, fn_name: str) -> tuple[bool, str]:
    """impl.py must parse (compile() never executes) and must define the
    contracted function."""
    if not isinstance(impl, str) or not impl.strip():
        return False, "impl must be a non-empty string of Python source"
    try:
        compile(impl, "<impl.py>", "exec")
    except SyntaxError as exc:
        return False, f"impl does not compile: {exc}"
    if not re.search(rf"^def {re.escape(fn_name)}\s*\(", impl, re.M):
        return False, f"impl does not define the contracted function {fn_name}()"
    return True, ""


# ------------------------------------------------------------- register


def _strip_future_import(src: str) -> str:
    """Drop leading `from __future__ import ...` statements from an impl.

    A future import is ONLY legal at the very top of a file. Registration
    appends the impl at EOF of an existing module, where one is a
    SyntaxError - observed for real on the first gmail.send_document
    registration (the impl began with `from __future__ import annotations`,
    and the resulting module failed to import). Strips every future import
    that precedes any real code (a leading module docstring is kept and
    skipped), so the appended block always imports. The new-module path
    leaves the impl untouched - there the future import IS at the top."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src  # validate_impl already rejected unparseable source
    drop: list[ast.ImportFrom] = []
    for stmt in tree.body:
        # a leading module docstring is fine before the future import
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) \
                and isinstance(stmt.value.value, str):
            continue
        if isinstance(stmt, ast.ImportFrom) and stmt.module == "__future__":
            drop.append(stmt)
            continue
        break  # first real statement - nothing after this may be stripped
    if not drop:
        return src
    lines = src.splitlines(keepends=True)
    for stmt in sorted(drop, key=lambda s: s.lineno, reverse=True):
        if stmt.lineno == stmt.end_lineno:
            # a single-line future import may share the line with
            # `;`-joined statements (`from __future__ import x; import os`) -
            # keep the remainder, never delete other code with the import
            line = lines[stmt.lineno - 1]
            semi = line.find(";")
            if semi != -1:
                # lstrip: a leading space before a module-level statement
                # is an IndentationError
                lines[stmt.lineno - 1] = line[semi + 1:].lstrip()
                continue
        del lines[stmt.lineno - 1: stmt.end_lineno]
    return "".join(lines)


def register(contract_name: str, impl: str) -> tuple[bool, str]:
    """Register an approved, validated impl into friday/l1/. New module ->
    file created; existing module -> function appended at EOF (the module's
    existing imports serve it). Idempotent: an already-present function is a
    no-op success."""
    module, _, fn_name = contract_name.partition(".")
    target = _l1_dir() / f"{module}.py"
    if target.is_file():
        impl = _strip_future_import(impl)
        existing = target.read_text(encoding="utf-8")
        if re.search(rf"^def {re.escape(fn_name)}\s*\(", existing, re.M):
            return True, f"{contract_name} already registered in {target} (no-op)"
        with open(target, "a", encoding="utf-8") as fh:
            fh.write(f"\n\n# ---- gate-registered {contract_name} ({_today()}) ----\n")
            fh.write(impl.rstrip() + "\n")
        return True, f"appended {contract_name} to {target}"
    header = (
        # canonical marker format: the CAPABILITIES generator matches
        # '# ---- gate-registered' - the APPEND path uses this exact form,
        # and a new-module header must too or the doc undercounts
        # (observed 2026-08-13: calendar.py showed 3 gate-registered instead
        # of 4 after the loop's second registration)
        f"# ---- gate-registered {contract_name} ({_today()}) ----\n"
        "# created by the capability-gap approval gate; reviewed by a human\n"
        "# before signing.\n"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(header + impl.rstrip() + "\n", encoding="utf-8")
    return True, f"created {target} with {contract_name}"


def _today() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _annotate_rejection(proposal: Path, reason: str) -> None:
    """Append the gate's rejection to the proposal's rationale.md so the
    artifact itself tells the truth - a rejected draft must not keep
    saying APPROVAL: PENDING (observed on the first ambient gmail draft,
    rejected at contract schema with no record left behind). The automated
    gate already annotates its own rejections; this covers the earlier
    contract-schema and impl-syntax stages. Best-effort: a broken write
    never blocks the gate."""
    from datetime import datetime, timezone

    try:
        rationale = proposal / "rationale.md"
        existing = rationale.read_text(encoding="utf-8") if rationale.is_file() else ""
        note = (
            f"\n## Gate rejection ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')})\n"
            f"{reason}\n"
        )
        rationale.write_text(existing.rstrip() + "\n" + note, encoding="utf-8")
    except Exception:
        pass


def verify_registered(contract_name: str) -> bool:
    """Confirm REGISTRY knows the primitive. Reloads the module if it was
    already imported in this process (a long-lived run appends to a cached
    module). Best-effort: returns False without raising when the module
    cannot be imported (e.g. tests pointing FRIDAY_L1_DIR at a temp dir)."""
    module = contract_name.partition(".")[0]
    full = f"friday.l1.{module}"
    try:
        if full in sys.modules:
            # the module was already imported BEFORE registration - reload
            # so the appended function registers in this process too
            importlib.reload(sys.modules[full])
        else:
            importlib.import_module(full)
        from friday.contracts import REGISTRY

        return contract_name in REGISTRY
    except Exception:
        return False


# ------------------------------------------------------------------ gate


def approve_and_register(
    proposal: Path,
    *,
    goal: str | None = None,
    sandbox_timeout_s: int = automated_gate.DEFAULT_SANDBOX_TIMEOUT_S,
) -> tuple[bool, str]:
    """The whole gate for one proposal. STAGE 1 (automated): contract
    schema -> impl syntax -> AST checks -> sandboxed test run, all BEFORE
    any human involvement - a failure here never reaches the signature.
    STAGE 2 (human): APPROVED.md signature -> register -> registry check
    -> (optional) goal re-run."""
    contract = json.loads((proposal / "contract.json").read_text(encoding="utf-8"))
    ok, err = validate_contract(contract)
    if not ok:
        _annotate_rejection(proposal, f"REJECTED: {err}")
        # record the failure class as a lesson event (best-effort) - the
        # lessons loop turns rejection clusters into remembered behavior
        record_lesson_event(
            category="draft_schema", source="register_proposal",
            detail=f"{contract.get('name', '?') if isinstance(contract, dict) else '?'}: {err}",
            primitive=contract.get("name") if isinstance(contract, dict) else None,
        )
        return False, f"REJECTED: {err}"
    impl = (proposal / "impl.py").read_text(encoding="utf-8")
    fn_name = contract["name"].partition(".")[2]
    ok, err = validate_impl(impl, fn_name)
    if not ok:
        _annotate_rejection(proposal, f"REJECTED: {err}")
        record_lesson_event(
            category="draft_impl_syntax", source="register_proposal",
            detail=f"{contract['name']}: {err}", primitive=contract["name"],
        )
        return False, f"REJECTED: {err}"

    # STAGE 1 - the automated gate, before the human signature. A failure
    # here is written into rationale.md and never reaches APPROVED.md.
    gate_ok, gate_lines = automated_gate.run_automated_gate(
        proposal, contract=contract, impl_src=impl, timeout_s=sandbox_timeout_s
    )
    lines = ["automated gate (AST + sandbox):"] + [f"  {l}" for l in gate_lines]
    if not gate_ok:
        return False, "REJECTED by the automated gate - never reached the human signature:\n" + "\n".join(lines)

    # STAGE 2 - the human signature.
    ok, err = require_approval(proposal)
    if not ok:
        return False, f"REJECTED: {err}"
    ok, msg = register(contract["name"], impl)
    if not ok:
        return False, msg
    verified = verify_registered(contract["name"])
    lines += [f"registered {contract['name']}: {msg}", f"registry check: {'present' if verified else 'NOT VERIFIED (module not importable here)'}"]
    if goal:
        try:
            from friday.l3.executor import run_plan
            from friday.l4.planner import plan as llm_plan

            p = llm_plan(goal, run_id="gap-gate-rerun")
            result = run_plan(p, run_id="gap-gate-rerun")
            lines.append(f"goal re-run: {result.status} ({len(result.steps)} steps)")
            for sr in result.steps:
                lines.append(f"  step {sr.step_id}: {sr.primitive} {sr.status}")
        except Exception as exc:
            lines.append(f"goal re-run FAILED: {type(exc).__name__}: {exc}")
    return True, "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Friday capability-gap approval gate (register an approved proposal)")
    ap.add_argument("--proposal", required=True, help="path to a proposal dir (gates/proposed_primitives/<prim>/")
    ap.add_argument("--goal", default=None, help="re-run this goal after registration to prove the loop closes")
    args = ap.parse_args(argv)
    proposal = Path(args.proposal)
    if not proposal.is_dir():
        print(f"ERROR: proposal dir not found: {proposal}")
        return 2
    ok, msg = approve_and_register(proposal, goal=args.goal)
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
