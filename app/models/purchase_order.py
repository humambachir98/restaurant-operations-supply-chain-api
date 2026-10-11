import enum
from datetime import date, datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.types import LocalDateTime
from app.utils.time import now_local


class PurchaseOrderStatus(enum.StrEnum):
    pending = "pending"
    received = "received"


class PurchaseOrder(Base):
    """A supplier order (Bestellung), delivered on the next Tue/Thu/Sat."""

    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        default=PurchaseOrderStatus.pending, index=True
    )
    created_at: Mapped[datetime] = mapped_column(LocalDateTime, default=now_local)
    expected_delivery_date: Mapped[date]
    received_at: Mapped[datetime | None] = mapped_column(LocalDateTime)
    notes: Mapped[str | None] = mapped_column(String(500))

    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"), index=True)
    packs: Mapped[int]  # whole supplier packs ordered
    # The item's pack size when the order was placed, so changing it later doesn't alter
    # what this order adds to stock.
    pack_size: Mapped[float]

    order: Mapped[PurchaseOrder] = relationship(back_populates="items")

    @hybrid_property
    def quantity(self) -> float:
        """Total in stock units (packs * pack_size); usable in queries too."""
        return self.packs * self.pack_size
