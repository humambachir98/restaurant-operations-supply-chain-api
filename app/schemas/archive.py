from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import AuditType
from app.schemas.audit import InventoryAuditLineRead
from app.schemas.stock_movement import StoreTransferRead, WasteLogRead


class WasteBatchRead(BaseModel):
    """One waste booking (e.g. an end-of-day submission) with all its lines."""

    batch_id: str
    created_at: datetime
    lines: list[WasteLogRead]


class TransferBatchRead(BaseModel):
    """One transfer list with another store."""

    batch_id: str
    created_at: datetime
    target_store_name: str
    lines: list[StoreTransferRead]


class AuditBatchRead(BaseModel):
    """One physical count. Each line keeps the system quantity it replaced (`expected_quantity`)."""

    model_config = ConfigDict(from_attributes=True)

    batch_id: int = Field(validation_alias="id")
    audit_type: AuditType
    created_at: datetime
    notes: str | None
    lines: list[InventoryAuditLineRead]
