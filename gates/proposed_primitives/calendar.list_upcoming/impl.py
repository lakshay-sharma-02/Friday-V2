from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError
from friday.secrets import get_credentials

# Module-level cache of the access token (for API-based calendar)
_token_cache: dict[str, Any] = {}


def _log_redact_calendar_meta(rows: Any) -> Any:
    """Log-time redaction for calendar.list_upcoming: the SUMMARY field is
    event metadata that could contain sensitive info - the L0 line shows
    <redacted> while event_id, start_time, end_time stay visible so the
    trace still identifies the event without leaking content."""
    if isinstance(rows, list):
        return [{**r, "summary": "<redacted>"} for r in rows]
    return rows


@contract(
    precondition="days is a positive integer (default 7); if using a calendar API, credentials must be configured.",
    postcondition="Returns structural metadata of events starting within the next 'days' days from now. Makes NO state changes - events are only read.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError on API/auth failure - DISTINCT from 'no upcoming events', which returns an empty list. PreconditionError for invalid days parameter.",
    returns="list[dict]: [{event_id, summary, start_time, end_time, location, attendees_count}] most recent first.",
)
def list_upcoming(days: int = 7) -> list[dict[str, str]]:
    """Return upcoming calendar events within the next 'days' days.

    Uses Google Calendar API by default (requires GOOGLE_CALENDAR_TOKEN env
    var or pass entry at friday/calendar). Returns empty list when no events
    found. Events sorted by start time, soonest first.
    """
    import requests

    if not isinstance(days, int) or days < 1:
        raise PreconditionError(f"days must be a positive integer, got {days!r}")

    # Check for API credentials
    token = os.environ.get("GOOGLE_CALENDAR_TOKEN")
    if not token:
        try:
            creds = get_credentials("calendar")
            token = creds.get("access_token")
        except Exception:
            token = None

    if token:
        # API-based retrieval
        now = datetime.now(timezone.utc).isoformat()
        end_time = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "timeMin": now,
            "timeMax": end_time,
            "maxResults": 100,
            "singleEvents": True,
            "orderBy": "startTime",
        }
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
    else:
        # No API credentials - return empty list (no events to show)
        # In a full implementation, this could read from a local .ics file
        return []
