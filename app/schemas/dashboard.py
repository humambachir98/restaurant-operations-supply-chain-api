from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.stock_movement import StoreTransferRead


class StockHealth(BaseModel):
    total_items: int
    ok: int
    low: int  # at or below reorder level (but not negative)
    negative: int


class WasteItemTotal(BaseModel):
    item_id: int
    item_name: str
    unit: str
    quantity: float
    entries: int


class WasteToday(BaseModel):
    date: date
    entries: int
    items: list[WasteItemTotal]  # largest quantity first


class DashboardSummary(BaseModel):
    generated_at: datetime
    stock_health: StockHealth
    waste_today: WasteToday
    recent_transfers: list[StoreTransferRead]
    pending_deliveries: int
    pending_complaints: int
