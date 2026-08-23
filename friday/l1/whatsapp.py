"""L1 primitive: whatsapp (official WhatsApp Business Cloud API).

Deterministic HTTP mechanism for sending text / document messages AND
downloading media received via WhatsApp - no browser, no chat-history
sync, no QR. Files are uploaded to WhatsApp's own servers and sent by
media id, so no public URL hosting is required. Incoming media (files,
images, audio, video sent TO Friday) can be downloaded via the media
download flow: get_media_url resolves a media_id to a download URL,
download_media fetches the binary content to disk.

Credentials (never hardcoded, never logged in plaintext):
  - env vars WHATSAPP_ACCESS_TOKEN + WHATSAPP_PHONE_NUMBER_ID, or
  - a pass entry `friday/whatsapp` (JSON) with access_token and
    phone_number_id.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import requests

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError
from friday.secrets import get_credentials

API_VERSION = "v22.0"  # bump if the Graph API rejects the version
GRAPH_URL = f"https://graph.facebook.com/{API_VERSION}"
UPLOAD_TIMEOUT_S = 60

# WhatsApp Cloud API only accepts media uploads with an allowed MIME type
# (rejecting octet-stream with 400). Map common extensions to those types.
# If an extension is missing, upload_document fails loudly rather than
# guessing - a wrong guess is exactly the silent-corruption the plan bans.
MIME_BY_EXTENSION: dict[str, str] = {
    # documents
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/plain",
    ".csv": "text/plain",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    # images
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    # audio
    ".mp3": "audio/mpeg",
    ".aac": "audio/aac",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".opus": "audio/opus",
    ".amr": "audio/amr",
}


def _mime_for(path: Path) -> str:
    mime = MIME_BY_EXTENSION.get(path.suffix.lower())
    if mime is None:
        raise PreconditionError(
            f"unsupported file type for whatsapp upload: {path.suffix or '(no extension)'}; "
            f"supported: {sorted(MIME_BY_EXTENSION)}"
        )
    return mime


def _auth() -> tuple[str, str]:
    token = os.environ.get("WHATSAPP_ACCESS_TOKEN")
    phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    if not (token and phone_id):
        creds = get_credentials("whatsapp")
        token = creds.get("access_token") or creds.get("token")
        phone_id = creds.get("phone_number_id")
    if not (token and phone_id):
        raise PrimitiveError(
            "whatsapp credentials missing: set WHATSAPP_ACCESS_TOKEN and "
            "WHATSAPP_PHONE_NUMBER_ID, or store them in pass at "
            "friday/whatsapp",
            state="nothing sent",
        )
    return token, phone_id


def _default_phone() -> str:
    """The default recipient for sends: WHATSAPP_DEFAULT_PHONE env or the
    'default_phone' key in the pass entry. Lets a plan omit `to` entirely
    (like telegram/discord default from their credentials) so the goal is
    recipient-agnostic."""
    phone = os.environ.get("WHATSAPP_DEFAULT_PHONE")
    if not phone:
        try:
            creds = get_credentials("whatsapp")
        except PrimitiveError:
            return ""
        phone = creds.get("default_phone") or ""
    return phone


@contract(
    precondition="access token and phone_number_id are configured and the token is valid.",
    postcondition="Returns the phone number the token belongs to; nothing is "
    "sent. Confirms the credential path end-to-end before any messaging.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError with the Graph API error detail on non-2xx.",
    returns="str: the display phone number, e.g. '15552014242'.",
)
def get_me() -> str:
    token, phone_id = _auth()
    resp = requests.get(
        f"{GRAPH_URL}/{phone_id}",
        headers={"Authorization": f"Bearer {token}"},
        params={"fields": "display_phone_number,verified_name"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise PrimitiveError(
            f"whatsapp get_me failed ({resp.status_code}): {resp.text[:300]}",
            state="credentials not confirmed",
        )
    body = resp.json()
    display = body.get("display_phone_number")
    if not display:
        raise PrimitiveError(
            f"whatsapp get_me returned no display_phone_number: {resp.text[:300]}",
            state="credentials not confirmed",
        )
    return str(display)


@contract(
    precondition="file_path exists, the access token is valid, and the file "
    "extension has an allowed WhatsApp MIME type.",
    postcondition="The file is uploaded to WhatsApp servers and a media id is "
    "returned (valid ~30 days). Nothing is sent yet.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="PreconditionError for missing/unsupported files; PrimitiveError "
    "with the Graph API error detail on non-2xx; no message is sent.",
    returns="str: the media id.",
)
def upload_document(file_path: str) -> str:
    if not Path(file_path).exists():
        raise PreconditionError(f"upload_document requires an existing file: {file_path!r}")
    mime = _mime_for(Path(file_path))
    token, phone_id = _auth()
    url = f"{GRAPH_URL}/{phone_id}/media"
    with open(file_path, "rb") as fh:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            data={"messaging_product": "whatsapp", "type": "document"},
            files={"file": (Path(file_path).name, fh, mime)},
            timeout=UPLOAD_TIMEOUT_S,
        )
    if resp.status_code not in (200, 201):
        raise PrimitiveError(
            f"whatsapp media upload failed ({resp.status_code}): {resp.text[:500]}",
            state="nothing sent",
        )
    media_id = resp.json().get("id")
    if not media_id:
        raise PrimitiveError(
            f"whatsapp media upload returned no id: {resp.text[:300]}",
            state="nothing sent",
        )
    return str(media_id)


@contract(
    precondition="to (if given) is a digit-only E.164 number without '+' (e.g. "
    "'918396020807'); when omitted it defaults to the configured default phone. "
    "file_path must exist.",
    postcondition="WhatsApp accepts the document message; the returned wamid is proof "
    "of acceptance by the API.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError with the Graph API error detail on non-2xx. If the "
    "response is lost, the message may still have been sent - verify before retrying.",
    returns="dict: {message_id, to, filename, api}.",
)
def send_document(
    file_path: str, to: str | None = None, caption: str | None = None
) -> dict[str, Any]:
    to = to or _default_phone()
    if not re.fullmatch(r"\d{10,15}", to):
        raise PreconditionError(
            f"to must be digit-only E.164 without '+' (or configure a default phone), got {to!r}"
        )
    if not Path(file_path).exists():
        raise PreconditionError(f"send_document requires an existing file: {file_path!r}")
    token, phone_id = _auth()
    media_id = upload_document(file_path)
    doc: dict[str, Any] = {"id": media_id, "filename": Path(file_path).name}
    if caption:
        doc["caption"] = caption
    payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "document",
        "document": doc,
    }
    resp = requests.post(
        f"{GRAPH_URL}/{phone_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=30,
    )
    if resp.status_code != 200:
        raise PrimitiveError(
            f"whatsapp send failed ({resp.status_code}): {resp.text[:500]}",
            state="message not accepted by WhatsApp",
        )
    body = resp.json()
    wamid = (body.get("messages") or [{}])[0].get("id")
    return {
        "message_id": wamid,
        "to": to,
        "filename": Path(file_path).name,
        "api": body,
    }


@contract(
    precondition="to (if given) is a digit-only E.164 number without '+'; when "
    "omitted it defaults to the configured default phone.",
    postcondition="WhatsApp accepts the text message; the returned wamid is proof of "
    "acceptance by the API.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError with the Graph API error detail on non-2xx.",
    returns="dict: {message_id, to, api}.",
)
def send_text(text: str, to: str | None = None) -> dict[str, Any]:
    to = to or _default_phone()
    if not re.fullmatch(r"\d{10,15}", to):
        raise PreconditionError(
            f"to must be digit-only E.164 without '+' (or configure a default phone), got {to!r}"
        )
    if not text:
        raise PreconditionError("send_text requires non-empty text")
    token, phone_id = _auth()
    payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    resp = requests.post(
        f"{GRAPH_URL}/{phone_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=30,
    )
    if resp.status_code != 200:
        raise PrimitiveError(
            f"whatsapp send failed ({resp.status_code}): {resp.text[:500]}",
            state="message not accepted by WhatsApp",
        )
    body = resp.json()
    wamid = (body.get("messages") or [{}])[0].get("id")
    return {"message_id": wamid, "to": to, "api": body}


# ---- incoming media download (2026-08-18) ----
# The WhatsApp Cloud API media-download flow:
#   1. A webhook delivers an incoming message with a media object containing
#      an "id" field (the media_id).
#   2. GET /<media_id> with the access token returns
#      {url, mime_type, file_size, id, messaging_product}.
#   3. GET <url> with the access token returns the raw binary content.
# This module exposes get_media_url (step 2) and download_media (steps 2+3)
# so plans can save incoming files to disk.

DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Downloads")
DOWNLOAD_TIMEOUT_S = 60


@contract(
    precondition="media_id is a non-empty string; the access token is valid.",
    postcondition="Returns the download URL and MIME type for the media item."
    " The URL is temporary (expires in ~5 minutes).",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError with the Graph API error detail on non-2xx.",
    returns="dict: {url, mime_type, file_size, media_id}.",
)
def get_media_url(media_id: str) -> dict[str, Any]:
    if not media_id or not media_id.strip():
        raise PreconditionError("get_media_url requires a non-empty media_id")
    token, _phone_id = _auth()
    resp = requests.get(
        f"{GRAPH_URL}/{media_id.strip()}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise PrimitiveError(
            f"whatsapp get_media_url failed ({resp.status_code}): {resp.text[:300]}",
            state="media URL not retrieved",
        )
    body = resp.json()
    url = body.get("url")
    if not url:
        raise PrimitiveError(
            f"whatsapp get_media_url returned no url: {resp.text[:300]}",
            state="media URL not retrieved",
        )
    return {
        "url": url,
        "mime_type": body.get("mime_type", ""),
        "file_size": body.get("file_size", 0),
        "media_id": body.get("id", media_id),
    }


@contract(
    precondition="media_id is a non-empty string; the access token is valid;"
    " dest_dir is a writable directory.",
    postcondition="The media file is downloaded to dest_dir with the original"
    " filename (from Content-Disposition) or a fallback name based on"
    " the MIME type.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError for empty media_id; PrimitiveError on"
    " network/download failure.",
    returns="dict: {path, filename, mime_type, file_size}.",
)
def download_media(
    media_id: str,
    dest_dir: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    if not media_id or not media_id.strip():
        raise PreconditionError("download_media requires a non-empty media_id")
    dest = Path(dest_dir) if dest_dir else Path(DEFAULT_DOWNLOAD_DIR)
    if not dest.is_dir():
        raise PreconditionError(f"download_media: dest_dir does not exist: {dest}")

    # Step 1: get the download URL
    info = get_media_url(media_id)
    url = info["url"]
    mime = info["mime_type"]

    # Step 2: download the binary content
    token, _phone_id = _auth()
    try:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=DOWNLOAD_TIMEOUT_S,
        )
    except requests.Timeout as exc:
        raise PrimitiveError(
            f"whatsapp media download timed out after {DOWNLOAD_TIMEOUT_S}s",
            state="URL retrieved but download incomplete",
        ) from exc
    if resp.status_code != 200:
        raise PrimitiveError(
            f"whatsapp media download failed ({resp.status_code}): {resp.text[:300]}",
            state="URL retrieved but download failed",
        )

    # Step 3: determine filename
    if not filename:
        # Try Content-Disposition header first
        cd = resp.headers.get("Content-Disposition", "")
        match = re.search(r'filename[*]?="?([^";]+)"?', cd)
        if match:
            filename = match.group(1).strip()
        else:
            # Fallback: media_id + extension from MIME type
            ext = _EXT_FOR_MIME.get(mime, ".bin")
            filename = f"{media_id}{ext}"

    out_path = dest / filename
    out_path.write_bytes(resp.content)

    return {
        "path": str(out_path),
        "filename": filename,
        "mime_type": mime,
        "file_size": len(resp.content),
    }


# Reverse MIME map for filename fallback when Content-Disposition is absent
_EXT_FOR_MIME: dict[str, str] = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "audio/mpeg": ".mp3",
    "audio/aac": ".aac",
    "audio/mp4": ".m4a",
    "audio/ogg": ".ogg",
    "audio/opus": ".opus",
    "audio/amr": ".amr",
    "video/mp4": ".mp4",
    "video/3gpp": ".3gp",
}


# ---- webhook -> pending download queue (2026-08-18) ----
# The WhatsApp Cloud API delivers incoming messages via webhooks only;
# there is no REST endpoint to list incoming messages. This module
# provides a file-based queue: a webhook handler calls
# enqueue_media_for_download() to write a media_id + metadata to a
# pending file, and the watcher's whatsapp-media trigger polls it.

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PENDING_FILE = PROJECT_ROOT / "var" / "state" / "whatsapp_pending_media.json"


def _pending_file() -> Path:
    return Path(os.environ.get(
        "FRIDAY_WHATSAPP_PENDING_FILE", str(DEFAULT_PENDING_FILE)
    ))


def enqueue_media_for_download(
    media_id: str,
    sender: str = "",
    media_type: str = "",
    caption: str = "",
) -> dict[str, Any]:
    """Webhook handler: enqueue a media_id for the watcher to download.

    Call this from a webhook endpoint when an incoming WhatsApp message
    contains media (image, document, video, audio, sticker). The media_id
    is written to a pending file; the whatsapp-media watcher trigger
    polls this file and downloads each item to ~/Downloads.

    Idempotent: enqueueing the same media_id twice is harmless (the
    second write is a no-op).
    """
    if not media_id or not media_id.strip():
        raise PreconditionError("enqueue_media_for_download requires a non-empty media_id")
    pending = _pending_file()
    pending.parent.mkdir(parents=True, exist_ok=True)
    # Load existing pending list (best-effort)
    existing: list[dict[str, Any]] = []
    try:
        data = json.loads(pending.read_text(encoding="utf-8"))
        if isinstance(data, list):
            existing = data
    except (OSError, ValueError):
        pass
    # Deduplicate by media_id
    seen_ids = {item.get("media_id") for item in existing}
    if media_id in seen_ids:
        return {"status": "already_enqueued", "media_id": media_id}
    entry = {
        "media_id": media_id,
        "sender": sender,
        "type": media_type,
        "caption": caption,
    }
    existing.append(entry)
    # Atomic write
    tmp = pending.with_name(pending.name + ".tmp")
    tmp.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, pending)
    return {"status": "enqueued", "media_id": media_id, "pending_count": len(existing)}


def load_pending_media() -> list[dict[str, Any]]:
    """Read and return the pending media queue (read-only, does not
    clear). Returns [] on any error."""
    try:
        data = json.loads(_pending_file().read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def clear_pending_media(media_ids: list[str] | None = None) -> None:
    """Remove processed media_ids from the pending file. If media_ids is
    None, clear the entire file (all items processed). Atomic write."""
    pending = _pending_file()
    try:
        existing: list[dict[str, Any]] = json.loads(
            pending.read_text(encoding="utf-8")
        )
        if not isinstance(existing, list):
            existing = []
    except (OSError, ValueError):
        existing = []
    if media_ids is None:
        new_list: list[dict[str, Any]] = []
    else:
        ids_to_remove = set(media_ids)
        new_list = [item for item in existing if item.get("media_id") not in ids_to_remove]
    pending.parent.mkdir(parents=True, exist_ok=True)
    tmp = pending.with_name(pending.name + ".tmp")
    tmp.write_text(json.dumps(new_list, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, pending)
