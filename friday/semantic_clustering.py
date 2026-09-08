"""Semantic clustering for goal proposals.

This module provides semantic clustering capabilities that go beyond
simple text-based grouping. It can:
- Cluster goals by semantic similarity using embeddings (when available)
- Identify semantic themes and patterns in recurring failures
- Provide richer context for goal proposals

The semantic clustering is optional and falls back gracefully
to text-based clustering when embeddings are not available.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

# Try to import embedding utilities - optional dependency
try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# Try to import sentence transformers or similar embedding libraries
try:
    from sentence_transformers import SentenceTransformer

    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

    # Fake class for type hints
    class SentenceTransformer:
        pass


# Semantic keywords that indicate categories/themes
SEMANTIC_CATEGORIES = {
    "email": ["gmail", "email", "mail", "inbox", "unread", "message", "sender"],
    "browser": ["browser", "firefox", "chrome", "safari", "web", "page", "url"],
    "media": ["media", "audio", "music", "video", "play", "pause", "volume", "mpv"],
    "window": ["window", "app", "close", "open", "focus", "terminal", "kitty"],
    "file": ["file", "files", "document", "pdf", "read", "write", "find"],
    "calendar": ["calendar", "event", "schedule", "meeting", "reminder"],
    "messaging": ["whatsapp", "telegram", "discord", "send", "message"],
    "system": ["system", "cpu", "ram", "memory", "disk", "battery", "uptime"],
    "screenshot": ["screenshot", "capture", "screen", "image"],
    "vision": ["vision", "ocr", "text", "extract", "describe"],
    "git": ["git", "commit", "branch", "log", "status", "repo"],
    "clipboard": ["clipboard", "copy", "paste"],
}


@dataclass
class SemanticCluster:
    """A cluster of goals with semantic grouping information."""

    key: str  # Normalized goal key
    goal: str  # Verbatim goal text
    occurrences: int = 0
    task_ids: list[str] = field(default_factory=list)
    timestamps: list[str] = field(default_factory=list)
    last_failed_at: str = ""
    l0_evidence: list[dict[str, Any]] = field(default_factory=list)
    semantic_category: str = ""
    semantic_similarity: float = 0.0  # Average similarity within cluster
    related_clusters: list[str] = field(default_factory=list)  # Semantically related cluster keys


@dataclass
class SemanticProposal:
    """A goal proposal with enhanced semantic information."""

    trigger: dict[str, Any]
    semantic_category: str = ""
    semantic_keywords: list[str] = field(default_factory=list)
    related_goals: list[str] = field(default_factory=list)
    similarity_score: float = 0.0

    @property
    def id(self) -> str:
        return self.trigger.get("id", "")

    @property
    def goal(self) -> str:
        return self.trigger.get("goal", "")


class SemanticClusterer:
    """Cluster goals by semantic similarity."""

    def __init__(self, use_embeddings: bool = False):
        self.use_embeddings = use_embeddings and HAS_SENTENCE_TRANSFORMERS
        self.model: SentenceTransformer | None = None
        self.embeddings_cache: dict[str, Any] = {}

        if self.use_embeddings:
            try:
                self.model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception:
                self.use_embeddings = False
                self.model = None

    def compute_embeddings(self, texts: list[str]) -> Any:
        """Compute embeddings for a list of texts."""
        if not self.use_embeddings or self.model is None:
            return None

        try:
            # Use cache for repeated texts
            uncached = []
            uncached_indices = []
            for i, text in enumerate(texts):
                if text in self.embeddings_cache:
                    uncached_indices.append(i)
                else:
                    uncached.append(text)
                    self.embeddings_cache[text] = i  # Mark as being processed

            if not uncached:
                # All from cache
                result = np.zeros((len(texts), 0))
                return result

            # Compute embeddings for uncached texts
            embeddings = self.model.encode(uncached, convert_to_numpy=True)

            return embeddings
        except Exception:
            return None

    def semantic_distance(self, text1: str, text2: str) -> float:
        """Compute semantic distance between two texts (0-1, 1 = identical)."""
        if not self.use_embeddings:
            return 0.0

        emb1 = self.compute_embeddings([text1])
        emb2 = self.compute_embeddings([text2])

        if emb1 is None or emb2 is None:
            return 0.0

        # Cosine similarity
        from numpy import dot
        from numpy.linalg import norm

        if norm(emb1) == 0 or norm(emb2) == 0:
            return 0.0

        similarity = dot(emb1, emb2) / (norm(emb1) * norm(emb2))
        return float(similarity)

    def semantic_similarity(self, text1: str, text2: str) -> float:
        """Compute semantic similarity between two texts (0-1, 1 = identical)."""
        return self.semantic_distance(text1, text2)


def detect_semantic_category(goal: str) -> str:
    """Detect the semantic category of a goal based on keywords.

    Returns:
        Category name or empty string if no category detected.
    """
    goal_lower = goal.lower()

    # Find matching categories and their keyword matches
    category_matches: dict[str, list[str]] = defaultdict(list)

    for category, keywords in SEMANTIC_CATEGORIES.items():
        for keyword in keywords:
            if keyword in goal_lower:
                category_matches[category].append(keyword)

    if not category_matches:
        return ""

    # Return the category with the most matches
    best_category = max(category_matches.items(), key=lambda x: len(x[1]))
    return best_category[0]


def extract_semantic_keywords(goal: str) -> list[str]:
    """Extract relevant semantic keywords from a goal.

    Returns a list of keywords that indicate the goal's category and intent.
    """
    goal_lower = goal.lower()
    keywords: list[str] = []

    for category, cats_keywords in SEMANTIC_CATEGORIES.items():
        for kw in cats_keywords:
            if kw in goal_lower:
                keywords.append(kw)

    # Also extract potential action verbs
    action_verbs = [
        "send", "receive", "read", "write", "create", "delete", "delete",
        "open", "close", "find", "summarize", "check", "list", "show",
        "capture", "describe", "extract", "play", "pause", "stop",
        "copy", "move", "upload", "download",
    ]

    for verb in action_verbs:
        if verb in goal_lower and verb not in keywords:
            keywords.append(verb)

    return keywords


def cluster_by_semantic_category(
    clusters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Enhance clusters with semantic category information.

    Args:
        clusters: List of cluster dicts from the basic mining process

    Returns:
        Lists of clusters with semantic_category added to each
    """
    enhanced = []

    for cluster in clusters:
        goal = cluster.get("goal", "")
        category = detect_semantic_category(goal)
        keywords = extract_semantic_keywords(goal)

        enhanced_cluster = dict(cluster)
        enhanced_cluster["semantic_category"] = category
        enhanced_cluster["semantic_keywords"] = keywords

        enhanced.append(enhanced_cluster)

    return enhanced


def group_clusters_by_semantic(
    clusters: list[dict[str, Any]],
    use_embeddings: bool = False,
) -> list[list[dict[str, Any]]]:
    """Group clusters by semantic similarity.

    Returns a list of grouped clusters (each group is a list of similar clusters).
    """
    if not clusters:
        return []

    if not use_embeddings:
        # Fallback: group by semantic category
        by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for cluster in clusters:
            category = cluster.get("semantic_category", "other")
            by_category[category].append(cluster)

        return list(by_category.values())

    # With embeddings: use similarity-based grouping
    clusterer = SemanticClusterer(use_embeddings=True)
    groups: list[list[dict[str, Any]]] = []
    assigned = set()

    for i, cluster in enumerate(clusters):
        if i in assigned:
            continue

        goal = cluster.get("goal", "")
        group = [cluster]

        for j, other in enumerate(clusters):
            if j <= i or j in assigned:
                continue

            other_goal = other.get("goal", "")
            similarity = clusterer.semantic_similarity(goal, other_goal)

            if similarity > 0.7:  # Threshold for semantic similarity
                group.append(other)
                assigned.add(j)

        groups.append(group)

    return groups


def find_semantic_relations(
    clusters: list[dict[str, Any]],
    similarity_threshold: float = 0.6,
) -> dict[str, list[str]]:
    """Find semantic relationships between clusters.

    Returns a dict mapping cluster keys to lists of related cluster keys.
    """
    # Use keyword-based similarity as a proxy for embeddings
    relations: dict[str, list[str]] = {}

    for cluster in clusters:
        key = cluster.get("key", cluster.get("goal", ""))
        keywords = set(cluster.get("semantic_keywords", []))

        related = []
        for other in clusters:
            other_key = other.get("key", other.get("goal", ""))
            if other_key == key:
                continue

            other_keywords = set(other.get("semantic_keywords", []))

            if keywords and other_keywords:
                # Jaccard similarity
                intersection = len(keywords & other_keywords)
                union = len(keywords | other_keywords)

                if union > 0:
                    jaccard = intersection / union
                    if jaccard >= similarity_threshold:
                        related.append(other_key)

        relations[key] = related

    return relations


def build_semantic_proposal(
    cluster: dict[str, Any],
    related_clusters: list[str] = None,
) -> SemanticProposal:
    """Build an enhanced semantic proposal from a cluster.

    Args:
        cluster: A cluster dict from mining
        related_clusters: Optional list of related cluster keys

    Returns:
        SemanticProposal with enhanced metadata
    """
    from friday.goal_proposals import _draft_trigger

    trigger = _draft_trigger(cluster)
    semantic_category = cluster.get("semantic_category", "")
    keywords = cluster.get("semantic_keywords", [])

    return SemanticProposal(
        trigger=trigger,
        semantic_category=semantic_category,
        semantic_keywords=keywords,
        related_goals=related_clusters or [],
        similarity_score=cluster.get("semantic_similarity", 0.0),
    )


# Enhanced mining function that includes semantic clustering
def mine_with_semantics(
    days: int = 14,
    min_recurrence: int = 2,
    use_embeddings: bool = False,
) -> list[dict[str, Any]]:
    """Mine recurring failures and enhance with semantic information.

    This is an enhanced version of the basic mine() function that
    includes semantic categorization and keyword extraction.

    Args:
        days: Lookback window in days
        min_recurrence: Minimum failures to be considered a cluster
        use_embeddings: Whether to use embedding-based similarity

    Returns:
        List of enhanced cluster dicts with semantic information
    """
    from friday.goal_proposals import mine, existing_triggers

    # Get basic clusters
    triggers = existing_triggers()
    basic_clusters = mine(
        days=days,
        min_recurrence=min_recurrence,
        triggers=triggers,
    )

    # Add semantic information
    enhanced = cluster_by_semantic_category(basic_clusters)

    # Compute embedding-based similarities if requested
    if use_embeddings and HAS_SENTENCE_TRANSFORMERS:
        clusterer = SemanticClusterer(use_embeddings=True)

        for cluster in enhanced:
            goal = cluster.get("goal", "")
            # Compute similarity to other clusters in same category
            same_category = [
                c for c in enhanced
                if c.get("semantic_category") == cluster.get("semantic_category")
                and c != cluster
            ]

            if same_category:
                similarities = []
                for other in same_category:
                    sim = clusterer.semantic_similarity(goal, other.get("goal", ""))
                    similarities.append(sim)

                if similarities:
                    cluster["semantic_similarity"] = sum(similarities) / len(similarities)

                    # Find related clusters
                    related = [
                        c.get("key", c.get("goal", ""))
                        for c in same_category
                        if clusterer.semantic_similarity(goal, c.get("goal", "")) > 0.65
                    ]
                    cluster["related_clusters"] = related

    return enhanced