from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    unit: Mapped[str] = mapped_column(String(20))  # e.g. kg, L, pcs
    # May go negative: POS mis-rings and unrecorded waste are corrected by the next audit.
    quantity: Mapped[float] = mapped_column(default=0)
    reorder_level: Mapped[float] = mapped_column(default=0)
    # Units per supplier pack (e.g. French Fries come in 15 kg boxes -> 15). Orders are placed in
    # whole packs. Stock, reorder levels and audits stay in `unit`.
    pack_size: Mapped[float] = mapped_column(default=1.0, server_default="1.0")
    # Key Items that are physically counted every day (in addition to the weekly audit).
    is_daily_tracked: Mapped[bool] = mapped_column(default=False, index=True)
