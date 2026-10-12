import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.types import LocalDateTime
from app.utils.time import now_local

if TYPE_CHECKING:
    from app.models.inventory import InventoryItem


class ComplaintStatus(enum.StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Complaint(Base):
    """A delivery complaint (Reklamation): goods missing, damaged or delivered in excess.

    Approving it applies `quantity_difference` to stock, correcting what the order added.
    """

    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"), index=True)
    # In the item's stock unit: negative for missing/damaged goods, positive for extra goods.
    quantity_difference: Mapped[float]
    notes: Mapped[str] = mapped_column(String(500))
    status: Mapped[ComplaintStatus] = mapped_column(default=ComplaintStatus.pending, index=True)
    created_at: Mapped[datetime] = mapped_column(LocalDateTime, default=now_local)
    resolved_at: Mapped[datetime | None] = mapped_column(LocalDateTime)

    item: Mapped["InventoryItem"] = relationship(lazy="joined")

    @property
    def item_name(self) -> str:
        return self.item.name

    @property
    def unit(self) -> str:
        return self.item.unit
