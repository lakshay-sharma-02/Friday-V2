"""Natural communication — adaptive tone, context-aware messages.

Makes Friday's messages feel human, not robotic:
- Adaptive tone: formal for work, casual for personal
- Context-aware messages: include relevant history
- Progressive disclosure: summary first, details on request
- Confirmation flows: "I'm about to send this email — confirm?"
- Platform-aware formatting: markdown for Discord, plain for WhatsApp
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


# ── Tone profiles


@dataclass
class ToneProfile:
    """A communication tone profile."""

    name: str
    greeting: str = ""
    closing: str = ""
    emoji_style: str = "minimal"  # "none" | "minimal" | "full"
    sentence_style: str = "medium"  # "terse" | "medium" | "verbose"
    formality: str = "auto"  # "formal" | "casual" | "auto"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "greeting": self.greeting,
            "closing": self.closing,
            "emoji_style": self.emoji_style,
            "sentence_style": self.sentence_style,
            "formality": self.formality,
        }


# Predefined tone profiles
TONE_PROFILES: dict[str, ToneProfile] = {
    "formal": ToneProfile(
        name="formal",
        greeting="Good day.",
        closing="Kind regards,",
        emoji_style="none",
        sentence_style="verbose",
        formality="formal",
    ),
    "casual": ToneProfile(
        name="casual",
        greeting="Hey!",
        closing="Cheers,",
        emoji_style="minimal",
        sentence_style="terse",
        formality="casual",
    ),
    "work": ToneProfile(
        name="work",
        greeting="Hi,",
        closing="Best,",
        emoji_style="none",
        sentence_style="medium",
        formality="formal",
    ),
    "personal": ToneProfile(
        name="personal",
        greeting="Hey!",
        closing="Talk later!",
        emoji_style="minimal",
        sentence_style="terse",
        formality="casual",
    ),
    "neutral": ToneProfile(
        name="neutral",
        greeting="",
        closing="",
        emoji_style="minimal",
        sentence_style="medium",
        formality="auto",
    ),
}


# ── Message types


@dataclass
class NaturalMessage:
    """A message formatted by the natural communication engine."""

    content: str
    tone: str = "neutral"
    summary: str = ""  # short summary (for progressive disclosure)
    details: str = ""  # full details (shown on request)
    requires_confirmation: bool = False
    confirmation_prompt: str = ""
    platform: str = ""  # "whatsapp" | "telegram" | "discord" | "email"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "tone": self.tone,
            "summary": self.summary,
            "has_details": bool(self.details),
            "requires_confirmation": self.requires_confirmation,
            "platform": self.platform,
        }


# ── Platform formatters


def _format_for_platform(content: str, platform: str) -> str:
    """Adapt message formatting for the target platform."""
    if platform == "discord":
        # Discord supports markdown
        return content
    elif platform == "telegram":
        # Telegram supports basic markdown
        return content
    elif platform == "whatsapp":
        # WhatsApp: strip markdown, use plain text
        content = re.sub(r"\*\*(.+?)\*\*", r"\1", content)  # bold
        content = re.sub(r"__(.+?)__", r"\1", content)  # italic
        content = re.sub(r"`(.+?)`", r"\1", content)  # code
        return content
    elif platform == "email":
        # Email: plain text is safest
        return content
    return content


# ── Natural message builder


class NaturalComms:
    """Builds natural, context-aware messages.

    Usage:
        comms = NaturalComms()
        msg = comms.build_goal_result(
            goal="check email",
            result="3 unread emails",
            details="From: boss@company.com - Q3 report...\nFrom: mom - dinner Sunday...",
            context={"time_of_day": "morning", "platform": "telegram"},
        )
        # msg.content is the formatted message
        # msg.summary is the short version
    """

    def __init__(self) -> None:
        self._tone_history: list[str] = []
        self._platform_tones: dict[str, str] = {}

    def set_platform_tone(self, platform: str, tone: str) -> None:
        """Set the default tone for a platform."""
        self._platform_tones[platform] = tone

    def get_tone(self, platform: str = "", context: dict[str, Any] | None = None) -> ToneProfile:
        """Get the appropriate tone for the current context.

        Tone selection priority:
        1. Explicit tone in context
        2. Platform default
        3. Time-of-day heuristic
        4. Neutral
        """
        ctx = context or {}

        # Explicit tone
        if "tone" in ctx and ctx["tone"] in TONE_PROFILES:
            return TONE_PROFILES[ctx["tone"]]

        # Platform default
        if platform and platform in self._platform_tones:
            tone_name = self._platform_tones[platform]
            if tone_name in TONE_PROFILES:
                return TONE_PROFILES[tone_name]

        # Time-of-day heuristic
        hour = ctx.get("hour", datetime.now().hour)
        if 9 <= hour <= 17:  # work hours
            return TONE_PROFILES["work"]
        elif 18 <= hour <= 22:  # evening
            return TONE_PROFILES["personal"]
        else:
            return TONE_PROFILES["neutral"]

    # ── Message builders

    def build_goal_result(
        self,
        goal: str,
        result: str,
        details: str = "",
        context: dict[str, Any] | None = None,
        platform: str = "",
    ) -> NaturalMessage:
        """Build a natural message for a goal result.

        Progressive disclosure:
        - content: summary (shown immediately)
        - details: full details (shown on request)
        """
        tone = self.get_tone(platform, context)
        success = context.get("success", True) if context else True

        # Build summary
        if success:
            summary = self._build_success_summary(goal, result, tone)
        else:
            error = context.get("error", "Unknown error") if context else "Unknown error"
            summary = self._build_failure_summary(goal, error, tone)

        # Build full content with details
        content = summary
        if details:
            content += f"\n\nDetails:\n{details}"

        # Format for platform
        content = _format_for_platform(content, platform)

        return NaturalMessage(
            content=content,
            tone=tone.name,
            summary=summary,
            details=details,
            platform=platform,
        )

    def build_proactive_suggestion(
        self,
        suggestion: str,
        reason: str = "",
        context: dict[str, Any] | None = None,
        platform: str = "",
    ) -> NaturalMessage:
        """Build a natural proactive suggestion."""
        tone = self.get_tone(platform, context)

        # Progressive disclosure: short suggestion, details on request
        summary = suggestion
        if reason:
            summary = f"{suggestion}\n\n_Why: {reason}_" if platform in ("telegram", "discord") else f"{suggestion}\n(Why: {reason})"

        content = _format_for_platform(summary, platform)

        return NaturalMessage(
            content=content,
            tone=tone.name,
            summary=suggestion,
            details=reason,
            platform=platform,
        )

    def build_confirmation_request(
        self,
        action: str,
        context: dict[str, Any] | None = None,
        platform: str = "",
    ) -> NaturalMessage:
        """Build a confirmation request before a side-effecting action.

        "I'm about to send this email — confirm?"
        """
        tone = self.get_tone(platform, context)

        if tone.formality == "formal":
            prompt = f"I am about to {action}. Please confirm to proceed."
        else:
            prompt = f"I'm about to {action}. Want me to go ahead?"

        content = _format_for_platform(prompt, platform)

        return NaturalMessage(
            content=content,
            tone=tone.name,
            requires_confirmation=True,
            confirmation_prompt=prompt,
            platform=platform,
        )

    def build_error_report(
        self,
        goal: str,
        error: str,
        context: dict[str, Any] | None = None,
        platform: str = "",
    ) -> NaturalMessage:
        """Build a natural error report."""
        tone = self.get_tone(platform, context)

        if tone.formality == "formal":
            summary = f"An error occurred while attempting '{goal}': {error}"
        elif tone.emoji_style == "none":
            summary = f"Failed to {goal}: {error}"
        else:
            summary = f"Failed to {goal}: {error}"

        # Add context if available
        attempts = context.get("attempts", 0) if context else 0
        if attempts > 1:
            summary += f"\n_(after {attempts} attempts)_"

        content = _format_for_platform(summary, platform)

        return NaturalMessage(
            content=content,
            tone=tone.name,
            platform=platform,
        )

    def build_daily_briefing(
        self,
        items: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
        platform: str = "",
    ) -> NaturalMessage:
        """Build a daily briefing from a list of items.

        Each item: {"title": str, "summary": str, "priority": str}
        """
        tone = self.get_tone(platform, context)

        lines: list[str] = []
        if tone.greeting:
            lines.append(tone.greeting)
            lines.append("")

        # Sort by priority
        priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
        sorted_items = sorted(items, key=lambda x: priority_order.get(x.get("priority", "medium"), 2))

        for item in sorted_items:
            title = item.get("title", "")
            summary = item.get("summary", "")
            priority = item.get("priority", "medium")

            if priority == "urgent":
                prefix = "!!!" if tone.emoji_style != "none" else "[URGENT]"
            elif priority == "high":
                prefix = "!!" if tone.emoji_style != "none" else "[HIGH]"
            else:
                prefix = ""

            if prefix:
                lines.append(f"{prefix} {title}")
            else:
                lines.append(f"• {title}")

            if summary:
                lines.append(f"  {summary}")

        if tone.closing:
            lines.append("")
            lines.append(tone.closing)

        content = "\n".join(lines)
        content = _format_for_platform(content, platform)

        # Summary is just the item count
        summary = f"{len(items)} items" + (f" ({sum(1 for i in items if i.get('priority') == 'urgent')} urgent)" if any(i.get('priority') == 'urgent' for i in items) else "")

        return NaturalMessage(
            content=content,
            tone=tone.name,
            summary=summary,
            platform=platform,
        )

    # ── Internal helpers

    def _build_success_summary(self, goal: str, result: str, tone: ToneProfile) -> str:
        """Build a success summary."""
        goal_verb = self._goal_to_verb(goal)

        if tone.formality == "formal":
            return f"The {goal_verb} completed successfully.\n\n{result}"
        elif tone.emoji_style == "none":
            return f"{goal_verb.capitalize()} done.\n\n{result}"
        else:
            return f"Done! {result}"

    def _build_failure_summary(self, goal: str, error: str, tone: ToneProfile) -> str:
        """Build a failure summary."""
        if tone.formality == "formal":
            return f"The {goal} encountered an error: {error}"
        elif tone.emoji_style == "none":
            return f"Failed: {goal}\n{error}"
        else:
            return f"Failed to {goal}: {error}"

    def _goal_to_verb(self, goal: str) -> str:
        """Extract the main verb from a goal string."""
        # Simple heuristic: take the first verb-like word
        goal_lower = goal.lower().strip()
        verbs = [
            "check", "send", "summarize", "find", "read", "write",
            "list", "download", "upload", "capture", "describe",
            "play", "pause", "stop", "close", "open", "focus",
        ]
        for verb in verbs:
            if goal_lower.startswith(verb):
                return verb
        # Default: first word
        words = goal_lower.split()
        return words[0] if words else "task"

    # ── Learning

    def record_tone_choice(self, tone: str) -> None:
        """Record a tone choice for learning."""
        self._tone_history.append(tone)
        if len(self._tone_history) > 100:
            self._tone_history = self._tone_history[-100:]

    def get_preferred_tone(self) -> str:
        """Get the most commonly used tone."""
        if not self._tone_history:
            return "neutral"
        from collections import Counter
        counts = Counter(self._tone_history)
        return counts.most_common(1)[0][0]

    def get_stats(self) -> dict[str, Any]:
        """Get communication statistics."""
        return {
            "tone_history": len(self._tone_history),
            "platform_tones": dict(self._platform_tones),
            "preferred_tone": self.get_preferred_tone(),
        }
