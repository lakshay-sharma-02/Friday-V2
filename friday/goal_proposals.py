"""goal_proposals - the goals-proposal stage of the self-improvement loop.

The gap loop proposes new PRIMITIVES when a goal is refused; the lessons
loop makes rejections stick. This module is the third stage: Friday
proposes new TRIGGERS (scheduled goals) from its own failure history -
the "propose goals on its own" half that was still open. It mines
var/logs/tasks.jsonl (FRIDAY_TASKS_FILE overrides) and the L0 log
(var/logs/friday.jsonl, FRIDAY_LOG_FILE overrides) and turns clusters of
recurring FAILED goals into reviewable, INERT trigger proposals under
gates/proposed_triggers/<id>/ (FRIDAY_PROPOSED_TRIGGERS_DIR overrides):

    trigger.json   a fully watcher-validated trigger object, ALWAYS with
                   "enabled": false and an empty "allow" by default -
                   nothing can run until a human grants scope
    rationale.md   the quoted evidence: the verbatim goal, how many times
                   it failed, when, which task ids, any WATCH-layer L0
                   failures for the same goal, and a prominent warning
                   that the goal HAS FAILED N TIMES - review why before
                   enabling

What gets mined (deliberately narrow, honest v1):

  - tasks.jsonl records with gate6_passed=false, EXCLUDING allowlist
    REFUSED records (a refusal is a deliberate terminal outcome - the
    probes generate them on purpose) and the ambient-gap-probe task ids.
  - Goals grouped by normalized text; a cluster needs >= MIN_RECURRENCE
    (2) failed runs inside the window to become a candidate - one-off
    proof-run failures are not a pattern.
  - Deduped against triggers already in config/watcher.json (FRIDAY_WATCHER_CONFIG
    overrides; a cluster whose goal is textually covered by an existing
    trigger - e.g. the gmail-summary failures are covered by the enabled
    morning-gmail-summary trigger - is SKIPPED) and against proposal dirs
    that already exist (idempotent coverage, like proposed_primitives).
  - The L0 log contributes (a) WATCH-layer trigger failures whose goal
    matches the cluster (direct evidence) and (b) a global failure-signature
    summary in the run output and rationale appendix - the signal for
    primitives that fail often WITHOUT a goal cluster behind them.

The drafted goal is ALWAYS the verbatim quoted goal - never an LLM
rewrite (a rewritten goal is exactly the provenance-confabulation risk
this project learned to guard against). The LLM (optional --llm, off by
default for cost) drafts only id/schedule/allowlist/rationale; a strict
validator falls back to deterministic defaults (daily 09:00 mon-fri,
allow []) on any failure.

SAFETY: nothing here ever writes config/watcher.json. A proposal is
approved by the same human gate as every other artifact: copy
trigger.json into config/watcher.json, review and expand the allowlist,
and only then flip "enabled" to true. A recurring-FAILURE goal is
flagged in the rationale as such - it is proposed for the human to judge
(watch it? fix it? reject it?), never silently scheduled.

Run:  ./.venv/bin/python -m friday.goal_proposals [--limit N] [--days 14]
      [--min-recurrence 2] [--dry-run] [--llm]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASKS_FILE = ROOT / "var" / "logs" / "tasks.jsonl"
DEFAULT_LOG_FILE = ROOT / "var" / "logs" / "friday.jsonl"
DEFAULT_CONFIG = ROOT / "config" / "watcher.json"
DEFAULT_PROPOSALS = ROOT / "gates" / "proposed_triggers"

MIN_RECURRENCE = 2
DEFAULT_DAYS = 14
DEFAULT_TIME = "09:00"
DEFAULT_DAYS_OF_WEEK = ["mon", "tue", "wed", "thu", "fri"]
_MAX_ID_LEN = 40
_ALLOW_NONE: list[str] = []  # the safe default: nothing may run until granted

# Words too generic to distinguish one goal from another - only
# significant tokens count toward goal-overlap dedupe.
_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "for",
    "with",
    "from",
    "my",
    "me",
    "i",
    "it",
    "at",
    "on",
    "is",
    "are",
    "was",
    "were",
    "this",
    "that",
    "then",
    "any",
    "all",
    "new",
    "your",
    "you",
    "s",
    "t",
    "if",
    "do",
    "be",
    "by",
    "as",
    "its",
    "them",
    "their",
}

# Fraction of the smaller goal's significant tokens that must overlap an
# existing trigger's goal for the cluster to count as SOLVED (never
# re-propose what already exists). Substring containment is also checked
# first. 0.5 is deliberately conservative: a near-duplicate goal IS a
# duplicate - the human reviews intent anyway.
_COVER_THRESHOLD = 0.5


def _tasks_file() -> Path:
    return Path(os.environ.get("FRIDAY_TASKS_FILE", str(DEFAULT_TASKS_FILE)))


def _log_file() -> Path:
    return Path(os.environ.get("FRIDAY_LOG_FILE", str(DEFAULT_LOG_FILE)))


def _config_file() -> Path:
    return Path(os.environ.get("FRIDAY_WATCHER_CONFIG", str(DEFAULT_CONFIG)))


def _proposals_dir() -> Path:
    return Path(os.environ.get("FRIDAY_PROPOSED_TRIGGERS_DIR", str(DEFAULT_PROPOSALS)))


# ------------------------------------------------------------------ read


def read_tasks() -> list[dict[str, Any]]:
    """Every task record, in file order. Malformed/truncated lines are
    skipped, never raised on - the same resilience as all_gaps()."""
    try:
        raw = _tasks_file().read_text(encoding="utf-8")
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


def read_l0_failures() -> list[dict[str, Any]]:
    """FAILED/ABORT lines from the L0 log. Malformed lines are skipped."""
    try:
        raw = _log_file().read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    out: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("result") in ("FAILED", "ABORT"):
            out.append(d)
    return out


def _parse_ts(value: Any) -> datetime | None:
    """ISO timestamp -> aware datetime (naive is assumed UTC). None when
    unparseable - an unparseable timestamp is treated as in-window."""
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _in_window(ts: Any, window: timedelta | None) -> bool:
    if window is None:
        return True
    dt = _parse_ts(ts)
    if dt is None:
        return True  # cannot prove staleness - keep it
    return datetime.now(UTC) - dt <= window


def _normalize_goal(goal: Any) -> str:
    """Grouping key: lowercase, whitespace collapsed, trailing punctuation
    dropped. Goals that differ only in case/spacing group together."""
    if not isinstance(goal, str):
        return ""
    return re.sub(r"\s+", " ", goal.strip().lower()).rstrip(".!?;:")


def _task_is_probe(task_id: Any) -> bool:
    return isinstance(task_id, str) and "ambient-gap-probe" in task_id


def _task_was_refused(rec: dict[str, Any]) -> bool:
    """An allowlist REFUSED record (deliberate terminal outcome) is not a
    failure to mine - the probe refusals generate these on purpose."""
    proof = rec.get("proof")
    if isinstance(proof, str):
        try:
            proof = json.loads(proof)
        except json.JSONDecodeError:
            return False
    return isinstance(proof, dict) and proof.get("status") == "REFUSED"


def existing_triggers() -> list[dict[str, Any]]:
    """The watcher's real triggers, validated through the real loader.
    An unreadable/invalid config degrades to [] - a broken config must
    never crash the proposal stage (the watcher itself will complain)."""
    from friday.watcher import load_config

    try:
        return load_config(_config_file())
    except Exception:
        return []


def _sig_tokens(goal: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", goal.lower()) if len(t) >= 3 and t not in _STOPWORDS}


def _goal_covered(goal: str, triggers: list[dict[str, Any]]) -> bool:
    """A cluster goal is SOLVED when any existing trigger's goal covers it:
    normalized substring containment either direction, OR a significant-
    token overlap of >= _COVER_THRESHOLD of the smaller goal's tokens
    (the gmail-summary failures are covered by the enabled
    morning-gmail-summary trigger even though the sender text differs -
    "accounts.google.com" vs "$facts.gmail_sender"). Never propose a
    trigger that already exists."""
    n = _normalize_goal(goal)
    if not n:
        return False
    nt = _sig_tokens(n)
    for t in triggers:
        tg = _normalize_goal(t.get("goal"))
        if not tg:
            continue
        if n in tg or tg in n:
            return True
        tt = _sig_tokens(tg)
        if nt and tt:
            overlap = len(nt & tt) / min(len(nt), len(tt))
            if overlap >= _COVER_THRESHOLD:
                return True
    return False


def existing_trigger_ids() -> set[str]:
    return {str(tid) for t in existing_triggers() if isinstance(tid := t.get("id"), str)}


# ------------------------------------------------------------------ mine


def mine(
    days: int = DEFAULT_DAYS,
    min_recurrence: int = MIN_RECURRENCE,
    l0: list[dict[str, Any]] | None = None,
    triggers: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Cluster recurring FAILED goals into candidates. Returns a list of
    cluster dicts, best first (most failures, then most recent):
    {goal, occurrences, task_ids, timestamps, last_failed_at, l0_evidence}.
    `triggers` may be passed in to avoid re-reading the watcher config
    (the caller already loaded it for id-dedupe)."""
    window = timedelta(days=days) if days and days > 0 else None
    tasks = read_tasks()
    l0 = read_l0_failures() if l0 is None else l0

    clusters: dict[str, dict[str, Any]] = {}
    for rec in tasks:
        if rec.get("gate6_passed"):
            continue
        if _task_was_refused(rec) or _task_is_probe(rec.get("task_id")):
            continue
        if not _in_window(rec.get("timestamp"), window):
            continue
        goal = rec.get("goal")
        key = _normalize_goal(goal)
        if not key:
            continue
        c = clusters.setdefault(
            key,
            {"goal": goal, "occurrences": 0, "task_ids": [], "timestamps": []},
        )
        c["occurrences"] += 1
        c["task_ids"].append(rec.get("task_id", "?"))
        c["timestamps"].append(rec.get("timestamp", "?"))

    triggers = existing_triggers() if triggers is None else triggers
    covered = 0
    candidates: list[dict[str, Any]] = []
    for key, c in clusters.items():
        if c["occurrences"] < min_recurrence:
            continue
        if _goal_covered(c["goal"], triggers):
            covered += 1
            continue
        try:
            c["last_failed_at"] = max(ts for ts in c["timestamps"] if _parse_ts(ts) is not None)
        except ValueError:
            c["last_failed_at"] = c["timestamps"][-1]
        # WATCH-layer L0 failures for this exact goal are direct evidence;
        # everything else is the global failure-signature summary.
        c["l0_evidence"] = [
            d
            for d in l0
            if d.get("layer") == "WATCH"
            and d.get("primitive") == "trigger"
            and _normalize_goal((d.get("args") or {}).get("goal")) == key
        ]
        candidates.append(c)

    candidates.sort(
        key=lambda c: (c["occurrences"], str(c.get("last_failed_at", ""))),
        reverse=True,
    )
    return candidates


def l0_failure_summary(
    l0: list[dict[str, Any]] | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Top recurring FAILED/ABORT signatures (layer, primitive, exception
    fragment) - the environment-wide signal the human sees alongside the
    goal clusters. Not a trigger source by itself in v1 (a reliability
    watch would need a new primitive, which is the gap loop's job)."""
    l0 = read_l0_failures() if l0 is None else l0
    counts: dict[tuple[str, str, str], int] = {}
    for d in l0:
        exc = str(d.get("exception") or "")[:80]
        key = (str(d.get("layer")), str(d.get("primitive")), exc)
        counts[key] = counts.get(key, 0) + 1
    top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [{"layer": k[0], "primitive": k[1], "exception": k[2], "count": v} for k, v in top]


# ------------------------------------------------------------------ draft


def _slug(goal: str) -> str:
    """Deterministic trigger id from the goal: lowercase, non-alnum -> '-',
    collapsed, capped. '' fallback for a goal that slugs to nothing."""
    s = re.sub(r"[^a-z0-9]+", "-", _normalize_goal(goal)).strip("-")[:_MAX_ID_LEN]
    return s or "proposed-goal"


def _unique_id(goal: str, taken: set[str]) -> str:
    base = _slug(goal)
    if base not in taken:
        return base
    i = 2
    while f"{base}-{i}" in taken:
        i += 1
    return f"{base}-{i}"


_DRAFT_TMPL = """You are proposing ONE new Friday watcher trigger (a scheduled
goal) from real evidence. The goal is QUOTED EVIDENCE - never rewrite or
reword it, use it verbatim. Reply with ONLY a JSON object (no markdown):
{{"id": str, "schedule": {{"type": "time", "at": "HH:MM", "days": [day names]}},
"allow": [primitive patterns], "rationale_note": str}}

REAL FAILURE EVIDENCE (the goal failed {n} times):
{evidence}

RULES:
- "id": a short kebab-case slug of the goal.
- "schedule": a sensible time for a recurring goal of this kind.
- "allow": a conservative primitive allowlist (module.* patterns) - the
  human will review it; prefer read-only scopes. Empty list is allowed.
- "rationale_note": one plain sentence on why this recurring failure is
  worth watching or fixing.
"""


def _draft_llm(cluster: dict[str, Any]) -> dict[str, Any] | None:
    """One LLM draft of id/schedule/allow/rationale_note (goal stays
    verbatim). Returns None when unparseable/invalid - the caller falls
    back to deterministic defaults. Unlogged, same discipline as triage.
    Parsing reuses gap_triage._extract_json (fence-tolerant, first-object)
    instead of a fragile raw json.loads."""
    from friday.gap_triage import _extract_json
    from friday.l1.dev import MODEL_ALIAS, _run_claude

    evidence = "\n".join(
        f"- {ts} {tid}" for ts, tid in zip(cluster["timestamps"], cluster["task_ids"], strict=True)
    )
    prompt = _DRAFT_TMPL.format(n=cluster["occurrences"], evidence=evidence)
    try:
        res = _run_claude(prompt, None, 120, MODEL_ALIAS, False)
        raw = res.get("result") if isinstance(res, dict) else res
        text = raw if isinstance(raw, str) else (json.dumps(raw) if raw else "")
        draft = _extract_json(text)
        if draft is None:
            return None
        if not isinstance(draft.get("id"), str) or not draft["id"].strip():
            return None
        if not isinstance(draft.get("schedule"), dict):
            return None
        if not isinstance(draft.get("allow"), list) or not all(
            isinstance(a, str) and a.strip() for a in draft["allow"]
        ):
            return None
        return draft
    except Exception:
        return None


def _draft_trigger(
    cluster: dict[str, Any],
    *,
    use_llm: bool = False,
    taken_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Build the INERT trigger proposal: the verbatim goal, a schedule and
    allowlist (LLM-drafted when --llm and valid, else deterministic
    defaults), always "enabled": false, always watcher-validated. The
    allowlist defaults to [] so NOTHING can run until a human grants
    scope."""
    taken = set(taken_ids or existing_trigger_ids())
    trigger: dict[str, Any] = {
        "id": _unique_id(cluster["goal"], taken),
        "goal": cluster["goal"],  # verbatim quoted evidence - never rewritten
        "schedule": {"type": "time", "at": DEFAULT_TIME, "days": list(DEFAULT_DAYS_OF_WEEK)},
        "allow": list(_ALLOW_NONE),
        "notify": True,
        "enabled": False,  # inert until a human approves + grants scope
    }
    if use_llm:
        draft = _draft_llm(cluster)
        if draft is not None:
            candidate = dict(trigger)
            candidate["id"] = _unique_id(cluster["goal"], taken | {trigger["id"]})
            candidate["schedule"] = draft["schedule"]
            candidate["allow"] = draft["allow"]
            if isinstance(draft.get("rationale_note"), str):
                candidate["_draft_note"] = draft["rationale_note"][:300]
            # validate strictly against the REAL watcher schema; a bad LLM
            # draft falls back to deterministic (never partially applied)
            from friday.watcher import _validate_trigger

            try:
                _validate_trigger(candidate, set())
                if candidate["schedule"].get("type") == "time":
                    trigger = candidate
            except Exception:
                pass
    # final safety assertion: proposals are inert by construction
    from friday.watcher import _validate_trigger

    trigger["enabled"] = False
    _validate_trigger(trigger, set())
    return trigger


# ---------------------------------------------------------------- propose


def proposal_dir(trigger_id: str) -> Path:
    return _proposals_dir() / re.sub(r"[^A-Za-z0-9_.-]", "_", trigger_id)


def _write_proposal(cluster: dict[str, Any], trigger: dict[str, Any]) -> Path:
    d = proposal_dir(trigger["id"])
    d.mkdir(parents=True, exist_ok=True)
    # the artifact a human copies into config must be CLEAN - the LLM's
    # rationale note is documentation, not a watcher field, so it is kept
    # in the rationale.md only, never in trigger.json
    on_disk = {k: v for k, v in trigger.items() if not k.startswith("_")}
    (d / "trigger.json").write_text(
        json.dumps(on_disk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    draft_note = trigger.get("_draft_note")
    note_row = f"\nLLM draft note: {draft_note}\n" if draft_note else ""
    l0_rows = (
        "\n".join(
            f"- {e.get('timestamp', '?')[:19]} WATCH trigger FAILED: "
            f"{(e.get('extra') or {}).get('status') or e.get('result')!s} "
            f"{str(e.get('exception') or '')[:120]}"
            for e in cluster.get("l0_evidence", [])[-6:]
        )
        or "  (no matching WATCH-layer L0 failures)"
    )
    rationale = f"""# Proposed trigger: {trigger["id"]}

STATUS: PROPOSED - NOT approved, and INERT. This trigger is proposed by
Friday from its own failure history; nothing runs until YOU approve it.

## The goal (verbatim quoted evidence - never rewritten)

> {trigger["goal"]}

## WARNING: this goal has FAILED {cluster["occurrences"]} time(s)

It is proposed precisely BECAUSE it kept failing - review WHY before you
ever enable it. It is not silently scheduled; the human gate is the whole
point of this stage.

## Evidence

- failed {cluster["occurrences"]} time(s): {", ".join(cluster["task_ids"])}
- last failure: {cluster.get("last_failed_at", "?")}
- failure timestamps:
{chr(10).join("  - " + ts for ts in cluster["timestamps"])}

WATCH-layer L0 failures for this exact goal:
{l0_rows}
{note_row}
## The draft trigger (watcher-validated, enabled: false)

```json
{json.dumps(on_disk, ensure_ascii=False, indent=2)}
```

Note: "allow" is empty by design - with no allowlist the trigger would
refuse every step, so it cannot act until you grant each primitive scope.
The draft goal is quoted evidence; if you approve it, review the goal
text and the schedule too.

## To approve (the human gate - same philosophy as APPROVED.md)

1. Copy trigger.json into config/watcher.json (inside "triggers").
2. Expand "allow" to the primitives this goal legitimately needs
   (e.g. ["gmail.*"]); an empty allowlist is a refusal-only trigger.
3. Review the goal text and schedule.
4. Flip "enabled" to true. Until then this proposal changes nothing.
To reject, delete this directory - the cluster then re-candidates when
new failures arrive.
"""
    (d / "rationale.md").write_text(rationale, encoding="utf-8")
    return d


def propose(
    *,
    limit: int | None = None,
    days: int = DEFAULT_DAYS,
    min_recurrence: int = MIN_RECURRENCE,
    use_llm: bool = False,
    dry_run: bool = False,
) -> list[str]:
    """Mine -> draft -> write one proposal dir per cluster. Idempotent: a
    cluster whose proposal dir already exists is skipped (covered). Never
    touches config/watcher.json. Returns the proposal dirs written (or
    the would-be dirs in dry-run mode)."""
    # load the watcher config ONCE and thread it through - mine() dedupes
    # against it and _draft_trigger needs the taken ids
    triggers = existing_triggers()
    clusters = mine(days=days, min_recurrence=min_recurrence, triggers=triggers)
    written: list[str] = []
    taken = {t["id"] for t in triggers if isinstance(t.get("id"), str)}
    for c in clusters:
        if limit is not None and len(written) >= limit:
            break
        trigger = _draft_trigger(c, use_llm=use_llm, taken_ids=taken)
        d = proposal_dir(trigger["id"])
        if (d / "trigger.json").is_file():
            continue  # covered - never re-propose a goal already proposed
        taken.add(trigger["id"])
        if dry_run:
            print(
                f"  WOULD propose {trigger['id']} ({c['occurrences']} failures): {c['goal'][:60]}"
            )
        else:
            _write_proposal(c, trigger)
        written.append(str(d))
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Friday goals-proposal stage (mine failures -> inert trigger proposals)"
    )
    ap.add_argument("--limit", type=int, default=None, help="max proposals to write")
    ap.add_argument(
        "--days", type=int, default=DEFAULT_DAYS, help="failure window in days (0 = all)"
    )
    ap.add_argument(
        "--min-recurrence", type=int, default=MIN_RECURRENCE, help="min failed runs for a cluster"
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="print what would be proposed, write nothing"
    )
    ap.add_argument(
        "--llm", action="store_true", help="LLM-draft schedules/allowlists (off by default - cost)"
    )
    args = ap.parse_args(argv)

    clusters = mine(days=args.days, min_recurrence=args.min_recurrence)
    summary = l0_failure_summary()
    print(f"recurring-failure clusters: {len(clusters)}")
    for c in clusters:
        print(f"  {c['occurrences']}x {c['goal'][:70]} (last {str(c.get('last_failed_at'))[:16]})")
    print("top L0 failure signatures (context, not a trigger source by itself):")
    for s in summary[:5]:
        print(f"  {s['count']:3d}  {s['layer']}/{s['primitive']}  {s['exception'][:70]}")
    written = propose(
        limit=args.limit,
        days=args.days,
        min_recurrence=args.min_recurrence,
        use_llm=args.llm,
        dry_run=args.dry_run,
    )
    print(
        f"{'would propose' if args.dry_run else 'proposed'}: {len(written)} -> {_proposals_dir()}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
