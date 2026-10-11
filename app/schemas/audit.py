from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import AuditType
from app.schemas.common import ensure_unique_item_ids


class AuditCount(BaseModel):
    item_id: int
    # A physical count can't be negative, even though the system balance can.
    counted_quantity: float = Field(ge=0)


class InventoryAuditCreate(BaseModel):
    audit_type: AuditType
    notes: str | None = None
    counts: list[AuditCount] = Field(min_length=1)

    @model_validator(mode="after")
    def check_unique_items(self):
        ensure_unique_item_ids(self.counts)
        return self


class InventoryAuditLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: int
    expected_quantity: float
    counted_quantity: float
    variance: float


class InventoryAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    audit_type: AuditType
    created_at: datetime
    notes: str | None
    lines: list[InventoryAuditLineRead]
