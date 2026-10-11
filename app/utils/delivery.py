from datetime import date, datetime, timedelta

from app.config import settings
from app.utils.time import now_local, to_local

# date.weekday(): Monday=0 ... Sunday=6
DELIVERY_WEEKDAYS = frozenset({1, 3, 5})  # Tuesday, Thursday, Saturday


def get_next_delivery_date(ordered_at: datetime | None = None) -> date:
    """Return the delivery day (Tue/Thu/Sat) an order placed at `ordered_at` will arrive on.

    An order makes a delivery only if it is placed before the cutoff (default 14:00,
    restaurant local time) on the day before that delivery. E.g. Monday 13:59 -> Tuesday,
    Monday 14:00 -> Thursday. Naive datetimes are taken as local time; defaults to now.
    """
    ordered_at = to_local(ordered_at) if ordered_at is not None else now_local()
    days_until_earliest = 1 if ordered_at.time() < settings.order_cutoff else 2
    earliest = ordered_at.date() + timedelta(days=days_until_earliest)
    for days_ahead in range(7):
        candidate = earliest + timedelta(days=days_ahead)
        if candidate.weekday() in DELIVERY_WEEKDAYS:
            return candidate
    raise AssertionError("unreachable: every week contains a delivery day")
