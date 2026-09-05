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
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError
from friday.observability import emit_event

# Thread/process safety: file locking for concurrent access.
# The watcher runs serially, but the MCP server or webhook server
# could invoke memory.store concurrently with memory.maintenance.
_IS_WINDOWS = os.name == "nt"

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
# Minimum key similarity to consider a duplicate (0.0-1.0)
DUPLICATE_THRESHOLD = 0.85
# Max tags per memory entry
MAX_TAGS = 20


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
    maintenance). Individual stores use append. Thread-safe via file lock."""
    path = _memory_file()
    try:
        with _file_lock():
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
    """Append one entry to the memory file. Thread-safe via file lock."""
    path = _memory_file()
    try:
        with _file_lock():
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


@contextmanager
def _file_lock():
    """Acquire an exclusive file lock on the memory file's .lock companion.
    Prevents concurrent _save_all calls from clobbering each other.
    Best-effort: if locking fails (NFS, permission), we proceed without
    it (the atomic writes provide some safety)."""
    lock_path = _memory_file().with_suffix(".jsonl.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = None
    try:
        fd = open(lock_path, "w")
        if _IS_WINDOWS:
            import msvcrt
            msvcrt.locking(fd.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
        yield
    except (OSError, IOError):
        # Locking failed (NFS, permission, etc.) - proceed without lock.
        # The atomic writes (os.replace) provide best-effort safety.
        yield
    finally:
        if fd is not None:
            try:
                if _IS_WINDOWS:
                    import msvcrt
                    msvcrt.locking(fd.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
            except (OSError, IOError):
                pass
            fd.close()


def _make_id(key: str, category: str) -> str:
    """Deterministic id from key + category (upsert-safe)."""
    raw = f"{category}:{key}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _normalize_tokens(text: str) -> list[str]:
    """Split text into lowercase tokens, stripping punctuation.
    This is the normalization step shared by all scoring functions."""
    import re
    return [t for t in re.split(r'[^a-z0-9]+', text.lower()) if t]


# ---- Semantic search (sentence-transformers) ----
# Uses all-MiniLM-L6-v2 (384-dim, ~80MB, CPU-only) for real semantic
# matching. Falls back to TF-IDF when the model is unavailable.

_model = None  # lazy-loaded SentenceTransformer
_model_name = "all-MiniLM-L6-v2"
_embedding_cache: dict[str, list[float]] = {}  # entry_id -> embedding
_embedding_cache_dirty = False


def _get_model():
    """Lazy-load the sentence-transformers model. Returns None if
    the library or model is unavailable (falls back to TF-IDF)."""
    global _model
    if _model is not None:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_model_name)
        return _model
    except (ImportError, Exception):
        return None


def _embed_text(text: str) -> list[float] | None:
    """Embed a single text string. Returns None on failure."""
    model = _get_model()
    if model is None:
        return None
    try:
        import numpy as np
        emb = model.encode(text, normalize_embeddings=True)
        return emb.tolist()
    except Exception:
        return None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _get_entry_embedding(entry: dict[str, Any]) -> list[float] | None:
    """Get or compute the embedding for a memory entry. Uses a cache
    keyed by entry id to avoid re-encoding unchanged entries."""
    global _embedding_cache_dirty
    eid = entry.get("id", "")
    if not eid:
        return None
    # Check cache
    if eid in _embedding_cache:
        return _embedding_cache[eid]
    # Compute: embed key + value together for richer representation
    text = f"{entry.get('key', '')}: {entry.get('value', '')}"
    emb = _embed_text(text)
    if emb is not None:
        _embedding_cache[eid] = emb
        _embedding_cache_dirty = True
    return emb


def _invalidate_embeddings() -> None:
    """Clear the embedding cache when entries change."""
    global _embedding_cache, _embedding_cache_dirty
    _embedding_cache = {}
    _embedding_cache_dirty = False


# ---- TF-IDF fallback ----
# Used when sentence-transformers is unavailable.

_idf_cache: dict[str, float] = {}
_idf_cache_size: int = 0


def _compute_idf(entries: list[dict[str, Any]]) -> dict[str, float]:
    """Compute IDF weights for all tokens across memory entries."""
    global _idf_cache, _idf_cache_size
    n_docs = len(entries)
    if n_docs == _idf_cache_size and _idf_cache:
        return _idf_cache

    import math
    doc_freq: dict[str, int] = {}
    for e in entries:
        text = f"{e.get('key', '')} {e.get('value', '')}"
        tokens = set(_normalize_tokens(text))
        for t in tokens:
            doc_freq[t] = doc_freq.get(t, 0) + 1

    idf: dict[str, float] = {}
    for token, df in doc_freq.items():
        idf[token] = math.log((n_docs + 1) / (df + 1)) + 1

    _idf_cache = idf
    _idf_cache_size = n_docs
    return idf


def _invalidate_idf_cache() -> None:
    global _idf_cache, _idf_cache_size
    _idf_cache = {}
    _idf_cache_size = 0


def _tfidf_score(query_tokens: list[str], target_tokens: list[str],
                  idf: dict[str, float]) -> float:
    """TF-IDF weighted cosine similarity. Returns 0.0-1.0."""
    if not query_tokens or not target_tokens:
        return 0.0
    import math
    q_tf: dict[str, int] = {}
    for t in query_tokens:
        q_tf[t] = q_tf.get(t, 0) + 1
    t_tf: dict[str, int] = {}
    for t in target_tokens:
        t_tf[t] = t_tf.get(t, 0) + 1
    q_weighted = {t: tf * idf.get(t, 1.0) for t, tf in q_tf.items()}
    t_weighted = {t: tf * idf.get(t, 1.0) for t, tf in t_tf.items()}
    common = set(q_weighted.keys()) & set(t_weighted.keys())
    dot = sum(q_weighted[t] * t_weighted[t] for t in common)
    q_norm = math.sqrt(sum(v * v for v in q_weighted.values()))
    t_norm = math.sqrt(sum(v * v for v in t_weighted.values()))
    if q_norm == 0 or t_norm == 0:
        return 0.0
    return dot / (q_norm * t_norm)


# ---- unified scoring ----
# Semantic (sentence-transformers) is primary; TF-IDF is fallback.
# Exact/prefix/substring matches are always boosted on top.

def _score_match(text: str, query: str, query_emb: list[float] | None = None,
                  entry_emb: list[float] | None = None,
                  idf: dict[str, float] | None = None) -> float:
    """Relevance score for key matching. Returns 0.0-1.0."""
    query_lower = query.lower()
    key_lower = text.lower()

    # Exact key match
    if query_lower == key_lower:
        return 1.0
    # Prefix match
    if key_lower.startswith(query_lower):
        return 0.9
    # Substring match
    if query_lower in key_lower:
        return 0.7

    # Semantic similarity (primary)
    if query_emb is not None and entry_emb is not None:
        sim = _cosine_similarity(query_emb, entry_emb)
        return sim * 0.8  # scale to leave room for boosts

    # TF-IDF fallback
    query_tokens = _normalize_tokens(query)
    key_tokens = _normalize_tokens(text)
    if idf is None:
        idf = _compute_idf(_load_all())
    return _tfidf_score(query_tokens, key_tokens, idf) * 0.6


def _score_value(value: str, query: str, query_emb: list[float] | None = None,
                 value_emb_hint: list[float] | None = None,
                 idf: dict[str, float] | None = None) -> float:
    """Score how relevant a value is to the query. Returns 0.0-0.8."""
    query_lower = query.lower()
    value_lower = value.lower()

    if query_lower == value_lower:
        return 0.8
    if value_lower.startswith(query_lower):
        return 0.75
    if query_lower in value_lower:
        return 0.7

    # TF-IDF fallback for value (semantic is done at entry level)
    query_tokens = _normalize_tokens(query)
    value_tokens = _normalize_tokens(value)
    if idf is None:
        idf = _compute_idf(_load_all())
    return _tfidf_score(query_tokens, value_tokens, idf) * 0.4


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

    # Duplicate detection: if no exact id match, check for semantically
    # similar keys in the same category. If found, update instead of
    # creating a duplicate.
    if existing_idx is None and entries:
        # Try semantic similarity first
        query_emb = _embed_text(f"{key}: {value}")
        best_score = 0.0
        best_idx = -1
        for i, e in enumerate(entries):
            if e.get("category") != category:
                continue
            if query_emb is not None:
                # Semantic: embed the existing entry and compare
                e_emb = _get_entry_embedding(e)
                if e_emb is not None:
                    score = _cosine_similarity(query_emb, e_emb)
                else:
                    score = 0.0
            else:
                # TF-IDF fallback
                idf = _compute_idf(entries)
                query_tokens = _normalize_tokens(key)
                e_tokens = _normalize_tokens(e.get("key", ""))
                score = _tfidf_score(query_tokens, e_tokens, idf)
            if score > best_score:
                best_score = score
                best_idx = i
        if best_score >= DUPLICATE_THRESHOLD and best_idx >= 0:
            existing_idx = best_idx
            mem_id = entries[best_idx].get("id", mem_id)

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

    # Invalidate IDF cache since corpus changed
    _invalidate_idf_cache()

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
    tags: list[str] | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Search memories by relevance.

    Returns the most relevant memories matching the query, optionally
    filtered by category and/or tags. Access timestamps are updated
    for returned memories (reinforcement).

    Args:
        query: Search terms (matched against keys and values).
        category: Optional category filter.
        tags: Optional list of tags — entries must contain ALL listed tags.
        limit: Max results (default 5, max 20).
    """
    if not query or not query.strip():
        raise PreconditionError("retrieve requires a non-empty 'query'")

    if category is not None and category not in CATEGORIES:
        raise PreconditionError(
            f"retrieve: category must be one of {sorted(CATEGORIES)}, got {category!r}"
        )
    if tags and not isinstance(tags, list):
        raise PreconditionError("retrieve: tags must be a list of strings")

    limit = max(1, min(limit, MAX_RETRIEVE_RESULTS))
    entries = _load_all()

    # Compute query embedding once (semantic search)
    query_emb = _embed_text(query)

    # Compute IDF weights once for TF-IDF fallback
    idf = _compute_idf(entries) if query_emb is None else None

    # Tag filter set
    tag_filter = set(t.lower() for t in tags) if tags else None

    # Score and filter
    scored: list[tuple[float, dict[str, Any]]] = []
    for e in entries:
        if category and e.get("category") != category:
            continue
        # Tag filtering: entry must contain ALL requested tags
        if tag_filter:
            entry_tags = set(t.lower() for t in (e.get("tags") or []) if isinstance(t, str))
            if not tag_filter.issubset(entry_tags):
                continue

        # Get entry embedding for semantic comparison
        entry_emb = _get_entry_embedding(e) if query_emb is not None else None

        key_score = _score_match(
            e.get("key", ""), query,
            query_emb=query_emb, entry_emb=entry_emb, idf=idf,
        )
        value_score = _score_value(
            e.get("value", ""), query,
            query_emb=query_emb, idf=idf,
        )
        total = max(key_score, value_score)

        # Tag boost
        entry_tags = e.get("tags", [])
        if entry_tags:
            query_terms = set(query.lower().split())
            tag_terms = {t.lower() for t in entry_tags if isinstance(t, str)}
            if query_terms & tag_terms:
                total = min(total + 0.2, 1.0)

        # Freshness boost: recently accessed entries get a small bump
        try:
            last = e.get("last_accessed", "")
            if last:
                from datetime import datetime as _dt
                age_days = (_dt.now(UTC) - _dt.fromisoformat(last.replace("Z", "+00:00"))).days
                if age_days < 7:
                    total = min(total + 0.05, 1.0)
        except (ValueError, AttributeError):
            pass

        if total > 0.05:  # lower threshold for semantic search
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
        _invalidate_idf_cache()

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


# -------------------------------------------------------- list / export


@contract(
    precondition="None.",
    postcondition="Returns a paginated list of memory entries, optionally filtered by category and/or tags. Read-only.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError on storage read failure.",
    returns="dict: {entries: list[dict], total: int, offset: int, limit: int}.",
)
def list_memories(
    category: str | None = None,
    tags: list[str] | None = None,
    offset: int = 0,
    limit: int = 20,
) -> dict[str, Any]:
    """List memory entries with optional filtering and pagination.

    Args:
        category: Optional category filter.
        tags: Optional list of tags — entries must contain ALL listed tags.
        offset: Pagination offset (default 0).
        limit: Max results per page (default 20, max 100).
    """
    if category is not None and category not in CATEGORIES:
        raise PreconditionError(
            f"list_memories: category must be one of {sorted(CATEGORIES)}, got {category!r}"
        )
    if tags and not isinstance(tags, list):
        raise PreconditionError("list_memories: tags must be a list of strings")

    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    entries = _load_all()

    # Filter
    filtered: list[dict[str, Any]] = []
    for e in entries:
        if category and e.get("category") != category:
            continue
        if tags:
            entry_tags = set(t.lower() for t in (e.get("tags") or []) if isinstance(t, str))
            query_tags = set(t.lower() for t in tags)
            if not query_tags.issubset(entry_tags):
                continue
        filtered.append(e)

    # Sort by last_accessed (most recent first)
    filtered.sort(key=lambda e: e.get("last_accessed", ""), reverse=True)

    total = len(filtered)
    page = filtered[offset : offset + limit]

    return {
        "entries": [
            {
                "id": e.get("id", ""),
                "key": e.get("key", ""),
                "value": e.get("value", "")[:500],
                "category": e.get("category", ""),
                "tags": e.get("tags", []),
                "created_at": e.get("created_at", ""),
                "last_accessed": e.get("last_accessed", ""),
                "access_count": e.get("access_count", 0),
            }
            for e in page
        ],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@contract(
    precondition="None.",
    postcondition="Returns all memory entries as a JSON string for backup. Read-only.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError on storage read failure.",
    returns="dict: {data: str (JSON), count: int, exported_at: str}.",
)
def export_memories() -> dict[str, Any]:
    """Export all memories as a JSON string for backup.

    Returns the raw JSONL data as a single JSON array string, plus
    metadata. Import with import_memories().
    """
    entries = _load_all()
    return {
        "data": json.dumps(entries, ensure_ascii=False, indent=2),
        "count": len(entries),
        "exported_at": _now_iso(),
    }


@contract(
    precondition="data is a non-empty JSON string (array of memory entries).",
    postcondition="Imports entries from the JSON data. Merges by id (updates existing, appends new).",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="PreconditionError for empty/malformed data; PrimitiveError on storage failure.",
    returns="dict: {imported: int, updated: int, skipped: int}.",
)
def import_memories(data: str) -> dict[str, Any]:
    """Import memories from a JSON export.

    Merges by id: entries with an existing id are updated, new entries
    are appended. Skips malformed entries.

    Args:
        data: JSON string (array of memory entry objects).
    """
    if not data or not data.strip():
        raise PreconditionError("import_memories requires non-empty 'data'")

    try:
        incoming = json.loads(data)
    except json.JSONDecodeError as exc:
        raise PreconditionError(f"import_memories: invalid JSON: {exc}")

    if not isinstance(incoming, list):
        raise PreconditionError("import_memories: data must be a JSON array")

    existing = _load_all()
    existing_by_id = {e.get("id"): i for i, e in enumerate(existing)}

    imported = 0
    updated = 0
    skipped = 0

    for entry in incoming:
        if not isinstance(entry, dict) or "key" not in entry:
            skipped += 1
            continue
        entry_id = entry.get("id") or _make_id(entry.get("key", ""), entry.get("category", "facts"))
        entry["id"] = entry_id
        if entry_id in existing_by_id:
            idx = existing_by_id[entry_id]
            existing[idx] = entry
            updated += 1
        else:
            existing.append(entry)
            imported += 1

    if imported or updated:
        _save_all(existing)
        _invalidate_idf_cache()

    return {"imported": imported, "updated": updated, "skipped": skipped}


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
        _invalidate_idf_cache()

    return {
        "archived": len(entries) - len(keep),
        "remaining": len(keep),
        "archived_keys": archived_keys,
    }


# --------------------------------------------------- planner integration


def build_memory_context(query: str, category: str | None = None, limit: int = 5) -> str:
    """Build a memory context block for the planner prompt.

    Returns a formatted string of relevant memories, including:
    - Successful goal patterns (what worked before)
    - Relevant facts and preferences
    - Lessons from past failures
    Called by the planner when building prompts.
    """
    try:
        # Get general relevant memories
        results = retrieve(query, category=category, limit=limit)

        # Also fetch recent successes for similar goals
        success_results = []
        try:
            success_results = retrieve(
                query,
                category="context",
                tags=["type:success"],
                limit=3,
            )
        except Exception:
            pass

        # Also fetch relevant lessons
        lesson_results = []
        try:
            lesson_results = retrieve(
                query,
                category="lessons",
                limit=2,
            )
        except Exception:
            pass
    except Exception:
        return ""

    # Deduplicate by id across all result sets
    seen_ids: set[str] = set()
    all_results: list[dict[str, Any]] = []
    for r in results + success_results + lesson_results:
        rid = r.get("id", "")
        if rid and rid not in seen_ids:
            seen_ids.add(rid)
            all_results.append(r)

    if not all_results:
        return ""

    lines = ["Known from past sessions:"]
    for r in all_results:
        cat = r.get("category", "")
        key = r.get("key", "")
        value = r.get("value", "")
        # Truncate long values in the context block
        if len(value) > 200:
            value = value[:200] + "..."
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
