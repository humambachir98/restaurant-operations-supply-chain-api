from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import WasteLog
from app.routers.inventory import get_items_or_400
from app.schemas import WasteBatchCreate, WasteLogRead
from app.services.stock import adjust_stock
from app.utils.time import local_day_bounds, now_local

router = APIRouter(prefix="/waste", tags=["waste"])


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


@router.post("/", response_model=list[WasteLogRead], status_code=status.HTTP_201_CREATED)
def book_waste(payload: WasteBatchCreate, db: Session = Depends(get_db)):
    """Book a batch of waste (e.g. end of day) and deduct every line from stock.

    All or nothing: one transaction, so an invalid line or a failure leaves stock untouched.
    """
    get_items_or_400(db, (line.item_id for line in payload.items))
    booked_at = now_local()
    entries = [WasteLog(**line.model_dump(), created_at=booked_at) for line in payload.items]
    try:
        db.add_all(entries)
        for line in payload.items:
            adjust_stock(db, line.item_id, -line.quantity)
        db.commit()
    except Exception:
        db.rollback()
        raise
    for entry in entries:
        db.refresh(entry)
    return entries
