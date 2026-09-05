"""Predictions engine — pattern-based predictions from observed data.

Uses patterns from the PatternDetector and memory data to predict:
- What the user will likely ask for next
- When they'll likely ask for it
- What success rate to expect
- Environmental predictions (battery, workload, etc.)

Not magic — statistical inference from observed behavior.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from friday_mcu.observer._time import to_datetime


@dataclass
class Prediction:
    """A single prediction about future user behavior or system state."""

    id: str
    type: str  # "goal" | "timing" | "success_rate" | "environment" | "opportunity"
    description: str
    confidence: float  # 0.0 to 1.0
    predicted_value: Any = None  # the predicted value (goal text, time, rate, etc.)
    evidence: list[str] = field(default_factory=list)  # what supports this prediction
    suggested_action: str = ""  # what Friday should do about it
    valid_until_s: float = 3600.0  # how long this prediction is valid
    created_at: float = field(default_factory=time.time)

    def is_valid(self) -> bool:
        """Check if this prediction is still within its validity window."""
        return time.time() - self.created_at < self.valid_until_s

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "description": self.description,
            "confidence": self.confidence,
            "predicted_value": self.predicted_value,
            "evidence_count": len(self.evidence),
            "suggested_action": self.suggested_action,
            "valid": self.is_valid(),
        }


class PredictionEngine:
    """Generates predictions from patterns, memory, and context.

    Prediction types:
    - goal: "User will likely ask for X next"
    - timing: "User typically asks for X at Y:00"
    - success_rate: "This goal succeeds N% of the time"
    - opportunity: "User hasn't checked email in 6 hours — might be busy"
    """

    def __init__(self) -> None:
        self._predictions: dict[str, Prediction] = {}
        self._history: list[dict[str, Any]] = []

    def generate_predictions(
        self,
        tasks: list[dict[str, Any]],
        recent_goals: list[str] | None = None,
        memory_context: str = "",
    ) -> list[Prediction]:
        """Generate all predictions from available data.

        Args:
            tasks: Recent task history (goal, timestamp, success, etc.)
            recent_goals: Most recent goals in order
            memory_context: Context from memory search

        Returns:
            List of predictions sorted by confidence
        """
        predictions: list[Prediction] = []

        # Goal predictions: what the user will likely ask next
        predictions.extend(self._predict_next_goal(tasks, recent_goals or []))

        # Timing predictions: when the user will likely ask
        predictions.extend(self._predict_timing(tasks))

        # Success rate predictions
        predictions.extend(self._predict_success_rate(tasks))

        # Opportunity predictions
        predictions.extend(self._predict_opportunities(tasks, recent_goals or []))

        # Store and sort
        for p in predictions:
            self._predictions[p.id] = p

        return sorted(predictions, key=lambda p: p.confidence, reverse=True)

    def _predict_next_goal(
        self, tasks: list[dict[str, Any]], recent_goals: list[str]
    ) -> list[Prediction]:
        """Predict what the user will likely ask for next."""
        predictions: list[Prediction] = []

        # Find recurring goal patterns
        goal_counts: dict[str, int] = {}
        for t in tasks:
            goal = t.get("goal", "")
            if goal:
                sig = self._normalize_goal(goal)
                goal_counts[sig] = goal_counts.get(sig, 0) + 1

        for sig, count in goal_counts.items():
            if count >= 3:  # need at least 3 occurrences
                # Find the most recent instance of this goal
                for t in reversed(tasks):
                    if self._normalize_goal(t.get("goal", "")) == sig:
                        confidence = min(0.9, count / 10.0)
                        predictions.append(Prediction(
                            id=f"next_goal_{hash(sig) % 10000}",
                            type="goal",
                            description=f"User frequently asks: '{t.get('goal', '')[:50]}' ({count} times)",
                            confidence=confidence,
                            predicted_value=t.get("goal"),
                            evidence=[f"occurred {count} times in history"],
                            suggested_action=f"Pre-load context for: {t.get('goal', '')[:50]}",
                            valid_until_s=3600,
                        ))
                        break

        return predictions[:5]  # top 5

    def _predict_timing(self, tasks: list[dict[str, Any]]) -> list[Prediction]:
        """Predict when the user will likely ask for something."""
        predictions: list[Prediction] = []

        # Group goals by hour
        hour_goals: dict[int, list[str]] = {}
        for t in tasks:
            goal = t.get("goal", "")
            dt = to_datetime(t.get("timestamp"))
            if dt is None or not goal:
                continue
            hour = dt.hour
            if hour not in hour_goals:
                hour_goals[hour] = []
            hour_goals[hour].append(goal)

        for hour, goals in hour_goals.items():
            if len(goals) >= 3:
                # Most common goal at this hour
                goal_counts: dict[str, int] = {}
                for g in goals:
                    goal_counts[g] = goal_counts.get(g, 0) + 1
                top_goal = max(goal_counts, key=goal_counts.get)  # type: ignore
                count = goal_counts[top_goal]
                confidence = min(0.8, count / 10.0)

                predictions.append(Prediction(
                    id=f"timing_{hour}_{hash(top_goal) % 1000}",
                    type="timing",
                    description=f"User typically asks '{top_goal[:40]}' around {hour:02d}:00",
                    confidence=confidence,
                    predicted_value={"hour": hour, "goal": top_goal},
                    evidence=[f"observed {count} times at hour {hour}"],
                    suggested_action=f"Pre-load context before {hour:02d}:00",
                    valid_until_s=86400,  # valid for 24h
                ))

        return predictions[:3]

    def _predict_success_rate(self, tasks: list[dict[str, Any]]) -> list[Prediction]:
        """Predict success rate for recurring goals."""
        predictions: list[Prediction] = []

        goal_results: dict[str, list[bool]] = {}
        for t in tasks:
            goal = t.get("goal", "")
            if not goal:
                continue
            sig = self._normalize_goal(goal)
            if sig not in goal_results:
                goal_results[sig] = []
            success = t.get("gate6_passed", False)
            if isinstance(success, str):
                success = success.lower() in ("true", "yes", "passed", "completed")
            goal_results[sig].append(success)

        for sig, results in goal_results.items():
            if len(results) >= 3:
                success_count = sum(1 for r in results if r)
                rate = success_count / len(results)
                confidence = min(0.9, len(results) / 10.0)

                predictions.append(Prediction(
                    id=f"success_{hash(sig) % 10000}",
                    type="success_rate",
                    description=f"Goal succeeds {rate:.0%} of the time ({success_count}/{len(results)})",
                    confidence=confidence,
                    predicted_value=rate,
                    evidence=[f"{success_count} successes, {len(results) - success_count} failures"],
                    suggested_action="Retry with adapted approach" if rate < 0.5 else "High confidence — proceed",
                    valid_until_s=86400,
                ))

        return predictions[:3]

    def _predict_opportunities(
        self, tasks: list[dict[str, Any]], recent_goals: list[str]
    ) -> list[Prediction]:
        """Detect opportunities for proactive action."""
        predictions: list[Prediction] = []

        # Check if user hasn't done common tasks recently
        common_tasks = {
            "check email": 6 * 3600,  # 6 hours
            "check calendar": 12 * 3600,  # 12 hours
        }

        for task_name, max_gap in common_tasks.items():
            last_seen = 0.0
            for t in reversed(tasks):
                if task_name in t.get("goal", "").lower():
                    dt = to_datetime(t.get("timestamp"))
                    if dt is not None:
                        last_seen = dt.timestamp()
                    break

            if last_seen > 0:
                gap = time.time() - last_seen
                if gap > max_gap:
                    hours = int(gap / 3600)
                    predictions.append(Prediction(
                        id=f"opportunity_{task_name.replace(' ', '_')}",
                        type="opportunity",
                        description=f"User hasn't {task_name} in {hours}h — might want to",
                        confidence=0.3,
                        predicted_value=task_name,
                        evidence=[f"last {task_name} was {hours}h ago"],
                        suggested_action=f"Suggest: want me to {task_name}?",
                        valid_until_s=1800,
                    ))

        return predictions

    def _normalize_goal(self, goal: str) -> str:
        """Normalize a goal for grouping."""
        import re
        g = goal.lower().strip()
        g = re.sub(r"\s+", " ", g)
        g = re.sub(r"\b(my|the|a|an|some)\b", "", g)
        g = re.sub(r"\s+", " ", g).strip()
        g = re.sub(r"\S+@\S+", "<email>", g)
        g = re.sub(r"[/\\]\S+", "<path>", g)
        g = re.sub(r"\b\d+\b", "<n>", g)
        return g

    def get_predictions(self, prediction_type: str | None = None) -> list[Prediction]:
        """Get all valid predictions, optionally filtered by type."""
        predictions = [p for p in self._predictions.values() if p.is_valid()]
        if prediction_type:
            predictions = [p for p in predictions if p.type == prediction_type]
        return sorted(predictions, key=lambda p: p.confidence, reverse=True)

    def get_stats(self) -> dict[str, Any]:
        """Get prediction engine statistics."""
        valid = [p for p in self._predictions.values() if p.is_valid()]
        return {
            "total_predictions": len(self._predictions),
            "valid_predictions": len(valid),
            "by_type": {
                t: len([p for p in valid if p.type == t])
                for t in set(p.type for p in valid)
            } if valid else {},
        }
