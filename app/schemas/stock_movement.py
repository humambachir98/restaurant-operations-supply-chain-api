from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import AuditType, TransferDirection

# Trimmed before the length check, so whitespace-only text is rejected.
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
StoreName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class WasteLogCreate(BaseModel):
    item_id: int
    quantity: float = Field(gt=0, description="Amount thrown away, in the item's stock unit")
    audit_type: AuditType = AuditType.daily
    reason: Reason = Field(examples=["Fries held past 7 minutes"])


class WasteLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    item_name: str
    unit: str
    quantity: float
    audit_type: AuditType
    reason: str
    created_at: datetime


class StoreTransferCreate(BaseModel):
    item_id: int
    quantity: float = Field(gt=0, description="Amount moved, in the item's stock unit")
    direction: TransferDirection = Field(description="'in' adds to stock, 'out' deducts from it")
    target_store_name: StoreName = Field(examples=["Berlin Alexanderplatz"])


class StoreTransferRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    item_name: str
    unit: str
    quantity: float
    direction: TransferDirection
    stock_change: float  # +quantity for 'in', -quantity for 'out'
    target_store_name: str
    created_at: datetime
