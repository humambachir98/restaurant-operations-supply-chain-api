from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditType, WasteLog
from app.routers.inventory import get_items_or_400
from app.schemas import WasteLogCreate, WasteLogRead
from app.services.stock import adjust_stock
from app.utils.time import local_day_bounds

router = APIRouter(prefix="/waste", tags=["waste"])


@router.get("/", response_model=list[WasteLogRead])
def list_waste(
    on: date | None = Query(None, description="Only waste logged on this Berlin calendar day"),
    audit_type: AuditType | None = None,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Newest first."""
    query = select(WasteLog).order_by(WasteLog.created_at.desc(), WasteLog.id.desc()).limit(limit)
    if on is not None:
        start, end = local_day_bounds(on)
        query = query.where(WasteLog.created_at >= start, WasteLog.created_at < end)
    if audit_type is not None:
        query = query.where(WasteLog.audit_type == audit_type)
    return db.scalars(query).all()


@router.post("/", response_model=WasteLogRead, status_code=status.HTTP_201_CREATED)
def log_waste(payload: WasteLogCreate, db: Session = Depends(get_db)):
    """Record waste and deduct it from stock in the same transaction."""
    get_items_or_400(db, [payload.item_id])
    entry = WasteLog(**payload.model_dump())
    try:
        db.add(entry)
        adjust_stock(db, payload.item_id, -payload.quantity)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(entry)
    return entry
