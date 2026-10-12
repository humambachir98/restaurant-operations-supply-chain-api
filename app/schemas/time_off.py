import datetime as dt

from pydantic import BaseModel, ConfigDict

from app.models import TimeOffStatus


class TimeOffCreate(BaseModel):
    employee_id: int
    date: dt.date
    status: TimeOffStatus


class TimeOffUpdate(BaseModel):
    date: dt.date | None = None
    status: TimeOffStatus | None = None


class TimeOffRead(TimeOffCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
