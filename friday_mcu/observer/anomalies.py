"""Anomaly detection — detects unusual patterns, consecutive failures,
missed routines, and environmental anomalies.

Not error logging. Intelligence: "this is unusual, something might be wrong"
or "this is an opportunity, the user might need something."
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Anomaly:
    """A detected anomaly in system behavior or user patterns."""

    id: str
    type: str  # "failure_streak" | "volume_spike" | "missed_routine" | "performance" | "environment"
    severity: str  # "low" | "medium" | "high" | "critical"
    description: str
    detected_at: float = field(default_factory=time.time)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    suggested_action: str = ""
    auto_resolved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "severity": self.severity,
            "description": self.description,
            "detected_at": self.detected_at,
            "evidence_count": len(self.evidence),
            "suggested_action": self.suggested_action,
            "auto_resolved": self.auto_resolved,
        }


class AnomalyDetector:
    """Detects anomalies in task history, system behavior, and user patterns.

    Detection types:
    - failure_streak: N consecutive failures of the same goal
    - volume_spike: significantly more/fewer goals than usual
    - missed_routine: a regular habit didn't happen when expected
    - performance: goals taking much longer than usual
    - environment: system-level anomalies (adapter failures, etc.)
    """

    def __init__(self) -> None:
        self._anomalies: dict[str, Anomaly] = {}
        self._baseline: dict[str, Any] = {}

    def detect(
        self,
        tasks: list[dict[str, Any]],
        baseline: dict[str, Any] | None = None,
    ) -> list[Anomaly]:
        """Detect anomalies in the task history.

        Args:
            tasks: Recent task history
            baseline: Optional baseline stats (avg daily goals, etc.)

        Returns:
            List of detected anomalies sorted by severity
        """
        if baseline:
            self._baseline = baseline

        anomalies: list[Anomaly] = []

        # Failure streak detection
        anomalies.extend(self._detect_failure_streaks(tasks))

        # Volume spike detection
        anomalies.extend(self._detect_volume_spikes(tasks))

        # Performance degradation
        anomalies.extend(self._detect_performance_issues(tasks))

        # Store
        for a in anomalies:
            self._anomalies[a.id] = a

        return sorted(anomalies, key=lambda a: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(a.severity, 4))

    def _detect_failure_streaks(self, tasks: list[dict[str, Any]]) -> list[Anomaly]:
        """Detect consecutive failures of the same goal."""
        anomalies: list[Anomaly] = []

        # Group by normalized goal
        goal_failures: dict[str, list[dict[str, Any]]] = {}
        current_streak: list[dict[str, Any]] = []
        current_goal_sig = ""

        for t in tasks:
            goal = t.get("goal", "")
            sig = self._normalize_goal(goal)
            success = t.get("gate6_passed", False)
            if isinstance(success, str):
                success = success.lower() in ("true", "yes", "passed", "completed")

            if sig == current_goal_sig and not success:
                current_streak.append(t)
            elif sig == current_goal_sig and success:
                # Streak broken by success
                current_streak = []
            else:
                # New goal
                if len(current_streak) >= 3:
                    goal_failures[current_goal_sig] = list(current_streak)
                current_streak = [t] if not success else []
                current_goal_sig = sig

        # Check final streak
        if len(current_streak) >= 3:
            goal_failures[current_goal_sig] = list(current_streak)

        for sig, failures in goal_failures.items():
            severity = "high" if len(failures) >= 5 else "medium"
            anomalies.append(Anomaly(
                id=f"failure_streak_{hash(sig) % 10000}",
                type="failure_streak",
                severity=severity,
                description=f"Goal '{failures[0].get('goal', '')[:40]}' has failed {len(failures)} times in a row",
                evidence=[{"goal": f.get("goal", ""), "timestamp": f.get("timestamp", "")} for f in failures[:5]],
                suggested_action="Investigate root cause or adapt the approach",
            ))

        return anomalies

    def _detect_volume_spikes(self, tasks: list[dict[str, Any]]) -> list[Anomaly]:
        """Detect unusual volume of goals (too many or too few)."""
        anomalies: list[Anomaly] = []

        if len(tasks) < 10:
            return anomalies

        # Count goals per day
        daily_counts: dict[str, int] = {}
        for t in tasks:
            ts = t.get("timestamp", "")
            if not ts:
                continue
            try:
                from datetime import datetime
                if isinstance(ts, str):
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                else:
                    dt = datetime.fromtimestamp(ts)
                day = dt.date().isoformat()
                daily_counts[day] = daily_counts.get(day, 0) + 1
            except (ValueError, TypeError):
                continue

        if len(daily_counts) < 3:
            return anomalies

        counts = list(daily_counts.values())
        avg = sum(counts) / len(counts)
        today = max(daily_counts.values()) if daily_counts else 0

        # Volume spike: today is 3x the average
        if today > avg * 3 and today > 10:
            anomalies.append(Anomaly(
                id="volume_spike_high",
                type="volume_spike",
                severity="medium",
                description=f"Today's goal volume ({today}) is {today/avg:.1f}x the average ({avg:.0f})",
                evidence=[{"today": today, "average": round(avg, 1), "days": len(daily_counts)}],
                suggested_action="Check if user is in a high-activity mode",
            ))

        # Volume drop: today is 0 (missed routine)
        if today == 0 and avg >= 2:
            anomalies.append(Anomaly(
                id="volume_drop",
                type="missed_routine",
                severity="low",
                description=f"No goals today (average is {avg:.0f}/day)",
                evidence=[{"today": 0, "average": round(avg, 1)}],
                suggested_action="User might be away or busy",
            ))

        return anomalies

    def _detect_performance_issues(self, tasks: list[dict[str, Any]]) -> list[Anomaly]:
        """Detect goals taking much longer than usual."""
        anomalies: list[Anomaly] = []

        # Group by goal type and check durations
        goal_durations: dict[str, list[float]] = {}
        for t in tasks:
            goal = t.get("goal", "")
            duration = t.get("duration_s", 0)
            if not goal or duration <= 0:
                continue
            sig = self._normalize_goal(goal)
            if sig not in goal_durations:
                goal_durations[sig] = []
            goal_durations[sig].append(duration)

        for sig, durations in goal_durations.items():
            if len(durations) < 3:
                continue
            avg = sum(durations) / len(durations)
            latest = durations[-1]

            # Latest is 3x the average
            if latest > avg * 3 and latest > 30:
                anomalies.append(Anomaly(
                    id=f"perf_degradation_{hash(sig) % 10000}",
                    type="performance",
                    severity="medium",
                    description=f"Goal now takes {latest:.0f}s (average: {avg:.0f}s)",
                    evidence=[{"latest": latest, "average": round(avg, 1), "samples": len(durations)}],
                    suggested_action="Check for network issues or API slowdowns",
                ))

        return anomalies

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

    def get_anomalies(
        self, anomaly_type: str | None = None, min_severity: str = "low"
    ) -> list[Anomaly]:
        """Get detected anomalies, optionally filtered."""
        severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        min_sev = severity_order.get(min_severity, 0)

        anomalies = [
            a for a in self._anomalies.values()
            if severity_order.get(a.severity, 0) >= min_sev
        ]

        if anomaly_type:
            anomalies = [a for a in anomalies if a.type == anomaly_type]

        return sorted(anomalies, key=lambda a: severity_order.get(a.severity, 0), reverse=True)

    def resolve(self, anomaly_id: str) -> bool:
        """Mark an anomaly as auto-resolved."""
        if anomaly_id in self._anomalies:
            self._anomalies[anomaly_id].auto_resolved = True
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Get anomaly detection statistics."""
        return {
            "total_anomalies": len(self._anomalies),
            "unresolved": sum(1 for a in self._anomalies.values() if not a.auto_resolved),
            "by_type": {
                t: len([a for a in self._anomalies.values() if a.type == t])
                for t in set(a.type for a in self._anomalies.values())
            } if self._anomalies else {},
            "by_severity": {
                s: len([a for a in self._anomalies.values() if a.severity == s])
                for s in set(a.severity for a in self._anomalies.values())
            } if self._anomalies else {},
        }
