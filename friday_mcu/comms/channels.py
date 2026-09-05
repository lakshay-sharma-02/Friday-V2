"""Channel abstraction — abstract interface for all messaging platforms.

Each channel wraps a platform (WhatsApp, Telegram, Discord, etc.)
and provides send/receive/status operations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    """A message to send or received from a channel."""

    channel: str
    recipient: str
    content: str
    message_type: str = "text"  # "text" | "file" | "image" | "voice"
    file_path: str | None = None
    reply_to: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChannelStatus:
    """Status of a messaging channel."""

    name: str
    connected: bool
    last_activity: float = 0.0
    messages_sent: int = 0
    messages_received: int = 0
    error: str | None = None


class Channel(ABC):
    """Abstract channel interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Channel name (e.g. 'whatsapp', 'telegram')."""
        ...

    @abstractmethod
    def send(self, message: Message) -> str:
        """Send a message. Returns the platform message ID."""
        ...

    @abstractmethod
    def receive(self, limit: int = 10) -> list[dict[str, Any]]:
        """Poll for new incoming messages."""
        ...

    @abstractmethod
    def status(self) -> ChannelStatus:
        """Get channel status."""
        ...

    def is_available(self) -> bool:
        """Check if the channel is available for sending."""
        return self.status().connected


# Channel registry
_CHANNELS: dict[str, Channel] = {}


def register_channel(channel: Channel) -> None:
    """Register a channel."""
    _CHANNELS[channel.name] = channel


def get_channel(name: str) -> Channel | None:
    """Get a registered channel by name."""
    return _CHANNELS.get(name)


def list_channels() -> dict[str, Channel]:
    """List all registered channels."""
    return dict(_CHANNELS)


def select_channel(
    message: Message,
    preferences: dict[str, Any] | None = None,
) -> Channel | None:
    """Select the best channel for a message.

    Considers:
    - Which channels are available
    - User preferences (from memory)
    - Message type (text vs file)
    - Time of day (don't disturb at night)
    """
    available = {name: ch for name, ch in _CHANNELS.items() if ch.is_available()}
    if not available:
        return None

    # Prefer user's preferred channel
    if preferences:
        preferred = preferences.get("preferred_channel")
        if preferred and preferred in available:
            return available[preferred]

    # For files, prefer platforms that support file sending
    if message.file_path:
        for name in ("whatsapp", "telegram", "discord"):
            if name in available:
                return available[name]

    # Default: first available
    return next(iter(available.values()))
