from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Employee, Shift
from app.schemas import ShiftCreate, ShiftRead, ShiftUpdate
from app.schemas.shift import check_shift_window
from app.services.roster import ensure_not_off, shift_day

router = APIRouter(prefix="/shifts", tags=["shifts"])


def _get_or_404(db: Session, shift_id: int) -> Shift:
    shift = db.get(Shift, shift_id)
    if shift is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shift not found")
    return shift


def _get_employee_or_400(db: Session, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Employee does not exist")
    return employee


def _ensure_no_overlap(
    db: Session, employee_id: int, start: datetime, end: datetime, exclude_shift_id: int | None = None
) -> None:
    """400 if the employee already has a shift overlapping [start, end).

    Back-to-back shifts (one ends exactly when the next starts) are allowed.
    """
    query = select(Shift).where(
        Shift.employee_id == employee_id, Shift.start_time < end, Shift.end_time > start
    )
    if exclude_shift_id is not None:
        query = query.where(Shift.id != exclude_shift_id)
    clash = db.scalars(query.order_by(Shift.start_time).limit(1)).first()
    if clash is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Employee {employee_id} already has an overlapping shift (id {clash.id}, "
            f"{clash.start_time.isoformat()} to {clash.end_time.isoformat()})",
        )


@router.get("/", response_model=list[ShiftRead])
def list_shifts(employee_id: int | None = None, db: Session = Depends(get_db)):
    query = select(Shift).order_by(Shift.start_time)
    if employee_id is not None:
        query = query.where(Shift.employee_id == employee_id)
    return db.scalars(query).all()


@router.post("/", response_model=ShiftRead, status_code=status.HTTP_201_CREATED)
def create_shift(payload: ShiftCreate, db: Session = Depends(get_db)):
    """Schedule a shift. `role_worked` defaults to the employee's role.

    Rejected if it lasts over 10 hours, overlaps another of the employee's shifts, or falls on a
    day the employee is marked off.
    """
    employee = _get_employee_or_400(db, payload.employee_id)
    _ensure_no_overlap(db, payload.employee_id, payload.start_time, payload.end_time)
    ensure_not_off(db, payload.employee_id, shift_day(payload.start_time))
    shift = Shift(**payload.model_dump(exclude={"role_worked"}), role_worked=payload.role_worked or employee.role)
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return shift


@router.get("/{shift_id}", response_model=ShiftRead)
def get_shift(shift_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, shift_id)


@router.patch("/{shift_id}", response_model=ShiftRead)
def update_shift(shift_id: int, payload: ShiftUpdate, db: Session = Depends(get_db)):
    shift = _get_or_404(db, shift_id)
    data = payload.model_dump(exclude_unset=True)
    employee = _get_employee_or_400(db, data["employee_id"]) if "employee_id" in data else shift.employee
    if "role_worked" in data and data["role_worked"] is None:
        data["role_worked"] = employee.role  # null resets it to the employee's role
    employee_id = data.get("employee_id", shift.employee_id)
    start = data.get("start_time", shift.start_time)
    end = data.get("end_time", shift.end_time)
    try:
        check_shift_window(start, end)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))
    _ensure_no_overlap(db, employee_id, start, end, exclude_shift_id=shift.id)
    if employee_id != shift.employee_id or shift_day(start) != shift_day(shift.start_time):
        ensure_not_off(db, employee_id, shift_day(start))
    for field, value in data.items():
        setattr(shift, field, value)
    db.commit()
    db.refresh(shift)
    return shift


@router.delete("/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shift(shift_id: int, db: Session = Depends(get_db)):
    db.delete(_get_or_404(db, shift_id))
    db.commit()
