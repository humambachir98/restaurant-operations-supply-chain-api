import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import WasteLog
from app.routers.inventory import get_items_or_400
from app.routers.menu_items import get_menu_items_or_400
from app.schemas import WasteBatchCreate, WasteLineCreate, WasteLogRead
from app.services.stock import adjust_stock
from app.utils.time import local_day_bounds, now_local

router = APIRouter(prefix="/waste", tags=["waste"])

REASON_MAX_LENGTH = 500


@router.get("/", response_model=list[WasteLogRead])
def list_waste(
    on: date | None = Query(None, description="Only waste booked on this Berlin calendar day"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Newest first."""
    query = select(WasteLog).order_by(WasteLog.created_at.desc(), WasteLog.id.desc()).limit(limit)
    if on is not None:
        start, end = local_day_bounds(on)
        query = query.where(WasteLog.created_at >= start, WasteLog.created_at < end)
    return db.scalars(query).all()


def _deconstructed_reason(line: WasteLineCreate, menu_item_name: str) -> str:
    """The line's reason with an auto-note naming the menu item, e.g. "Dropped (From wasted Whopper)".

    Corrections (negative quantities) are noted as "(Correction: returned Whopper)".
    """
    note = f"(From wasted {menu_item_name})" if line.quantity > 0 else f"(Correction: returned {menu_item_name})"
    if line.reason is None:
        return note
    return f"{line.reason[: REASON_MAX_LENGTH - len(note) - 1]} {note}"


@router.post("/", response_model=list[WasteLogRead], status_code=status.HTTP_201_CREATED)
def book_waste(payload: WasteBatchCreate, db: Session = Depends(get_db)):
    """Book a batch of waste (e.g. end of day) and deduct every line from stock.

    Each line is either a raw inventory item (`item_id`) or a finished menu item
    (`menu_item_id`). A menu item is broken down by its recipe: every ingredient is logged as
    its own waste entry (quantity_needed x quantity) with a note naming the menu item.

    A negative quantity corrects an earlier mistake: it is logged as a negative entry and adds the
    amount back to stock. For a menu item every ingredient is returned (e.g. -2 Whoppers returns
    2 patties and 2 buns).

    All or nothing: one transaction, so an invalid line or a failure leaves stock untouched.
    """
    raw_lines = [line for line in payload.items if line.item_id is not None]
    menu_lines = [line for line in payload.items if line.menu_item_id is not None]
    get_items_or_400(db, (line.item_id for line in raw_lines))
    menu_items = get_menu_items_or_400(db, (line.menu_item_id for line in menu_lines))

    batch = {"batch_id": str(uuid.uuid4()), "created_at": now_local()}
    entries = [
        WasteLog(item_id=line.item_id, quantity=line.quantity, reason=line.reason, **batch) for line in raw_lines
    ]
    for line in menu_lines:
        menu_item = menu_items[line.menu_item_id]
        reason = _deconstructed_reason(line, menu_item.name)
        entries.extend(
            WasteLog(
                item_id=ingredient.inventory_item_id,
                quantity=ingredient.quantity_needed * line.quantity,
                reason=reason,
                **batch,
            )
            for ingredient in menu_item.ingredients
        )

    try:
        db.add_all(entries)
        for entry in entries:
            adjust_stock(db, entry.item_id, -entry.quantity)
        db.commit()
    except Exception:
        db.rollback()
        raise
    for entry in entries:
        db.refresh(entry)
    return entries
