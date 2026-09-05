"""Adaptive communication — learns how to communicate effectively.

Channel learning: user responds faster on Telegram than WhatsApp.
Timing learning: don't send notifications after 10pm.
Volume learning: don't spam — batch updates hourly.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChannelPreference:
    """Learned preference for a communication channel."""

    channel: str
    score: float = 0.5  # 0.0 = never use, 1.0 = always prefer
    last_used: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    avg_response_time_s: float = 0.0

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.5


@dataclass
class TimingPreference:
    """Learned timing preferences."""

    quiet_start_hour: int = 22
    quiet_end_hour: int = 7
    preferred_hours: list[int] = field(default_factory=lambda: list(range(8, 20)))
    max_messages_per_hour: int = 5
    batch_interval_s: float = 3600.0  # 1 hour


class AdaptiveComms:
    """Learns how to communicate with the user effectively.

    Tracks:
    - Which channels work best for which types of messages
    - When the user is available and responsive
    - How much messaging is too much
    """

    def __init__(self) -> None:
        self._channel_prefs: dict[str, ChannelPreference] = {}
        self._timing = TimingPreference()
        self._send_history: list[dict[str, Any]] = []
        self._response_times: dict[str, list[float]] = defaultdict(list)

    def record_send(
        self,
        channel: str,
        message_type: str,
        success: bool,
        response_time_s: float = 0.0,
    ) -> None:
        """Record a message send for learning."""
        if channel not in self._channel_prefs:
            self._channel_prefs[channel] = ChannelPreference(channel=channel)
        pref = self._channel_prefs[channel]
        if success:
            pref.success_count += 1
        else:
            pref.failure_count += 1
        pref.last_used = time.time()

        if response_time_s > 0:
            self._response_times[channel].append(response_time_s)
            # Keep last 50 response times
            if len(self._response_times[channel]) > 50:
                self._response_times[channel] = self._response_times[channel][-50:]
            pref.avg_response_time_s = sum(self._response_times[channel]) / len(
                self._response_times[channel]
            )

        # Update score: success rate + response speed bonus
        speed_bonus = max(0, 1.0 - pref.avg_response_time_s / 60.0) * 0.2
        pref.score = pref.success_rate * 0.8 + speed_bonus

        self._send_history.append({
            "channel": channel,
            "type": message_type,
            "success": success,
            "timestamp": time.time(),
        })

    def select_channel(
        self,
        available_channels: list[str],
        message_type: str = "text",
        priority: str = "normal",
    ) -> str | None:
        """Select the best channel for a message."""
        if not available_channels:
            return None

        now_hour = time.localtime().tm_hour

        # Check quiet hours (skip if disabled via (0,0))
        if self._timing.quiet_start_hour != 0 or self._timing.quiet_end_hour != 0:
            if self._timing.quiet_start_hour <= now_hour or now_hour < self._timing.quiet_end_hour:
                if priority not in ("urgent",):
                    return None  # suppress during quiet hours

        # Check volume limit
        recent_sends = [
            s for s in self._send_history
            if time.time() - s["timestamp"] < 3600  # last hour
        ]
        if len(recent_sends) >= self._timing.max_messages_per_hour:
            return None  # too many messages

        # Score channels
        scored: list[tuple[float, str]] = []
        for ch in available_channels:
            pref = self._channel_prefs.get(ch)
            if pref:
                scored.append((pref.score, ch))
            else:
                scored.append((0.5, ch))  # default score for unknown channels

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1] if scored else None

    def is_available(self) -> bool:
        """Check if we should send a message right now."""
        now_hour = time.localtime().tm_hour
        if self._timing.quiet_start_hour <= now_hour or now_hour < self._timing.quiet_end_hour:
            return False
        recent = [
            s for s in self._send_history
            if time.time() - s["timestamp"] < 3600
        ]
        return len(recent) < self._timing.max_messages_per_hour

    def get_stats(self) -> dict[str, Any]:
        """Get communication learning stats."""
        return {
            "channels": {
                name: {
                    "score": pref.score,
                    "success_rate": pref.success_rate,
                    "avg_response_time_s": pref.avg_response_time_s,
                    "total_sends": pref.success_count + pref.failure_count,
                }
                for name, pref in self._channel_prefs.items()
            },
            "total_sends": len(self._send_history),
            "quiet_hours": f"{self._timing.quiet_start_hour}:00-{self._timing.quiet_end_hour}:00",
            "max_per_hour": self._timing.max_messages_per_hour,
        }


_SHARED: AdaptiveComms | None = None


def get_shared() -> AdaptiveComms:
    """Process-wide AdaptiveComms singleton so ProactiveEngine/others share one
    learning history instead of each caller starting from zero."""
    global _SHARED
    if _SHARED is None:
        _SHARED = AdaptiveComms()
    return _SHARED
