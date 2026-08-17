"""L1 primitive: discord (official Discord REST API).

Deterministic HTTPS mechanism for sending text / file messages to a channel
- a single multipart POST per message, no websocket gateway needed for
sending. Files are attached directly.

Credentials (never hardcoded, never logged in plaintext):
  - env vars DISCORD_BOT_TOKEN + DISCORD_CHANNEL_ID, or
  - a pass entry `friday/discord` (JSON) with bot_token and channel_id.

Recipient rules (documented so the contract is honest):
  - The bot must be invited to the server (OAuth2 invite with Send Messages
    + Attach Files permissions) and channel_id must point at a channel the
    bot can see. There is no recipient cap - any channel the bot can
    access is fair game.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError
from friday.secrets import get_credentials

API_BASE = "https://discord.com/api/v10"
TIMEOUT_S = 60


def _auth() -> tuple[str, str]:
    token = os.environ.get("DISCORD_BOT_TOKEN")
    channel_id = os.environ.get("DISCORD_CHANNEL_ID")
    if not (token and channel_id):
        creds = get_credentials("discord")
        token = creds.get("bot_token") or creds.get("token")
        channel_id = creds.get("channel_id")
    if not (token and channel_id):
        raise PrimitiveError(
            "discord credentials missing: set DISCORD_BOT_TOKEN and "
            "DISCORD_CHANNEL_ID, or store them in pass at friday/discord",
            state="nothing sent",
        )
    return token, channel_id


@contract(
    precondition="bot_token is configured and valid.",
    postcondition="Returns the bot's own username; nothing is sent. Confirms "
    "the credential path end-to-end before any messaging.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError with the API detail on non-2xx.",
    returns="str: the bot username, e.g. 'FridayBot'.",
)
def get_me() -> str:
    token, _ = _auth()
    resp = requests.get(
        f"{API_BASE}/users/@me",
        headers={"Authorization": f"Bot {token}"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise PrimitiveError(
            f"discord getMe failed ({resp.status_code}): {resp.text[:300]}",
            state="credentials not confirmed",
        )
    return str((resp.json() or {}).get("username", ""))


@contract(
    precondition="bot_token and channel_id are configured; the file exists; "
    "channel_id is non-empty (defaults to the configured channel_id).",
    postcondition="Discord accepts the message with attachment; the returned "
    "message id is proof of acceptance.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PreconditionError for a missing file or empty channel_id; "
    "PrimitiveError with the API detail on failure. If the response is lost "
    "the message may still have been sent - verify before retrying.",
    returns="dict: {message_id, channel_id, filename, api}.",
)
def send_file(
    file_path: str, channel_id: str | None = None, caption: str | None = None
) -> dict[str, Any]:
    """Send a local file as an attachment to a channel, defaulting to the
    configured channel_id when omitted. Any file type is accepted and sent
    as-is (Discord imposes no MIME allow-list)."""
    if not Path(file_path).exists():
        raise PreconditionError(f"send_file requires an existing file: {file_path!r}")
    token, configured_channel = _auth()
    target = channel_id or configured_channel
    if not target:
        raise PreconditionError(
            "send_file requires a channel_id: pass one or configure it in credentials"
        )
    with open(file_path, "rb") as fh:
        files = {"file": (Path(file_path).name, fh, "application/octet-stream")}
        payload: dict[str, Any] = {}
        if caption:
            payload["content"] = caption
        resp = requests.post(
            f"{API_BASE}/channels/{target}/messages",
            headers={"Authorization": f"Bot {token}"},
            data=payload,
            files=files,
            timeout=TIMEOUT_S,
        )
    if resp.status_code != 200:
        raise PrimitiveError(
            f"discord send_file failed ({resp.status_code}): {resp.text[:500]}",
            state="message not accepted by Discord",
        )
    try:
        body = resp.json()
    except ValueError as exc:
        raise PrimitiveError(
            f"discord send_file returned non-JSON: {resp.text[:300]}",
            state="message status unknown",
        ) from exc
    message_id = body.get("id")
    if not message_id:
        raise PrimitiveError(
            f"discord send_file returned no message id: {resp.text[:300]}",
            state="message status unknown",
        )
    return {
        "message_id": str(message_id),
        "channel_id": target,
        "filename": Path(file_path).name,
        "api": body,
    }


@contract(
    precondition="bot_token and channel_id are configured; channel_id is "
    "non-empty (defaults to the configured channel_id).",
    postcondition="Discord accepts the text message; the returned message id "
    "is proof of acceptance.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PreconditionError for empty text or channel_id; PrimitiveError "
    "with the API detail on failure.",
    returns="dict: {message_id, channel_id, api}.",
)
def send_text(text: str, channel_id: str | None = None) -> dict[str, Any]:
    if not text:
        raise PreconditionError("send_text requires non-empty text")
    token, configured_channel = _auth()
    target = channel_id or configured_channel
    if not target:
        raise PreconditionError(
            "send_text requires a channel_id: pass one or configure it in credentials"
        )
    resp = requests.post(
        f"{API_BASE}/channels/{target}/messages",
        headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
        json={"content": text},
        timeout=30,
    )
    if resp.status_code != 200:
        raise PrimitiveError(
            f"discord send_text failed ({resp.status_code}): {resp.text[:500]}",
            state="message not accepted by Discord",
        )
    try:
        body = resp.json()
    except ValueError as exc:
        raise PrimitiveError(
            f"discord send_text returned non-JSON: {resp.text[:300]}",
            state="message status unknown",
        ) from exc
    message_id = body.get("id")
    if not message_id:
        raise PrimitiveError(
            f"discord send_text returned no message id: {resp.text[:300]}",
            state="message status unknown",
        )
    return {"message_id": str(message_id), "channel_id": target, "api": body}
