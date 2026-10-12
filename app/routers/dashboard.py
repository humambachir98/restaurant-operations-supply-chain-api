from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Complaint, ComplaintStatus, InventoryItem, PurchaseOrder, PurchaseOrderStatus, StoreTransfer, WasteLog
from app.routers.inventory import IS_LOW_STOCK
from app.schemas import DashboardSummary, StockHealth, WasteItemTotal, WasteToday
from app.utils.time import local_day_bounds, now_local

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

RECENT_TRANSFERS = 5


def _count(db: Session, model, *where) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*where))


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db)):
    """Area manager overview: stock health, today's waste (Berlin day), recent transfers, open work."""
    now = now_local()

    health = select(
        func.count(),
        func.sum(case((InventoryItem.quantity < 0, 1), else_=0)),
        func.sum(case(((InventoryItem.quantity >= 0) & IS_LOW_STOCK, 1), else_=0)),
    ).select_from(InventoryItem)
    total, negative, low = db.execute(health).one()
    negative, low = negative or 0, low or 0

    start, end = local_day_bounds(now.date())
    waste_rows = db.execute(
        select(InventoryItem.id, InventoryItem.name, InventoryItem.unit, func.sum(WasteLog.quantity), func.count())
        .join(WasteLog.item)
        .where(WasteLog.created_at >= start, WasteLog.created_at < end)
        .group_by(InventoryItem.id)
        .order_by(func.sum(WasteLog.quantity).desc(), InventoryItem.name)
    ).all()

    transfers = db.scalars(
        select(StoreTransfer).order_by(StoreTransfer.created_at.desc(), StoreTransfer.id.desc()).limit(RECENT_TRANSFERS)
    ).all()

    return DashboardSummary(
        generated_at=now,
        stock_health=StockHealth(total_items=total, ok=total - low - negative, low=low, negative=negative),
        waste_today=WasteToday(
            date=now.date(),
            entries=sum(row[4] for row in waste_rows),
            items=[
                WasteItemTotal(item_id=i, item_name=name, unit=unit, quantity=round(qty, 3), entries=n)
                for i, name, unit, qty, n in waste_rows
            ],
        ),
        recent_transfers=transfers,
        pending_deliveries=_count(db, PurchaseOrder, PurchaseOrder.status == PurchaseOrderStatus.pending),
        pending_complaints=_count(db, Complaint, Complaint.status == ComplaintStatus.pending),
    )
