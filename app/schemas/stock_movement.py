from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.models import TransferDirection
from app.schemas.common import ensure_unique, ensure_unique_item_ids

# Trimmed before the length check, so whitespace-only text is rejected.
StoreName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]

MAX_BATCH = 500


class WasteLineCreate(BaseModel):
    """Either a raw inventory item, or a finished menu item that is broken down by its recipe."""

    item_id: int | None = None
    menu_item_id: int | None = None
    quantity: float = Field(
        description=(
            "Amount thrown away: in the item's stock unit, or the number of menu items. "
            "Negative to correct an earlier booking: it returns the amount to stock."
        )
    )
    reason: str | None = Field(default=None, max_length=500, examples=["Fries held past 7 minutes"])

    @field_validator("reason", mode="before")
    @classmethod
    def blank_reason_is_none(cls, value):
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("quantity")
    @classmethod
    def quantity_not_zero(cls, value: float) -> float:
        if value == 0:
            raise ValueError("Quantity must not be 0")
        return value

    @model_validator(mode="after")
    def check_exactly_one_target(self):
        if (self.item_id is None) == (self.menu_item_id is None):
            raise ValueError("Give exactly one of item_id or menu_item_id")
        return self


class WasteBatchCreate(BaseModel):
    """An end-of-day waste booking: one line per raw item and per menu item that had waste."""

    items: list[WasteLineCreate] = Field(min_length=1, max_length=MAX_BATCH)

    @model_validator(mode="after")
    def check_unique_items(self):
        ensure_unique((line.item_id for line in self.items if line.item_id is not None), "item_id")
        ensure_unique((line.menu_item_id for line in self.items if line.menu_item_id is not None), "menu_item_id")
        return self


class WasteLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    item_name: str
    unit: str
    quantity: float
    reason: str | None
    batch_id: str
    created_at: datetime


class TransferLineCreate(BaseModel):
    item_id: int
    quantity: float = Field(gt=0, description="Amount moved, in the item's stock unit")
    direction: TransferDirection = Field(description="'in' adds to stock, 'out' deducts from it")


class TransferBatchCreate(BaseModel):
    """A transfer list with one other store: each line goes in or out."""

    target_store_name: StoreName = Field(examples=["Berlin Alexanderplatz"])
    items: list[TransferLineCreate] = Field(min_length=1, max_length=MAX_BATCH)

    @model_validator(mode="after")
    def check_unique_items(self):
        ensure_unique_item_ids(self.items)
        return self


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
    batch_id: str
    created_at: datetime
