from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError

def _log_redact_add_event(result):
    """Log-time redaction for calendar.add_event: the SUMMARY field could """ + \
    """contain sensitive info - the L0 line shows <redacted> while event_id stays visible."""
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
    """
    from datetime import datetime

    from friday.l1.calendar import API_BASE, _access_token
    import requests

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
        raise PrimitiveError(
            f"calendar.add_event failed ({resp.status_code}): {resp.text[:300]}",
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