from datetime import UTC, date, datetime, time, timedelta
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


def local_day_bounds(day: date) -> tuple[datetime, datetime]:
    """[start, end) of a calendar day in the restaurant's zone (23 or 25 hours on DST days)."""
    return (
        datetime.combine(day, time.min, tzinfo=LOCAL_TZ),
        datetime.combine(day + timedelta(days=1), time.min, tzinfo=LOCAL_TZ),
    )


def local_month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    """[start, end) of a calendar month in the restaurant's zone."""
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    return (
        datetime(year, month, 1, tzinfo=LOCAL_TZ),
        datetime(next_year, next_month, 1, tzinfo=LOCAL_TZ),
    )
