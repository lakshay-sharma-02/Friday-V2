"""Gmail adapter — OAuth2 email access via env vars.

Uses env vars: GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN.
Auto-refreshes access tokens.
"""

from __future__ import annotations

import base64
import json
import os
import time
from typing import Any

import requests

from friday_mcu.adapters import Adapter, register_adapter
from friday_mcu.core.contracts import Idempotency, contract
from friday_mcu.core.errors import AdapterError, PreconditionError

API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
_token_cache: dict[str, Any] = {}


def _get_token() -> str:
    """Get a valid access token, refreshing if needed."""
    global _token_cache
    now = time.time()

    # Return cached token if still valid
    if _token_cache.get("access_token") and _token_cache.get("expiry", 0) > now + 60:
        return _token_cache["access_token"]

    client_id = os.environ.get("GMAIL_CLIENT_ID", "")
    client_secret = os.environ.get("GMAIL_CLIENT_SECRET", "")
    refresh_token = os.environ.get("GMAIL_REFRESH_TOKEN", "")

    if not all([client_id, client_secret, refresh_token]):
        raise AdapterError(
            "Gmail credentials missing: set GMAIL_CLIENT_ID, "
            "GMAIL_CLIENT_SECRET, and GMAIL_REFRESH_TOKEN env vars"
        )

    try:
        resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        _token_cache = {
            "access_token": data["access_token"],
            "expiry": now + data.get("expires_in", 3600),
        }
        return _token_cache["access_token"]
    except Exception as exc:
        raise AdapterError(f"Failed to refresh Gmail token: {exc}") from exc


def _api_call(method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
    """Make an authenticated Gmail API call."""
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{API_BASE}/{endpoint}"
    try:
        resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as exc:
        raise AdapterError(f"Gmail API error: {exc}") from exc
    except Exception as exc:
        raise AdapterError(f"Gmail API call failed: {exc}") from exc


@contract(
    precondition="Gmail OAuth env vars are set.",
    postcondition="Returns a list of unread message summaries.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="AdapterError if the API call fails.",
    returns="list[dict]: [{message_id, sender, subject, date}].",
)
def list_unread(sender: str = "", max_results: int = 10) -> list[dict[str, str]]:
    """List unread Gmail messages, optionally filtered by sender."""
    query = "is:unread"
    if sender:
        query += f" from:{sender}"
    # An API/auth failure must propagate loudly, never masquerade as an empty
    # inbox: an expired token returning [] would silently turn every email
    # goal into a misleading "no unread" COMPLETED.
    data = _api_call("GET", "messages", params={"q": query, "maxResults": max_results})
    messages = data.get("messages", [])
    results: list[dict[str, str]] = []
    for msg in messages:
        msg_id = msg.get("id", "")
        if not msg_id:
            continue
        try:
            detail = _api_call(
                "GET", f"messages/{msg_id}",
                params={"format": "full"},
            )
            headers = {
                h["name"].lower(): h["value"]
                for h in detail.get("payload", {}).get("headers", [])
            }
            results.append({
                "message_id": msg_id,
                "sender": headers.get("from", ""),
                "subject": headers.get("subject", ""),
                "date": headers.get("date", ""),
            })
        except AdapterError:
            continue
    return results


@contract(
    precondition="message_id is a valid Gmail message ID.",
    postcondition="Returns the full message with body.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="AdapterError if the message cannot be fetched.",
    returns="dict: {message_id, sender, subject, date, body, snippet}.",
)
def get_message(message_id: str) -> dict[str, str]:
    """Get a full Gmail message by ID."""
    if not message_id:
        raise PreconditionError("message_id is required")
    data = _api_call("GET", f"messages/{message_id}", params={"format": "full"})
    headers = {
        h["name"].lower(): h["value"]
        for h in data.get("payload", {}).get("headers", [])
    }

    body = ""
    snippet = data.get("snippet", "")
    payload = data.get("payload", {})
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    elif payload.get("parts"):
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                break
    if not body:
        body = snippet

    return {
        "message_id": message_id,
        "sender": headers.get("from", ""),
        "subject": headers.get("subject", ""),
        "date": headers.get("date", ""),
        "body": body[:10000],
        "snippet": snippet,
    }


@contract(
    precondition="message_id is a valid Gmail message ID.",
    postcondition="Returns a plain-text summary of the message.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="AdapterError if the message cannot be summarized.",
    returns="str: the summary text.",
)
def summarize(message_id: str) -> str:
    """Summarize a Gmail message."""
    msg = get_message(message_id)
    body = msg.get("body", "")
    subject = msg.get("subject", "")
    sender = msg.get("sender", "")
    if not body:
        return f"Email from {sender} with subject '{subject}' — no readable body."
    summary = body[:500].strip()
    if len(body) > 500:
        summary += "..."
    return f"From: {sender}\nSubject: {subject}\n\n{summary}"


class GmailAdapter(Adapter):
    """Gmail adapter."""

    @property
    def name(self) -> str:
        return "gmail"

    @property
    def capabilities(self) -> list[str]:
        return ["list_unread", "get_message", "summarize"]

    async def initialize(self) -> None:
        _get_token()  # will raise if not configured

    async def execute(self, action: str, **kwargs: Any) -> Any:
        actions = {"list_unread": list_unread, "get_message": get_message, "summarize": summarize}
        fn = actions.get(action)
        if fn is None:
            raise AdapterError(f"Unknown gmail action: {action}")
        return fn(**kwargs)

    async def observe(self) -> list:
        return []

    def health_check(self) -> bool:
        return all([
            os.environ.get("GMAIL_CLIENT_ID"),
            os.environ.get("GMAIL_CLIENT_SECRET"),
            os.environ.get("GMAIL_REFRESH_TOKEN"),
        ])


try:
    register_adapter(GmailAdapter())
except Exception:
    pass
