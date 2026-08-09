"""L1 primitive: whatsapp (official WhatsApp Business Cloud API).

Deterministic HTTP mechanism for sending text / document messages - no
browser, no chat-history sync, no QR. The file is uploaded to WhatsApp's
own servers and sent by media id, so no public URL hosting is required.

Credentials (never hardcoded, never logged in plaintext):
  - env vars WHATSAPP_ACCESS_TOKEN + WHATSAPP_PHONE_NUMBER_ID, or
  - a pass entry `friday/whatsapp` (JSON) with access_token and
    phone_number_id.
"""

from __future__ import annotations

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
    precondition="access token and phone_number_id are configured and the "
    "token is valid.",
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
    return media_id


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
def send_document(file_path: str, to: str | None = None, caption: str | None = None) -> dict[str, Any]:
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
    payload = {
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
    payload = {
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
