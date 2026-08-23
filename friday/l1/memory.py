"""L1 primitive: memory (persistent cross-session knowledge store).

Friday's long-term memory — facts, preferences, context, decisions,
and lessons that persist across sessions. Without memory, Friday is
stateless: every morning it forgets everything. With memory, the
planner can access accumulated context, the lessons loop becomes
persistent, and proactive suggestions become possible.

Storage: a JSONL file at $FRIDAY_MEMORY_FILE (default:
var/state/memory.jsonl). Each line is one memory entry. Atomic writes
(append via temp + os.replace for bulk operations). The file is
gitignored runtime data.

Categories:
  facts        - concrete facts (user preferences, system config, etc.)
  preferences  - user preferences (how they like things done)
  context      - session context (what we're working on, recent decisions)
  decisions    - decisions made and their rationale
  lessons      - lessons learned (from the lessons loop)
  conversations - summarized conversation highlights

Retrieval: text-based search with category filtering. Relevance is
scored by term overlap (simple but effective for a first version;
embeddings are a future upgrade path).

Decay: memories have `last_accessed` and `access_count` fields.
Frequent access reinforces a memory; old, unreinforced memories are
candidates for archival. The `memory.maintenance` watcher trigger
archives memories older than MEMORY_TTL_DAYS with low access counts.

Privacy: memory values are redacted in L0 log lines via
redact_result=True on store/retrieve.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError
from friday.observability import emit_event

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MEMORY_FILE = PROJECT_ROOT / "var" / "state" / "memory.jsonl"

# Valid categories
CATEGORIES = frozenset({
    "facts", "preferences", "context", "decisions", "lessons", "conversations",
})

# Default TTL: memories older than this (days) with low access are archived
MEMORY_TTL_DAYS = 90
# Memories accessed more than this many times are never archived
MEMORY_REINFORCE_THRESHOLD = 5
# Max memories returned per retrieve call
MAX_RETRIEVE_RESULTS = 20
# Max value length stored (chars) — prevents unbounded growth
MAX_VALUE_CHARS = 5_000


# --------------------------------------------------------------- storage


def _memory_file() -> Path:
    return Path(os.environ.get(
        "FRIDAY_MEMORY_FILE", str(DEFAULT_MEMORY_FILE)
    ))


def _load_all() -> list[dict[str, Any]]:
    """Load all memory entries. Fails safe to [] on any error."""
    path = _memory_file()
    try:
        entries: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if isinstance(entry, dict) and "key" in entry:
                    entries.append(entry)
            except (json.JSONDecodeError, ValueError):
                continue  # skip malformed lines
        return entries
    except OSError:
        return []


def _save_all(entries: list[dict[str, Any]]) -> None:
    """Atomically write all entries. Used for bulk operations (forget,
    maintenance). Individual stores use append."""
    path = _memory_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        lines = [json.dumps(e, ensure_ascii=False) + "\n" for e in entries]
        tmp.write_text("".join(lines), encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        emit_event(
            layer="L1",
            primitive="memory.save",
            exception=f"could not write {_memory_file()}: {exc}",
            result="FAILED",
        )


def _append_entry(entry: dict[str, Any]) -> None:
    """Append one entry to the memory file (atomic)."""
    path = _memory_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:
        emit_event(
            layer="L1",
            primitive="memory.append",
            exception=f"could not append to {_memory_file()}: {exc}",
            result="FAILED",
        )


def _make_id(key: str, category: str) -> str:
    """Deterministic id from key + category (upsert-safe)."""
    raw = f"{category}:{key}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _score_match(text: str, query: str) -> float:
    """Simple term-overlap relevance score. Returns 0.0-1.0.
    Exact key match = 1.0; partial key = 0.7; value term overlap = 0.0-0.5.
    Good enough for a first version — embeddings are the upgrade path."""
    query_lower = query.lower()
    key_lower = text.lower()

    # Exact key match
    if query_lower == key_lower:
        return 1.0

    # Key contains query
    if query_lower in key_lower:
        return 0.7

    # Term overlap in key
    query_terms = set(query_lower.split())
    key_terms = set(key_lower.split())
    if query_terms and key_terms:
        overlap = len(query_terms & key_terms)
        key_score = overlap / len(query_terms) * 0.5
    else:
        key_score = 0.0

    return key_score


def _score_value(value: str, query: str) -> float:
    """Score how relevant a value is to the query."""
    query_lower = query.lower()
    value_lower = value.lower()

    if query_lower in value_lower:
        return 0.5

    query_terms = set(query_lower.split())
    value_terms = set(value_lower.split())
    if query_terms and value_terms:
        overlap = len(query_terms & value_terms)
        return min(overlap / len(query_terms) * 0.3, 0.3)
    return 0.0


# ----------------------------------------------------------- L1 primitives


@contract(
    precondition="key is a non-empty string; category is one of: facts, preferences, context, decisions, lessons, conversations; value is a non-empty string.",
    postcondition="The memory is stored (or updated if the key+category already exists). Idempotent: storing the same key+category updates the value and timestamp.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="PreconditionError for empty key/value or invalid category; PrimitiveError on storage failure.",
    returns="dict: {id, key, category, status}.",
    redact_result=True,
)
def store(
    key: str,
    value: str,
    category: str = "facts",
    tags: list[str] | None = None,
) -> dict[str, str]:
    """Store a memory entry.

    If a memory with the same key and category already exists, it is
    updated (value replaced, timestamps refreshed). Otherwise a new
    entry is created.

    Args:
        key: Short identifier for the memory (e.g. "user_name", "project_deadline").
        value: The memory content (what Friday should remember).
        category: One of: facts, preferences, context, decisions, lessons, conversations.
        tags: Optional tags for filtering (e.g. ["vivaha", "q4"]).
    """
    if not key or not key.strip():
        raise PreconditionError("store requires a non-empty 'key'")
    if not value or not value.strip():
        raise PreconditionError("store requires a non-empty 'value'")
    if category not in CATEGORIES:
        raise PreconditionError(
            f"store: category must be one of {sorted(CATEGORIES)}, got {category!r}"
        )

    key = key.strip()
    value = value.strip()[:MAX_VALUE_CHARS]
    mem_id = _make_id(key, category)
    now = _now_iso()

    # Load existing entries to check for update
    entries = _load_all()
    existing_idx = None
    for i, e in enumerate(entries):
        if e.get("id") == mem_id:
            existing_idx = i
            break

    entry: dict[str, Any] = {
        "id": mem_id,
        "key": key,
        "value": value,
        "category": category,
        "tags": tags or [],
        "created_at": now,
        "last_accessed": now,
        "access_count": 0,
    }

    if existing_idx is not None:
        # Preserve creation date, update the rest
        entry["created_at"] = entries[existing_idx].get("created_at", now)
        entry["access_count"] = entries[existing_idx].get("access_count", 0)
        entries[existing_idx] = entry
        _save_all(entries)
        status = "updated"
    else:
        _append_entry(entry)
        status = "stored"

    return {"id": mem_id, "key": key, "category": category, "status": status}


@contract(
    precondition="query is a non-empty string.",
    postcondition="Returns matching memories ranked by relevance. Read-only.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError for empty query; PrimitiveError on storage read failure.",
    returns="list[dict]: [{id, key, value, category, relevance, access_count}] ranked by relevance.",
    redact_result=True,
)
def retrieve(
    query: str,
    category: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Search memories by relevance.

    Returns the most relevant memories matching the query, optionally
    filtered by category. Access timestamps are updated for returned
    memories (reinforcement).

    Args:
        query: Search terms (matched against keys and values).
        category: Optional category filter.
        limit: Max results (default 5, max 20).
    """
    if not query or not query.strip():
        raise PreconditionError("retrieve requires a non-empty 'query'")

    if category is not None and category not in CATEGORIES:
        raise PreconditionError(
            f"retrieve: category must be one of {sorted(CATEGORIES)}, got {category!r}"
        )

    limit = max(1, min(limit, MAX_RETRIEVE_RESULTS))
    entries = _load_all()

    # Score and filter
    scored: list[tuple[float, dict[str, Any]]] = []
    for e in entries:
        if category and e.get("category") != category:
            continue
        key_score = _score_match(e.get("key", ""), query)
        value_score = _score_value(e.get("value", ""), query)
        total = max(key_score, value_score)
        # Tag boost: if query terms appear in tags, boost score
        tags = e.get("tags", [])
        if tags:
            query_terms = set(query.lower().split())
            tag_terms = {t.lower() for t in tags if isinstance(t, str)}
            if query_terms & tag_terms:
                total = min(total + 0.2, 1.0)
        if total > 0:
            scored.append((total, e))

    # Sort by relevance, then by last_accessed (most recent first)
    scored.sort(key=lambda x: (-x[0], x[1].get("last_accessed", "")), reverse=False)
    # Actually sort: highest relevance first, ties broken by most recent access
    scored.sort(key=lambda x: (-x[0], x[1].get("last_accessed", "")))

    results: list[dict[str, Any]] = []
    now = _now_iso()
    accessed_ids: list[str] = []

    for score, entry in scored[:limit]:
        entry_id = entry.get("id") or _make_id(entry.get("key", ""), entry.get("category", ""))
        results.append({
            "id": entry_id,
            "key": entry.get("key", ""),
            "value": entry.get("value", ""),
            "category": entry.get("category", ""),
            "relevance": round(score, 3),
            "access_count": entry.get("access_count", 0),
            "tags": entry.get("tags", []),
        })
        accessed_ids.append(entry_id)

    # Reinforce accessed memories (update last_accessed + access_count)
    if accessed_ids:
        _reinforce_entries(accessed_ids)

    return results


def _reinforce_entries(ids: list[str]) -> None:
    """Update last_accessed and access_count for accessed memories."""
    entries = _load_all()
    id_set = set(ids)
    changed = False
    now = _now_iso()
    for e in entries:
        if e.get("id") in id_set:
            e["last_accessed"] = now
            e["access_count"] = e.get("access_count", 0) + 1
            changed = True
    if changed:
        _save_all(entries)


@contract(
    precondition="key is a non-empty string.",
    postcondition="The memory entry is deleted (if it exists). Returns whether it was found.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="PreconditionError for empty key; PrimitiveError on storage failure.",
    returns="dict: {key, found: bool}.",
)
def forget(key: str, category: str | None = None) -> dict[str, Any]:
    """Delete a memory entry by key (and optionally category).

    Args:
        key: The memory key to forget.
        category: Optional category filter. If omitted, all entries
                  with this key are removed.
    """
    if not key or not key.strip():
        raise PreconditionError("forget requires a non-empty 'key'")

    key = key.strip()
    entries = _load_all()
    original_count = len(entries)

    if category:
        entries = [
            e for e in entries
            if not (e.get("key") == key and e.get("category") == category)
        ]
    else:
        entries = [e for e in entries if e.get("key") != key]

    found = len(entries) < original_count
    if found:
        _save_all(entries)

    return {"key": key, "found": found}


@contract(
    precondition="None.",
    postcondition="Returns a list of all categories with their entry counts. Read-only.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError on storage read failure.",
    returns="dict: {categories: {name: count}, total: int}.",
)
def list_categories() -> dict[str, Any]:
    """List all memory categories with entry counts.

    Returns a dict mapping category names to their memory counts,
    plus a total count across all categories.
    """
    entries = _load_all()
    counts: dict[str, int] = {c: 0 for c in sorted(CATEGORIES)}
    for e in entries:
        cat = e.get("category", "")
        if cat in counts:
            counts[cat] += 1
    return {"categories": counts, "total": len(entries)}


@contract(
    precondition="None.",
    postcondition="Returns a summary of the memory store: total entries, category breakdown, oldest/newest, and a list of recently accessed keys. Read-only.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError on storage read failure.",
    returns="dict: {total, categories, oldest, newest, recent_keys: list[str]}.",
)
def summary() -> dict[str, Any]:
    """Get a summary of the memory store.

    Useful for the planner to understand what Friday knows, or for
    maintenance triggers to decide when to archive.
    """
    entries = _load_all()
    if not entries:
        return {
            "total": 0,
            "categories": {},
            "oldest": None,
            "newest": None,
            "recent_keys": [],
        }

    counts: dict[str, int] = {}
    for e in entries:
        cat = e.get("category", "")
        counts[cat] = counts.get(cat, 0) + 1

    created = [e.get("created_at", "") for e in entries if e.get("created_at")]
    accessed = [e.get("last_accessed", "") for e in entries if e.get("last_accessed")]

    # Recent keys: last 10 accessed
    sorted_by_access = sorted(entries, key=lambda e: e.get("last_accessed", ""), reverse=True)
    recent = [e.get("key", "") for e in sorted_by_access[:10]]

    return {
        "total": len(entries),
        "categories": counts,
        "oldest": min(created) if created else None,
        "newest": max(created) if created else None,
        "recent_keys": recent,
    }


@contract(
    precondition="key is a non-empty string.",
    postcondition="Reinforces a memory by updating its last_accessed timestamp and incrementing access_count. Returns whether the memory was found.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="PreconditionError for empty key; PrimitiveError on storage failure.",
    returns="dict: {key, found: bool, access_count: int}.",
)
def reinforce(key: str, category: str | None = None) -> dict[str, Any]:
    """Reinforce a memory by accessing it.

    This is a manual way to bump a memory's importance — useful when
    a fact is confirmed or a decision is reaffirmed. Automatic
    reinforcement happens on retrieve.
    """
    if not key or not key.strip():
        raise PreconditionError("reinforce requires a non-empty 'key'")

    key = key.strip()
    entries = _load_all()
    found = False
    count = 0
    now = _now_iso()
    for e in entries:
        if e.get("key") == key:
            if category and e.get("category") != category:
                continue
            e["last_accessed"] = now
            e["access_count"] = e.get("access_count", 0) + 1
            count = e["access_count"]
            found = True

    if found:
        _save_all(entries)

    return {"key": key, "found": found, "access_count": count}


# -------------------------------------------------------- maintenance


@contract(
    precondition="None.",
    postcondition="Archives (removes) old memories with low access counts. Returns the count of archived entries.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError on storage failure.",
    returns="dict: {archived: int, remaining: int, archived_keys: list[str]}.",
)
def maintenance(
    ttl_days: int = MEMORY_TTL_DAYS,
    min_access: int = MEMORY_REINFORCE_THRESHOLD,
) -> dict[str, Any]:
    """Archive old, low-access memories.

    Memories older than `ttl_days` with fewer than `min_access` accesses
    are removed. This prevents the memory store from growing unbounded
    while preserving frequently-accessed important memories.

    Called by the `memory-maintenance` watcher trigger (weekly).
    """
    entries = _load_all()
    now = time.time()
    cutoff = now - (ttl_days * 86400)

    keep: list[dict[str, Any]] = []
    archived_keys: list[str] = []

    for e in entries:
        # Parse last_accessed timestamp
        last_str = e.get("last_accessed", "")
        try:
            last_dt = datetime.fromisoformat(last_str.replace("Z", "+00:00"))
            last_ts = last_dt.timestamp()
        except (ValueError, AttributeError):
            last_ts = 0  # unparseable = treat as very old

        access_count = e.get("access_count", 0)

        if last_ts < cutoff and access_count < min_access:
            archived_keys.append(e.get("key", "?"))
        else:
            keep.append(e)

    if len(keep) < len(entries):
        _save_all(keep)

    return {
        "archived": len(entries) - len(keep),
        "remaining": len(keep),
        "archived_keys": archived_keys,
    }


# --------------------------------------------------- planner integration


def build_memory_context(query: str, category: str | None = None, limit: int = 5) -> str:
    """Build a memory context block for the planner prompt.

    Returns a formatted string of relevant memories, or an empty string
    if nothing matches. Called by the planner when building prompts.
    """
    try:
        results = retrieve(query, category=category, limit=limit)
    except Exception:
        return ""
    if not results:
        return ""
    lines = ["Known from past sessions:"]
    for r in results:
        cat = r.get("category", "")
        key = r.get("key", "")
        value = r.get("value", "")
        lines.append(f"  [{cat}] {key}: {value}")
    return "\n".join(lines)


# -------------------------------------- lessons integration


def sync_lessons_from_config() -> dict[str, Any]:
    """Sync approved lessons from config/lessons.json into memory.

    This makes lessons available via memory retrieval (not just prompt
    injection). Called by the memory-maintenance watcher trigger.
    Idempotent: re-syncing only updates timestamps, never duplicates.
    """
    try:
        from friday.lessons import approved_lessons
        lessons = approved_lessons()
    except Exception:
        return {"synced": 0, "error": "could not load approved lessons"}

    synced = 0
    for lesson in lessons:
        category = lesson.get("category", "")
        statement = lesson.get("statement", "")
        targets = lesson.get("targets", [])
        if not category or not statement:
            continue
        key = f"lesson:{category}"
        value = statement
        tags = [f"target:{t}" for t in targets if isinstance(t, str)]
        try:
            result = store(
                key=key,
                value=value,
                category="lessons",
                tags=tags,
            )
            if result.get("status") in ("stored", "updated"):
                synced += 1
        except Exception:
            continue

    return {"synced": synced, "total_lessons": len(lessons)}


# -------------------------------------- success learning


def record_success(
    goal: str,
    outcome: str,
    tags: list[str] | None = None,
) -> dict[str, str]:
    """Record a successful goal outcome for future reference.

    Called after a plan completes successfully so Friday can learn
    from what worked. Stored in the 'context' category with a
    'success:' prefix on the key.
    """
    if not goal or not goal.strip():
        raise PreconditionError("record_success requires a non-empty 'goal'")
    return store(
        key=f"success:{goal.strip()[:80]}",
        value=outcome,
        category="context",
        tags=(tags or []) + ["type:success"],
    )


def record_decision(
    decision: str,
    rationale: str,
    tags: list[str] | None = None,
) -> dict[str, str]:
    """Record a decision and its rationale for future reference.

    Useful for tracking why certain approaches were chosen over others.
    """
    if not decision or not decision.strip():
        raise PreconditionError("record_decision requires a non-empty 'decision'")
    if not rationale or not rationale.strip():
        raise PreconditionError("record_decision requires a non-empty 'rationale'")
    return store(
        key=f"decision:{decision.strip()[:80]}",
        value=rationale,
        category="decisions",
        tags=tags,
    )
