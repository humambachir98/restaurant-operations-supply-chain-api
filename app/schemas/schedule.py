import datetime as dt

from pydantic import BaseModel

from app.schemas.employee import EmployeeRead
from app.schemas.shift import ShiftRead
from app.schemas.time_off import TimeOffRead


class ScheduleDay(BaseModel):
    """One cell of the roster: an employee's shifts and time-off on one Berlin day."""

    date: dt.date
    shifts: list[ShiftRead]
    time_off: TimeOffRead | None


class ScheduleRow(BaseModel):
    employee: EmployeeRead
    days: list[ScheduleDay]  # Monday to Sunday


class WeeklySchedule(BaseModel):
    start_date: dt.date  # Monday
    end_date: dt.date  # Sunday
    days: list[dt.date]
    rows: list[ScheduleRow]  # shift managers first, then crew; by name
