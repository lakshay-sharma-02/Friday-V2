"""Proactive communication — Friday reaches out, not just responds.

Scheduled insights, event-driven alerts, pattern-based suggestions,
failure notifications.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from friday_mcu.comms.channels import Channel, Message, get_channel, select_channel
from friday_mcu.core.events import EventType, emit


@dataclass
class ProactiveMessage:
    """A message Friday wants to send proactively."""

    content: str
    priority: str = "normal"  # "low" | "normal" | "high" | "urgent"
    channel_hint: str | None = None  # preferred channel
    recipient: str | None = None
    confidence: float = 1.0
    reason: str = ""  # why Friday is sending this
    metadata: dict[str, Any] = field(default_factory=dict)


class ProactiveEngine:
    """Manages proactive messaging — decides when and how to reach out."""

    def __init__(self) -> None:
        self._queue: list[ProactiveMessage] = []
        self._sent: list[ProactiveMessage] = []
        self._suppressed: dict[str, float] = {}  # reason -> last_suppressed_time
        self._quiet_hours = (22, 7)  # 10pm to 7am — no proactive messages

    def suggest(self, message: ProactiveMessage) -> bool:
        """Suggest a proactive message for delivery.

        Returns True if the message was queued, False if suppressed.
        """
        # Check quiet hours (unless set to disabled)
        if self._quiet_hours != (0, 0):
            hour = time.localtime().tm_hour
            if self._quiet_hours[0] <= hour or hour < self._quiet_hours[1]:
                if message.priority not in ("urgent",):
                    self._suppressed[message.reason] = time.time()
                    return False

        # Check for recent suppression of the same reason
        if message.reason in self._suppressed:
            elapsed = time.time() - self._suppressed[message.reason]
            if elapsed < 3600:  # don't repeat within an hour
                return False

        # Check confidence threshold
        if message.confidence < 0.3:
            return False

        self._queue.append(message)
        return True

    def flush(self, user_preferences: dict[str, Any] | None = None) -> list[str]:
        """Send all queued proactive messages. Returns list of sent message IDs.

        Messages are formatted through NaturalComms for adaptive tone
        before being sent via the channel.
        """
        from friday_mcu.comms.natural import NaturalComms

        _nat = NaturalComms()
        sent_ids: list[str] = []

        from friday_mcu.comms.adaptive import get_shared
        adaptive = get_shared()

        while self._queue:
            msg = self._queue.pop(0)
            channel = self._select_channel(msg, user_preferences)
            if channel is None:
                continue

            # Format through NaturalComms for adaptive tone
            try:
                nat_msg = _nat.build_proactive_suggestion(
                    suggestion=msg.content,
                    reason=msg.reason,
                    platform=channel.name,
                )
                platform_msg = Message(
                    channel=channel.name,
                    recipient=msg.recipient or "",
                    content=nat_msg.content,
                )
            except Exception:
                continue

            success = False
            try:
                msg_id = channel.send(platform_msg)
                msg.metadata["message_id"] = msg_id
                msg.metadata["tone"] = nat_msg.tone
                self._sent.append(msg)

                emit(
                    EventType.MESSAGE_SENT,
                    source="proactive",
                    data={
                        "channel": channel.name,
                        "recipient": msg.recipient,
                        "priority": msg.priority,
                        "reason": msg.reason,
                        "confidence": msg.confidence,
                        "tone": nat_msg.tone,
                    },
                )
                sent_ids.append(msg_id)
                success = True
            except Exception:
                pass  # channel errors don't crash the proactive engine
            adaptive.record_send(channel.name, platform_msg.message_type, success)

        return sent_ids

    def _select_channel(
        self,
        msg: ProactiveMessage,
        user_preferences: dict[str, Any] | None,
    ) -> Channel | None:
        """Select the best channel for a proactive message."""
        # Use hint if provided
        if msg.channel_hint:
            ch = get_channel(msg.channel_hint)
            if ch and ch.is_available():
                return ch

        # Use user preferences
        placeholder = Message(
            channel="",
            recipient=msg.recipient or "",
            content=msg.content,
        )
        return select_channel(placeholder, user_preferences)

    def recent(self, limit: int = 20) -> list[ProactiveMessage]:
        """Get recently sent proactive messages."""
        return self._sent[-limit:]

    def stats(self) -> dict[str, Any]:
        """Get proactive messaging statistics."""
        return {
            "queued": len(self._queue),
            "sent": len(self._sent),
            "suppressed": len(self._suppressed),
        }
