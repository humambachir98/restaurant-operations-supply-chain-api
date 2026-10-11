from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import PurchaseOrderStatus
from app.schemas.common import ensure_unique_item_ids


class PurchaseOrderItemCreate(BaseModel):
    item_id: int
    packs: int = Field(gt=0)  # whole supplier packs; units = packs * the item's pack_size


class PurchaseOrderCreate(BaseModel):
    notes: str | None = None
    items: list[PurchaseOrderItemCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def check_unique_items(self):
        ensure_unique_item_ids(self.items)
        return self


class PurchaseOrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    packs: int
    pack_size: float  # as of when the order was placed
    quantity: float  # packs * pack_size, in stock units; added to stock on receipt


class PurchaseOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: PurchaseOrderStatus
    created_at: datetime
    expected_delivery_date: date
    received_at: datetime | None
    notes: str | None
    items: list[PurchaseOrderItemRead]


class SuggestedOrderItem(PurchaseOrderItemCreate):
    """A suggested line. `item_id` + `packs` are what gets submitted; the rest is for display."""

    name: str
    unit: str
    pack_size: float
    quantity: float  # packs * pack_size, in stock units
    needed: float  # raw shortfall in stock units, before rounding up to whole packs
    current_quantity: float
    reorder_level: float
    on_order: float  # stock units already in pending purchase orders


class PurchaseOrderSuggestion(BaseModel):
    """Draft order for review. Not saved: POST {"items": [...]} to /purchase-orders/ to submit."""

    generated_at: datetime
    expected_delivery_date: date  # if submitted now
    items: list[SuggestedOrderItem]
