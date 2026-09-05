"""Pattern detection — finds recurring behaviors in goal history.

Temporal patterns, goal patterns, platform patterns, failure patterns.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from friday_mcu.observer._time import to_datetime


@dataclass
class Pattern:
    """A detected pattern in user behavior."""

    id: str
    type: str  # "temporal" | "goal" | "platform" | "failure"
    description: str
    frequency: int
    confidence: float
    evidence: list[dict[str, Any]] = field(default_factory=list)
    first_seen: str = ""
    last_seen: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "description": self.description,
            "frequency": self.frequency,
            "confidence": self.confidence,
            "evidence_count": len(self.evidence),
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
        }


class PatternDetector:
    """Analyzes goal history to detect recurring patterns."""

    def __init__(self) -> None:
        self._patterns: dict[str, Pattern] = {}

    def analyze(
        self,
        tasks: list[dict[str, Any]],
        min_occurrences: int = 2,
    ) -> list[Pattern]:
        """Analyze task history and return detected patterns."""
        patterns: list[Pattern] = []

        # Temporal patterns (time-of-day, day-of-week)
        patterns.extend(self._detect_temporal_patterns(tasks, min_occurrences))

        # Goal patterns (recurring goal text)
        patterns.extend(self._detect_goal_patterns(tasks, min_occurrences))

        # Failure patterns (common failure modes)
        patterns.extend(self._detect_failure_patterns(tasks, min_occurrences))

        # Store
        for p in patterns:
            self._patterns[p.id] = p

        return patterns

    def _detect_temporal_patterns(
        self,
        tasks: list[dict[str, Any]],
        min_occurrences: int,
    ) -> list[Pattern]:
        """Find goals that happen at the same time/day."""
        patterns: list[Pattern] = []
        hour_goals: dict[int, list[dict[str, Any]]] = defaultdict(list)

        for t in tasks:
            dt = to_datetime(t.get("timestamp"))
            if dt is None:
                continue
            hour_goals[dt.hour].append(t)

        # Hour patterns
        for hour, records in hour_goals.items():
            if len(records) >= min_occurrences:
                goals = [r.get("goal", "") for r in records if r.get("goal")]
                if goals:
                    goal_counter = Counter(goals)
                    top_goal = goal_counter.most_common(1)[0][0]
                    confidence = min(1.0, len(records) / 10.0)
                    patterns.append(Pattern(
                        id=f"temporal_hour_{hour}_{hash(top_goal) % 1000}",
                        type="temporal",
                        description=f"Goal '{top_goal[:50]}' typically runs at {hour:02d}:00",
                        frequency=len(records),
                        confidence=confidence,
                        evidence=records[:5],
                    ))

        return patterns

    def _detect_goal_patterns(
        self,
        tasks: list[dict[str, Any]],
        min_occurrences: int,
    ) -> list[Pattern]:
        """Find goals that recur with similar text."""
        patterns: list[Pattern] = []
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for t in tasks:
            goal = t.get("goal", "")
            if not goal:
                continue
            sig = self._normalize_goal(goal)
            groups[sig].append(t)

        for sig, records in groups.items():
            if len(records) < min_occurrences:
                continue
            goals = [r.get("goal", "") for r in records if r.get("goal")]
            if not goals:
                continue
            goal_counter = Counter(goals)
            top_goal = goal_counter.most_common(1)[0]
            successes = sum(1 for r in records if r.get("gate6_passed", False))
            success_rate = successes / len(records) if records else 0
            confidence = min(1.0, (len(records) / 10.0) * success_rate)

            patterns.append(Pattern(
                id=f"goal_{hash(sig) % 10000}",
                type="goal",
                description=f"Goal '{top_goal[0][:50]}' ran {len(records)} times ({success_rate:.0%} success)",
                frequency=len(records),
                confidence=confidence,
                evidence=records[:5],
            ))

        return patterns

    def _detect_failure_patterns(
        self,
        tasks: list[dict[str, Any]],
        min_occurrences: int,
    ) -> list[Pattern]:
        """Find goals that consistently fail in the same way."""
        patterns: list[Pattern] = []
        failure_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for t in tasks:
            if t.get("gate6_passed", False):
                continue  # skip successes
            goal = t.get("goal", "")
            if not goal:
                continue
            sig = self._normalize_goal(goal)
            failure_groups[sig].append(t)

        for sig, records in failure_groups.items():
            if len(records) < min_occurrences:
                continue
            goals = [r.get("goal", "") for r in records if r.get("goal")]
            if not goals:
                continue
            goal_counter = Counter(goals)
            top_goal = goal_counter.most_common(1)[0][0]
            confidence = min(1.0, len(records) / 5.0)

            patterns.append(Pattern(
                id=f"failure_{hash(sig) % 10000}",
                type="failure",
                description=f"Goal '{top_goal[:50]}' has failed {len(records)} times",
                frequency=len(records),
                confidence=confidence,
                evidence=records[:5],
            ))

        return patterns

    def _normalize_goal(self, goal: str) -> str:
        """Normalize a goal for grouping."""
        g = goal.lower().strip()
        g = re.sub(r"\s+", " ", g)
        g = re.sub(r"\b(my|the|a|an|some)\b", "", g)
        g = re.sub(r"\s+", " ", g).strip()
        g = re.sub(r"\S+@\S+", "<email>", g)
        g = re.sub(r"[/\\]\S+", "<path>", g)
        g = re.sub(r"\b\d+\b", "<n>", g)
        return g

    def get_patterns(self, pattern_type: str | None = None) -> list[Pattern]:
        """Get all detected patterns, optionally filtered by type."""
        patterns = list(self._patterns.values())
        if pattern_type:
            patterns = [p for p in patterns if p.type == pattern_type]
        return sorted(patterns, key=lambda p: p.confidence, reverse=True)
