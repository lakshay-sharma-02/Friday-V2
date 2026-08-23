"""L1 primitive: telegram (official Telegram Bot API).

Deterministic HTTPS mechanism for sending text / document messages AND
receiving media files - the Bot API is a plain HTTP POST, no browser,
no websocket. Files are uploaded directly (multipart), so no media-id
dance and no public URL hosting is required.

Receiving: Telegram bots can POLL for incoming messages via getUpdates
(no webhook, no public URL, works behind NAT). Each update carries
message content including photo/document/file_id values that can be
downloaded via getFile.

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

# Default offset file: tracks the last processed update_id so we never
# re-download the same messages. Persisted in var/state/ (gitignored).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OFFSET_FILE = PROJECT_ROOT / "var" / "state" / "telegram_offset.json"


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
        chat_id = creds.get("chat_id") or ""
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
    return str((body.get("result") or {}).get("username", ""))


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
def send_document(
    file_path: str, to: str | None = None, caption: str | None = None
) -> dict[str, Any]:
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


# ---- incoming media polling + download (2026-08-19) ----
# Telegram bots can POLL for incoming messages via getUpdates - no
# webhook, no public URL, works behind NAT. The offset mechanism
# ensures we never re-process the same update.


def _offset_file() -> Path:
    return Path(os.environ.get(
        "FRIDAY_TELEGRAM_OFFSET_FILE", str(DEFAULT_OFFSET_FILE)
    ))


def _load_offset() -> int:
    """Load the last processed update_id. Returns 0 on any error (first
    poll starts from the beginning)."""
    try:
        data = __import__("json").loads(_offset_file().read_text(encoding="utf-8"))
        return int(data.get("offset", 0))
    except (OSError, ValueError, KeyError):
        return 0


def _save_offset(offset: int) -> None:
    """Persist the last processed update_id. Atomic write, best-effort."""
    import json as _json

    path = _offset_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(_json.dumps({"offset": offset}) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


@contract(
    precondition="bot_token is configured and the token is valid.",
    postcondition="Returns a list of new incoming messages since the last poll. Each message dict contains at minimum: update_id, message_id, chat_id, date, and any media fields (photo, document, etc.).",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError on API failure.",
    returns="list[dict]: messages with update_id, message_id, chat_id, date, text/photo/document/audio/video fields.",
)
def poll_updates(limit: int = 10) -> list[dict[str, Any]]:
    """Poll for new incoming messages. Uses getUpdates with offset tracking
    so each message is processed exactly once. Returns a list of parsed
    message dicts (only messages that contain media are included - text
    messages are skipped since there is nothing to download)."""
    token = _get_token()
    offset = _load_offset()
    params: dict[str, Any] = {"limit": limit, "timeout": 0}
    if offset > 0:
        params["offset"] = offset
    try:
        resp = requests.get(
            _api_url(token, "getUpdates"), params=params, timeout=30
        )
    except requests.Timeout as exc:
        raise PrimitiveError(
            "telegram getUpdates timed out", state="offset not updated"
        ) from exc
    if resp.status_code != 200:
        raise PrimitiveError(
            f"telegram getUpdates failed ({resp.status_code}): {resp.text[:300]}",
            state="offset not updated",
        )
    body = resp.json()
    if not body.get("ok"):
        raise PrimitiveError(
            f"telegram getUpdates rejected: {resp.text[:300]}",
            state="offset not updated",
        )
    updates = body.get("result", [])
    messages: list[dict[str, Any]] = []
    max_id = offset
    for update in updates:
        uid = update.get("update_id", 0)
        if uid >= max_id:
            max_id = uid + 1
        msg = update.get("message", {})
        if not msg:
            continue
        # Only include messages that carry media
        has_media = any(
            msg.get(field) for field in ("photo", "document", "audio", "video", "sticker")
        )
        if not has_media:
            continue
        parsed = {
            "update_id": uid,
            "message_id": msg.get("message_id"),
            "chat_id": str(msg.get("chat", {}).get("id", "")),
            "date": msg.get("date", 0),
            "from": msg.get("from", {}).get("username", ""),
        }
        # Extract the relevant media field
        for field in ("photo", "document", "audio", "video", "sticker"):
            if msg.get(field):
                parsed["media_type"] = field
                if field == "photo":
                    # Telegram sends multiple sizes; take the largest
                    photos = msg["photo"]
                    parsed["file_id"] = photos[-1]["file_id"]
                    parsed["filename"] = photos[-1].get("file_unique_id", "photo") + ".jpg"
                else:
                    media_obj = msg[field]
                    parsed["file_id"] = media_obj.get("file_id", "")
                    parsed["filename"] = media_obj.get("file_name") or (
                        media_obj.get("file_unique_id", "file") + ".bin"
                    )
                break
        if msg.get("caption"):
            parsed["caption"] = msg["caption"]
        messages.append(parsed)
    # Advance offset so we never re-process these updates
    if max_id > offset:
        _save_offset(max_id)
    return messages


@contract(
    precondition="file_id is a non-empty string; bot_token is configured.",
    postcondition="The file is downloaded to dest_dir with an appropriate filename.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError for empty file_id; PrimitiveError on"
    " network/download failure.",
    returns="dict: {path, filename, file_size, file_id}.",
)
def download_file(
    file_id: str,
    dest_dir: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    """Download a file from Telegram using its file_id.

    The flow: 1) getFile returns a file_path on Telegram's servers,
    2) GET https://api.telegram.org/file/bot<TOKEN>/<path> returns the
    binary content.
    """
    if not file_id or not file_id.strip():
        raise PreconditionError("download_file requires a non-empty file_id")
    from pathlib import Path as _Path

    dest = _Path(dest_dir) if dest_dir else _Path.home() / "Downloads"
    if not dest.is_dir():
        raise PreconditionError(f"download_file: dest_dir does not exist: {dest}")

    token = _get_token()
    # Step 1: get file info
    try:
        resp = requests.get(
            _api_url(token, "getFile"),
            params={"file_id": file_id.strip()},
            timeout=30,
        )
    except requests.Timeout as exc:
        raise PrimitiveError("telegram getFile timed out", state="file not downloaded") from exc
    if resp.status_code != 200:
        raise PrimitiveError(
            f"telegram getFile failed ({resp.status_code}): {resp.text[:300]}",
            state="file not downloaded",
        )
    body = resp.json()
    if not body.get("ok"):
        raise PrimitiveError(
            f"telegram getFile rejected: {resp.text[:300]}",
            state="file not downloaded",
        )
    file_path = (body.get("result") or {}).get("file_path", "")
    if not file_path:
        raise PrimitiveError(
            f"telegram getFile returned no file_path: {resp.text[:300]}",
            state="file not downloaded",
        )

    # Step 2: download the binary
    download_url = f"{API_BASE}/file/bot{token}/{file_path}"
    try:
        dl_resp = requests.get(download_url, timeout=TIMEOUT_S)
    except requests.Timeout as exc:
        raise PrimitiveError(
            f"telegram file download timed out after {TIMEOUT_S}s",
            state="file_path retrieved but download incomplete",
        ) from exc
    if dl_resp.status_code != 200:
        raise PrimitiveError(
            f"telegram file download failed ({dl_resp.status_code}): {dl_resp.text[:300]}",
            state="file_path retrieved but download failed",
        )

    # Step 3: determine filename
    if not filename:
        # Use the original filename from the path, or fallback
        filename = Path(file_path).name or f"{file_id}.bin"

    out_path = dest / filename
    out_path.write_bytes(dl_resp.content)

    return {
        "path": str(out_path),
        "filename": filename,
        "file_size": len(dl_resp.content),
        "file_id": file_id,
    }
