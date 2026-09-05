"""User model — tracks user preferences, habits, and behavioral patterns.

Not a static config file. A living model that learns from interaction:
- Preferences: tone, platform, notification style
- Habits: daily routines, weekly patterns
- Context: current project, focus areas, upcoming deadlines

Indexed by concept and relationship, updated by observed behavior.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_FILE = PROJECT_ROOT / "var" / "state" / "user_model.json"


@dataclass
class Preference:
    """A single user preference."""

    key: str
    value: Any
    confidence: float = 0.5
    source: str = "observed"  # "observed" | "explicit" | "inferred"
    last_updated: float = field(default_factory=time.time)
    evidence_count: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "confidence": self.confidence,
            "source": self.source,
            "last_updated": self.last_updated,
            "evidence_count": self.evidence_count,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Preference:
        return cls(
            key=d["key"],
            value=d["value"],
            confidence=d.get("confidence", 0.5),
            source=d.get("source", "observed"),
            last_updated=d.get("last_updated", time.time()),
            evidence_count=d.get("evidence_count", 1),
        )


@dataclass
class Habit:
    """A detected behavioral habit."""

    id: str
    description: str
    pattern: str  # e.g. "daily:09:00:check_email"
    frequency: int = 0
    last_seen: float = 0.0
    confidence: float = 0.5
    suggested_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "pattern": self.pattern,
            "frequency": self.frequency,
            "last_seen": self.last_seen,
            "confidence": self.confidence,
            "suggested_action": self.suggested_action,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Habit:
        return cls(
            id=d["id"],
            description=d["description"],
            pattern=d["pattern"],
            frequency=d.get("frequency", 0),
            last_seen=d.get("last_seen", 0.0),
            confidence=d.get("confidence", 0.5),
            suggested_action=d.get("suggested_action", ""),
        )


class UserModel:
    """Learns and tracks user preferences, habits, and context.

    Usage:
        model = UserModel()
        model.observe_goal("check email", success=True, platform="telegram")
        model.record_preference("preferred_channel", "telegram", source="observed")
        prefs = model.get_preference("preferred_channel")
        context = model.build_context()
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path else DEFAULT_MODEL_FILE
        self._preferences: dict[str, Preference] = {}
        self._habits: dict[str, Habit] = {}
        self._goal_history: list[dict[str, Any]] = []
        self._context: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load model from disk."""
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for k, v in data.get("preferences", {}).items():
                    self._preferences[k] = Preference.from_dict(v)
                for k, v in data.get("habits", {}).items():
                    self._habits[k] = Habit.from_dict(v)
                self._goal_history = data.get("goal_history", [])[-100:]
                self._context = data.get("context", {})
        except (OSError, json.JSONDecodeError):
            pass

    def _save(self) -> None:
        """Save model to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "preferences": {k: v.to_dict() for k, v in self._preferences.items()},
                "habits": {k: v.to_dict() for k, v in self._habits.items()},
                "goal_history": self._goal_history[-100:],
                "context": self._context,
            }
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            import os
            os.replace(tmp, self._path)
        except OSError:
            pass

    # ── Preferences

    def record_preference(
        self, key: str, value: Any, confidence: float = 0.5, source: str = "observed"
    ) -> None:
        """Record or update a user preference."""
        if key in self._preferences:
            pref = self._preferences[key]
            # If same value, increase confidence
            if pref.value == value:
                pref.evidence_count += 1
                pref.confidence = min(1.0, pref.confidence + 0.1)
            else:
                # New value — if higher confidence, replace
                if confidence > pref.confidence:
                    pref.value = value
                    pref.confidence = confidence
                    pref.source = source
                    pref.evidence_count = 1
                else:
                    pref.evidence_count += 1
            pref.last_updated = time.time()
        else:
            self._preferences[key] = Preference(
                key=key, value=value, confidence=confidence, source=source
            )
        self._save()

    def get_preference(self, key: str) -> Any | None:
        """Get a user preference value. Returns None if not set or low confidence."""
        pref = self._preferences.get(key)
        if pref is None or pref.confidence < 0.3:
            return None
        return pref.value

    def get_all_preferences(self) -> dict[str, Any]:
        """Get all preferences as a flat dict."""
        return {
            k: v.value
            for k, v in self._preferences.items()
            if v.confidence >= 0.3
        }

    # ── Habits

    def observe_habit(
        self,
        habit_id: str,
        description: str,
        pattern: str,
        suggested_action: str = "",
    ) -> None:
        """Record or strengthen a detected habit."""
        if habit_id in self._habits:
            habit = self._habits[habit_id]
            habit.frequency += 1
            habit.last_seen = time.time()
            habit.confidence = min(1.0, habit.confidence + 0.1)
        else:
            self._habits[habit_id] = Habit(
                id=habit_id,
                description=description,
                pattern=pattern,
                frequency=1,
                last_seen=time.time(),
                confidence=0.3,
                suggested_action=suggested_action,
            )
        self._save()

    def get_habits(self, min_confidence: float = 0.3) -> list[Habit]:
        """Get detected habits above confidence threshold."""
        return sorted(
            [h for h in self._habits.values() if h.confidence >= min_confidence],
            key=lambda h: h.confidence,
            reverse=True,
        )

    # ── Goal observation

    def observe_goal(
        self,
        goal: str,
        success: bool,
        duration_s: float = 0.0,
        platform: str = "",
    ) -> None:
        """Record a goal observation for habit detection."""
        import re
        from datetime import datetime

        now = time.time()
        hour = datetime.now().hour
        weekday = datetime.now().strftime("%A").lower()

        self._goal_history.append({
            "goal": goal,
            "success": success,
            "duration_s": duration_s,
            "platform": platform,
            "timestamp": now,
            "hour": hour,
            "weekday": weekday,
        })

        # Keep last 200
        if len(self._goal_history) > 200:
            self._goal_history = self._goal_history[-200:]

        # Learn platform preference
        if platform and success:
            self.record_preference(
                f"platform_for_{self._goal_type(goal)}",
                platform,
                confidence=0.4,
            )

        # Learn time patterns
        goal_type = self._goal_type(goal)
        pattern_key = f"time:{goal_type}:{weekday}"
        if pattern_key not in self._habits:
            self.observe_habit(
                habit_id=pattern_key,
                description=f"User asks '{goal[:30]}' around {hour:02d}:00 on {weekday}",
                pattern=f"{weekday}:{hour:02d}:{goal_type}",
                suggested_action=f"Pre-load context for {goal_type} at {hour:02d}:00",
            )
        else:
            habit = self._habits[pattern_key]
            habit.frequency += 1
            habit.last_seen = now

        self._save()

    def _goal_type(self, goal: str) -> str:
        """Classify a goal into a type category."""
        g = goal.lower()
        if any(w in g for w in ["email", "mail", "inbox"]):
            return "email"
        if any(w in g for w in ["calendar", "event", "meeting"]):
            return "calendar"
        if any(w in g for w in ["file", "read", "write", "find"]):
            return "files"
        if any(w in g for w in ["play", "pause", "music", "audio"]):
            return "media"
        if any(w in g for w in ["send", "message", "chat"]):
            return "messaging"
        if any(w in g for w in ["screenshot", "capture"]):
            return "screenshot"
        if any(w in g for w in ["git", "commit", "branch"]):
            return "git"
        return "other"

    # ── Context

    def set_context(self, key: str, value: Any) -> None:
        """Set a context value (current project, focus area, etc.)."""
        self._context[key] = value
        self._save()

    def get_context(self, key: str) -> Any | None:
        """Get a context value."""
        return self._context.get(key)

    def build_context(self) -> str:
        """Build a text context block for the planner from the user model."""
        lines: list[str] = []

        # Preferences
        prefs = self.get_all_preferences()
        if prefs:
            lines.append("USER PREFERENCES:")
            for k, v in prefs.items():
                lines.append(f"  - {k}: {v}")

        # Habits
        habits = self.get_habits(min_confidence=0.4)
        if habits:
            lines.append("DETECTED HABITS:")
            for h in habits[:5]:
                lines.append(f"  - {h.description} (confidence={h.confidence:.0%})")

        # Context
        if self._context:
            lines.append("CURRENT CONTEXT:")
            for k, v in self._context.items():
                lines.append(f"  - {k}: {v}")

        return "\n".join(lines) if lines else ""

    def get_stats(self) -> dict[str, Any]:
        """Get user model statistics."""
        return {
            "preferences": len(self._preferences),
            "habits": len(self._habits),
            "goal_history": len(self._goal_history),
            "context_keys": list(self._context.keys()),
        }
