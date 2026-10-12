from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import InventoryItem


def adjust_stock(db: Session, item_id: int, delta: float) -> None:
    """Add `delta` (may be negative) to an item's stock. Doesn't commit.

    Incremented in SQL rather than read-modify-write, so concurrent stock changes aren't lost.
    Stock may go negative: the next physical count corrects it.
    """
    db.execute(
        update(InventoryItem).where(InventoryItem.id == item_id).values(quantity=InventoryItem.quantity + delta)
    )
