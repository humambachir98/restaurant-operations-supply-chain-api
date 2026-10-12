import enum
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.types import LocalDateTime
from app.utils.time import now_local


class AuditType(enum.StrEnum):
    daily = "daily"  # Key Items only
    weekly = "weekly"
    monthly = "monthly"  # end-of-month full count


class InventoryAudit(Base):
    """One physical count session: daily Key Item count, or a weekly / end-of-month full count."""

    __tablename__ = "inventory_audits"

    id: Mapped[int] = mapped_column(primary_key=True)
    audit_type: Mapped[AuditType]
    created_at: Mapped[datetime] = mapped_column(LocalDateTime, default=now_local)
    notes: Mapped[str | None] = mapped_column(String(500))

    lines: Mapped[list["InventoryAuditLine"]] = relationship(
        back_populates="audit", cascade="all, delete-orphan"
    )


class InventoryAuditLine(Base):
    """Counted quantity for one item, with the system quantity it replaced."""

    __tablename__ = "inventory_audit_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    audit_id: Mapped[int] = mapped_column(ForeignKey("inventory_audits.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"), index=True)
    expected_quantity: Mapped[float]  # system quantity before the count
    counted_quantity: Mapped[float]
    variance: Mapped[float]  # counted - expected; negative means shrinkage

    audit: Mapped[InventoryAudit] = relationship(back_populates="lines")
