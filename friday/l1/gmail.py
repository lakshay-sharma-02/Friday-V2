"""L1 primitive: gmail (official Gmail REST API, OAuth2).

Deterministic HTTPS mechanism for mail - no browser, no IMAP parsing.
READ side (the original surface): list_unread / get_message / summarize -
no state changes, and only the `gmail.readonly` scope was requested.
SEND side (gate-registered 2026-08-11): send_document emails a file as an
attachment via the Gmail API `messages.send` endpoint - it needs the
`gmail.send` scope, which is fixed at consent time: the refresh token in
pass now carries BOTH scopes after the one-time re-consent documented in
gates/GMAIL_SETUP.md section 6.5, and a readonly-only token sends nothing
(403 at send time).

Credentials (never hardcoded, never logged in plaintext):
  - env vars GMAIL_CLIENT_ID + GMAIL_CLIENT_SECRET + GMAIL_REFRESH_TOKEN,
    or
  - a pass entry `friday/gmail` (JSON) with client_id, client_secret,
    refresh_token.

Auth: a desktop-app OAuth2 flow. The one-time consent step (creating the
Google Cloud project, enabling the Gmail API, configuring the OAuth
consent screen, and authorizing once in a browser) is a USER action,
documented in gates/BRINGUP_GMAIL_PROOF.md. After that, only the refresh
token is needed and this module refreshes access tokens automatically.

LLM exception (documented, deliberate): `summarize()` internally invokes
the LLM through friday.l1.dev.run - a deliberate exception to the rule
"primitives don't call LLMs", because a summary is a terminal read-only
artifact with no external state to verify against. It is the ONLY
primitive in this module (and one of the very few in L1) that does so.
"""

from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Any, cast

import requests

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError
from friday.l1 import dev
from friday.secrets import get_credentials

TOKEN_URL = "https://oauth2.googleapis.com/token"
API_BASE = "https://gmail.googleapis.com/gmail/v1"
SCOPE = "https://www.googleapis.com/auth/gmail.readonly"

# Module-level cache of the access token so we refresh at most once per
# hour of use, never on every call.
_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0}


def _auth() -> tuple[str, str, str]:
    """(client_id, client_secret, refresh_token) from env or the pass
    entry `friday/gmail`. An unconfigured credential path raises
    PrimitiveError - distinct from an empty mailbox, which is a SUCCESS
    (returns []), so auth failure can never masquerade as 'no mail'."""
    client_id = os.environ.get("GMAIL_CLIENT_ID")
    client_secret = os.environ.get("GMAIL_CLIENT_SECRET")
    refresh_token = os.environ.get("GMAIL_REFRESH_TOKEN")
    if not (client_id and client_secret and refresh_token):
        try:
            creds = get_credentials("gmail")
        except PrimitiveError:
            creds = {}
        client_id = client_id or creds.get("client_id")
        client_secret = client_secret or creds.get("client_secret")
        refresh_token = refresh_token or creds.get("refresh_token")
    if not (client_id and client_secret and refresh_token):
        raise PrimitiveError(
            "gmail credentials missing: set GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET "
            "and GMAIL_REFRESH_TOKEN, or store them in pass at friday/gmail",
            state="authentication not configured",
        )
    return client_id, client_secret, refresh_token


def _access_token() -> str:
    """A fresh OAuth access token, refreshing via the refresh grant when
    the cached one is missing or close to expiry."""
    client_id, client_secret, refresh_token = _auth()
    now = time.time()
    if _token_cache["access_token"] and _token_cache["expires_at"] > now + 60:
        return str(_token_cache["access_token"])
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise PrimitiveError(
            f"gmail token refresh failed ({resp.status_code}): {resp.text[:300]}",
            state="authentication failed",
        )
    body = resp.json()
    token = body.get("access_token")
    if not token:
        raise PrimitiveError(
            f"gmail token refresh returned no access_token: {resp.text[:200]}",
            state="authentication failed",
        )
    _token_cache["access_token"] = token
    _token_cache["expires_at"] = now + int(body.get("expires_in", 3600))
    return str(token)


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """One authenticated GET against the Gmail API. Non-2xx raises
    PrimitiveError with the API's error detail; a 401 triggers exactly one
    token refresh + retry (a stale cached token must not fail a call that
    a refresh fixes). The internal _refreshed retry marker is stripped
    before the request - it never reaches the API."""
    retried = bool((params or {}).get("_refreshed"))
    query = {k: v for k, v in (params or {}).items() if k != "_refreshed"}
    url = f"{API_BASE}{path}"
    headers = {"Authorization": f"Bearer {_access_token()}"}
    resp = requests.get(url, headers=headers, params=query, timeout=30)
    if resp.status_code == 401 and not retried:
        _token_cache["access_token"] = None  # force refresh
        return _get(path, {**query, "_refreshed": True})
    if resp.status_code != 200:
        raise PrimitiveError(
            f"gmail API error ({resp.status_code}): {resp.text[:300]}",
            state="gmail API error",
        )
    return cast(dict[str, Any], resp.json())


def _header(payload: dict[str, Any], name: str) -> str:
    """Pull a header value (e.g. From/Subject) out of a message payload,
    case-insensitively. Returns '' when absent - never crashes."""
    for h in payload.get("headers", []):
        if str(h.get("name", "")).lower() == name.lower():
            return str(h.get("value", ""))
    return ""


def _log_redact_mail_meta(rows: Any) -> Any:
    """Log-time redaction for gmail.list_unread: the real result keeps
    sender/subject (plans and L2 checks read them), but the L0 line shows
    <redacted> for the two fields that carry mail metadata (who sent,
    what about) - the same privacy discipline as get_message's
    redact_result, but surgical: message_id and date stay visible so the
    trace still identifies the message."""
    if isinstance(rows, list):
        return [{**r, "sender": "<redacted>", "subject": "<redacted>"} for r in rows]
    return rows


def _body_text(payload: dict[str, Any]) -> str:
    """Best-effort plain-text extraction: single-part body.data, then
    text/plain parts, then the API snippet. Deterministic and bounded -
    a summary needs readable text, not perfect MIME parsing."""

    def _decode(data: str | None) -> str:
        if not data:
            return ""
        try:
            raw = base64.urlsafe_b64decode(data + "===")
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return ""

    body = payload.get("body", {}).get("data")
    if body:
        return _decode(body)
    for part in payload.get("parts", []):
        mime = part.get("mimeType", "")
        if mime == "text/plain":
            text = _decode(part.get("body", {}).get("data"))
            if text:
                return text
    return ""


@contract(
    precondition="OAuth credentials are configured and the refresh token is "
    "valid; sender is a non-empty email address or display-name fragment.",
    postcondition="Returns structural metadata of the most recent matching "
    "UNREAD messages. Makes NO state changes - nothing is marked read.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError on auth failure (refresh rejected) or API "
    "error - DISTINCT from 'no matching emails', which is an empty list, "
    "never an exception.",
    returns="list[dict]: [{message_id, sender, subject, date}] most recent first.",
    log_transform=_log_redact_mail_meta,
)
def list_unread(sender: str, max_results: int = 5) -> list[dict[str, str]]:
    if not sender or not sender.strip():
        raise PreconditionError("list_unread requires a non-empty sender")
    if max_results < 1:
        raise PreconditionError("max_results must be >= 1")
    q = f"is:unread from:{sender}"
    body = _get("/users/me/messages", {"q": q, "maxResults": max_results})
    items = body.get("messages") or []
    out: list[dict[str, str]] = []
    for item in items[:max_results]:
        mid = item.get("id", "")
        if not mid:
            continue
        meta = _get(
            f"/users/me/messages/{mid}",
            {
                "format": "metadata",
                # metadataHeaders is a REPEATED query param in the Gmail API
                # (metadataHeaders=From&metadataHeaders=Subject&...) - a
                # comma-joined string silently returns empty headers.
                "metadataHeaders": ["From", "Subject", "Date"],
            },
        )
        payload = meta.get("payload", {})
        out.append(
            {
                "message_id": mid,
                "sender": _header(payload, "From"),
                "subject": _header(payload, "Subject"),
                "date": _header(payload, "Date"),
            }
        )
    return out


@contract(
    precondition="message_id comes from a prior list_unread() call.",
    postcondition="Returns the message's structural metadata plus a plain-text "
    "body. Makes NO state changes.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if the message no longer exists or the fetch "
    "fails (auth/API). Never conflated with 'no such message id found'.",
    returns="dict: {message_id, sender, subject, date, snippet, body}.",
    redact_result=True,  # the body is mail content - log shows <redacted>
)
def get_message(message_id: str) -> dict[str, str]:
    if not message_id or not message_id.strip():
        raise PreconditionError("get_message requires a message_id")
    meta = _get(f"/users/me/messages/{message_id}", {"format": "full"})
    payload = meta.get("payload", {})
    return {
        "message_id": message_id,
        "sender": _header(payload, "From"),
        "subject": _header(payload, "Subject"),
        "date": _header(payload, "Date"),
        "snippet": str(meta.get("snippet", "")),
        "body": _body_text(payload),
    }


@contract(
    precondition="message_id comes from a prior list_unread() call.",
    postcondition="Returns an LLM-generated plain-text summary of the message. "
    "Makes NO state changes. NOTE: internally invokes the LLM via "
    "friday.l1.dev.run - a DELIBERATE, documented exception to the rule "
    "'primitives don't call LLMs' (a summary is a terminal read-only "
    "artifact with no external state to verify against).",
    idempotency=Idempotency.IDEMPOTENT,  # re-summarizing is harmless (but see note)
    failure_mode="PrimitiveError from get_message (missing message/auth) or "
    "dev.run (LLM failure); nothing is marked read either way. NOTE: because "
    "the step is idempotent the executor may retry it, and each attempt is a "
    "fresh LLM call - the summary text is NOT guaranteed identical across "
    "attempts (it is a generated artifact, not stable state).",
    returns="str: the summary text (the task's human-verifiable deliverable).",
)
def summarize(message_id: str) -> str:
    msg = get_message(message_id)
    if not msg["body"] and not msg["snippet"]:
        raise PrimitiveError(
            f"gmail summarize: message {message_id} has no readable body or snippet",
            state="message not readable",
        )
    source = msg["body"] or msg["snippet"]
    task = (
        "Summarize this email in at most 5 plain sentences, covering who it is "
        "from, what it asks or announces, and any deadlines or actions. "
        "Reply with ONLY the summary text.\n\n"
        f"From: {msg['sender']}\nSubject: {msg['subject']}\n\n{source[:8000]}"
    )
    # Deliberate, documented exception: call the private _run_claude
    # directly instead of the observed dev.run primitive. The task string
    # contains the message BODY (mail content); the redaction discipline
    # keeps mail content out of the L0 log, and dev.run logs its bound
    # args - so the public path would leak the body into
    # var/logs/friday.jsonl. The gmail.summarize L1 call itself is fully
    # observed ({message_id} -> summary); only this internal subprocess
    # call is unlogged, by design.
    res = dev._run_claude(task, None, 120, dev.MODEL_ALIAS, False)
    summary = ""
    if isinstance(res, dict):
        inner = res.get("result")
        if isinstance(inner, str):
            summary = inner
        elif isinstance(inner, dict):
            summary = str(inner.get("summary") or inner.get("result") or "")
    summary = summary.strip()
    if not summary:
        raise PrimitiveError(
            f"gmail summarize: LLM returned no usable summary for {message_id}",
            state="summary not produced",
        )
    return summary


# ---- gate-registered gmail.send_document (2026-08-11) ----
"""gmail.send_document - the capability-gap loop's FIRST side-effecting
primitive, hand-built (not LLM-drafted). The two prior LLM drafts for this
gap were REJECTED on record: a confabulated wrapper around a nonexistent
`send_document` function, and a contract with an invalid qualified name.
This impl is written by hand and reviewed by the human gate.

The impl carries ONLY the imports the target module lacks: gmail.py
already provides _access_token / API_BASE / requests / base64 / Path /
contract / Idempotency / PreconditionError / PrimitiveError /
get_credentials - registration appends this block to the module, so the
email MIME imports ride WITH the function.

NO `from __future__ import annotations` here: registration appends this
block at EOF of the existing module, where a future import is a
SyntaxError (register_proposal strips one if a draft carries it).
"""

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from friday.contracts import Idempotency, contract


def _default_to() -> str:
    """The default recipient for sends: GMAIL_DEFAULT_TO env or the
    'default_to' key in the pass entry (set during the send-scope consent
    flow). Lets a plan omit `to` entirely so the goal is recipient-
    agnostic - the same convention as whatsapp's default_phone."""
    to = os.environ.get("GMAIL_DEFAULT_TO")
    if not to:
        try:
            creds = get_credentials("gmail")
        except PrimitiveError:
            return ""
        to = creds.get("default_to") or ""
    return to


def _log_redact_send_meta(result: Any) -> Any:
    """Log-time redaction for gmail.send_document: the RECIPIENT address is
    mail metadata (the same discipline as list_unread's sender/subject
    redaction) - the L0 line shows <redacted> for `to` while message_id,
    thread_id and filename stay visible so the trace still identifies the
    send. The real returned value is untouched."""
    if isinstance(result, dict):
        return {**result, "to": "<redacted>"}
    return result


@contract(
    precondition="OAuth credentials are configured and the refresh token "
    "carries the gmail.send scope (a 403 at send time means the token was "
    "minted before this scope - re-consent with gates/_gmail_oauth_setup.py "
    "--scope); to is a non-empty email address; file_path exists and is "
    "readable.",
    postcondition="The file is emailed as an attachment to `to` from the "
    "authenticated account; the returned message id is the Gmail API's "
    "proof of acceptance. No other state changes - nothing is read, moved "
    "or deleted.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PreconditionError for a missing file or an empty "
    "recipient; PrimitiveError with the API error detail on non-2xx. If "
    "the HTTP response is lost, the message may still have been sent - "
    "verify before retrying.",
    returns="dict: {message_id, thread_id, to, filename}.",
    log_transform=_log_redact_send_meta,
)
def send_document(
    file_path: str,
    to: str | None = None,
    subject: str | None = None,
    body: str | None = None,
) -> dict[str, Any]:
    """Email `file_path` as an attachment to `to` (default: the configured
    default recipient) via the Gmail API `messages.send` endpoint. Builds a
    MIME multipart message, base64url-encodes the raw bytes, and returns
    the API's message id as proof of acceptance. The From header is left to
    the API - Gmail always sends from the authenticated account."""
    to = to or _default_to()
    if not to or not to.strip():
        raise PreconditionError(
            "send_document requires a non-empty 'to' (or a configured "
            "default: GMAIL_DEFAULT_TO env / 'default_to' in pass at "
            "friday/gmail)"
        )
    src = Path(file_path)
    if not src.is_file():
        raise PreconditionError(f"send_document requires an existing file: {file_path!r}")

    msg = MIMEMultipart()
    msg["To"] = to
    msg["Subject"] = subject or f"Friday: {src.name}"
    msg.attach(MIMEText(body or "See the attached file.", "plain"))
    with open(src, "rb") as fh:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(fh.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", "attachment", filename=src.name)
    msg.attach(part)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    resp = requests.post(
        f"{API_BASE}/users/me/messages/send",
        headers={"Authorization": f"Bearer {_access_token()}"},
        json={"raw": raw},
        timeout=60,
    )
    if resp.status_code != 200:
        raise PrimitiveError(
            f"gmail send failed ({resp.status_code}): {resp.text[:300]}",
            state="message not accepted by Gmail",
        )
    body_resp = resp.json()
    return {
        "message_id": str(body_resp.get("id", "")),
        "thread_id": str(body_resp.get("threadId", "")),
        "to": to,
        "filename": src.name,
    }
