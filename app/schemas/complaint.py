from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import ComplaintStatus


class ComplaintCreate(BaseModel):
    order_id: int
    item_id: int
    # In the item's stock unit (kg, L, pcs).
    quantity_difference: float = Field(description="Negative for missing/damaged goods, positive for extra goods")
    notes: str = Field(min_length=1, max_length=500, examples=["Squished buns due to bad pallets"])


class ComplaintRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    item_id: int
    item_name: str
    unit: str
    quantity_difference: float
    notes: str
    status: ComplaintStatus
    created_at: datetime
    resolved_at: datetime | None
