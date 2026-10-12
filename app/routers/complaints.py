from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Complaint, ComplaintStatus, PurchaseOrder, PurchaseOrderStatus
from app.schemas import ComplaintCreate, ComplaintRead
from app.services.stock import adjust_stock
from app.utils.time import now_local

router = APIRouter(prefix="/complaints", tags=["complaints"])


def _get_or_404(db: Session, complaint_id: int) -> Complaint:
    complaint = db.get(Complaint, complaint_id)
    if complaint is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Complaint not found")
    return complaint


def _resolve(db: Session, complaint: Complaint, new_status: ComplaintStatus, apply_to_stock: bool) -> Complaint:
    """Move a pending complaint to `new_status` in one transaction, optionally adjusting stock.

    The conditional UPDATE lets only one of two concurrent decisions win, so a complaint's
    difference is never applied twice.
    """
    try:
        flipped = db.execute(
            update(Complaint)
            .where(Complaint.id == complaint.id, Complaint.status == ComplaintStatus.pending)
            .values(status=new_status, resolved_at=now_local())
        ).rowcount
        if flipped == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Complaint has already been {complaint.status}")
        if apply_to_stock:
            adjust_stock(db, complaint.item_id, complaint.quantity_difference)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(complaint)
    return complaint


@router.get("/", response_model=list[ComplaintRead])
def list_complaints(
    status_filter: ComplaintStatus | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    """Newest first."""
    query = select(Complaint).order_by(Complaint.created_at.desc(), Complaint.id.desc())
    if status_filter is not None:
        query = query.where(Complaint.status == status_filter)
    return db.scalars(query).all()


@router.post("/", response_model=ComplaintRead, status_code=status.HTTP_201_CREATED)
def create_complaint(payload: ComplaintCreate, db: Session = Depends(get_db)):
    """File a complaint about a received delivery. Stock changes only once it's approved."""
    order = db.get(PurchaseOrder, payload.order_id)
    if order is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Purchase order does not exist")
    if order.status != PurchaseOrderStatus.received:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Complaints can only be filed for received orders")

    line = next((line for line in order.items if line.item_id == payload.item_id), None)
    if line is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Item is not part of this order")
    if payload.quantity_difference == 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "quantity_difference must not be 0")
    if payload.quantity_difference < -line.quantity:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Can't report more missing than was delivered ({line.quantity:g} {line.unit})",
        )

    complaint = Complaint(**payload.model_dump())
    db.add(complaint)
    db.commit()
    db.refresh(complaint)
    return complaint


@router.get("/{complaint_id}", response_model=ComplaintRead)
def get_complaint(complaint_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, complaint_id)


@router.post("/{complaint_id}/approve", response_model=ComplaintRead)
def approve_complaint(complaint_id: int, db: Session = Depends(get_db)):
    """Accept the complaint and apply its quantity difference to the item's stock, atomically."""
    return _resolve(db, _get_or_404(db, complaint_id), ComplaintStatus.approved, apply_to_stock=True)


@router.post("/{complaint_id}/reject", response_model=ComplaintRead)
def reject_complaint(complaint_id: int, db: Session = Depends(get_db)):
    """Close the complaint without changing stock."""
    return _resolve(db, _get_or_404(db, complaint_id), ComplaintStatus.rejected, apply_to_stock=False)
