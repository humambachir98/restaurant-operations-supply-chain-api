import logging
from datetime import date, datetime, time, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import PurchaseOrder, PurchaseOrderStatus
from app.services.stock import adjust_stock
from app.utils.time import now_local, to_local

logger = logging.getLogger(__name__)


def mark_received(db: Session, order: PurchaseOrder) -> bool:
    """Flip a pending order to received and add every line to stock. Doesn't commit.

    Returns False (changing nothing) if the order isn't pending anymore. The conditional UPDATE
    means that of two concurrent attempts (scheduler, manual trigger, receive endpoint) only
    one can flip it, so stock is never added twice.
    """
    flipped = db.execute(
        update(PurchaseOrder)
        .where(PurchaseOrder.id == order.id, PurchaseOrder.status == PurchaseOrderStatus.pending)
        .values(status=PurchaseOrderStatus.received, received_at=now_local())
    ).rowcount
    if flipped == 0:
        return False

    for line in order.items:
        adjust_stock(db, line.item_id, line.quantity)  # packs * pack_size
    return True


def auto_receive_due_orders(db: Session, as_of: date | None = None) -> list[int]:
    """Receive every pending order whose expected delivery date is on or before `as_of`.

    Defaults to today in Berlin. Earlier dates are included so orders missed while the server
    was down are still received. Each order is its own transaction: one failure doesn't block
    the rest. Returns the ids of the orders received.
    """
    as_of = as_of or now_local().date()
    due = db.scalars(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.status == PurchaseOrderStatus.pending,
            PurchaseOrder.expected_delivery_date <= as_of,
        )
        .order_by(PurchaseOrder.expected_delivery_date, PurchaseOrder.id)
    ).all()

    received = []
    for order in due:
        try:
            if mark_received(db, order):
                db.commit()
                received.append(order.id)
            else:
                db.rollback()  # received by someone else in the meantime
        except Exception:
            db.rollback()
            logger.exception("Auto-receive failed for purchase order %s", order.id)
    if received:
        logger.info("Auto-received purchase orders %s (due on or before %s)", received, as_of)
    return received


def catch_up_date(now: datetime, receive_time: time) -> date:
    """Latest delivery date that should already be received at `now` (Berlin).

    Before the daily receive time, today's deliveries are still to come.
    """
    now = to_local(now)
    return now.date() if now.time() >= receive_time else now.date() - timedelta(days=1)
