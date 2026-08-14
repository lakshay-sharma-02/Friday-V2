"""gap_triage - turn recorded capability gaps into proposed L1 primitives.

Reads UNPROCESSED records from var/logs/capability_gaps.jsonl
(FRIDAY_GAPS_FILE overrides), groups them by attempted_primitive, and for
each group asks the LLM to draft a proposal that follows the REAL contract
schema in friday/contracts.py and the shipped primitive conventions. Each
draft lands in gates/proposed_primitives/<primitive>/:

    contract.json   the Contract fields (+ redact_result / log_transform)
    impl.py         a single @contract-decorated function, following the
                    real L1 conventions (friday/l1/<module>.py)
    test.py         a hermetic stdlib unittest, mocked external boundaries
    rationale.md    plain language: which real refused goal(s) drove this,
                    the refusal_reason and arg shape, why Friday needs it,
                    and an auto-appended DRAFT STATUS (compile checks,
                    APPROVAL: PENDING)

A group is marked processed ONLY after all four artifacts are written, so
a failed draft is re-offered next run and a completed one is never
regenerated. Idempotent by construction.

SELF-CORRECTING DRAFTS (2026-08-13): after parsing, every draft is run
through the gate's OWN structural checks (_self_check: contract schema,
exact name == attempted primitive, impl compiles, AST imports/danger/
fs-scope/dead-args - the same checks register_proposal runs later). A
structurally-broken draft is NOT written: the exact rejection is fed back
as the next attempt's last_error (bounded, `attempts`), so the LLM
repairs it at TRIAGE time instead of reaching the gate only to fail
there. Observed history drove this: four consecutive real drafts were
all caught at gate stage 1 (bad contract names, renamed primitives,
non-compiling impls) - the loop produced proposals but never a survivor.
A draft that still fails after bounded attempts is left unprocessed
(re-offered next run), never written as a known-broken artifact.

A group whose attempted_primitive is now REGISTERED is SOLVED - its gaps
are consumed with no draft (the post-approval lifecycle: a trigger that
keeps refusing a primitive AFTER it was approved and registered must not
make the loop re-propose it). The registry is populated from the real
friday/l1/ scan (planner's discovery) before the check.

The LLM call goes through dev._run_claude - deliberately UNLOGGED, same
discipline as gmail.summarize: goal_context strings can carry private mail
metadata, and they must never ride an L0 line.

MODEL FALLBACK CHAIN (2026-08-14): drafting tries the model chain in
order - FRIDAY_TRIAGE_MODEL (or the opus alias) first, then each entry
of FRIDAY_TRIAGE_FALLBACK_MODELS (comma-separated full model ids) after
a TIMEOUT or HARD FAILURE of the LLM call. A slow or DEGRADED provider
is therefore handled AUTOMATICALLY (observed live: the opus alias
provider-DEGRADED for hours; laguna-s timing out at 300s on the
new-module draft shape) instead of burning every attempt on a dead
model. A structural rejection does NOT advance the chain - a model that
responds is alive even when its draft is wrong, and the repair loop
feeds the rejection back to the SAME model.

THIS MODULE ONLY DRAFTS. Nothing is registered and no generated code is
ever executed here. The approval gate is a separate concern
(friday/register_proposal.py + friday/automated_gate.py): a draft is
first checked by the AUTOMATED gate (AST checks - derived import
allowlist, no exec/eval/subprocess/os-system calls, contracted function
defined, no dead arguments - plus a sandboxed run of the draft's own
test.py in an isolated subprocess), and only a proposal that passes then
reaches the human signature (APPROVED.md). Sandboxed-BUILD isolation and
dual-human approval remain aspirational (gates/PLAN_STATUS.md).

Run:  ./.venv/bin/python -m friday.gap_triage [--limit N]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from friday.capability_gaps import group_by_primitive, mark_processed, unprocessed_gaps
from friday.lessons import render_known_mistakes

ROOT = Path(__file__).resolve().parents[1]
PROPOSALS = ROOT / "gates" / "proposed_primitives"
ARTIFACTS = ("contract.json", "impl.py", "test.py", "rationale.md")


def _proposals_root() -> Path:
    """FRIDAY_PROPOSALS_DIR overrides the draft location (tests point it at
    a temp dir so they never write into the repo)."""
    return Path(os.environ.get("FRIDAY_PROPOSALS_DIR", str(PROPOSALS)))

# A real shipped contract used as the exemplar in every drafting prompt -
# the schema reference must be the codebase's own, never an invented shape.
_EXEMPLAR = '''@contract(
    precondition="OAuth credentials are configured and the refresh token is "
    "valid; sender is a non-empty email address or display-name fragment.",
    postcondition="Returns structural metadata of the most recent matching "
    "UNREAD messages. Makes NO state changes - nothing is marked read.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError on auth failure (refresh rejected) or API "
    "error - DISTINCT from 'no matching emails', which is an empty list, "
    "never an exception.",
    returns="list[dict]: [{message_id, sender, subject, date}] most recent first.",
    log_transform=_log_redact_mail_meta,
)
def list_unread(sender: str, max_results: int = 5) -> list[dict[str, str]]:
    """One-sentence summary. ...more docstring..."""
    ...body...'''

_PROMPT_TMPL = """You are drafting a proposal for a NEW Friday L1 primitive, driven by real
refusals recorded from the running desktop-automation agent. Reply with ONLY
a single JSON object (no markdown fences) with EXACTLY four keys:
"contract", "impl", "test", "rationale".

REAL GAP RECORDS (the actual refusals this proposal must address):
{records}

THE REAL CONTRACT SCHEMA (friday/contracts.py - follow it exactly):
- "contract" MUST be a PLAIN JSON OBJECT of the fields below - never Python
  source and never the @contract(...) decorator call itself.
- Contract object fields: name (str, "<module>.<fn>" qualified),
  precondition (str), postcondition (str), idempotency (one of
  "idempotent" | "at-most-once" | "commutative-safe"), failure_mode (str),
  returns (str).
- Decorator extras: redact_result (bool, default false), log_transform (a
  function applied to the LOGGED result only - the real return value is
  untouched).

REAL EXEMPLAR (gmail.list_unread, shipped code - match this shape):
{exemplar}

CONVENTIONS:
- "impl": a single public function for friday/l1/<module>.py, decorated with
  @contract(...) using the exact schema above. First docstring line is a
  one-sentence summary; document behavior and side effects. Import only
  stdlib + what the module needs. Prefer "idempotent" for reads.
- "test": stdlib unittest, HERMETIC - no network, no compositor, no
  notifications, no real subprocess. Use tests.helpers.EnvTestCase when env
  vars are involved; mock every external boundary (subprocess, socket,
  requests, hyprctl).
- "rationale": plain markdown in plain language - quote the real
  goal_context(s) that drove this, the refusal_reason, the arg shape, and
  why Friday needs this primitive. If the gap is an ALLOWLIST refusal of a
  primitive that ALREADY EXISTS, say so explicitly - the real fix may be
  the trigger's allowlist, not a new primitive.

Never invent a primitive that already exists in friday/l1/.
{lessons}{last_error}"""


def proposal_dir(primitive: str) -> Path:
    """<proposals root>/<sanitized primitive name>/ - the root is
    FRIDAY_PROPOSALS_DIR if set, else gates/proposed_primitives/."""
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", primitive)
    return _proposals_root() / safe


def _extract_json(text: str) -> dict[str, Any] | None:
    """Parse the LLM's reply: strip markdown fences if present, then the
    first balanced JSON object. Returns None when unparseable."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[A-Za-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    # fallback: first {...} block
    start = text.find("{")
    end = text.rfind("}")
    if 0 <= start < end:
        try:
            parsed = json.loads(text[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _build_prompt(records: list[dict[str, Any]], last_error: str = "") -> str:
    note = (
        "\nYOUR PREVIOUS REPLY WAS REJECTED (unparseable or failed Friday's "
        "structural self-check). Fix it and reply with ONLY the JSON object. "
        f"Rejection: {last_error}"
        if last_error
        else ""
    )
    # the bounded, human-approved KNOWN MISTAKES block for drafting (""
    # when none approved) - approved lessons shape the next draft, they
    # never gate it
    return _PROMPT_TMPL.format(
        records=json.dumps(records, ensure_ascii=False, indent=2),
        exemplar=_EXEMPLAR,
        lessons=render_known_mistakes("triage"),
        last_error=note,
    )


def _normalize_contract_name(name: str) -> str:
    """Strip a fully-qualified package prefix from a contract name: the
    model keeps qualifying it with the Python path ('friday.l1.files.write_text'
    - observed live 2026-08-13, repeated across bounded repair attempts) but
    the contract name is '<module>.<fn>' - so the last two dot-segments are
    the name. SAFE: the exact-name check in _self_check still requires the
    normalized result to equal the attempted primitive, so a genuine rename
    ('write_notes') is still rejected - this only repairs the deterministic
    prefix defect, never masks a semantic one."""
    parts = name.split(".")
    return ".".join(parts[-2:]) if len(parts) > 2 else name


def _self_check(primitive: str, draft: dict[str, Any]) -> list[str]:
    """The gate's OWN structural checks run on a draft BEFORE it is
    written - validate_contract / validate_impl / check_impl_ast, the
    exact checks register_proposal would run later - plus the observed
    defect the schema check alone cannot name: the contract name must
    EXACTLY equal the attempted primitive (a draft that renames
    files.write_text to write_notes would pass schema yet never solve the
    gap). Returns a list of defect strings ([] = structurally clean).
    Never executes the draft - pure static checks, so the module's
    'drafts only, never executes generated code' discipline is kept."""
    from friday.automated_gate import check_impl_ast
    from friday.register_proposal import validate_contract, validate_impl

    issues: list[str] = []
    contract = draft.get("contract")
    ok, err = validate_contract(contract)
    if not ok:
        issues.append(f"contract: {err}")
    if isinstance(contract, dict):
        name = contract.get("name")
        if isinstance(name, str) and name != primitive:
            issues.append(
                f"contract name {name!r} must EXACTLY equal the attempted "
                f"primitive {primitive!r} - a renamed primitive would never "
                "solve this gap (the executor will keep refusing the gapped name)"
            )
    if issues:
        return issues
    fn_name = contract["name"].partition(".")[2]
    ok, err = validate_impl(draft.get("impl", ""), fn_name)
    if not ok:
        issues.append(f"impl: {err}")
        return issues
    for issue in check_impl_ast(draft.get("impl", ""), fn_name):
        issues.append(f"impl AST: {issue}")
    if not _compiles(draft.get("test", "")):
        issues.append("test: the drafted test.py does not compile")
    return issues


def _triage_model_chain() -> list[str]:
    """Primary + fallback drafting models, in order of use. The primary
    is FRIDAY_TRIAGE_MODEL (the per-run override) if set, else
    MODEL_ALIAS; the fallbacks are FRIDAY_TRIAGE_FALLBACK_MODELS
    (comma-separated full model ids), tried in order AFTER the primary
    times out or hard-fails. Default is a single-model chain - the
    fallback is opt-in because the right target is machine-specific (it
    must route through the user's local router). Note FRIDAY_MODEL (the
    whole-agent override inside _run_claude) supersedes every entry here
    when set - the chain only matters when it is not."""
    from friday.l1.dev import MODEL_ALIAS

    primary = os.environ.get("FRIDAY_TRIAGE_MODEL", MODEL_ALIAS)
    chain = [primary]
    fb = os.environ.get("FRIDAY_TRIAGE_FALLBACK_MODELS", "")
    chain += [m.strip() for m in fb.split(",") if m.strip()]
    return chain


def draft_one(records: list[dict[str, Any]], attempts: int = 3) -> tuple[dict[str, Any] | None, str]:
    """One LLM drafting pass over a grouped gap; bounded repair retries.
    After the reply parses, the draft is run through the gate's OWN
    structural checks (_self_check) and the EXACT rejection is fed back as
    the next attempt's last_error - so a structurally-broken draft (bad
    contract name, renamed primitive, impl that does not compile, AST
    defect) is repaired at TRIAGE time instead of reaching the gate only
    to fail there. Returns (self-check-clean draft dict | None, last
    error/defect string) - the second element makes a failed draft
    DIAGNOSABLE (LLM-call failure, unparseable replies and self-check
    rejections are different problems with different fixes). The LLM call
    itself failing is not fatal - the group stays unprocessed."""
    from friday.l1.dev import _run_claude

    # Model chain: primary = FRIDAY_TRIAGE_MODEL (per-run override) or
    # MODEL_ALIAS, then each FRIDAY_TRIAGE_FALLBACK_MODELS entry after a
    # timeout/hard failure. The opus alias on this machine routes through
    # the user's local router to a free provider model that can be
    # DEGRADED for hours (observed live 2026-08-13 - 'DEGRADED function
    # cannot be invoked'), and laguna-s timed out at 300s on the largest
    # draft shape (cycle 2) - the chain switches models automatically
    # instead of burning every attempt on a dead/slow one.
    models = _triage_model_chain()

    primitive = records[0].get("attempted_primitive", "?") if records else "?"
    last_error = ""
    # 300s per attempt: a full 4-artifact draft (contract+impl+test+
    # rationale) plus the repair feedback is a big single LLM response - the
    # old 180s budget timed out LIVE on 2026-08-13 (which also surfaced the
    # dormant PrimitiveTimeout-init bug); a timed-out draft costs the whole
    # run, so the budget is sized for the real workload, not the minimum.
    for _ in range(attempts):
        try:
            res = _run_claude(
                _build_prompt(records, last_error),
                None,
                300,
                models[0],
                False,
            )
        except Exception as exc:
            # the LLM call ITSELF failed (CLI down, timeout, DEGRADED
            # provider): leave the group unprocessed, never kill the whole
            # triage run. A failed model is ALSO advanced out of the chain
            # - the next attempt retries a FALLBACK instead of the same
            # dead/slow one, so the loop survives a provider outage or a
            # too-slow model without human intervention.
            failed = models[0]
            last_error = f"LLM call failed ({failed}): {type(exc).__name__}: {exc}"
            if len(models) > 1:
                models = models[1:]
            continue
        raw = res.get("result") if isinstance(res, dict) else res
        text = raw if isinstance(raw, str) else (json.dumps(raw) if raw else "")
        draft = _extract_json(text)
        if not (draft and all(k in draft for k in ("contract", "impl", "test", "rationale"))):
            last_error = f"missing keys or unparseable JSON (got {text[:200]!r})"
            continue
        # deterministic prefix repair: the contract name field is
        # fundamentally gap-derived ('<module>.<fn>'), so a fully-qualified
        # 'friday.l1.<module>.<fn>' name is normalized BEFORE the checks -
        # the exact-name check below still guards the semantics
        contract = draft.get("contract")
        if isinstance(contract, dict) and isinstance(contract.get("name"), str):
            contract["name"] = _normalize_contract_name(contract["name"])
        issues = _self_check(primitive, draft)
        if issues:
            # structural defect - feed the EXACT rejection back, bounded retry
            last_error = "structural self-check failed: " + "; ".join(issues)
            continue
        return draft, ""
    return None, last_error


def _rel(p: Path) -> str:
    """p relative to the project root, or the absolute path when p is
    outside it (tests point the proposals root at a temp dir)."""
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _compiles(source: str) -> bool:
    """compile() parses WITHOUT executing - a cheap honesty check on the
    draft, not an approval gate."""
    try:
        compile(source, "<draft>", "exec")
        return True
    except SyntaxError:
        return False


def _complete(d: Path) -> bool:
    return all((d / a).is_file() for a in ARTIFACTS)


def _registered_primitives() -> set[str]:
    """Every contract-registered primitive - the SOLVED set. Populates the
    real REGISTRY by reusing the planner's _ensure_registry (scan
    friday/l1/*.py, FRIDAY_L1_DIR overrides; falls back to the module
    tuple) so the check reflects what the executor can actually resolve.
    FAIL-OPEN by design: if the registry cannot be populated the set is
    empty and triage drafts anyway - a genuine gap is never dropped, and
    re-drafting a registered primitive is recoverable (the _complete
    dir-check and the drafting prompt's 'never invent an existing
    primitive' still apply)."""
    from friday.contracts import REGISTRY
    from friday.l4.planner import _ensure_registry

    try:
        _ensure_registry()
    except Exception:
        pass
    return set(REGISTRY)


def write_proposal(primitive: str, records: list[dict[str, Any]], draft: dict[str, Any]) -> Path:
    """Write the four reviewable artifacts. Returns the proposal dir."""
    d = proposal_dir(primitive)
    d.mkdir(parents=True, exist_ok=True)
    (d / "contract.json").write_text(
        json.dumps(draft["contract"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    impl, test = draft["impl"], draft["test"]
    (d / "impl.py").write_text(impl, encoding="utf-8")
    (d / "test.py").write_text(test, encoding="utf-8")
    rationale = str(draft["rationale"]).strip() + "\n\n## Draft status\n"
    sc = _self_check(primitive, draft)
    rationale += (
        f"- generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n"
        f"- structural self-check: {'passed' if not sc else 'FAILED - ' + '; '.join(sc)}\n"
        f"- impl compiles: {'yes' if _compiles(impl) else 'no'}\n"
        f"- test compiles: {'yes' if _compiles(test) else 'no'}\n"
        f"- driving gap records: {len(records)}\n"
        "- APPROVAL: PENDING - this is a DRAFT; nothing is registered. To\n"
        "  register, run friday/register_proposal.py on this dir: the\n"
        "  AUTOMATED gate (AST checks + sandboxed test run) runs first and\n"
        "  rejects structural defects without a human; only then does your\n"
        "  APPROVED.md signature authorize registration into friday/l1/.\n"
    )
    (d / "rationale.md").write_text(rationale, encoding="utf-8")
    return d


def triage(limit: int | None = None) -> list[str]:
    """Process unprocessed gaps: group by primitive, LLM-draft a proposal
    per group, mark processed. Returns the proposal dirs written."""
    groups = group_by_primitive(unprocessed_gaps())
    written: list[str] = []
    registered = _registered_primitives()
    for prim, records in groups.items():
        if limit is not None and len(written) >= limit:
            break
        if prim in registered:
            # SOLVED: the primitive exists now (post-approval lifecycle of
            # the ambient-gap probes) - consume the gaps, never re-draft
            mark_processed([r["gap_id"] for r in records])
            print(f"  {prim}: already REGISTERED - gaps consumed, no draft")
            continue
        d = proposal_dir(prim)
        if _complete(d):
            # already drafted in a prior run - just consume the gaps
            mark_processed([r["gap_id"] for r in records])
            print(f"  {prim}: already drafted ({_rel(d)}), gaps consumed")
            continue
        print(f"  {prim}: drafting proposal from {len(records)} gap record(s)...")
        draft, reason = draft_one(records)
        if draft is None:
            # the reason is visible so a failed draft is diagnosable (an
            # LLM-call failure, unparseable replies and self-check
            # rejections are three different problems with three different
            # fixes - a bare 'failed' hides which one happened)
            print(f"  {prim}: LLM draft FAILED - left unprocessed for the next run")
            print(f"          reason: {reason}")
            continue
        write_proposal(prim, records, draft)
        mark_processed([r["gap_id"] for r in records])
        written.append(str(d))
        print(f"  {prim}: draft written to {_rel(d)}")
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Friday capability-gap triage (draft-only)")
    ap.add_argument("--limit", type=int, default=None, help="max proposals to draft")
    args = ap.parse_args(argv)
    groups = group_by_primitive(unprocessed_gaps())
    print(f"unprocessed gap groups: {len(groups)}")
    written = triage(args.limit)
    print(f"drafted: {len(written)} proposal(s) -> {_rel(_proposals_root())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
