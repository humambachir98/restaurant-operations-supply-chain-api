from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.types import LocalDateTime

if TYPE_CHECKING:
    from app.models.employee import Employee


class Shift(Base):
    __tablename__ = "shifts"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    start_time: Mapped[datetime] = mapped_column(LocalDateTime)
    end_time: Mapped[datetime] = mapped_column(LocalDateTime)
    notes: Mapped[str | None] = mapped_column(String(500))

    employee: Mapped["Employee"] = relationship(back_populates="shifts")
