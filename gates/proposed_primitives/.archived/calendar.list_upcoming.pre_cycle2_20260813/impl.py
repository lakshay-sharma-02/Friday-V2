from typing import List, Dict
from friday.l1 import calendar

@contract(
    precondition="OAuth credentials are configured and the refresh token is valid; days is a non‑negative integer.",
    postcondition="Returns structural metadata of the upcoming calendar events for the specified number of days. Makes NO state changes – no events are marked read or modified.",
    idempotency="idempotent",
    failure_mode="PrimitiveError on auth failure (refresh rejected) or API error – distinct from 'no upcoming events', which yields an empty list, never an exception.",
    returns="list[dict]: [{event_id, title, start_date, end_date}] most recent first.",
    log_transform="_log_redact_event_meta",
    redact_result=False,
)
def list_upcoming(days: int = 7) -> List[Dict[str, str]]:
    """Return upcoming calendar events for the given number of days."""
    if days < 0:
        raise ValueError("days must be non‑negative")
    return calendar.fetch_upcoming(days)