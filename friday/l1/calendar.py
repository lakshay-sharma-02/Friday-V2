# ---- gate-registered calendar.list_upcoming (2026-08-13) ----
# created by the capability-gap approval gate; reviewed by a human
# before signing.
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError
from friday.secrets import get_credentials

TOKEN_URL = "https://oauth2.googleapis.com/token"
API_BASE = "https://www.googleapis.com/calendar/v3"
# The scopes are fixed at OAuth CONSENT time - a refresh token only
# carries what the consent screen granted. list_upcoming needs only the
# readonly scope; add_event needs the WRITE scope too. The shared refresh
# token in pass friday/calendar was re-minted 2026-08-14 with BOTH scopes
# (gates/_calendar_oauth_setup.py --scope "...readonly ...events"); a
# readonly-only token would 403 on add_event (the error is surfaced with
# the fix in add_event's 403 handler below).
SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
SCOPE_EVENTS = "https://www.googleapis.com/auth/calendar.events"

# Module-level cache of the access token so we refresh at most once per
# hour of use, never on every call - the same pattern gmail.py uses.
_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0}


def _auth() -> tuple[str, str, str]:
    """(client_id, client_secret, refresh_token) from env or the pass
    entry `friday/calendar`. An unconfigured credential path raises
    PrimitiveError - distinct from 'no upcoming events', which is an
    empty list, so auth failure can never masquerade as 'no events' (the
    registered contract's failure_mode). The 2026-08-14 fix: the original
    draft read a raw access_token that expires in ~1 hour with no refresh
    path - the refresh grant (gmail.py's proven pattern) is required for
    a persistent trigger to work at all."""
    client_id = os.environ.get("CALENDAR_CLIENT_ID")
    client_secret = os.environ.get("CALENDAR_CLIENT_SECRET")
    refresh_token = os.environ.get("CALENDAR_REFRESH_TOKEN")
    if not (client_id and client_secret and refresh_token):
        try:
            creds = get_credentials("calendar")
        except PrimitiveError:
            creds = {}
        client_id = client_id or creds.get("client_id")
        client_secret = client_secret or creds.get("client_secret")
        refresh_token = refresh_token or creds.get("refresh_token")
    if not (client_id and client_secret and refresh_token):
        raise PrimitiveError(
            "calendar credentials missing: set CALENDAR_CLIENT_ID, "
            "CALENDAR_CLIENT_SECRET and CALENDAR_REFRESH_TOKEN, or store "
            "them in pass at friday/calendar (see gates/_calendar_oauth_setup.py)",
            state="authentication not configured",
        )
    return client_id, client_secret, refresh_token


def _access_token() -> str:
    """A fresh OAuth access token, refreshing via the refresh grant when
    the cached one is missing or close to expiry (mirrors gmail.py)."""
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
            f"calendar token refresh failed ({resp.status_code}): {resp.text[:300]}",
            state="authentication failed",
        )
    body = resp.json()
    token = body.get("access_token")
    if not token:
        raise PrimitiveError(
            f"calendar token refresh returned no access_token: {resp.text[:200]}",
            state="authentication failed",
        )
    _token_cache["access_token"] = token
    _token_cache["expires_at"] = now + int(body.get("expires_in", 3600))
    return token


def _log_redact_calendar_meta(rows: Any) -> Any:
    """Log-time redaction for calendar.list_upcoming: the SUMMARY field is
    event metadata that could contain sensitive info - the L0 line shows
    <redacted> while event_id, start_time, end_time stay visible so the
    trace still identifies the event without leaking content."""
    if isinstance(rows, list):
        return [{**r, "summary": "<redacted>"} for r in rows]
    return rows


@contract(
    precondition="days is a positive integer (default 7); credentials must be configured (pass friday/calendar or CALENDAR_* env).",
    postcondition="Returns structural metadata of events starting within the next 'days' days from now. Makes NO state changes - events are only read.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError on auth/API failure - DISTINCT from 'no upcoming events', which returns an empty list. PreconditionError for invalid days parameter.",
    returns="list[dict]: [{event_id, summary, start_time, end_time, location, attendees_count}] most recent first.",
    # the 2026-08-14 review found _log_redact_calendar_meta was defined
    # but never wired in - event summaries were reaching the L0 log raw;
    # the log_transform is the fix (log-only, the real value is untouched)
    log_transform=_log_redact_calendar_meta,
)
def list_upcoming(days: int = 7) -> list[dict[str, str]]:
    """Return upcoming calendar events within the next 'days' days.

    Uses the Google Calendar API (calendar.readonly scope), authenticating
    through the refresh grant - CALENDAR_CLIENT_ID / CALENDAR_CLIENT_SECRET
    / CALENDAR_REFRESH_TOKEN env vars or the pass entry at friday/calendar
    (see gates/_calendar_oauth_setup.py for the one-time consent flow).
    Returns empty list when no events found; events sorted by start time,
    soonest first. Auth failure raises PrimitiveError, never an empty
    list (an unconfigured calendar is not 'no events').
    """
    if not isinstance(days, int) or days < 1:
        raise PreconditionError(f"days must be a positive integer, got {days!r}")

    token = _access_token()
    now = datetime.now(timezone.utc).isoformat()
    end_time = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    url = f"{API_BASE}/calendars/primary/events"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "timeMin": now,
        "timeMax": end_time,
        "maxResults": 100,
        "singleEvents": True,
        "orderBy": "startTime",
    }
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    if resp.status_code == 401:
        # stale cached token: refresh once and retry (mirrors gmail.py)
        _token_cache["access_token"] = None
        token = _access_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(url, headers=headers, params=params, timeout=30)
    if resp.status_code != 200:
        raise PrimitiveError(
            f"calendar API error ({resp.status_code}): {resp.text[:300]}",
            state="calendar API request failed",
        )
    body = resp.json()
    items = body.get("items", [])
    result: list[dict[str, str]] = []
    for item in items:
        start = item.get("start", {})
        end = item.get("end", {})
        # Handle both dateTime and date formats
        start_time = start.get("dateTime", start.get("date", ""))
        end_time = end.get("dateTime", end.get("date", ""))
        attendees = item.get("attendees", [])
        location = item.get("location", "")
        summary = item.get("summary", "")
        result.append({
            "event_id": item.get("id", ""),
            "summary": summary,
            "start_time": start_time,
            "end_time": end_time,
            "location": location,
            "attendees_count": str(len(attendees)),
        })
    return result


# ---- gate-registered calendar.add_event (2026-08-14) ----

def _log_redact_add_event(result):
    """Log-time redaction for calendar.add_event: the SUMMARY field could
    contain sensitive info - the L0 line shows <redacted> while event_id
    stays visible."""
    if isinstance(result, dict):
        return {**result, "summary": "<redacted>"}
    return result

@contract(
    precondition="OAuth credentials are configured and the refresh token carries the "
    "calendar.events scope; summary is a non-empty string; start and end are valid RFC 3339 "
    "datetime strings with end after start.",
    postcondition="Creates an event on the primary calendar; returns structural metadata of the created event."
    "Makes NO state changes except the single event creation.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PreconditionError for invalid parameters; PrimitiveError on auth/API failure. "
    "If the HTTP response is lost, the event may still have been created - verify before retrying.",
    returns="dict: {event_id, summary, start_time, end_time, status}.",
    log_transform=_log_redact_add_event,
)
def add_event(summary: str, start: str, end: str) -> dict[str, str]:
    """Add an event to the primary Google Calendar.

    Creates an event with the given summary, start time, and end time (both RFC 3339
    formatted). Returns the created event's metadata including the assigned event_id.
    Hand-corrected at human review (2026-08-14): the draft compared end <= start as
    STRINGS, which is wrong across mixed timezone offsets (e.g. '14:00+05:30' vs
    '10:00Z') and does not validate the format at all despite the contract promising
    RFC 3339 validation - now parsed properly with datetime.fromisoformat.
    Requires the calendar.events OAuth scope at consent time - a readonly-only
    token 403s with an actionable PrimitiveError (see below).
    """
    if not summary or not summary.strip():
        raise PreconditionError("summary must be a non-empty string")

    # REAL datetime parsing, not string comparison: '14:00+05:30' vs '10:00Z'
    # must compare by instant, and garbage must be rejected (the contract
    # claims RFC 3339 validation). Python 3.11+ fromisoformat accepts the
    # trailing 'Z' used by Google's API.
    try:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PreconditionError(
            f"start/end must be RFC 3339 datetimes, got start={start!r} end={end!r}"
        ) from exc
    if end_dt <= start_dt:
        raise PreconditionError(f"end time {end!r} must be after start time {start!r}")

    token = _access_token()
    url = f"{API_BASE}/calendars/primary/events"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"summary": summary, "start": {"dateTime": start}, "end": {"dateTime": end}}

    resp = requests.post(url, headers=headers, json=body, timeout=30)
    if resp.status_code not in (200, 201):
        detail = resp.text[:300]
        if resp.status_code == 403 and any(
            s in detail.lower() for s in ("insufficient permission", "permissiondenied")
        ):
            # The refresh token only carries calendar.readonly - the consent
            # was granted before the WRITE scope existed. Name the fix so the
            # failure is actionable, not a generic 403.
            raise PrimitiveError(
                "calendar.add_event needs the calendar.events OAuth scope, but the "
                "stored refresh token only carries calendar.readonly. Re-run the "
                "one-time consent WITH the write scope to re-mint the token:\n"
                "  ./.venv/bin/python gates/_calendar_oauth_setup.py --scope \""
                f"{SCOPE} {SCOPE_EVENTS}\"\n"
                f"(API: {detail[:160]})",
                state="event creation failed - missing calendar.events scope",
            )
        raise PrimitiveError(
            f"calendar.add_event failed ({resp.status_code}): {detail}",
            state="event creation failed",
        )
    result = resp.json()
    start_dt = result.get("start", {}).get("dateTime", "")
    end_dt = result.get("end", {}).get("dateTime", "")
    return {
        "event_id": result.get("id", ""),
        "summary": summary,
        "start_time": start_dt,
        "end_time": end_dt,
        "status": result.get("status", ""),
    }
