from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import settings

LOCAL_TZ = ZoneInfo(settings.timezone)


def now_local() -> datetime:
    """Current time in the restaurant's time zone (timezone-aware)."""
    return datetime.now(LOCAL_TZ)


def to_local(value: datetime) -> datetime:
    """Convert to the restaurant's time zone. Naive values are taken to already be local time."""
    if value.tzinfo is None:
        return value.replace(tzinfo=LOCAL_TZ)
    return value.astimezone(LOCAL_TZ)


def elapsed(start: datetime, end: datetime) -> timedelta:
    """Real time between two datetimes, correct across DST changes.

    Python subtracts aware datetimes that share a tzinfo by wall clock, so a 22:00-06:00
    shift over the October change would come out as 8h instead of 9h. Compare in UTC instead.
    """
    return to_local(end).astimezone(UTC) - to_local(start).astimezone(UTC)
