import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.database.types import LocalDateTime
from app.models.audit import AuditType
from app.utils.time import now_local

if TYPE_CHECKING:
    from app.models.inventory import InventoryItem


class _ItemDetails:
    """`item_name` / `unit` for API responses, from the joined inventory item."""

    item: "InventoryItem"

    @property
    def item_name(self) -> str:
        return self.item.name

    @property
    def unit(self) -> str:
        return self.item.unit


class WasteLog(_ItemDetails, Base):
    """Stock thrown away (expired, dropped, burnt). Logging it deducts the quantity from stock."""

    __tablename__ = "waste_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"), index=True)
    quantity: Mapped[float]  # in the item's stock unit, always positive
    audit_type: Mapped[AuditType]  # the reporting period the waste is booked against
    reason: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(LocalDateTime, default=now_local, index=True)

    item: Mapped["InventoryItem"] = relationship(lazy="joined")


class TransferDirection(enum.StrEnum):
    incoming = "in"  # received from another store: adds to stock
    outgoing = "out"  # sent to another store: deducts from stock


class StoreTransfer(_ItemDetails, Base):
    """Stock lent to or borrowed from another store (e.g. buns sent to a branch that ran out)."""

    __tablename__ = "store_transfers"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"), index=True)
    quantity: Mapped[float]  # in the item's stock unit, always positive
    # Store the values ('in'/'out'): `in` can't be a Python member name.
    direction: Mapped[TransferDirection] = mapped_column(
        Enum(TransferDirection, values_callable=lambda e: [m.value for m in e], length=3)
    )
    target_store_name: Mapped[str] = mapped_column(String(100))  # the other store, either way
    created_at: Mapped[datetime] = mapped_column(LocalDateTime, default=now_local, index=True)

    item: Mapped["InventoryItem"] = relationship(lazy="joined")

    @property
    def stock_change(self) -> float:
        return self.quantity if self.direction == TransferDirection.incoming else -self.quantity
