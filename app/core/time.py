"""Timezone-aware clock helpers.

``datetime.utcnow()`` returns a *naive* datetime and is deprecated in Python
3.12.  Everything in the application should go through :func:`utcnow` so that
timestamps are always aware and comparable with values read back from the
database (see :class:`app.models.types.UTCDateTime`).
"""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return the current time as an aware UTC ``datetime``."""
    return datetime.now(UTC)


def ensure_utc(value: datetime | None) -> datetime | None:
    """Coerce ``value`` to an aware UTC datetime.

    Naive datetimes are *assumed* to already be in UTC (that is how the
    database stores them on backends without timezone support).
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def from_timestamp(ts: float) -> datetime:
    """Aware UTC datetime from a POSIX timestamp."""
    return datetime.fromtimestamp(ts, tz=UTC)
