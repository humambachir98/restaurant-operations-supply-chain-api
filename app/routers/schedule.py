import datetime as dt
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Employee, EmployeeRole, Shift, TimeOff
from app.schemas import WeeklySchedule
from app.services.roster import shift_day
from app.utils.time import local_day_bounds

router = APIRouter(prefix="/schedule", tags=["schedule"])

ROLE_ORDER = {EmployeeRole.shift_manager: 0, EmployeeRole.crew: 1}  # Schichtführer first


@router.get("/weekly", response_model=WeeklySchedule)
def weekly_schedule(
    start_date: dt.date = Query(description="Any day of the week; the roster runs Monday to Sunday"),
    db: Session = Depends(get_db),
):
    """The roster for one week: per employee and day, their shifts and time-off status.

    Rows are active employees, plus inactive ones with entries that week; shift managers first,
    then by name. A shift belongs to the Berlin day it starts on.
    """
    monday = start_date - dt.timedelta(days=start_date.weekday())
    days = [monday + dt.timedelta(days=i) for i in range(7)]
    week_start, _ = local_day_bounds(days[0])
    _, week_end = local_day_bounds(days[-1])

    shifts = db.scalars(
        select(Shift).where(Shift.start_time >= week_start, Shift.start_time < week_end).order_by(Shift.start_time)
    ).all()
    time_off = db.scalars(select(TimeOff).where(TimeOff.date >= days[0], TimeOff.date <= days[-1])).all()

    shifts_by_cell = defaultdict(list)
    for shift in shifts:
        shifts_by_cell[shift.employee_id, shift_day(shift.start_time)].append(shift)
    time_off_by_cell = {(t.employee_id, t.date): t for t in time_off}

    scheduled_ids = {s.employee_id for s in shifts} | {t.employee_id for t in time_off}
    employees = db.scalars(select(Employee).where(or_(Employee.is_active.is_(True), Employee.id.in_(scheduled_ids))))
    employees = sorted(employees, key=lambda e: (ROLE_ORDER[e.role], e.name.casefold(), e.id))

    return {
        "start_date": days[0],
        "end_date": days[-1],
        "days": days,
        "rows": [
            {
                "employee": employee,
                "days": [
                    {
                        "date": day,
                        "shifts": shifts_by_cell.get((employee.id, day), []),
                        "time_off": time_off_by_cell.get((employee.id, day)),
                    }
                    for day in days
                ],
            }
            for employee in employees
        ],
    }
