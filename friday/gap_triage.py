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

The LLM call goes through dev._run_claude - deliberately UNLOGGED, same
discipline as gmail.summarize: goal_context strings can carry private mail
metadata, and they must never ride an L0 line.

THIS MODULE ONLY DRAFTS. Nothing is registered and no generated code is
ever executed. The approval gate is a separate concern: the meta-engine
gate (AST-validation + sandboxed build + dual human approval) is
ASPIRATIONAL, not implemented (see gates/PLAN_STATUS.md). Until a human
approves a proposal and it is wired through the real registration path
(friday/l1/<module>.py + planner._L1_MODULES), drafts stay as reviewable
artifacts in the repo.

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
{last_error}"""


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
        "\nYOUR PREVIOUS REPLY COULD NOT BE PARSED as JSON. Fix it and reply "
        f"with ONLY the JSON object. Error: {last_error}"
        if last_error
        else ""
    )
    return _PROMPT_TMPL.format(
        records=json.dumps(records, ensure_ascii=False, indent=2),
        exemplar=_EXEMPLAR,
        last_error=note,
    )


def draft_one(records: list[dict[str, Any]], attempts: int = 2) -> dict[str, Any] | None:
    """One LLM drafting pass over a grouped gap; one retry on a parse
    failure. Returns the parsed draft dict or None (left unprocessed)."""
    from friday.l1.dev import MODEL_ALIAS, _run_claude

    last_error = ""
    for _ in range(attempts):
        try:
            res = _run_claude(
                _build_prompt(records, last_error),
                None,
                180,
                MODEL_ALIAS,
                False,
            )
        except Exception as exc:
            # the LLM call ITSELF failed (CLI down, timeout): leave the
            # group unprocessed, never kill the whole triage run
            last_error = f"LLM call failed: {type(exc).__name__}: {exc}"
            continue
        raw = res.get("result") if isinstance(res, dict) else res
        text = raw if isinstance(raw, str) else (json.dumps(raw) if raw else "")
        draft = _extract_json(text)
        if draft and all(k in draft for k in ("contract", "impl", "test", "rationale")):
            return draft
        last_error = f"missing keys or unparseable JSON (got {text[:200]!r})"
    return None


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
    rationale += (
        f"- generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n"
        f"- impl compiles: {'yes' if _compiles(impl) else 'no'}\n"
        f"- test compiles: {'yes' if _compiles(test) else 'no'}\n"
        f"- driving gap records: {len(records)}\n"
        "- APPROVAL: PENDING - this is a DRAFT; nothing is registered. The\n"
        "  meta-engine approval gate does not exist yet (aspirational, see\n"
        "  gates/PLAN_STATUS.md). A human must review these files and wire an\n"
        "  approved primitive through the REAL registration path: create\n"
        "  friday/l1/<module>.py, then add the module name to planner._L1_MODULES.\n"
    )
    (d / "rationale.md").write_text(rationale, encoding="utf-8")
    return d


def triage(limit: int | None = None) -> list[str]:
    """Process unprocessed gaps: group by primitive, LLM-draft a proposal
    per group, mark processed. Returns the proposal dirs written."""
    groups = group_by_primitive(unprocessed_gaps())
    written: list[str] = []
    for prim, records in groups.items():
        if limit is not None and len(written) >= limit:
            break
        d = proposal_dir(prim)
        if _complete(d):
            # already drafted in a prior run - just consume the gaps
            mark_processed([r["gap_id"] for r in records])
            print(f"  {prim}: already drafted ({_rel(d)}), gaps consumed")
            continue
        print(f"  {prim}: drafting proposal from {len(records)} gap record(s)...")
        draft = draft_one(records)
        if draft is None:
            print(f"  {prim}: LLM draft FAILED - left unprocessed for the next run")
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
