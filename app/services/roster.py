import datetime as dt

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Shift, TimeOff
from app.utils.time import local_day_bounds, to_local


def shift_day(start: dt.datetime) -> dt.date:
    """The Berlin calendar day a shift belongs to: the day it starts (a night shift stays on its first day)."""
    return to_local(start).date()


def ensure_not_off(db: Session, employee_id: int, day: dt.date) -> None:
    """400 if the employee is marked off (Urlaub / Krank / Frei) on `day`."""
    time_off = db.scalar(select(TimeOff).where(TimeOff.employee_id == employee_id, TimeOff.date == day))
    if time_off is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Employee {employee_id} is marked '{time_off.status.value}' on {day.isoformat()}; "
            "remove the time-off before scheduling a shift",
        )


def ensure_no_shift_on(db: Session, employee_id: int, day: dt.date) -> None:
    """400 if the employee has a shift starting on `day`."""
    start, end = local_day_bounds(day)
    shift = db.scalar(
        select(Shift).where(Shift.employee_id == employee_id, Shift.start_time >= start, Shift.start_time < end)
    )
    if shift is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Employee {employee_id} has a shift on {day.isoformat()} (id {shift.id}); "
            "remove the shift before marking time-off",
        )
