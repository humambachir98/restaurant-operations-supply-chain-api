from pydantic import BaseModel, ConfigDict, Field


class InventoryItemBase(BaseModel):
    name: str
    unit: str
    # No lower bound: stock may legitimately go negative (POS mis-rings, unrecorded waste).
    quantity: float = 0
    reorder_level: float = Field(default=0, ge=0)
    pack_size: float = Field(default=1.0, gt=0)  # units per supplier pack
    is_daily_tracked: bool = False


class InventoryItemCreate(InventoryItemBase):
    pass


class InventoryItemUpdate(BaseModel):
    name: str | None = None
    unit: str | None = None
    quantity: float | None = None
    reorder_level: float | None = Field(default=None, ge=0)
    pack_size: float | None = Field(default=None, gt=0)
    is_daily_tracked: bool | None = None


class InventoryItemRead(InventoryItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
