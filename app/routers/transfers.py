from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StoreTransfer, TransferDirection
from app.routers.inventory import get_items_or_400
from app.schemas import StoreTransferCreate, StoreTransferRead
from app.services.stock import adjust_stock

router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.get("/", response_model=list[StoreTransferRead])
def list_transfers(
    direction: TransferDirection | None = None,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Newest first."""
    query = select(StoreTransfer).order_by(StoreTransfer.created_at.desc(), StoreTransfer.id.desc()).limit(limit)
    if direction is not None:
        query = query.where(StoreTransfer.direction == direction)
    return db.scalars(query).all()


@router.post("/", response_model=StoreTransferRead, status_code=status.HTTP_201_CREATED)
def record_transfer(payload: StoreTransferCreate, db: Session = Depends(get_db)):
    """Record stock moved to ('out') or from ('in') another store, updating stock in the same transaction."""
    get_items_or_400(db, [payload.item_id])
    transfer = StoreTransfer(**payload.model_dump())
    try:
        db.add(transfer)
        adjust_stock(db, payload.item_id, transfer.stock_change)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(transfer)
    return transfer
