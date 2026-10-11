from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database.migrations import upgrade_to_head
from app.routers import employees, inventory, purchase_orders, shifts


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is owned by Alembic: bring the database up to the latest migration.
    if settings.migrate_on_startup:
        upgrade_to_head()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(employees.router)
app.include_router(shifts.router)
app.include_router(inventory.router)
app.include_router(purchase_orders.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
