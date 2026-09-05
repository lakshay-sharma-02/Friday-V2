"""Calendar adapter — Google Calendar API (OAuth2 read-only + add event)."""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from friday_mcu.adapters import Adapter, register_adapter
from friday_mcu.core.contracts import Idempotency, contract
from friday_mcu.core.errors import AdapterError, PreconditionError

API_BASE = "https://www.googleapis.com/calendar/v3"
_token_cache: dict[str, Any] = {}


def _get_token() -> str:
    """Get a valid access token, refreshing if needed."""
    global _token_cache
    now = time.time()
    if _token_cache.get("access_token") and _token_cache.get("expiry", 0) > now + 60:
        return _token_cache["access_token"]

    client_id = os.environ.get("GMAIL_CLIENT_ID", "")
    client_secret = os.environ.get("GMAIL_CLIENT_SECRET", "")
    refresh_token = os.environ.get("GMAIL_REFRESH_TOKEN", "")
    if not all([client_id, client_secret, refresh_token]):
        raise AdapterError("Gmail/Calendar credentials missing: set GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN")

    try:
        resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token, "grant_type": "refresh_token"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        _token_cache = {"access_token": data["access_token"], "expiry": now + data.get("expires_in", 3600)}
        return _token_cache["access_token"]
    except Exception as exc:
        raise AdapterError(f"Failed to refresh Calendar token: {exc}") from exc


@contract(
    precondition="Calendar OAuth token is configured.",
    postcondition="Returns upcoming events for the next N days.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="AdapterError if the API call fails.",
    returns="list[dict]: [{summary, start, end, location}].",
)
def list_upcoming(days: int = 1) -> list[dict[str, str]]:
    """List upcoming calendar events."""
    try:
        token = _get_token()
        now = datetime.now(UTC)
        end = now + timedelta(days=days)
        resp = requests.get(
            f"{API_BASE}/calendars/primary/events",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "timeMin": now.isoformat(),
                "timeMax": end.isoformat(),
                "singleEvents": True,
                "orderBy": "startTime",
                "maxResults": 20,
            },
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return [
            {
                "summary": item.get("summary", "(no title)"),
                "start": item.get("start", {}).get("dateTime", item.get("start", {}).get("date", "")),
                "end": item.get("end", {}).get("dateTime", item.get("end", {}).get("date", "")),
                "location": item.get("location", ""),
            }
            for item in items
        ]
    except Exception as exc:
        raise AdapterError(f"Calendar list_upcoming failed: {exc}") from exc


@contract(
    precondition="summary is non-empty, start and end are ISO datetime strings.",
    postcondition="Event is created on the calendar.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="AdapterError if the API call fails.",
    returns="dict: {event_id, summary, start, end}.",
)
def add_event(summary: str, start: str, end: str) -> dict[str, str]:
    """Add an event to the calendar."""
    if not summary:
        raise PreconditionError("summary is required")
    try:
        token = _get_token()
        resp = requests.post(
            f"{API_BASE}/calendars/primary/events",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "summary": summary,
                "start": {"dateTime": start},
                "end": {"dateTime": end},
            },
            timeout=15,
        )
        resp.raise_for_status()
        event = resp.json()
        return {
            "event_id": event.get("id", ""),
            "summary": event.get("summary", ""),
            "start": event.get("start", {}).get("dateTime", ""),
            "end": event.get("end", {}).get("dateTime", ""),
        }
    except Exception as exc:
        raise AdapterError(f"Calendar add_event failed: {exc}") from exc


class CalendarAdapter(Adapter):
    @property
    def name(self) -> str:
        return "calendar"

    @property
    def capabilities(self) -> list[str]:
        return ["list_upcoming", "add_event"]

    async def initialize(self) -> None:
        pass

    async def execute(self, action: str, **kwargs: Any) -> Any:
        if action == "list_upcoming":
            return list_upcoming(**kwargs)
        elif action == "add_event":
            return add_event(**kwargs)
        raise AdapterError(f"Unknown calendar action: {action}")

    async def observe(self) -> list:
        return []

    def health_check(self) -> bool:
        return all([os.environ.get("GMAIL_CLIENT_ID"), os.environ.get("GMAIL_CLIENT_SECRET"), os.environ.get("GMAIL_REFRESH_TOKEN")])


try:
    register_adapter(CalendarAdapter())
except Exception:
    pass
