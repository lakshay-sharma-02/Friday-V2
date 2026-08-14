"""friday/lessons - the lessons loop: rejections become remembered behavior.

The self-improvement loop's FIRST half is drafting (gap_triage + the
approval gate): refusals become proposed L1 primitives. This module is
the SECOND half - what the loop REMEMBERS. Today a rejected draft leaves
its rejection in that proposal's rationale.md and nothing ever consumes
it; the planner fails a schema check and the reason dies in the L0 log.
Rejections are a log, not a memory.

The lessons loop:

  1. RECORD - every mechanical rejection site writes one structured event
     to var/logs/lessons.jsonl (FRIDAY_LESSONS_FILE overrides):
     {event_id, timestamp, category, source, detail, ...}. Best-effort
     and additive, exactly like capability gaps - a broken lessons file
     never breaks the caller.

  2. GENERALIZE - a candidate lesson is a CATEGORY, not one event
     ("LLM drafts, when blocked by a boundary, fabricate a route around
     it" generalizes from one specific confabulation). generalize()
     groups events by category and writes a reviewable candidate to
     gates/proposed_lessons/<category>.md (FRIDAY_PROPOSED_LESSONS_DIR
     overrides) when a category has >= MIN_EXAMPLES events. Idempotent:
     a candidate is never regenerated for events it already covers, and
     new evidence extends an existing candidate instead of duplicating
     it.

  3. HUMAN GATE - a lesson is a PROPOSAL until a human approves it. The
     approved store is config/lessons.json (FRIDAY_APPROVED_LESSONS
     overrides), human-edited the same way planner_facts.json is;
     adding a lesson there IS the approval, same philosophy as
     APPROVED.md for primitives. Nothing auto-absorbs: a wrong lesson
     injected into every future prompt is worse than no lesson, so no
     path exists from the event log to the prompts that bypasses the
     approved store.

  4. INJECT (bounded) - render_known_mistakes(target) renders a small,
     fixed-size "KNOWN MISTAKES" block of the approved lessons for one
     prompt target ("triage" | "planner" | "digest"); the drafting,
     planning and digest prompts each embed their own target's block.
     Injection is capped (INJECT_LIMIT) so prompts never bloat and
     stale lessons are pruned by editing the approved store, not by
     code.

Categories are a fixed registry (CATEGORIES), each with its prompt
target(s) and a canonical statement a candidate generalizes to. The
mechanical record sites: the automated gate (draft_ast /
draft_test_fail / draft_build_verify_fail), the approval gate's earlier
stages (draft_schema / draft_impl_syntax), the digest attribution check
(digest_misattribution), and the planner's retry failures
(planner_unparseable / planner_schema / planner_unknown_primitive /
planner_blocked_primitive / planner_facts_ref / planner_llm_error).
Human-observed categories with no mechanical detector
(draft_confabulation, draft_dead_arg, draft_wrapper_dodge) are recorded
via the --record CLI and are seeded into the approved store by a human
(the seed lessons in config/lessons.json are exactly those verified
findings).

Honest limits: a lesson is plain-language prompt guidance - it can stop
a RECOGNIZED failure class from recurring, but it cannot catch a
clean-but-subtly-wrong draft (that remains a human reading problem, and
no prompt block changes it). Lessons are statements, not code - they
shape the model's next attempt, they do not gate it.

Run:
    ./.venv/bin/python -m friday.lessons                  # generalize: candidates for event clusters
    ./.venv/bin/python -m friday.lessons --record \\
        --category draft_confabulation --detail "..."     # human-observed event
    ./.venv/bin/python -m friday.lessons --list           # approved lessons (the injected set)
    ./.venv/bin/python -m friday.lessons --check          # validate the approved store
    ./.venv/bin/python -m friday.lessons --events         # recent raw events
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_LESSONS_LOG = Path(__file__).resolve().parents[1] / "var" / "logs" / "lessons.jsonl"
DEFAULT_APPROVED = Path(__file__).resolve().parents[1] / "config" / "lessons.json"
DEFAULT_CANDIDATES = Path(__file__).resolve().parents[1] / "gates" / "proposed_lessons"

# A candidate lesson needs at least this many recorded events in its
# category - one event is a possibly-one-off mistake, a cluster is a
# pattern worth proposing (the seed lessons bypass this: they were
# human-verified findings, not event clusters).
MIN_EXAMPLES = 2
# Cap per prompt target so an accumulating approved store can never bloat
# the triage/planner/digest prompts.
INJECT_LIMIT = 5
_DETAIL_MAX = 500

TARGETS = ("triage", "planner", "digest")

# The fixed category registry: category -> prompt target(s) + the canonical
# statement a candidate generalizes to. Categories are added deliberately,
# never ad hoc - a category with no statement cannot produce a lesson.
CATEGORIES: dict[str, dict[str, Any]] = {
    # ---- drafting (injected into the gap_triage prompt) ----
    "draft_confabulation": {
        "targets": ("triage",),
        "statement": (
            "Never claim a primitive, mechanism, or capability exists unless it is "
            "actually present in the gathered context. A refusal means the capability "
            "does NOT exist here - not that it exists and is blocked. If a boundary "
            "cannot be satisfied, report the constraint instead of fabricating a route "
            "around it."
        ),
    },
    "draft_dead_arg": {
        "targets": ("triage",),
        "statement": (
            "Every declared parameter of the drafted function must be used in its "
            "body - never hardcode a value while ignoring an argument; the gate "
            "rejects dead arguments mechanically."
        ),
    },
    "draft_wrapper_dodge": {
        "targets": ("triage",),
        "statement": (
            "Never route around a capability boundary by renaming an existing "
            "primitive under a new name - that is a dodge, not a capability. If the "
            "gap is an allowlist refusal of a primitive that ALREADY EXISTS, say so "
            "explicitly: the real fix may be the trigger's allowlist, not a new "
            "primitive."
        ),
    },
    "draft_schema": {
        "targets": ("triage",),
        "statement": (
            "The contract must be a plain JSON object with the real Contract fields "
            "and a '<module>.<fn>' name (exactly one dot) - never the @contract(...) "
            "decorator source as the contract."
        ),
    },
    "draft_impl_syntax": {
        "targets": ("triage",),
        "statement": (
            "The drafted impl must be syntactically valid Python that compiles - a "
            "syntax error is rejected before anything else is reviewed."
        ),
    },
    "draft_ast": {
        "targets": ("triage",),
        "statement": (
            "The drafted impl must import only from the L1 allowlist and never call "
            "exec/eval/subprocess/os-system - arbitrary execution is rejected at AST "
            "before any review."
        ),
    },
    "draft_test_fail": {
        "targets": ("triage",),
        "statement": (
            "The draft's own test.py must actually run and pass in the sandbox - a "
            "test that cannot import the module it claims to test (or imports a "
            "module that does not exist) is a structural defect, not a design choice."
        ),
    },
    "draft_build_verify_fail": {
        "targets": ("triage",),
        "statement": (
            "The drafted function must behave correctly against a real target "
            "(files.*): returning the exact path, the right types, and sane error "
            "behavior - a self-authored test that passes is not proof the impl works."
        ),
    },
    # ---- digest synthesis (injected into the dev.digest prompt) ----
    "digest_misattribution": {
        "targets": ("digest",),
        "statement": (
            "Never attribute a mechanism or pattern to a repo unless it appears in "
            "that repo's OWN gathered content - misattribution is a fabrication and "
            "is flagged mechanically; absent confirmation, say it cannot be confirmed."
        ),
    },
    # ---- planning (injected into the planner prompt) ----
    "planner_unparseable": {
        "targets": ("planner",),
        "statement": (
            "The plan must be a single JSON object with no markdown fences and no "
            "prose before or after."
        ),
    },
    "planner_schema": {
        "targets": ("planner",),
        "statement": (
            "The plan must match the executor schema exactly: goal string, steps "
            "with registered primitives and args objects, and every step carrying a "
            "verify with a real check and an exact 'expect' value."
        ),
    },
    "planner_unknown_primitive": {
        "targets": ("planner",),
        "statement": (
            "Only primitives listed in the catalog may appear in a plan - never "
            "invent a primitive name."
        ),
    },
    "planner_blocked_primitive": {
        "targets": ("planner",),
        "statement": (
            "Never plan a step with a primitive the executor blocks - blocked "
            "primitives are never advertised in the catalog and are rejected."
        ),
    },
    "planner_facts_ref": {
        "targets": ("planner",),
        "statement": (
            "A $facts.<name> reference must name an entry in the NAMED FILE PATHS / "
            "NAMED RECIPIENTS sections - never invent one."
        ),
    },
    "planner_llm_error": {
        "targets": ("planner",),
        "statement": (
            "When the LLM call itself fails, stay within the bounded retries and "
            "report the goal as unplannable - never emit a plan built from a failed "
            "call."
        ),
    },
}


def _lessons_log() -> Path:
    return Path(os.environ.get("FRIDAY_LESSONS_FILE", str(DEFAULT_LESSONS_LOG)))


def _approved_file() -> Path:
    return Path(os.environ.get("FRIDAY_APPROVED_LESSONS", str(DEFAULT_APPROVED)))


def _candidates_dir() -> Path:
    return Path(os.environ.get("FRIDAY_PROPOSED_LESSONS_DIR", str(DEFAULT_CANDIDATES)))


# ---------------------------------------------------------------- record


def record_lesson_event(
    *,
    category: str,
    detail: str,
    source: str,
    primitive: str | None = None,
    goal_id: str | None = None,
) -> str:
    """Append one structured lesson event. Returns the event_id. NEVER
    raises - best-effort by design (a broken lessons file must never break
    the gate, the planner, or the digest). The detail is truncated to
    _DETAIL_MAX characters; category is accepted as-is (generalize only
    produces candidates for categories in CATEGORIES, so an unregistered
    category is recorded but never auto-proposed)."""
    event_id = f"{time.time_ns():x}{len(detail) % 97:02x}"
    rec: dict[str, Any] = {
        "event_id": event_id,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "category": category,
        "source": source,
        "detail": detail[:_DETAIL_MAX],
    }
    if primitive is not None:
        rec["primitive"] = primitive
    if goal_id is not None:
        rec["goal_id"] = goal_id
    try:
        path = _lessons_log()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass  # additive only - the rejection already happened elsewhere
    return event_id


def all_events() -> list[dict[str, Any]]:
    """Every recorded lesson event, in file order. Malformed/truncated
    lines are skipped, never raised on - a partial append must not crash
    generalize()."""
    try:
        raw = _lessons_log().read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    out: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


# ------------------------------------------------------------ approve


def _load_approved() -> tuple[list[dict[str, Any]], list[str]]:
    """The approved store: a human-edited JSON object {"lessons": [...]},
    each lesson {category, statement, targets, ...}. Returns
    (valid_lessons, invalid_reasons) - invalid entries are reported by
    --check and silently excluded from injection (fail-open: a malformed
    store must never break a prompt)."""
    path = _approved_file()
    if not path.is_file():
        return [], []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        # UnicodeDecodeError included deliberately: read_text raises it on
        # invalid UTF-8 bytes, and a single bad byte in the approved store
        # must degrade to an empty block, never crash the planner/triage/
        # digest (the same resilience all_events and all_gaps already have)
        return [], [f"{path} is not valid JSON: {exc}"]
    if not isinstance(data, dict) or not isinstance(data.get("lessons"), list):
        return [], [f"{path} must be a JSON object with a 'lessons' list"]
    valid: list[dict[str, Any]] = []
    invalid: list[str] = []
    for i, entry in enumerate(data["lessons"]):
        if not isinstance(entry, dict):
            invalid.append(f"lessons[{i}]: not an object")
            continue
        category = entry.get("category")
        statement = entry.get("statement")
        targets = entry.get("targets")
        if not isinstance(category, str) or not category.strip():
            invalid.append(f"lessons[{i}]: missing non-empty 'category'")
            continue
        if not isinstance(statement, str) or not statement.strip():
            invalid.append(f"lessons[{i}] ({category}): missing non-empty 'statement'")
            continue
        if (
            not isinstance(targets, list)
            or not targets
            or not all(t in TARGETS for t in targets)
        ):
            invalid.append(
                f"lessons[{i}] ({category}): 'targets' must be a non-empty list of {TARGETS}"
            )
            continue
        valid.append(entry)
    return valid, invalid


def approved_lessons() -> list[dict[str, Any]]:
    """The valid approved lessons, in file order. Fail-open: invalid
    entries are excluded (see --check for the reasons)."""
    valid, _ = _load_approved()
    return valid


def render_known_mistakes(target: str, limit: int = INJECT_LIMIT) -> str:
    """The bounded 'KNOWN MISTAKES' block for one prompt target, or "" when
    there are no approved lessons for it. Never raises - a broken store
    degrades to an empty block, never a broken prompt."""
    lessons = [l for l in approved_lessons() if target in l.get("targets", [])][:limit]
    if not lessons:
        return ""
    lines = ["## KNOWN MISTAKES (approved lessons - do not repeat these):"]
    lines += [f"{i}. {l['statement']}" for i, l in enumerate(lessons, 1)]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------- generalize


def candidate_path(category: str) -> Path:
    """<candidates dir>/<category>.md - the reviewable proposal for one
    category; a sibling <category>.events.json tracks covered events so a
    candidate is never regenerated for evidence it already covers."""
    return _candidates_dir() / f"{category}.md"


def _covered_ids(category: str) -> set[str]:
    sidecar = _candidates_dir() / f"{category}.events.json"
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        return set(data.get("event_ids", []))
    except (OSError, json.JSONDecodeError):
        return set()


def _write_candidate(category: str, events: list[dict[str, Any]], covered: set[str]) -> bool:
    """Write the candidate .md + events sidecar. Returns True when both
    files were actually written - generalize() must not report a candidate
    that failed to write (honesty about state, like every other layer)."""
    meta = CATEGORIES[category]
    d = _candidates_dir()
    d.mkdir(parents=True, exist_ok=True)
    rows = sorted(events, key=lambda e: e.get("timestamp", ""))
    evidence = "\n".join(
        f"- {e.get('timestamp', '?')} [{e.get('source', '?')}] {e.get('detail', '')}"
        for e in rows
    )
    targets = ", ".join(meta["targets"])
    body = f"""# Candidate lesson: {category}

STATUS: PROPOSED - NOT approved. A lesson is a proposal until a human adds
it to the approved store; nothing in the event log reaches any prompt on
its own.

## Proposed statement (injected into the {targets} prompt(s) on approval)

> {meta['statement']}

## Evidence ({len(rows)} recorded event(s))

{evidence}

## To approve (the human gate)

Edit config/lessons.json - the act of editing that file IS the approval,
same philosophy as APPROVED.md for primitives. Add:

    {{
      "category": "{category}",
      "targets": ["{meta['targets'][0]}"],
      "statement": "<your reviewed wording - edit freely, this text is what gets injected>"
    }}

A wrong or over-general lesson injected into every future prompt is worse
than none - rewrite the statement in your own words, then add it. To
reject, delete this file (and its {category}.events.json sidecar): the
events then re-candidate when new evidence arrives.
"""
    try:
        (d / f"{category}.md").write_text(body, encoding="utf-8")
        (d / f"{category}.events.json").write_text(
            json.dumps({"category": category, "event_ids": sorted(covered)}, indent=2) + "\n",
            encoding="utf-8",
        )
        return True
    except OSError:
        return False  # best-effort: an unwritable candidates dir never breaks anything


def generalize(min_examples: int = MIN_EXAMPLES, limit: int | None = None) -> list[str]:
    """Group recorded events by category and (re)write a candidate for
    every category with >= min_examples events and at least one event not
    yet covered by an existing candidate. Returns the candidate files
    written. Idempotent by construction."""
    by_cat: dict[str, list[dict[str, Any]]] = {}
    unknown: list[str] = []
    for e in all_events():
        # events without a usable event_id cannot be coverage-tracked and
        # would read as forever-fresh (None is never in the covered set),
        # rewriting a candidate on every run - skip them like all_events
        # skips malformed lines
        if not isinstance(e.get("event_id"), str) or not e["event_id"]:
            continue
        cat = e.get("category", "?")
        if cat in CATEGORIES:
            by_cat.setdefault(cat, []).append(e)
        else:
            unknown.append(cat)
    written: list[str] = []
    for cat in sorted(by_cat):
        if limit is not None and len(written) >= limit:
            break
        events = by_cat[cat]
        if len(events) < min_examples:
            continue
        covered = _covered_ids(cat)
        fresh = [e for e in events if e.get("event_id") not in covered]
        if not fresh:
            continue
        if _write_candidate(cat, events, covered | {e.get("event_id") for e in fresh}):
            written.append(str(candidate_path(cat)))
    if unknown:
        print(f"  (skipped {len(unknown)} event(s) in unregistered categories: {sorted(set(unknown))})")
    return written


# ------------------------------------------------------------------ CLI


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Friday lessons loop - record, generalize, inject (draft-only except --record)")
    ap.add_argument("--record", action="store_true", help="record one lesson event (e.g. a human-observed category)")
    ap.add_argument("--category", default="", help="event/candidate category")
    ap.add_argument("--detail", default="", help="event detail (recorded, truncated)")
    ap.add_argument("--source", default="manual", help="event source for --record")
    ap.add_argument("--list", action="store_true", help="print approved lessons (the injected set)")
    ap.add_argument("--events", action="store_true", help="print recent raw events")
    ap.add_argument("--check", action="store_true", help="validate the approved store and report invalid entries")
    ap.add_argument("--min-examples", type=int, default=MIN_EXAMPLES, help="min events for a candidate")
    ap.add_argument("--limit", type=int, default=None, help="max candidates to write")
    args = ap.parse_args(argv)

    if args.record:
        if not args.category or not args.detail:
            print("ERROR: --record requires --category and --detail")
            return 2
        eid = record_lesson_event(category=args.category, detail=args.detail, source=args.source)
        print(f"recorded {args.category} event {eid} -> {_lessons_log()}")
        return 0
    if args.list:
        lessons = approved_lessons()
        if not lessons:
            print("no approved lessons")
            return 0
        for i, l in enumerate(lessons, 1):
            print(f"{i}. [{', '.join(l.get('targets', []))}] {l.get('category')}: {l['statement']}")
        return 0
    if args.events:
        events = all_events()
        if not events:
            print("no recorded lesson events")
            return 0
        for e in events[-20:]:
            print(f"{e.get('timestamp', '?')[:19]} {e.get('category', '?'):24s} [{e.get('source', '?')}] {e.get('detail', '')[:90]}")
        return 0
    if args.check:
        valid, invalid = _load_approved()
        print(f"approved store: {len(valid)} valid lesson(s), {len(invalid)} problem(s)")
        for reason in invalid:
            print(f"  INVALID: {reason}")
        return 0 if not invalid else 1

    by_cat: dict[str, int] = {}
    for e in all_events():
        by_cat[e.get("category", "?")] = by_cat.get(e.get("category", "?"), 0) + 1
    print(f"recorded lesson events by category ({len(by_cat)} category/categories):")
    for cat, n in sorted(by_cat.items()):
        print(f"  {cat:28s} {n}")
    written = generalize(min_examples=args.min_examples, limit=args.limit)
    print(f"candidates written: {len(written)} -> {_candidates_dir()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
