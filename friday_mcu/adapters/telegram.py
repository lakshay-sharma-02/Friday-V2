"""Telegram Bot API adapter.

Ported from V8 l1/telegram.py with the same contract-registered primitives.
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

STATE_DIR = Path.home() / ".config" / "friday" / "telegram"
OFFSET_FILE = STATE_DIR / "offset.json"


def _get_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise AdapterError("TELEGRAM_BOT_TOKEN not set")
    return token


def _api_url(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def _load_offset() -> int:
    if OFFSET_FILE.exists():
        try:
            return int(json.loads(OFFSET_FILE.read_text()))
        except (ValueError, OSError):
            pass
    return 0


def _save_offset(offset: int) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OFFSET_FILE.write_text(json.dumps(offset))


@contract(
    precondition="TELEGRAM_BOT_TOKEN is set.",
    postcondition="Returns the bot's profile info.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="AdapterError if the API call fails.",
    returns="dict: bot info from getMe.",
)
def get_me() -> dict[str, Any]:
    """Get Telegram bot profile."""
    token = _get_token()
    try:
        resp = requests.get(_api_url(token, "getMe"), timeout=10)
        resp.raise_for_status()
        return resp.json().get("result", {})
    except Exception as exc:
        raise AdapterError(f"Telegram getMe failed: {exc}") from exc


@contract(
    precondition="text is non-empty and chat_id is set.",
    postcondition="Returns {message_id, chat_id, status}.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="AdapterError if the send fails.",
    returns="dict: {message_id: str, chat_id: str, status: str}.",
)
def send_text(text: str, to: str = "") -> dict[str, Any]:
    """Send a text message via Telegram."""
    token = _get_token()
    chat_id = to or os.environ.get("TELEGRAM_DEFAULT_CHAT", "")
    if not chat_id:
        raise PreconditionError("No chat_id and no TELEGRAM_DEFAULT_CHAT set")
    try:
        resp = requests.post(
            _api_url(token, "sendMessage"),
            json={"chat_id": chat_id, "text": text},
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json().get("result", {})
        return {"message_id": str(result.get("message_id", "")), "chat_id": chat_id, "status": "sent"}
    except Exception as exc:
        raise AdapterError(f"Telegram sendText failed: {exc}") from exc


@contract(
    precondition="file_path points to an existing file.",
    postcondition="Returns {message_id, chat_id, status, file}.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="AdapterError if upload or send fails.",
    returns="dict: {message_id: str, chat_id: str, status: str, file: str}.",
)
def send_document(file_path: str, to: str = "", caption: str = "") -> dict[str, Any]:
    """Send a document via Telegram."""
    token = _get_token()
    chat_id = to or os.environ.get("TELEGRAM_DEFAULT_CHAT", "")
    if not chat_id:
        raise PreconditionError("No chat_id and no TELEGRAM_DEFAULT_CHAT set")
    p = Path(file_path)
    if not p.exists():
        raise PreconditionError(f"File not found: {file_path}")
    try:
        with open(p, "rb") as f:
            resp = requests.post(
                _api_url(token, "sendDocument"),
                data={"chat_id": chat_id, "caption": caption} if caption else {"chat_id": chat_id},
                files={"document": (p.name, f)},
                timeout=60,
            )
        resp.raise_for_status()
        result = resp.json().get("result", {})
        return {
            "message_id": str(result.get("message_id", "")),
            "chat_id": chat_id,
            "status": "sent",
            "file": p.name,
        }
    except Exception as exc:
        raise AdapterError(f"Telegram sendDocument failed: {exc}") from exc


@contract(
    precondition="TELEGRAM_BOT_TOKEN is set.",
    postcondition="Returns a list of received messages.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="AdapterError if polling fails.",
    returns="list[dict]: [{message_id, chat_id, text, from}].",
)
def poll_updates(limit: int = 10, commit: bool = True) -> list[dict[str, Any]]:
    """Poll for new Telegram messages.

    commit=False leaves the persisted offset untouched so the caller can
    process messages first and call mark_read() only for what it actually
    handled — a crash mid-processing must not permanently lose messages.
    """
    token = _get_token()
    offset = _load_offset()
    params: dict[str, Any] = {"limit": limit, "timeout": 5}
    if offset > 0:
        params["offset"] = offset
    try:
        resp = requests.get(_api_url(token, "getUpdates"), params=params, timeout=15)
        resp.raise_for_status()
        updates = resp.json().get("result", [])
    except Exception:
        return []

    messages: list[dict[str, Any]] = []
    max_update_id = offset
    for update in updates:
        update_id = update.get("update_id", 0)
        if update_id >= max_update_id:
            max_update_id = update_id + 1
        msg = update.get("message", {})
        if not msg:
            continue
        text = msg.get("text", "")
        chat_id = str(msg.get("chat", {}).get("id", ""))
        from_user = msg.get("from", {}).get("username", "")
        msg_id = str(msg.get("message_id", ""))
        if text and chat_id:
            messages.append({
                "update_id": update_id,
                "message_id": msg_id,
                "chat_id": chat_id,
                "text": text,
                "from": from_user,
            })

    if commit and max_update_id > offset:
        _save_offset(max_update_id)

    return messages


def mark_read(update_ids: list[int]) -> None:
    """Advance the persisted offset past the given update ids.

    Call after successfully processing the returned messages. Telegram only
    supports a contiguous offset (it cannot skip selectively), so passing the
    ids you handled is enough — earlier uncommitted updates would be returned
    again on the next poll.
    """
    if not update_ids:
        return
    highest = max(update_ids)
    if highest + 1 > _load_offset():
        _save_offset(highest + 1)


def poll_text_messages(limit: int = 10) -> list[dict[str, Any]]:
    """Poll for new text messages without committing the offset.

    The caller processes each message and calls mark_read() per handled
    update_id, so a failure on one message never loses the rest.
    """
    return poll_updates(limit=limit, commit=False)


def poll_media(limit: int = 10, commit: bool = False) -> list[dict[str, Any]]:
    """Poll for new MEDIA messages (photos/documents/audio/video).

    poll_updates intentionally returns text-only messages, so media arrivals
    need their own probe/download path. commit=False by default; the caller
    calls mark_read() once the batch has been handled successfully.
    """
    token = _get_token()
    offset = _load_offset()
    params: dict[str, Any] = {"limit": limit, "timeout": 5}
    if offset > 0:
        params["offset"] = offset
    try:
        resp = requests.get(_api_url(token, "getUpdates"), params=params, timeout=15)
        resp.raise_for_status()
        updates = resp.json().get("result", [])
    except Exception:
        return []

    media: list[dict[str, Any]] = []
    max_update_id = offset
    for update in updates:
        update_id = update.get("update_id", 0)
        if update_id >= max_update_id:
            max_update_id = update_id + 1
        msg = update.get("message", {})
        if not msg:
            continue
        chat_id = str(msg.get("chat", {}).get("id", ""))
        if not chat_id:
            continue
        file_id = ""
        filename = ""
        if "document" in msg:
            file_id = str(msg["document"].get("file_id", ""))
            filename = str(msg["document"].get("file_name", ""))
        elif "video" in msg:
            file_id = str(msg["video"].get("file_id", ""))
        elif "audio" in msg:
            file_id = str(msg["audio"].get("file_id", ""))
        elif "photo" in msg and msg["photo"]:
            file_id = str(msg["photo"][-1].get("file_id", ""))
        if not file_id:
            continue
        media.append({
            "update_id": update_id,
            "message_id": str(msg.get("message_id", "")),
            "chat_id": chat_id,
            "file_id": file_id,
            "filename": filename,
            "from": msg.get("from", {}).get("username", ""),
        })

    if commit and max_update_id > offset:
        _save_offset(max_update_id)

    return media


class TelegramAdapter(Adapter):
    """Telegram Bot API adapter."""

    @property
    def name(self) -> str:
        return "telegram"

    @property
    def capabilities(self) -> list[str]:
        return ["get_me", "send_text", "send_document", "poll_updates", "poll_text_messages", "poll_media", "mark_read"]

    async def initialize(self) -> None:
        _get_token()  # will raise if not set

    async def execute(self, action: str, **kwargs: Any) -> Any:
        actions = {
            "get_me": get_me,
            "send_text": send_text,
            "send_document": send_document,
            "poll_updates": poll_updates,
            "poll_text_messages": poll_text_messages,
            "poll_media": poll_media,
            "mark_read": mark_read,
        }
        fn = actions.get(action)
        if fn is None:
            raise AdapterError(f"Unknown telegram action: {action}")
        return fn(**kwargs)

    async def observe(self) -> list:
        return []

    def health_check(self) -> bool:
        return bool(os.environ.get("TELEGRAM_BOT_TOKEN"))


try:
    register_adapter(TelegramAdapter())
except Exception:
    pass
