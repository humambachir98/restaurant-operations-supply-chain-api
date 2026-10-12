from collections.abc import Iterable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditType, InventoryAudit, InventoryAuditLine, InventoryItem
from app.schemas import (
    InventoryAuditCreate,
    InventoryAuditRead,
    InventoryItemCreate,
    InventoryItemRead,
    InventoryItemUpdate,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])

# An item needs restocking when stock is at or below its reorder level. A reorder level of 0
# means "not managed by reorder rules", so such items are never flagged.
IS_LOW_STOCK = and_(InventoryItem.reorder_level > 0, InventoryItem.quantity <= InventoryItem.reorder_level)


def _get_or_404(db: Session, item_id: int) -> InventoryItem:
    item = db.get(InventoryItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Inventory item not found")
    return item


def get_items_or_400(db: Session, item_ids: Iterable[int]) -> dict[int, InventoryItem]:
    """Load items by id, failing with 400 if any id doesn't exist."""
    ids = set(item_ids)
    items = {item.id: item for item in db.scalars(select(InventoryItem).where(InventoryItem.id.in_(ids)))}
    missing = sorted(ids - items.keys())
    if missing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown inventory item id(s): {missing}")
    return items


@router.get("/", response_model=list[InventoryItemRead])
def list_items(low_stock: bool = False, db: Session = Depends(get_db)):
    query = select(InventoryItem).order_by(InventoryItem.name)
    if low_stock:
        query = query.where(IS_LOW_STOCK)
    return db.scalars(query).all()


@router.post("/", response_model=InventoryItemRead, status_code=status.HTTP_201_CREATED)
def create_item(payload: InventoryItemCreate, db: Session = Depends(get_db)):
    item = InventoryItem(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


# --- Fixed paths below must stay above "/{item_id}" so they aren't parsed as an id. ---


@router.get("/low-stock", response_model=list[InventoryItemRead])
def list_low_stock_items(db: Session = Depends(get_db)):
    """Items at or below their reorder level."""
    return db.scalars(select(InventoryItem).where(IS_LOW_STOCK).order_by(InventoryItem.name)).all()


@router.get("/daily-items", response_model=list[InventoryItemRead])
def list_daily_items(db: Session = Depends(get_db)):
    """The Key Items counted every day."""
    query = select(InventoryItem).where(InventoryItem.is_daily_tracked.is_(True)).order_by(InventoryItem.name)
    return db.scalars(query).all()


@router.post("/audit", response_model=InventoryAuditRead, status_code=status.HTTP_201_CREATED)
def submit_audit(payload: InventoryAuditCreate, db: Session = Depends(get_db)):
    """Record a physical count: stock is set to the counted quantity and the variance is logged."""
    items = get_items_or_400(db, (count.item_id for count in payload.counts))

    if payload.audit_type == AuditType.daily:
        not_daily = sorted(item_id for item_id, item in items.items() if not item.is_daily_tracked)
        if not_daily:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Daily audits may only include daily-tracked Key Items; not daily-tracked: {not_daily}",
            )

    audit = InventoryAudit(audit_type=payload.audit_type, notes=payload.notes)
    for count in payload.counts:
        item = items[count.item_id]
        audit.lines.append(
            InventoryAuditLine(
                item_id=item.id,
                expected_quantity=item.quantity,
                counted_quantity=count.counted_quantity,
                variance=count.counted_quantity - item.quantity,
            )
        )
        item.quantity = count.counted_quantity

    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit


@router.get("/audits", response_model=list[InventoryAuditRead])
def list_audits(audit_type: AuditType | None = None, db: Session = Depends(get_db)):
    """Audit history with per-item variances, newest first."""
    query = select(InventoryAudit).order_by(InventoryAudit.created_at.desc(), InventoryAudit.id.desc())
    if audit_type is not None:
        query = query.where(InventoryAudit.audit_type == audit_type)
    return db.scalars(query).all()


@router.get("/{item_id}", response_model=InventoryItemRead)
def get_item(item_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, item_id)


@router.patch("/{item_id}", response_model=InventoryItemRead)
def update_item(item_id: int, payload: InventoryItemUpdate, db: Session = Depends(get_db)):
    item = _get_or_404(db, item_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    db.delete(_get_or_404(db, item_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Item is referenced by audits, purchase orders or complaints and can't be deleted",
        )
