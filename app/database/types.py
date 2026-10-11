from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator

from app.utils.time import LOCAL_TZ, to_local


class LocalDateTime(TypeDecorator[datetime]):
    """Stores datetimes as naive UTC; returns them as aware datetimes in the restaurant's zone.

    SQLite has no timezone-aware datetime type, so storing UTC keeps ordering and
    comparisons correct across DST changes. Naive inputs are treated as local time.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        return to_local(value).astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC).astimezone(LOCAL_TZ)
