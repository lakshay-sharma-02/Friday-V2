"""Reasoning layer — intelligent decision-making.

Chain-of-thought, hypothesis testing, anomaly detection,
capability assessment. This is what makes MCU Friday think,
not just execute.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReasoningResult:
    """The output of a reasoning process."""

    decision: str  # "execute" | "ask" | "skip" | "adapt"
    confidence: float  # 0.0 to 1.0
    reasoning: str  # explanation
    suggested_primitives: list[str] = field(default_factory=list)
    context_used: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class Reasoner:
    """Intelligent decision-making engine.

    Considers:
    - Current context (time, environment, user state)
    - Memory (past successes, failures, patterns)
    - Capabilities (what primitives are available)
    - Risk (side effects, destructive actions)
    """

    def __init__(self) -> None:
        self._history: list[ReasoningResult] = []

    def assess_goal(
        self,
        goal: str,
        available_primitives: list[str],
        memory_context: str = "",
        current_context: str = "",
    ) -> ReasoningResult:
        """Assess a goal before planning.

        Returns a reasoning result with decision, confidence, and suggestions.
        """
        warnings: list[str] = []
        context_used: list[str] = []
        confidence = 0.7  # base confidence

        # Check if we have the primitives needed
        goal_lower = goal.lower()
        suggested: list[str] = []

        # Email-related
        if any(w in goal_lower for w in ["email", "mail", "inbox", "unread"]):
            suggested.extend(["gmail.list_unread", "gmail.get_message", "gmail.summarize"])
            context_used.append("email_pattern")

        # Window-related
        if any(w in goal_lower for w in ["window", "close", "open", "focus"]):
            suggested.extend(["window.list_clients", "window.open_app", "window.close_window"])
            context_used.append("window_pattern")

        # Media-related
        if any(w in goal_lower for w in ["play", "pause", "stop", "music", "audio", "volume"]):
            suggested.extend(["media.play", "media.stop", "media.pause", "media.is_playing"])
            context_used.append("media_pattern")

        # Browser-related
        if any(w in goal_lower for w in ["browse", "web", "search", "website", "url"]):
            suggested.extend(["browser.goto", "browser.click", "browser.read_page_text"])
            context_used.append("browser_pattern")

        # File-related
        if any(w in goal_lower for w in ["file", "read", "write", "find", "copy"]):
            suggested.extend(["files.find_file", "files.read_text", "files.write_text"])
            context_used.append("file_pattern")

        # Check coverage
        missing = [p for p in suggested if p not in available_primitives]
        if missing:
            warnings.append(f"Missing primitives: {', '.join(missing)}")
            confidence *= 0.8

        # Destructive action detection
        destructive_words = ["delete", "remove", "shutdown", "destroy", "kill", "format"]
        if any(w in goal_lower for w in destructive_words):
            warnings.append("Destructive action detected — requires confirmation")
            confidence *= 0.5

        # Memory boost
        if memory_context:
            confidence = min(1.0, confidence + 0.1)
            context_used.append("memory")

        # Context boost
        if current_context:
            context_used.append("environment")

        # Decide
        if missing and len(missing) > len(suggested) / 2:
            decision = "skip"
            reasoning = f"Most required primitives ({len(missing)}/{len(suggested)}) are unavailable"
        elif warnings and confidence < 0.3:
            decision = "ask"
            reasoning = f"Low confidence ({confidence:.0%}) with warnings: {'; '.join(warnings)}"
        elif confidence >= 0.5:
            decision = "execute"
            reasoning = f"Confidence {confidence:.0%}, primitives available"
        else:
            decision = "ask"
            reasoning = f"Moderate confidence ({confidence:.0%}) — seeking confirmation"

        result = ReasoningResult(
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            suggested_primitives=suggested,
            context_used=context_used,
            warnings=warnings,
        )
        self._history.append(result)
        return result

    def analyze_failure(
        self,
        goal: str,
        error: str,
        step_results: list[dict[str, Any]],
    ) -> ReasoningResult:
        """Analyze a failed goal to suggest adaptations."""
        confidence = 0.6
        warnings: list[str] = []
        suggested: list[str] = []

        error_lower = error.lower()

        # Common failure patterns
        if "timeout" in error_lower:
            warnings.append("Timeout — try with longer timeout or simpler goal")
            confidence *= 0.7
        elif "not found" in error_lower or "no such file" in error_lower:
            warnings.append("File/resource not found — verify paths")
            suggested.append("files.find_file")
        elif "permission" in error_lower or "access denied" in error_lower:
            warnings.append("Permission denied — may need elevated privileges")
            confidence *= 0.5
        elif "auth" in error_lower or "token" in error_lower or "oauth" in error_lower:
            warnings.append("Authentication issue — refresh credentials")
            confidence *= 0.4
        elif "network" in error_lower or "connection" in error_lower:
            warnings.append("Network issue — check connectivity")
            confidence *= 0.6

        # Check if any steps succeeded
        succeeded = [s for s in step_results if s.get("status") == "VERIFIED"]
        if succeeded:
            confidence = min(1.0, confidence + 0.2)
            warnings.append(f"{len(succeeded)} step(s) succeeded before failure")

        reasoning = f"Failure analysis: {'; '.join(warnings) if warnings else 'no known pattern'}"

        result = ReasoningResult(
            decision="adapt" if warnings else "ask",
            confidence=confidence,
            reasoning=reasoning,
            suggested_primitives=suggested,
            warnings=warnings,
        )
        self._history.append(result)
        return result

    def suggest_proactive_action(
        self,
        time_of_day: int,
        recent_goals: list[str],
        memory_context: str = "",
    ) -> ReasoningResult:
        """Suggest a proactive action based on time and patterns."""
        suggestions: list[str] = []
        confidence = 0.3
        context_used: list[str] = []

        # Morning routine
        if 7 <= time_of_day <= 9:
            suggestions.append("Check email summary")
            suggestions.append("Show today's calendar")
            confidence = 0.5
            context_used.append("morning_routine")

        # Work hours
        elif 9 <= time_of_day <= 17:
            if any("email" in g.lower() for g in recent_goals):
                suggestions.append("Email check reminder")
                confidence = 0.4
                context_used.append("work_pattern")

        # Evening
        elif 18 <= time_of_day <= 21:
            suggestions.append("Daily summary")
            confidence = 0.3
            context_used.append("evening_routine")

        if memory_context:
            confidence = min(1.0, confidence + 0.1)

        decision = "execute" if confidence >= 0.4 else "skip"
        reasoning = f"Time-based suggestion (hour={time_of_day}, confidence={confidence:.0%})"

        return ReasoningResult(
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            suggested_primitives=suggestions,
            context_used=context_used,
        )

    def recent_history(self, limit: int = 10) -> list[ReasoningResult]:
        """Get recent reasoning results."""
        return self._history[-limit:]
