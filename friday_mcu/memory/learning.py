"""Memory learning loop — makes the system genuinely learn.

Not just storing memories. Actively using them:
- Consolidation: working → episodic → semantic (like sleep consolidation)
- Reinforcement: successful recall strengthens memories
- Pattern extraction: recurring themes become semantic knowledge
- Failure analysis: failed goals produce actionable lessons
- Adaptation: behavior changes based on accumulated experience
"""

from __future__ import annotations

import json
import math
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Lesson:
    """A learned lesson from past experience."""

    id: str
    goal_pattern: str  # normalized goal pattern
    lesson: str  # what was learned
    lesson_type: str  # "success" | "failure" | "adaptation" | "preference"
    confidence: float = 0.5
    evidence_count: int = 1
    created_at: float = field(default_factory=time.time)
    last_applied: float = 0.0
    applied_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "goal_pattern": self.goal_pattern,
            "lesson": self.lesson,
            "lesson_type": self.lesson_type,
            "confidence": self.confidence,
            "evidence_count": self.evidence_count,
            "created_at": self.created_at,
            "last_applied": self.last_applied,
            "applied_count": self.applied_count,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Lesson:
        return cls(**d)


class MemoryLearner:
    """Learns from memory to improve future behavior.

    Usage:
        learner = MemoryLearner()
        learner.record_outcome("check email", success=True, duration_s=5.2)
        learner.record_outcome("check email", success=True, duration_s=3.1)
        learner.record_outcome("check email", success=False, duration_s=30.0)
        lessons = learner.get_lessons("check email")
        context = learner.build_learning_context("check email")
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path else Path(
            __file__).resolve().parents[2] / "var" / "state" / "memory_lessons.json"
        self._lessons: dict[str, Lesson] = {}
        self._outcomes: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for k, v in data.get("lessons", {}).items():
                    self._lessons[k] = Lesson.from_dict(v)
                self._outcomes = data.get("outcomes", [])[-500:]
        except (OSError, json.JSONDecodeError):
            pass

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "lessons": {k: v.to_dict() for k, v in self._lessons.items()},
                "outcomes": self._outcomes[-500:],
            }
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            import os
            os.replace(tmp, self._path)
        except OSError:
            pass

    # ── Outcome recording

    def record_outcome(
        self,
        goal: str,
        success: bool,
        duration_s: float = 0.0,
        steps: list[dict[str, Any]] | None = None,
        error: str = "",
    ) -> None:
        """Record a goal outcome for learning."""
        sig = self._normalize_goal(goal)
        outcome = {
            "goal": goal,
            "goal_pattern": sig,
            "success": success,
            "duration_s": duration_s,
            "steps": steps or [],
            "error": error,
            "timestamp": time.time(),
        }
        self._outcomes.append(outcome)

        # Keep last 500
        if len(self._outcomes) > 500:
            self._outcomes = self._outcomes[-500:]

        # Extract lessons from outcomes
        self._extract_lessons(sig, outcome)

        self._save()

    def _extract_lessons(self, goal_pattern: str, outcome: dict[str, Any]) -> None:
        """Extract lessons from a goal outcome."""
        success = outcome["success"]
        error = outcome.get("error", "")
        duration = outcome.get("duration_s", 0)

        if success:
            # Success lesson: this approach works
            lesson_id = f"success_{goal_pattern}"
            if lesson_id in self._lessons:
                lesson = self._lessons[lesson_id]
                lesson.evidence_count += 1
                lesson.confidence = min(1.0, lesson.confidence + 0.05)
                lesson.last_applied = time.time()
            else:
                self._lessons[lesson_id] = Lesson(
                    id=lesson_id,
                    goal_pattern=goal_pattern,
                    lesson=f"Goal succeeds with current approach",
                    lesson_type="success",
                    confidence=0.5,
                )

            # Duration lesson: learn expected duration (stored as "<n>s" so
            # renderers can prefix their own label without duplicating it)
            dur_id = f"duration_{goal_pattern}"
            if dur_id in self._lessons:
                lesson = self._lessons[dur_id]
                # Running average
                try:
                    old_avg = float(lesson.lesson.rstrip("s"))
                except ValueError:
                    old_avg = float(duration)  # legacy "Expected duration: Xs" text
                new_avg = (old_avg * lesson.evidence_count + duration) / (lesson.evidence_count + 1)
                lesson.lesson = f"{new_avg:.1f}s"
                lesson.evidence_count += 1
                lesson.confidence = min(1.0, lesson.confidence + 0.05)
            else:
                self._lessons[dur_id] = Lesson(
                    id=dur_id,
                    goal_pattern=goal_pattern,
                    lesson=f"{duration:.1f}s",
                    lesson_type="adaptation",
                    confidence=0.4,
                )
        else:
            # Failure lesson: this approach doesn't work
            if error:
                error_type = self._classify_error(error)
                lesson_id = f"failure_{goal_pattern}_{error_type}"
                if lesson_id in self._lessons:
                    lesson = self._lessons[lesson_id]
                    lesson.evidence_count += 1
                    lesson.confidence = min(1.0, lesson.confidence + 0.1)
                else:
                    self._lessons[lesson_id] = Lesson(
                        id=lesson_id,
                        goal_pattern=goal_pattern,
                        lesson=f"Fails with {error_type}: {error[:100]}",
                        lesson_type="failure",
                        confidence=0.4,
                    )

    def _classify_error(self, error: str) -> str:
        """Classify an error into a category."""
        e = error.lower()
        if "timeout" in e:
            return "timeout"
        if "not found" in e or "no such file" in e:
            return "not_found"
        if "permission" in e or "access denied" in e:
            return "permission"
        if "auth" in e or "token" in e or "oauth" in e:
            return "auth"
        if "refused" in e:
            return "refused"
        if "network" in e or "connection" in e:
            return "network"
        return "unknown"

    # ── Lesson retrieval

    def get_lessons(
        self, goal_pattern: str, min_confidence: float = 0.3
    ) -> list[Lesson]:
        """Get lessons relevant to a goal pattern.

        Matching is substring in EITHER direction, and the confidence floor
        applies to both branches (and binds tighter than the `or`).
        """
        sig = self._normalize_goal(goal_pattern)
        relevant = [
            l for l in self._lessons.values()
            if l.confidence >= min_confidence
            and (sig in l.goal_pattern or l.goal_pattern in sig)
        ]
        return sorted(relevant, key=lambda l: l.confidence, reverse=True)

    def get_all_lessons(self, min_confidence: float = 0.3) -> list[Lesson]:
        """Get all lessons above confidence threshold."""
        return sorted(
            [l for l in self._lessons.values() if l.confidence >= min_confidence],
            key=lambda l: l.confidence,
            reverse=True,
        )

    def apply_lesson(self, lesson_id: str) -> bool:
        """Mark a lesson as applied (used in planning)."""
        if lesson_id in self._lessons:
            lesson = self._lessons[lesson_id]
            lesson.last_applied = time.time()
            lesson.applied_count += 1
            lesson.confidence = min(1.0, lesson.confidence + 0.02)
            self._save()
            return True
        return False

    # ── Consolidation

    def consolidate(self) -> dict[str, int]:
        """Consolidate memories: decay weak lessons, strengthen strong ones.

        Like sleep consolidation — weak memories fade, strong ones persist.
        """
        decayed = 0
        strengthened = 0

        for lesson in self._lessons.values():
            # Decay: reduce confidence for unused lessons
            age_days = (time.time() - lesson.created_at) / 86400
            if lesson.applied_count == 0 and age_days > 7:
                lesson.confidence *= 0.95
                decayed += 1

            # Strengthen: boost confidence for frequently applied lessons
            if lesson.applied_count >= 3:
                lesson.confidence = min(1.0, lesson.confidence + 0.01)
                strengthened += 1

        # Prune very low confidence lessons
        before = len(self._lessons)
        self._lessons = {
            k: v for k, v in self._lessons.items()
            if v.confidence >= 0.1
        }
        pruned = before - len(self._lessons)

        self._save()
        return {"decayed": decayed, "strengthened": strengthened, "pruned": pruned}

    # ── Learning context for planner

    def build_learning_context(self, goal: str) -> str:
        """Build a learning context block for the planner.

        Includes relevant lessons, expected duration, and known failure modes.
        """
        lines: list[str] = []
        sig = self._normalize_goal(goal)

        # Relevant lessons
        lessons = self.get_lessons(goal, min_confidence=0.3)
        if lessons:
            lines.append("LESSONS FROM PAST EXPERIENCE:")
            for l in lessons[:5]:
                lines.append(f"  - [{l.lesson_type}] {l.lesson} (confidence={l.confidence:.0%})")

        # Expected duration
        dur_lessons = [l for l in lessons if l.lesson_type == "adaptation" and "duration" in l.id]
        if dur_lessons:
            lines.append(f"  Expected duration: {dur_lessons[0].lesson}")

        # Known failure modes
        failure_lessons = [l for l in lessons if l.lesson_type == "failure"]
        if failure_lessons:
            lines.append("KNOWN FAILURE MODES:")
            for l in failure_lessons[:3]:
                lines.append(f"  - {l.lesson}")

        # Success rate from procedural memory
        success_lessons = [l for l in lessons if l.lesson_type == "success"]
        if success_lessons:
            rate = success_lessons[0].confidence
            lines.append(f"  Historical success rate: {rate:.0%}")

        return "\n".join(lines) if lines else ""

    # ── Stats

    def get_stats(self) -> dict[str, Any]:
        """Get learning statistics."""
        return {
            "total_lessons": len(self._lessons),
            "total_outcomes": len(self._outcomes),
            "by_type": {
                t: len([l for l in self._lessons.values() if l.lesson_type == t])
                for t in set(l.lesson_type for l in self._lessons.values())
            } if self._lessons else {},
            "avg_confidence": (
                sum(l.confidence for l in self._lessons.values()) / len(self._lessons)
                if self._lessons else 0.0
            ),
        }

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
