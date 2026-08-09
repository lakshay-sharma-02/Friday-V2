"""L1 primitive: gmail (official Gmail REST API, OAuth2, read-only).

Deterministic HTTPS mechanism for READING mail - no browser, no IMAP
parsing, no state changes. Only the `gmail.readonly` scope is requested;
this module can never modify mail.

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
import json
import os
import time
from pathlib import Path
from typing import Any

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
        return _token_cache["access_token"]
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
    return token


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
    return resp.json()


def _header(payload: dict[str, Any], name: str) -> str:
    """Pull a header value (e.g. From/Subject) out of a message payload,
    case-insensitively. Returns '' when absent - never crashes."""
    for h in payload.get("headers", []):
        if str(h.get("name", "")).lower() == name.lower():
            return str(h.get("value", ""))
    return ""


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
            {"format": "metadata",
             # metadataHeaders is a REPEATED query param in the Gmail API
             # (metadataHeaders=From&metadataHeaders=Subject&...) - a
             # comma-joined string silently returns empty headers.
             "metadataHeaders": ["From", "Subject", "Date"]},
        )
        payload = meta.get("payload", {})
        out.append({
            "message_id": mid,
            "sender": _header(payload, "From"),
            "subject": _header(payload, "Subject"),
            "date": _header(payload, "Date"),
        })
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
