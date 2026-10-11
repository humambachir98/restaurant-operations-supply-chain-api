from pydantic import BaseModel, ConfigDict

from app.models import EmployeeRole


class EmployeeBase(BaseModel):
    name: str
    role: EmployeeRole
    email: str | None = None
    is_active: bool = True


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    name: str | None = None
    role: EmployeeRole | None = None
    email: str | None = None
    is_active: bool | None = None


class EmployeeRead(EmployeeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
