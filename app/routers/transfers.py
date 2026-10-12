import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StoreTransfer, TransferDirection
from app.routers.inventory import get_items_or_400
from app.schemas import StoreTransferRead, TransferBatchCreate
from app.services.stock import adjust_stock
from app.utils.time import now_local

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


@router.post("/", response_model=list[StoreTransferRead], status_code=status.HTTP_201_CREATED)
def record_transfers(payload: TransferBatchCreate, db: Session = Depends(get_db)):
    """Record a transfer list with one other store: 'out' lines deduct stock, 'in' lines add it.

    All or nothing: one transaction, so an invalid line or a failure leaves stock untouched.
    """
    get_items_or_400(db, (line.item_id for line in payload.items))
    batch = {"batch_id": str(uuid.uuid4()), "created_at": now_local()}
    transfers = [
        StoreTransfer(**line.model_dump(), target_store_name=payload.target_store_name, **batch)
        for line in payload.items
    ]
    try:
        db.add_all(transfers)
        for transfer in transfers:
            adjust_stock(db, transfer.item_id, transfer.stock_change)
        db.commit()
    except Exception:
        db.rollback()
        raise
    for transfer in transfers:
        db.refresh(transfer)
    return transfers
