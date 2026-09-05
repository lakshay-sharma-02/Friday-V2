"""Shared timestamp coercion for observer modules.

Episodic memory entries store `created_at` as a float epoch, but callers
historically handed the detector layers ISO strings, floats, or numeric
strings depending on the path — so temporal pattern detection silently
dropped most records. One parser, used everywhere.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def to_datetime(value: Any) -> datetime | None:
    """Coerce float epoch / ISO string / numeric string to an aware datetime.

    Returns None when the value cannot be interpreted.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    # Numeric string (e.g. "1750000000.123") — stored float rendered as text.
    try:
        return datetime.fromtimestamp(float(text), tz=UTC)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
