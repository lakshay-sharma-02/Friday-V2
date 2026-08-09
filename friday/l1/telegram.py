"""L1 primitive: telegram (official Telegram Bot API).

Deterministic HTTPS mechanism for sending text / document messages - the
Bot API is a plain HTTP POST, no browser, no websocket. Files are uploaded
directly (multipart), so no media-id dance and no public URL hosting is
required (unlike WhatsApp's Cloud API).

Credentials (never hardcoded, never logged in plaintext):
  - env vars TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID, or
  - a pass entry `friday/telegram` (JSON) with bot_token and chat_id.

Recipient rules (documented so the contract is honest):
  - A bot can only message users who have STARTED a chat with it first
    (user presses Start / sends one message). That one user action opens
    an indefinite window - there is no 24h expiry and no 5-recipient cap
    like the WhatsApp test number. To send to someone new, they must
    message the bot once.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError
from friday.secrets import get_credentials

API_BASE = "https://api.telegram.org"
TIMEOUT_S = 60


def _get_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        creds = get_credentials("telegram")
        token = creds.get("bot_token") or creds.get("token")
    if not token:
        raise PrimitiveError(
            "telegram bot token missing: set TELEGRAM_BOT_TOKEN or store it in "
            "pass at friday/telegram",
            state="nothing sent",
        )
    return token


def _auth() -> tuple[str, str]:
    """Token for API calls plus the default chat id for sends. get_me needs
    only the token; senders need a destination."""
    token = _get_token()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not chat_id:
        creds = get_credentials("telegram")
        chat_id = creds.get("chat_id")
    return token, chat_id


def _api_url(token: str, method: str) -> str:
    return f"{API_BASE}/bot{token}/{method}"


@contract(
    precondition="bot_token and chat_id are configured and the token is valid.",
    postcondition="Returns the bot's own username; nothing is sent. Confirms "
    "the credential path end-to-end before any messaging.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError with the API detail on non-2xx or ok=false.",
    returns="str: the bot username, e.g. 'MyFridayBot'.",
)
def get_me() -> str:
    token = _get_token()
    resp = requests.get(_api_url(token, "getMe"), timeout=30)
    if resp.status_code != 200:
        raise PrimitiveError(
            f"telegram getMe failed ({resp.status_code}): {resp.text[:300]}",
            state="credentials not confirmed",
        )
    body = resp.json()
    if not body.get("ok"):
        raise PrimitiveError(
            f"telegram getMe rejected: {resp.text[:300]}",
            state="credentials not confirmed",
        )
    return (body.get("result") or {}).get("username", "")


@contract(
    precondition="file_path exists; bot_token and chat_id are configured; to is a "
    "non-empty chat id or @username (defaults to the configured chat_id).",
    postcondition="Telegram accepts the document message; the returned message "
    "id is proof of acceptance.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PreconditionError for a missing file or empty to; PrimitiveError "
    "with the API detail on failure. If the response is lost the message may "
    "still have been sent - verify before retrying.",
    returns="dict: {message_id, chat_id, filename, api}.",
)
def send_document(file_path: str, to: str | None = None, caption: str | None = None) -> dict[str, Any]:
    """Send a local file as a document to a chat.

    `to` is the chat id (numeric string) or @username of the recipient chat,
    defaulting to the configured chat_id when omitted. Unlike WhatsApp, any
    file type is accepted and sent as-is.
    """
    if not Path(file_path).exists():
        raise PreconditionError(f"send_document requires an existing file: {file_path!r}")
    token, configured_chat = _auth()
    chat_id = to or configured_chat
    if not chat_id:
        raise PreconditionError(
            "send_document requires a chat_id: pass `to` or configure one in credentials"
        )
    if not isinstance(chat_id, str) or not chat_id.strip():
        raise PreconditionError(f"send_document requires a non-empty chat id, got {chat_id!r}")
    with open(file_path, "rb") as fh:
        files = {"document": (Path(file_path).name, fh, "application/octet-stream")}
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
        resp = requests.post(
            _api_url(token, "sendDocument"),
            data=data,
            files=files,
            timeout=TIMEOUT_S,
        )
    if resp.status_code != 200:
        raise PrimitiveError(
            f"telegram sendDocument failed ({resp.status_code}): {resp.text[:500]}",
            state="message not accepted by Telegram",
        )
    try:
        body = resp.json()
    except ValueError as exc:
        raise PrimitiveError(
            f"telegram sendDocument returned non-JSON: {resp.text[:300]}",
            state="message status unknown",
        ) from exc
    if not body.get("ok"):
        raise PrimitiveError(
            f"telegram sendDocument rejected: {resp.text[:500]}",
            state="message not accepted by Telegram",
        )
    result = body.get("result") or {}
    message_id = result.get("message_id")
    if not message_id:
        raise PrimitiveError(
            f"telegram sendDocument returned no message id: {resp.text[:300]}",
            state="message status unknown",
        )
    return {
        "message_id": str(message_id),
        "chat_id": chat_id,
        "filename": Path(file_path).name,
        "api": body,
    }


@contract(
    precondition="bot_token and chat_id are configured; to is a non-empty chat id "
    "or @username (defaults to the configured chat_id).",
    postcondition="Telegram accepts the text message; the returned message id "
    "is proof of acceptance.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PreconditionError for empty text or to; PrimitiveError with the "
    "API detail on failure.",
    returns="dict: {message_id, chat_id, api}.",
)
def send_text(text: str, to: str | None = None) -> dict[str, Any]:
    if not text:
        raise PreconditionError("send_text requires non-empty text")
    token, configured_chat = _auth()
    chat_id = to or configured_chat
    if not chat_id:
        raise PreconditionError(
            "send_text requires a chat_id: pass `to` or configure one in credentials"
        )
    if not isinstance(chat_id, str) or not chat_id.strip():
        raise PreconditionError(f"send_text requires a non-empty chat id, got {chat_id!r}")
    resp = requests.post(
        _api_url(token, "sendMessage"),
        json={"chat_id": chat_id, "text": text},
        timeout=30,
    )
    if resp.status_code != 200:
        raise PrimitiveError(
            f"telegram sendMessage failed ({resp.status_code}): {resp.text[:500]}",
            state="message not accepted by Telegram",
        )
    try:
        body = resp.json()
    except ValueError as exc:
        raise PrimitiveError(
            f"telegram sendMessage returned non-JSON: {resp.text[:300]}",
            state="message status unknown",
        ) from exc
    if not body.get("ok"):
        raise PrimitiveError(
            f"telegram sendMessage rejected: {resp.text[:500]}",
            state="message not accepted by Telegram",
        )
    result = body.get("result") or {}
    message_id = result.get("message_id")
    if not message_id:
        raise PrimitiveError(
            f"telegram sendMessage returned no message id: {resp.text[:300]}",
            state="message status unknown",
        )
    return {"message_id": str(message_id), "chat_id": chat_id, "api": body}
