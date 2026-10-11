import enum
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.shift import Shift


class EmployeeRole(enum.StrEnum):
    shift_manager = "shift_manager"
    crew = "crew"


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[EmployeeRole]
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    shifts: Mapped[list["Shift"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )
