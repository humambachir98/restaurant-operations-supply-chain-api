from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database.migrations import upgrade_to_head
from app.routers import (
    archive,
    complaints,
    dashboard,
    employees,
    inventory,
    menu_items,
    purchase_orders,
    shifts,
    transfers,
    waste,
)
from app.scheduler import catch_up_on_startup, create_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is owned by Alembic: bring the database up to the latest migration.
    if settings.migrate_on_startup:
        upgrade_to_head()

    scheduler = None
    if settings.auto_receive_enabled:
        catch_up_on_startup()
        scheduler = create_scheduler()
        scheduler.start()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(employees.router)
app.include_router(shifts.router)
app.include_router(inventory.router)
app.include_router(menu_items.router)
app.include_router(purchase_orders.router)
app.include_router(complaints.router)
app.include_router(waste.router)
app.include_router(transfers.router)
app.include_router(dashboard.router)
app.include_router(archive.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
