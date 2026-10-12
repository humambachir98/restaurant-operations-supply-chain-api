from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import InventoryItem, PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus
from app.routers.inventory import IS_LOW_STOCK, get_items_or_400
from app.schemas import (
    AutoReceiveResult,
    PurchaseOrderCreate,
    PurchaseOrderRead,
    PurchaseOrderSuggestion,
    SuggestedOrderItem,
)
from app.services.receiving import auto_receive_due_orders, mark_received
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


@router.post("/trigger-auto-receive", response_model=AutoReceiveResult)
def trigger_auto_receive(db: Session = Depends(get_db)):
    """Run the daily 06:00 auto-receive now: every pending order due today or earlier is received.

    Safe to call any number of times; already received orders are never counted twice.
    """
    as_of = now_local().date()
    return AutoReceiveResult(as_of=as_of, received_order_ids=auto_receive_due_orders(db, as_of))


@router.get("/{order_id}", response_model=PurchaseOrderRead)
def get_order(order_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, order_id)


@router.post("/{order_id}/receive", response_model=PurchaseOrderRead)
def receive_order(order_id: int, db: Session = Depends(get_db)):
    """Receive one order now (e.g. an early delivery), without waiting for the 06:00 auto-receive."""
    order = _get_or_404(db, order_id)
    try:
        if not mark_received(db, order):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Purchase order has already been received")
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(order)
    return order
