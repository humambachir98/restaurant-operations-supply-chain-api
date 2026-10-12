import datetime as dt
import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.employee import Employee


class TimeOffStatus(enum.StrEnum):
    vacation = "Urlaub"
    sick = "Krank"
    day_off = "Frei"


class TimeOff(Base):
    """A whole day an employee isn't available for the roster (vacation, sick leave, day off)."""

    __tablename__ = "time_off"
    __table_args__ = (UniqueConstraint("employee_id", "date"),)  # one status per employee and day

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    date: Mapped[dt.date] = mapped_column(index=True)  # Berlin calendar day
    # Store the German values ('Urlaub' / 'Krank' / 'Frei') that the roster shows.
    status: Mapped[TimeOffStatus] = mapped_column(
        Enum(TimeOffStatus, values_callable=lambda e: [m.value for m in e], length=10)
    )

    employee: Mapped["Employee"] = relationship(back_populates="time_off")
