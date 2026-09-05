"""Context system — what's happening RIGHT NOW.

Working context: current state (active windows, playing media, time)
Goal context: what the user is trying to achieve
Environmental context: system state (processes, network, battery)
"""

from __future__ import annotations

import os
import platform
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class WorkingContext:
    """Current state of the world."""

    timestamp: str = ""
    hour: int = 0
    weekday: str = ""
    active_windows: list[dict[str, Any]] = field(default_factory=list)
    playing_media: bool = False
    playing_title: str = ""
    recent_goals: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        """Render context as text for the planner."""
        lines = [
            f"Time: {self.timestamp} ({self.weekday})",
            f"Active windows: {len(self.active_windows)}",
        ]
        if self.playing_media:
            lines.append(f"Playing: {self.playing_title or 'unknown'}")
        if self.recent_goals:
            lines.append(f"Recent goals: {', '.join(self.recent_goals[-3:])}")
        return "\n".join(lines)


@dataclass
class GoalContext:
    """Context for the current goal."""

    goal: str = ""
    history: list[str] = field(default_factory=list)  # past similar goals
    success_rate: float = 0.0
    similar_goals: list[str] = field(default_factory=list)
    known_failures: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [f"Goal: {self.goal}"]
        if self.success_rate > 0:
            lines.append(f"Historical success rate: {self.success_rate:.0%}")
        if self.known_failures:
            lines.append(f"Known failure modes: {', '.join(self.known_failures[:3])}")
        return "\n".join(lines)


@dataclass
class EnvironmentalContext:
    """System state."""

    platform: str = ""
    hostname: str = ""
    python_version: str = ""
    available_adapters: list[str] = field(default_factory=list)
    missing_adapters: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [
            f"Platform: {self.platform}",
            f"Python: {self.python_version}",
            f"Available adapters: {', '.join(self.available_adapters) or 'none'}",
        ]
        if self.missing_adapters:
            lines.append(f"Missing: {', '.join(self.missing_adapters)}")
        return "\n".join(lines)


class ContextManager:
    """Manages all context sources and builds a unified context for the planner."""

    def __init__(self) -> None:
        self.working = WorkingContext()
        self.goal = GoalContext()
        self.environment = EnvironmentalContext()
        self._goal_history: list[str] = []

    def refresh_working(self) -> None:
        """Refresh the working context with current state."""
        now = datetime.now()
        self.working.timestamp = now.isoformat(timespec="seconds")
        self.working.hour = now.hour
        self.working.weekday = now.strftime("%A")

        # Try to get window info
        try:
            from friday_mcu.adapters.window import list_clients
            self.working.active_windows = list_clients()
        except Exception:
            pass

        # Try to get media info
        try:
            from friday_mcu.adapters.media import is_playing, get_playing_title
            self.working.playing_media = is_playing()
            if self.working.playing_media:
                self.working.playing_title = get_playing_title()
        except Exception:
            pass

        self.working.recent_goals = list(self._goal_history[-10:])

    def refresh_environment(self) -> None:
        """Refresh the environmental context."""
        self.environment.platform = platform.system()
        self.environment.hostname = platform.node()
        self.environment.python_version = platform.python_version()

        # Check adapter availability
        from friday_mcu.adapters import list_adapters
        adapters = list_adapters()
        self.environment.available_adapters = sorted(adapters.keys())

    def set_goal(self, goal: str) -> None:
        """Set the current goal and build its context."""
        self.goal.goal = goal
        self._goal_history.append(goal)

        # Search memory for similar goals
        try:
            from friday_mcu.memory.store import MemoryManager
            mgr = MemoryManager()
            similar = mgr.search(goal, memory_type="episodic", limit=5)
            self.goal.similar_goals = [m.content[:100] for m in similar]
        except Exception:
            pass

    def build_full_context(self) -> str:
        """Build the full context block for the planner."""
        self.refresh_working()
        self.refresh_environment()

        sections = []
        if self.working.to_text():
            sections.append(f"CURRENT STATE:\n{self.working.to_text()}")
        if self.goal.to_text():
            sections.append(f"GOAL CONTEXT:\n{self.goal.to_text()}")
        if self.environment.to_text():
            sections.append(f"ENVIRONMENT:\n{self.environment.to_text()}")
        # The phone is half of the user's world — presence/activity/battery
        # make behavior react to *you*, not just to the PC.
        try:
            from friday_mcu.phone import phone_context
            phone = phone_context()
            if phone:
                sections.append(phone)
        except Exception:
            pass
        return "\n\n".join(sections)

    def record_goal(self, goal: str, success: bool) -> None:
        """Record a goal outcome for future reference."""
        self._goal_history.append(goal)
        if len(self._goal_history) > 100:
            self._goal_history = self._goal_history[-100:]

    def get_recent_goals(self, limit: int = 10) -> list[str]:
        """Get recent goals."""
        return self._goal_history[-limit:]
