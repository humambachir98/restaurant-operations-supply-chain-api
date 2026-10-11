from datetime import UTC, date, datetime

import pytest

from app.utils.delivery import get_next_delivery_date
from app.utils.time import LOCAL_TZ


def berlin(*args) -> datetime:
    return datetime(*args, tzinfo=LOCAL_TZ)


@pytest.mark.parametrize(
    ("ordered_at", "expected"),
    [
        # Cutoff is 14:00 on the day before the delivery.
        (berlin(2026, 10, 5, 9, 0), date(2026, 10, 6)),     # Mon morning -> Tue
        (berlin(2026, 10, 5, 13, 59), date(2026, 10, 6)),   # Mon just before cutoff -> Tue
        (berlin(2026, 10, 5, 14, 0), date(2026, 10, 8)),    # Mon at cutoff -> misses Tue -> Thu
        (berlin(2026, 10, 5, 15, 0), date(2026, 10, 8)),    # Mon 15:00 -> Thu
        (berlin(2026, 10, 6, 10, 0), date(2026, 10, 8)),    # Tue (delivery day) -> Thu, never same day
        (berlin(2026, 10, 7, 13, 0), date(2026, 10, 8)),    # Wed before cutoff -> Thu
        (berlin(2026, 10, 7, 14, 30), date(2026, 10, 10)),  # Wed after cutoff -> Sat
        (berlin(2026, 10, 9, 13, 0), date(2026, 10, 10)),   # Fri before cutoff -> Sat
        (berlin(2026, 10, 9, 16, 0), date(2026, 10, 13)),   # Fri after cutoff -> Tue
        (berlin(2026, 10, 10, 9, 0), date(2026, 10, 13)),   # Sat -> Tue
        (berlin(2026, 10, 11, 23, 0), date(2026, 10, 13)),  # Sun late -> Tue (Mon 14:00 cutoff)
        (berlin(2026, 12, 31, 15, 0), date(2027, 1, 2)),    # Thu 15:00 still beats Fri cutoff -> Sat, across year end
        (berlin(2027, 1, 1, 15, 0), date(2027, 1, 5)),      # Fri after cutoff -> Tue
    ],
)
def test_next_delivery_date(ordered_at, expected):
    assert get_next_delivery_date(ordered_at) == expected


def test_utc_input_is_judged_in_berlin_time():
    # 12:30 UTC is 14:30 in Berlin (CEST): past the cutoff even though UTC says it's before 14:00.
    assert get_next_delivery_date(datetime(2026, 10, 5, 12, 30, tzinfo=UTC)) == date(2026, 10, 8)
    # Winter time (CET, UTC+1): 12:30 UTC is 13:30 Berlin, still before the cutoff.
    assert get_next_delivery_date(datetime(2026, 12, 7, 12, 30, tzinfo=UTC)) == date(2026, 12, 8)
    # 23:30 UTC Monday is already Tuesday 01:30 in Berlin.
    assert get_next_delivery_date(datetime(2026, 10, 5, 23, 30, tzinfo=UTC)) == date(2026, 10, 8)


def test_naive_input_is_taken_as_berlin_time():
    assert get_next_delivery_date(datetime(2026, 10, 5, 15, 0)) == date(2026, 10, 8)
