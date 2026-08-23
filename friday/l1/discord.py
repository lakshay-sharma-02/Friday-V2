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


# ---- inbound message polling (2026-08-23) ----
# Discord bots can read channel messages via REST API (GET /channels/{id}/messages).
# For receiving, the standard approach is the gateway websocket, but REST polling
# works for simpler use cases (reading recent messages, checking for attachments).
# The offset mechanism tracks the last processed message ID.

import json as _json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OFFSET_FILE = PROJECT_ROOT / "var" / "state" / "discord_offset.json"


def _offset_file() -> Path:
    return Path(os.environ.get(
        "FRIDAY_DISCORD_OFFSET_FILE", str(DEFAULT_OFFSET_FILE)
    ))


def _load_offset() -> int:
    """Load the last processed message ID. Returns 0 on any error."""
    try:
        data = _json.loads(_offset_file().read_text(encoding="utf-8"))
        return int(data.get("offset", 0))
    except (OSError, ValueError, KeyError):
        return 0


def _save_offset(offset: int) -> None:
    """Persist the last processed message ID. Atomic write, best-effort."""
    path = _offset_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(_json.dumps({"offset": offset}) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


@contract(
    precondition="bot_token and channel_id are configured and valid.",
    postcondition="Returns new messages since the last poll. Each message dict contains: id, author, content, timestamp, and any attachments.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError on API failure.",
    returns="list[dict]: messages with id, author, content, timestamp, attachments.",
)
def poll_messages(limit: int = 50) -> list[dict[str, Any]]:
    """Poll for new messages in the configured channel.

    Uses the REST API to get recent messages, filtering by the last
    processed message ID to avoid re-processing. Returns messages with
    their content, author, and attachments.

    Note: This reads messages the bot can see. The bot must have
    'Read Message History' permission in the channel.
    """
    token, channel_id = _auth()
    if not channel_id:
        raise PreconditionError(
            "poll_messages requires a channel_id: configure one in credentials"
        )

    after_id = _load_offset()
    params: dict[str, Any] = {"limit": min(limit, 100)}
    if after_id > 0:
        params["after"] = str(after_id)

    try:
        resp = requests.get(
            f"{API_BASE}/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {token}"},
            params=params,
            timeout=30,
        )
    except requests.Timeout as exc:
        raise PrimitiveError(
            "discord getMessages timed out", state="offset not updated"
        ) from exc
    if resp.status_code != 200:
        raise PrimitiveError(
            f"discord getMessages failed ({resp.status_code}): {resp.text[:300]}",
            state="offset not updated",
        )

    messages_raw = resp.json()
    if not isinstance(messages_raw, list):
        raise PrimitiveError(
            f"discord getMessages returned non-list: {resp.text[:300]}",
            state="offset not updated",
        )

    # Discord returns newest-first; reverse for chronological order
    messages_raw.reverse()

    messages: list[dict[str, Any]] = []
    max_id = after_id

    for msg in messages_raw:
        msg_id = int(msg.get("id", "0"))
        if msg_id <= after_id:
            continue
        if msg_id > max_id:
            max_id = msg_id

        # Skip messages from the bot itself
        author = msg.get("author", {})
        if author.get("bot", False):
            continue

        parsed = {
            "id": str(msg_id),
            "author": author.get("username", ""),
            "author_id": author.get("id", ""),
            "content": msg.get("content", ""),
            "timestamp": msg.get("timestamp", ""),
            "attachments": [
                {
                    "filename": a.get("filename", ""),
                    "url": a.get("url", ""),
                    "size": a.get("size", 0),
                    "content_type": a.get("content_type", ""),
                }
                for a in msg.get("attachments", [])
            ],
        }
        if msg.get("embeds"):
            parsed["embeds"] = len(msg["embeds"])
        messages.append(parsed)

    # Advance offset
    if max_id > after_id:
        _save_offset(max_id)

    return messages


@contract(
    precondition="file_url is a valid Discord CDN URL; bot_token is configured.",
    postcondition="The file is downloaded to dest_dir.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError for empty URL; PrimitiveError on download failure.",
    returns="dict: {path, filename, file_size}.",
)
def download_attachment(
    file_url: str,
    dest_dir: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    """Download a file attachment from Discord's CDN.

    Use the URL from poll_messages() attachments to download the file.
    No authentication needed for Discord CDN URLs (they are public).
    """
    if not file_url or not file_url.strip():
        raise PreconditionError("download_attachment requires a non-empty file_url")

    dest = Path(dest_dir) if dest_dir else Path.home() / "Downloads"
    if not dest.is_dir():
        raise PreconditionError(f"download_attachment: dest_dir does not exist: {dest}")

    try:
        resp = requests.get(file_url.strip(), timeout=TIMEOUT_S)
    except requests.Timeout as exc:
        raise PrimitiveError(
            f"discord file download timed out after {TIMEOUT_S}s",
            state="file not downloaded",
        ) from exc
    if resp.status_code != 200:
        raise PrimitiveError(
            f"discord file download failed ({resp.status_code})",
            state="file not downloaded",
        )

    if not filename:
        # Try to extract from Content-Disposition header
        cd = resp.headers.get("Content-Disposition", "")
        if "filename=" in cd:
            filename = cd.split("filename=")[-1].strip('"\' ')
        else:
            filename = Path(file_url.split("?")[0]).name or "discord_download.bin"

    out_path = dest / filename
    out_path.write_bytes(resp.content)

    return {
        "path": str(out_path),
        "filename": filename,
        "file_size": len(resp.content),
    }


# ---- inbound text message queue (2026-08-24) ----
# Discord bots can receive text messages via REST. This queue stores
# incoming text messages for the watcher to process.

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PENDING_TEXT_FILE = PROJECT_ROOT / "var" / "state" / "discord_pending_text.json"


def _pending_text_file() -> Path:
    return Path(os.environ.get(
        "FRIDAY_DISCORD_PENDING_TEXT_FILE", str(DEFAULT_PENDING_TEXT_FILE)
    ))


def enqueue_text_message(
    message_id: str,
    channel_id: str,
    text: str,
    sender: str = "",
) -> dict[str, Any]:
    """Enqueue an incoming text message for the watcher to process."""
    if not message_id:
        raise PreconditionError("enqueue_text_message requires a non-empty message_id")
    pending = _pending_text_file()
    pending.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, Any]] = []
    try:
        data = json.loads(pending.read_text(encoding="utf-8"))
        if isinstance(data, list):
            existing = data
    except (OSError, ValueError):
        pass
    seen_ids = {item.get("message_id") for item in existing}
    if message_id in seen_ids:
        return {"status": "already_enqueued", "message_id": message_id}
    entry = {
        "message_id": message_id,
        "channel_id": channel_id,
        "text": text,
        "sender": sender,
    }
    existing.append(entry)
    tmp = pending.with_name(pending.name + ".tmp")
    tmp.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, pending)
    return {"status": "enqueued", "message_id": message_id, "pending_count": len(existing)}


def load_pending_text() -> list[dict[str, Any]]:
    """Read and return the pending text message queue."""
    try:
        data = json.loads(_pending_text_file().read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def clear_pending_text(message_ids: list[str] | None = None) -> None:
    """Remove processed message_ids from the pending file."""
    pending = _pending_text_file()
    try:
        existing: list[dict[str, Any]] = json.loads(
            pending.read_text(encoding="utf-8")
        )
        if not isinstance(existing, list):
            existing = []
    except (OSError, ValueError):
        existing = []
    if message_ids is None:
        new_list: list[dict[str, Any]] = []
    else:
        ids_to_remove = set(message_ids)
        new_list = [item for item in existing if item.get("message_id") not in ids_to_remove]
    pending.parent.mkdir(parents=True, exist_ok=True)
    tmp = pending.with_name(pending.name + ".tmp")
    tmp.write_text(json.dumps(new_list, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, pending)
