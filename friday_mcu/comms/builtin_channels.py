"""Concrete Channel implementations.

comms.channels defines the Channel interface but nothing ever implemented it,
so ProactiveEngine could queue suggestions forever and silently drop every one
(suggest -> no channel -> nothing). These adapters wrap the platform adapter
primitives and register themselves lazily — only for platforms whose
credentials are present — via register_builtin_channels().
"""

from __future__ import annotations

import os
from typing import Any

from friday_mcu.comms.channels import Channel, ChannelStatus, Message, register_channel
from friday_mcu.core.errors import AdapterError


class _AdapterChannel(Channel):
    """Shared machinery: dispatch send/receive/status to adapter functions."""

    #: adapter module name under friday_mcu.adapters
    platform = ""
    #: env vars that must all be set for the channel to be available
    _required_env: tuple[str, ...] = ()

    @classmethod
    def _health(cls) -> bool:
        return all(bool(os.environ.get(k)) for k in cls._required_env)

    def _adapter(self):
        import importlib
        return importlib.import_module(f"friday_mcu.adapters.{self.platform}")

    def send(self, message: Message) -> str:
        ad = self._adapter()
        recipient = message.recipient or ""
        if message.message_type == "file" and message.file_path:
            send = getattr(ad, "send_file" if self.platform == "discord" else "send_document")
            kwargs: dict[str, Any] = {"file_path": message.file_path, "to": recipient} if self.platform != "discord" else {"file_path": message.file_path, "channel_id": recipient}
            if message.content:
                if self.platform == "discord":
                    kwargs["caption"] = message.content
                else:
                    kwargs["caption" if self.platform == "telegram" else "body"] = message.content
            result = send(**kwargs)
            return str((result or {}).get("message_id", ""))
        send = getattr(ad, "send_text")
        if self.platform == "discord":
            result = send(message.content, channel_id=recipient)
        else:
            result = send(message.content, to=recipient)
        return str((result or {}).get("message_id", ""))

    def receive(self, limit: int = 10) -> list[dict[str, Any]]:
        ad = self._adapter()
        if self.platform == "telegram":
            try:
                return ad.poll_text_messages(limit=limit)
            except Exception:
                return []
        if self.platform == "discord":
            try:
                raw = ad.poll_messages(limit=limit)
            except Exception:
                return []
            return [
                {"text": m.get("content", ""), "from": m.get("author", ""), "chat_id": m.get("channel_id", "")}
                for m in raw
            ]
        return []  # whatsapp inbound is webhook-driven

    def status(self) -> ChannelStatus:
        return ChannelStatus(name=self.name, connected=self._health())

    @property
    def name(self) -> str:
        return self.platform


class TelegramChannel(_AdapterChannel):
    platform = "telegram"
    _required_env = ("TELEGRAM_BOT_TOKEN",)


class DiscordChannel(_AdapterChannel):
    platform = "discord"
    _required_env = ("DISCORD_BOT_TOKEN",)


class WhatsAppChannel(_AdapterChannel):
    platform = "whatsapp"
    _required_env = ("WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID")


def register_builtin_channels() -> set[str]:
    """Register a Channel for every platform whose credentials are present.

    Returns the names registered this call ([] on repeat calls). Safe to call
    repeatedly; never unregisters anything.
    """
    from friday_mcu.comms import channels

    registered: set[str] = set()
    existing = channels.list_channels()
    for cls in (TelegramChannel, DiscordChannel, WhatsAppChannel):
        if cls.platform not in existing and cls._health():
            try:
                register_channel(cls())
                registered.add(cls.platform)
            except AdapterError:
                pass
    return registered
