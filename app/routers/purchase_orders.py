from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import InventoryItem, PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus
from app.routers.inventory import IS_LOW_STOCK, get_items_or_400
from app.schemas import (
    PurchaseOrderCreate,
    PurchaseOrderRead,
    PurchaseOrderSuggestion,
    SuggestedOrderItem,
)
from app.utils.delivery import get_next_delivery_date
from app.utils.restock import packs_to_order, suggested_order_quantity
from app.utils.time import now_local

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])


def _get_or_404(db: Session, order_id: int) -> PurchaseOrder:
    order = db.get(PurchaseOrder, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Purchase order not found")
    return order


@router.get("/", response_model=list[PurchaseOrderRead])
def list_orders(
    status_filter: PurchaseOrderStatus | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    query = select(PurchaseOrder).order_by(PurchaseOrder.expected_delivery_date, PurchaseOrder.id)
    if status_filter is not None:
        query = query.where(PurchaseOrder.status == status_filter)
    return db.scalars(query).all()


@router.post("/", response_model=PurchaseOrderRead, status_code=status.HTTP_201_CREATED)
def create_order(payload: PurchaseOrderCreate, db: Session = Depends(get_db)):
    items = get_items_or_400(db, (line.item_id for line in payload.items))

    created_at = now_local()
    order = PurchaseOrder(
        status=PurchaseOrderStatus.pending,
        created_at=created_at,
        expected_delivery_date=get_next_delivery_date(created_at),
        notes=payload.notes,
        items=[
            PurchaseOrderItem(item_id=line.item_id, packs=line.packs, pack_size=items[line.item_id].pack_size)
            for line in payload.items
        ],
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@router.post("/auto-suggest", response_model=PurchaseOrderSuggestion)
def auto_suggest_order(db: Session = Depends(get_db)):
    """Draft a restock order covering every low-stock item, for a manager to review.

    Each line is in whole supplier packs: the shortfall (see `suggested_order_quantity`) is
    rounded up to the item's `pack_size`. Nothing is saved. To place the order, edit the items as needed and POST
    {"items": [...]} to /purchase-orders/ (extra display fields are ignored).
    """
    on_order = dict(
        db.execute(
            select(PurchaseOrderItem.item_id, func.sum(PurchaseOrderItem.quantity))
            .join(PurchaseOrder)
            .where(PurchaseOrder.status == PurchaseOrderStatus.pending)
            .group_by(PurchaseOrderItem.item_id)
        ).all()
    )

    items = []
    for item in db.scalars(select(InventoryItem).where(IS_LOW_STOCK).order_by(InventoryItem.name)):
        pending = on_order.get(item.id, 0.0)
        needed = suggested_order_quantity(item.quantity, item.reorder_level, pending)
        packs = packs_to_order(needed, item.pack_size)
        if packs == 0:  # already covered by orders still on their way
            continue
        items.append(
            SuggestedOrderItem(
                item_id=item.id,
                packs=packs,
                name=item.name,
                unit=item.unit,
                pack_size=item.pack_size,
                quantity=round(packs * item.pack_size, 3),
                needed=needed,
                current_quantity=item.quantity,
                reorder_level=item.reorder_level,
                on_order=pending,
            )
        )

    now = now_local()
    return PurchaseOrderSuggestion(
        generated_at=now, expected_delivery_date=get_next_delivery_date(now), items=items
    )


@router.get("/{order_id}", response_model=PurchaseOrderRead)
def get_order(order_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, order_id)


@router.post("/{order_id}/receive", response_model=PurchaseOrderRead)
def receive_order(order_id: int, db: Session = Depends(get_db)):
    """Mark the delivery as received and add every ordered quantity to stock, atomically."""
    order = _get_or_404(db, order_id)
    try:
        # Conditional UPDATE: of two concurrent requests, only one can flip pending -> received,
        # so the stock is never added twice.
        flipped = db.execute(
            update(PurchaseOrder)
            .where(PurchaseOrder.id == order_id, PurchaseOrder.status == PurchaseOrderStatus.pending)
            .values(status=PurchaseOrderStatus.received, received_at=now_local())
        ).rowcount
        if flipped == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Purchase order has already been received")

        for line in order.items:
            # Increment in SQL rather than read-modify-write, so concurrent stock changes aren't lost.
            db.execute(
                update(InventoryItem)
                .where(InventoryItem.id == line.item_id)
                .values(quantity=InventoryItem.quantity + line.quantity)  # packs * pack_size
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(order)
    return order
