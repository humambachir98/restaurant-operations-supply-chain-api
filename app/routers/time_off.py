import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Employee, TimeOff
from app.schemas import TimeOffCreate, TimeOffRead, TimeOffUpdate
from app.services.roster import ensure_no_shift_on

router = APIRouter(prefix="/time-off", tags=["time-off"])


def _get_or_404(db: Session, time_off_id: int) -> TimeOff:
    time_off = db.get(TimeOff, time_off_id)
    if time_off is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Time-off entry not found")
    return time_off


def _ensure_day_is_free(db: Session, employee_id: int, day: dt.date, exclude_id: int | None = None) -> None:
    """400 unless the employee has neither another time-off entry nor a shift on `day`."""
    query = select(TimeOff).where(TimeOff.employee_id == employee_id, TimeOff.date == day)
    if exclude_id is not None:
        query = query.where(TimeOff.id != exclude_id)
    existing = db.scalar(query)
    if existing is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Employee {employee_id} is already marked '{existing.status.value}' on {day.isoformat()} "
            f"(id {existing.id})",
        )
    ensure_no_shift_on(db, employee_id, day)


@router.get("/", response_model=list[TimeOffRead])
def list_time_off(
    employee_id: int | None = None,
    start_date: dt.date | None = Query(None, description="From this day (inclusive)"),
    end_date: dt.date | None = Query(None, description="Up to this day (inclusive)"),
    db: Session = Depends(get_db),
):
    query = select(TimeOff).order_by(TimeOff.date, TimeOff.employee_id)
    if employee_id is not None:
        query = query.where(TimeOff.employee_id == employee_id)
    if start_date is not None:
        query = query.where(TimeOff.date >= start_date)
    if end_date is not None:
        query = query.where(TimeOff.date <= end_date)
    return db.scalars(query).all()


@router.post("/", response_model=TimeOffRead, status_code=status.HTTP_201_CREATED)
def create_time_off(payload: TimeOffCreate, db: Session = Depends(get_db)):
    """Mark an employee Urlaub / Krank / Frei for a day.

    Rejected if they already have a status or a shift on that day.
    """
    if db.get(Employee, payload.employee_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Employee does not exist")
    _ensure_day_is_free(db, payload.employee_id, payload.date)
    time_off = TimeOff(**payload.model_dump())
    db.add(time_off)
    db.commit()
    db.refresh(time_off)
    return time_off


@router.get("/{time_off_id}", response_model=TimeOffRead)
def get_time_off(time_off_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, time_off_id)


@router.patch("/{time_off_id}", response_model=TimeOffRead)
def update_time_off(time_off_id: int, payload: TimeOffUpdate, db: Session = Depends(get_db)):
    time_off = _get_or_404(db, time_off_id)
    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "date" in data and data["date"] != time_off.date:
        _ensure_day_is_free(db, time_off.employee_id, data["date"], exclude_id=time_off.id)
    for field, value in data.items():
        setattr(time_off, field, value)
    db.commit()
    db.refresh(time_off)
    return time_off


@router.delete("/{time_off_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_time_off(time_off_id: int, db: Session = Depends(get_db)):
    db.delete(_get_or_404(db, time_off_id))
    db.commit()
