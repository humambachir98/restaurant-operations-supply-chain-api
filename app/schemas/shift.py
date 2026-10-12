from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, model_validator

from app.models import EmployeeRole
from app.schemas.common import ZonedDateTime
from app.utils.time import elapsed

# German Working Hours Act (ArbZG § 3): at most 10 hours of work per day.
MAX_SHIFT_DURATION = timedelta(hours=10)


def check_shift_window(start: datetime, end: datetime) -> None:
    """Raise ValueError unless end is after start and the shift lasts at most 10 real hours."""
    duration = elapsed(start, end)
    if duration <= timedelta(0):
        raise ValueError("end_time must be after start_time")
    if duration > MAX_SHIFT_DURATION:
        raise ValueError(
            f"Shift lasts {duration}; the maximum is {MAX_SHIFT_DURATION} (German Working Hours Act)"
        )


class ShiftBase(BaseModel):
    employee_id: int
    start_time: ZonedDateTime
    end_time: ZonedDateTime
    # Left out: the employee's own role.
    role_worked: EmployeeRole | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def check_times(self):
        check_shift_window(self.start_time, self.end_time)
        return self


class ShiftCreate(ShiftBase):
    pass


class ShiftUpdate(BaseModel):
    employee_id: int | None = None
    start_time: ZonedDateTime | None = None
    end_time: ZonedDateTime | None = None
    role_worked: EmployeeRole | None = None
    notes: str | None = None


class ShiftRead(ShiftBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role_worked: EmployeeRole
