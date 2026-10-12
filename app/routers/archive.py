from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditType, InventoryAudit, StoreTransfer, WasteLog
from app.schemas import AuditBatchRead, TransferBatchRead, WasteBatchRead
from app.utils.time import local_month_bounds, now_local

router = APIRouter(prefix="/archive", tags=["archive"])


def month_bounds(
    year: int | None = Query(None, ge=2000, le=2100, description="Defaults to the current Berlin year"),
    month: int | None = Query(None, ge=1, le=12, description="Defaults to the current Berlin month"),
) -> tuple[datetime, datetime]:
    """[start, end) of the requested Berlin calendar month (the current one if not given)."""
    if (year is None) != (month is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Give both year and month, or neither")
    if year is None:
        today = now_local()
        year, month = today.year, today.month
    return local_month_bounds(year, month)


def _group_by_batch(rows) -> dict[str, list]:
    """Rows (already newest first) grouped by batch_id, keeping the order of first appearance."""
    batches: dict[str, list] = {}
    for row in rows:
        batches.setdefault(row.batch_id, []).append(row)
    return batches


@router.get("/waste", response_model=list[WasteBatchRead])
def waste_archive(bounds: tuple[datetime, datetime] = Depends(month_bounds), db: Session = Depends(get_db)):
    """Waste bookings of one month, newest first, each with all its lines."""
    start, end = bounds
    rows = db.scalars(
        select(WasteLog)
        .where(WasteLog.created_at >= start, WasteLog.created_at < end)
        .order_by(WasteLog.created_at.desc(), WasteLog.id)
    ).all()
    return [
        WasteBatchRead(batch_id=batch_id, created_at=lines[0].created_at, lines=lines)
        for batch_id, lines in _group_by_batch(rows).items()
    ]


@router.get("/transfers", response_model=list[TransferBatchRead])
def transfer_archive(bounds: tuple[datetime, datetime] = Depends(month_bounds), db: Session = Depends(get_db)):
    """Transfer lists of one month, newest first, each with all its lines."""
    start, end = bounds
    rows = db.scalars(
        select(StoreTransfer)
        .where(StoreTransfer.created_at >= start, StoreTransfer.created_at < end)
        .order_by(StoreTransfer.created_at.desc(), StoreTransfer.id)
    ).all()
    return [
        TransferBatchRead(
            batch_id=batch_id,
            created_at=lines[0].created_at,
            target_store_name=lines[0].target_store_name,
            lines=lines,
        )
        for batch_id, lines in _group_by_batch(rows).items()
    ]


@router.get("/audits", response_model=list[AuditBatchRead])
def audit_archive(
    audit_type: AuditType | None = None,
    bounds: tuple[datetime, datetime] = Depends(month_bounds),
    db: Session = Depends(get_db),
):
    """Audits of one month, newest first: each count with the system quantity it replaced."""
    start, end = bounds
    query = (
        select(InventoryAudit)
        .where(InventoryAudit.created_at >= start, InventoryAudit.created_at < end)
        .order_by(InventoryAudit.created_at.desc(), InventoryAudit.id.desc())
    )
    if audit_type is not None:
        query = query.where(InventoryAudit.audit_type == audit_type)
    return db.scalars(query).all()
