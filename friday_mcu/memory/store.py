"""Memory store — working, episodic, semantic, and procedural memory.

Not a JSONL file. A real memory system that:
- Remembers past interactions and outcomes
- Retrieves relevant memories for context
- Consolidates working → episodic → semantic over time
- Strengthens successful memories, weakens forgotten ones
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EPISODIC_FILE = PROJECT_ROOT / "var" / "state" / "memory_episodic.jsonl"
DEFAULT_SEMANTIC_FILE = PROJECT_ROOT / "var" / "state" / "memory_semantic.json"

# Per-file write locks: MemoryManager is constructed fresh by many callers
# (API threads, watcher, CLI) but they all write the same backing files.
_WRITE_LOCKS: dict[str, threading.RLock] = {}
_LOCK_REG = threading.Lock()


def _file_lock(path: str | Path) -> threading.RLock:
    """Get the process-wide write lock for a backing file."""
    key = str(path)
    with _LOCK_REG:
        lock = _WRITE_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _WRITE_LOCKS[key] = lock
        return lock


@dataclass
class MemoryEntry:
    """A single memory entry."""

    key: str
    content: str
    category: str  # "episodic" | "semantic" | "procedural"
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    strength: float = 1.0  # 0.0 = forgotten, 1.0 = fresh
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "content": self.content,
            "category": self.category,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "strength": self.strength,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MemoryEntry:
        return cls(
            key=d["key"],
            content=d.get("content", ""),
            category=d.get("category", "episodic"),
            created_at=d.get("created_at", time.time()),
            last_accessed=d.get("last_accessed", time.time()),
            access_count=d.get("access_count", 0),
            strength=d.get("strength", 1.0),
            tags=d.get("tags", []),
            metadata=d.get("metadata", {}),
        )


class WorkingMemory:
    """In-memory, TTL-based working memory.

    Current context, active goals, recent interactions.
    Evaporates after TTL — like human working memory.
    """

    def __init__(self, ttl_s: float = 3600.0, max_entries: int = 100) -> None:
        self._entries: dict[str, tuple[MemoryEntry, float]] = {}  # key -> (entry, expiry)
        self._ttl = ttl_s
        self._max = max_entries

    def store(self, key: str, content: str, **kwargs: Any) -> MemoryEntry:
        """Store a working memory entry."""
        self._evict()
        entry = MemoryEntry(key=key, content=content, category="working", **kwargs)
        self._entries[key] = (entry, time.time() + self._ttl)
        return entry

    def recall(self, key: str) -> MemoryEntry | None:
        """Recall a working memory by key."""
        pair = self._entries.get(key)
        if pair is None:
            return None
        entry, expiry = pair
        if time.time() > expiry:
            del self._entries[key]
            return None
        entry.last_accessed = time.time()
        entry.access_count += 1
        return entry

    def search(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """Simple substring search across working memory."""
        self._evict()
        query_lower = query.lower()
        results = []
        for key, (entry, _) in self._entries.items():
            if query_lower in key.lower() or query_lower in entry.content.lower():
                results.append(entry)
        results.sort(key=lambda e: e.last_accessed, reverse=True)
        return results[:limit]

    def all_entries(self) -> list[MemoryEntry]:
        """Get all non-expired entries."""
        self._evict()
        return [entry for entry, _ in self._entries.values()]

    def _evict(self) -> None:
        """Remove expired entries."""
        now = time.time()
        expired = [k for k, (_, exp) in self._entries.items() if now > exp]
        for k in expired:
            del self._entries[k]

    def clear(self) -> None:
        """Clear all working memory."""
        self._entries.clear()


class EpisodicMemory:
    """JSONL-backed episodic memory.

    "Last Tuesday, user asked me to send the report to WhatsApp"
    Indexed by: time, goal, outcome.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path else DEFAULT_EPISODIC_FILE
        self._entries: list[MemoryEntry] = []
        self._load()

    def _load(self) -> None:
        """Load existing episodic memories."""
        if not self._path.exists():
            return
        try:
            for line in self._path.read_text(encoding="utf-8").strip().splitlines():
                if line.strip():
                    self._entries.append(MemoryEntry.from_dict(json.loads(line)))
        except (OSError, json.JSONDecodeError):
            pass

    def store(
        self,
        key: str,
        content: str,
        tags: list[str] | None = None,
        **metadata: Any,
    ) -> MemoryEntry:
        """Store an episodic memory."""
        entry = MemoryEntry(
            key=key,
            content=content,
            category="episodic",
            tags=tags or [],
            metadata=metadata,
        )
        with _file_lock(self._path):
            self._entries.append(entry)
            self._append(entry)
        return entry

    def recall(self, key: str) -> MemoryEntry | None:
        """Recall by exact key."""
        for entry in reversed(self._entries):
            if entry.key == key:
                entry.last_accessed = time.time()
                entry.access_count += 1
                return entry
        return None

    def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Search episodic memories by content similarity."""
        query_lower = query.lower()
        query_tokens = set(re.findall(r"\w+", query_lower))
        scored: list[tuple[float, MemoryEntry]] = []
        for entry in self._entries:
            content_lower = entry.content.lower()
            content_tokens = set(re.findall(r"\w+", content_lower))
            # Simple TF-IDF-like scoring
            if not query_tokens or not content_tokens:
                continue
            overlap = len(query_tokens & content_tokens)
            score = overlap / max(len(query_tokens | content_tokens), 1)
            # Boost by recency (days since creation)
            age_days = (time.time() - entry.created_at) / 86400
            recency_boost = 1.0 / (1.0 + age_days * 0.1)
            # Boost by access count
            access_boost = 1.0 + math.log1p(entry.access_count) * 0.1
            final_score = score * recency_boost * access_boost * entry.strength
            scored.append((final_score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def recent(self, limit: int = 20) -> list[MemoryEntry]:
        """Get most recent episodic memories."""
        return sorted(self._entries, key=lambda e: e.created_at, reverse=True)[:limit]

    def _append(self, entry: MemoryEntry) -> None:
        """Append one entry to the JSONL file. Caller holds the file lock."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _rewrite(self) -> None:
        """Atomically persist the current in-memory entries. Caller holds lock."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                for entry in self._entries:
                    fh.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
            os.replace(tmp, self._path)
        except OSError:
            pass

    def consolidate(self) -> int:
        """Decay old memories: reduce strength based on age and access pattern.

        Returns the number of entries decayed. Decay is PERSISTED — without a
        rewrite the file kept full-strength copies that reappeared on reload.
        """
        with _file_lock(self._path):
            now = time.time()
            decayed = 0
            for entry in self._entries:
                age_days = (now - entry.created_at) / 86400
                # Decay formula: strength decays with age, boosted by recent access
                time_decay = math.exp(-age_days * 0.01)  # slow decay
                access_boost = min(1.0, entry.access_count * 0.1)
                new_strength = max(0.01, time_decay * (0.5 + access_boost))
                if abs(new_strength - entry.strength) > 0.01:
                    entry.strength = new_strength
                    decayed += 1
            if decayed:
                self._rewrite()
            return decayed

    def prune(self, threshold: float = 0.05) -> int:
        """Remove memories below the strength threshold.

        Returns the number pruned. PERSISTED: pruned entries are removed from
        the backing file too, so they cannot resurrect on the next load.
        """
        with _file_lock(self._path):
            before = len(self._entries)
            self._entries = [e for e in self._entries if e.strength >= threshold]
            removed = before - len(self._entries)
            if removed:
                self._rewrite()
            return removed


class SemanticMemory:
    """Key-value semantic memory with TF-IDF retrieval.

    "User prefers formal tone in work emails, casual in personal"
    Indexed by: concept, relationship.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path else DEFAULT_SEMANTIC_FILE
        self._entries: dict[str, MemoryEntry] = {}
        self._load()

    def _load(self) -> None:
        """Load existing semantic memories."""
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for key, val in data.items():
                    self._entries[key] = MemoryEntry.from_dict(val)
        except (OSError, json.JSONDecodeError):
            pass

    def store(
        self,
        key: str,
        content: str,
        tags: list[str] | None = None,
        **metadata: Any,
    ) -> MemoryEntry:
        """Store or update a semantic memory."""
        if key in self._entries:
            # Update existing
            entry = self._entries[key]
            entry.content = content
            entry.last_accessed = time.time()
            entry.access_count += 1
            if tags:
                entry.tags = list(set(entry.tags + tags))
            entry.metadata.update(metadata)
        else:
            entry = MemoryEntry(
                key=key,
                content=content,
                category="semantic",
                tags=tags or [],
                metadata=metadata,
            )
            self._entries[key] = entry
        self._save()
        return entry

    def recall(self, key: str) -> MemoryEntry | None:
        """Recall by exact key."""
        entry = self._entries.get(key)
        if entry:
            entry.last_accessed = time.time()
            entry.access_count += 1
        return entry

    def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Search semantic memories by content similarity."""
        query_lower = query.lower()
        query_tokens = set(re.findall(r"\w+", query_lower))
        scored: list[tuple[float, MemoryEntry]] = []
        for entry in self._entries.values():
            content_lower = entry.content.lower()
            key_lower = entry.key.lower()
            content_tokens = set(re.findall(r"\w+", content_lower + " " + key_lower))
            if not query_tokens or not content_tokens:
                continue
            overlap = len(query_tokens & content_tokens)
            score = overlap / max(len(query_tokens | content_tokens), 1)
            access_boost = 1.0 + math.log1p(entry.access_count) * 0.1
            final_score = score * access_boost * entry.strength
            scored.append((final_score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def list_all(self) -> list[MemoryEntry]:
        """List all semantic memories."""
        return list(self._entries.values())

    def _save(self) -> None:
        """Save semantic memories to disk (atomic replace, write-locked)."""
        with _file_lock(self._path):
            self._path.parent.mkdir(parents=True, exist_ok=True)
            try:
                data = {key: entry.to_dict() for key, entry in self._entries.items()}
                tmp = self._path.with_suffix(".tmp")
                tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                os.replace(tmp, self._path)
            except OSError:
                pass

    def forget(self, key: str) -> bool:
        """Remove a semantic memory."""
        if key in self._entries:
            del self._entries[key]
            self._save()
            return True
        return False


class ProceduralMemory:
    """Successful plan patterns, indexed by normalized goal signature.

    "To send Gmail, first list_unread, then get_message, then summarize"
    """

    def __init__(self) -> None:
        self._patterns: dict[str, list[dict[str, Any]]] = {}

    def store_pattern(
        self,
        goal: str,
        steps: list[dict[str, Any]],
        success: bool,
        confidence: float = 0.5,
    ) -> None:
        """Record a plan pattern."""
        sig = self._normalize_goal(goal)
        if sig not in self._patterns:
            self._patterns[sig] = []
        self._patterns[sig].append({
            "goal": goal,
            "steps": steps,
            "success": success,
            "confidence": confidence,
            "timestamp": time.time(),
        })

    def recall_pattern(self, goal: str) -> list[dict[str, Any]] | None:
        """Recall successful patterns for a similar goal."""
        sig = self._normalize_goal(goal)
        patterns = self._patterns.get(sig, [])
        successful = [p for p in patterns if p["success"]]
        return successful if successful else None

    def success_rate(self, goal: str) -> float:
        """Get the historical success rate for a goal pattern."""
        sig = self._normalize_goal(goal)
        patterns = self._patterns.get(sig, [])
        if not patterns:
            return 0.0
        successes = sum(1 for p in patterns if p["success"])
        return successes / len(patterns)

    def _normalize_goal(self, goal: str) -> str:
        """Normalize a goal for pattern matching."""
        g = goal.lower().strip()
        g = re.sub(r"\s+", " ", g)
        g = re.sub(r"\b(my|the|a|an|some)\b", "", g)
        g = re.sub(r"\s+", " ", g).strip()
        # Remove specific nouns
        g = re.sub(r"\b\d+\b", "<n>", g)
        g = re.sub(r"[/\\]\S+", "<path>", g)
        return g

    def all_patterns(self) -> dict[str, list[dict[str, Any]]]:
        """Get all stored patterns."""
        return dict(self._patterns)


class MemoryManager:
    """Unified memory interface — the single entry point for all memory ops."""

    def __init__(self) -> None:
        self.working = WorkingMemory()
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        self.procedural = ProceduralMemory()

    def store(
        self,
        key: str,
        content: str,
        memory_type: str = "episodic",
        **kwargs: Any,
    ) -> MemoryEntry:
        """Store a memory in the specified type."""
        if memory_type == "working":
            return self.working.store(key, content, **kwargs)
        elif memory_type == "episodic":
            return self.episodic.store(key, content, **kwargs)
        elif memory_type == "semantic":
            return self.semantic.store(key, content, **kwargs)
        else:
            raise ValueError(f"Unknown memory type: {memory_type}")

    def recall(self, key: str, memory_type: str = "episodic") -> MemoryEntry | None:
        """Recall a memory by key."""
        if memory_type == "working":
            return self.working.recall(key)
        elif memory_type == "episodic":
            return self.episodic.recall(key)
        elif memory_type == "semantic":
            return self.semantic.recall(key)
        return None

    def search(self, query: str, memory_type: str = "episodic", limit: int = 10) -> list[MemoryEntry]:
        """Search memories by content similarity."""
        if memory_type == "working":
            return self.working.search(query, limit)
        elif memory_type == "episodic":
            return self.episodic.search(query, limit)
        elif memory_type == "semantic":
            return self.semantic.search(query, limit)
        return []

    def search_all(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Search across all memory types."""
        results: list[MemoryEntry] = []
        results.extend(self.working.search(query, limit))
        results.extend(self.episodic.search(query, limit))
        results.extend(self.semantic.search(query, limit))
        results.sort(key=lambda e: e.strength * (1 + e.access_count), reverse=True)
        return results[:limit]

    def build_context(self, goal: str) -> str:
        """Build a context block for the planner from relevant memories."""
        memories = self.search_all(goal, limit=5)
        if not memories:
            return ""
        lines = ["Relevant memories from past sessions:"]
        for m in memories:
            lines.append(f"- [{m.category}] {m.content[:100]}")
        return "\n".join(lines)

    def consolidate(self) -> dict[str, int]:
        """Run maintenance across all memory types."""
        return {
            "episodic_decayed": self.episodic.consolidate(),
            "episodic_pruned": self.episodic.prune(),
        }
