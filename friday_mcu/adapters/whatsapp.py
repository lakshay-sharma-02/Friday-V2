"""WhatsApp Cloud API adapter.

Demonstrates the adapter pattern for MCU Friday.
Each adapter is a self-contained plugin with @contract-registered primitives.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests

from friday_mcu.adapters import Adapter, register_adapter
from friday_mcu.core.contracts import Idempotency, contract
from friday_mcu.core.errors import AdapterError, PreconditionError
from friday_mcu.core.events import EventType, Event


# ── Adapter class

class WhatsAppAdapter(Adapter):
    """WhatsApp Cloud API adapter."""

    def __init__(self) -> None:
        self._token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
        self._phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
        self._default_phone = os.environ.get("WHATSAPP_DEFAULT_PHONE", "")
        self._api_url = f"https://graph.facebook.com/v18.0/{self._phone_id}"

    @property
    def name(self) -> str:
        return "whatsapp"

    @property
    def capabilities(self) -> list[str]:
        return ["send_text", "send_document", "get_me"]

    async def initialize(self) -> None:
        if not self._token:
            raise AdapterError("WHATSAPP_ACCESS_TOKEN not set")
        if not self._phone_id:
            raise AdapterError("WHATSAPP_PHONE_NUMBER_ID not set")

    async def execute(self, action: str, **kwargs: Any) -> Any:
        if action == "send_text":
            return self._send_text(**kwargs)
        elif action == "send_document":
            return self._send_document(**kwargs)
        elif action == "get_me":
            return self._get_me()
        raise AdapterError(f"Unknown action: {action}")

    async def observe(self) -> list[Event]:
        """WhatsApp doesn't have a polling-based inbound — use webhook instead."""
        return []

    def health_check(self) -> bool:
        return bool(self._token and self._phone_id)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _get_me(self) -> dict[str, Any]:
        """Get the WhatsApp business account info."""
        try:
            resp = requests.get(
                f"{self._api_url}",
                headers=self._headers(),
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            raise AdapterError(f"WhatsApp get_me failed: {exc}") from exc

    def _send_text(self, text: str, to: str = "") -> dict[str, Any]:
        """Send a text message."""
        recipient = to or self._default_phone
        if not recipient:
            raise PreconditionError("No recipient specified and no default phone configured")
        try:
            resp = requests.post(
                f"{self._api_url}/messages",
                headers=self._headers(),
                json={
                    "messaging_product": "whatsapp",
                    "to": recipient,
                    "type": "text",
                    "text": {"body": text},
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            msg_id = data.get("messages", [{}])[0].get("id", "")
            return {"message_id": msg_id, "status": "sent"}
        except Exception as exc:
            raise AdapterError(f"WhatsApp send_text failed: {exc}") from exc

    def _send_document(self, file_path: str, to: str = "", body: str = "") -> dict[str, Any]:
        """Send a document."""
        recipient = to or self._default_phone
        if not recipient:
            raise PreconditionError("No recipient specified and no default phone configured")
        path = Path(file_path)
        if not path.exists():
            raise PreconditionError(f"File not found: {file_path}")

        # Detect MIME type from extension
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".pdf": "application/pdf",
            ".txt": "text/plain",
            ".mp4": "video/mp4",
            ".mp3": "audio/mpeg",
        }
        mime_type = mime_map.get(path.suffix.lower(), "application/octet-stream")

        # Upload media first
        try:
            with open(path, "rb") as f:
                upload_resp = requests.post(
                    f"{self._api_url}/media",
                    headers={"Authorization": f"Bearer {self._token}"},
                    files={"file": (path.name, f, mime_type)},
                    data={"messaging_product": "whatsapp", "type": mime_type},
                    timeout=30,
                )
            upload_resp.raise_for_status()
            media_id = upload_resp.json().get("id", "")

            # Send the document
            resp = requests.post(
                f"{self._api_url}/messages",
                headers=self._headers(),
                json={
                    "messaging_product": "whatsapp",
                    "to": recipient,
                    "type": "document",
                    "document": {
                        "id": media_id,
                        "filename": path.name,
                        "caption": body,
                    },
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            msg_id = data.get("messages", [{}])[0].get("id", "")
            return {"message_id": msg_id, "status": "sent", "file": path.name}
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError(f"WhatsApp send_document failed: {exc}") from exc


# ── Contract-registered primitives

@contract(
    precondition="WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID are set.",
    postcondition="Returns the WhatsApp business account info.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="AdapterError if the API call fails.",
    returns="dict: account info from the WhatsApp API.",
)
def get_me() -> dict[str, Any]:
    """Get WhatsApp business account info."""
    adapter = WhatsAppAdapter()
    return adapter._get_me()


@contract(
    precondition="text is non-empty and recipient is set (or default phone configured).",
    postcondition="Returns {message_id, status} for the sent message.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="AdapterError if the API call fails.",
    returns="dict: {message_id: str, status: str}.",
)
def send_text(text: str, to: str = "") -> dict[str, Any]:
    """Send a text message via WhatsApp."""
    adapter = WhatsAppAdapter()
    return adapter._send_text(text, to)


@contract(
    precondition="file_path points to an existing file.",
    postcondition="Returns {message_id, status, file} for the sent document.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="AdapterError if the upload or send fails.",
    returns="dict: {message_id: str, status: str, file: str}.",
)
def send_document(file_path: str, to: str = "", body: str = "") -> dict[str, Any]:
    """Send a document via WhatsApp."""
    adapter = WhatsAppAdapter()
    return adapter._send_document(file_path, to, body)


# ── Register the adapter
try:
    register_adapter(WhatsAppAdapter())
except Exception:
    pass  # adapter registration is best-effort
