from pydantic import BaseModel, ConfigDict, Field


class InventoryItemBase(BaseModel):
    name: str
    unit: str
    # No lower bound: stock may legitimately go negative (POS mis-rings, unrecorded waste).
    quantity: float = 0
    reorder_level: float = Field(default=0, ge=0)
    pack_size: float = Field(default=1.0, gt=0)  # units per supplier pack
    is_daily_tracked: bool = False
    # Pieces per carton and per bag inside it, for counting by hand. Empty if not applicable.
    units_per_carton: int | None = Field(default=None, gt=0)
    units_per_subpackage: int | None = Field(default=None, gt=0)


class InventoryItemCreate(InventoryItemBase):
    pass


class InventoryItemUpdate(BaseModel):
    name: str | None = None
    unit: str | None = None
    quantity: float | None = None
    reorder_level: float | None = Field(default=None, ge=0)
    pack_size: float | None = Field(default=None, gt=0)
    is_daily_tracked: bool | None = None
    units_per_carton: int | None = Field(default=None, gt=0)
    units_per_subpackage: int | None = Field(default=None, gt=0)


class InventoryItemRead(InventoryItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
