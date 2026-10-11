# Restaurant Shift & Inventory Management API

FastAPI + SQLite backend for managing staff, shifts, and inventory.

## Structure

```
app/
  main.py          # FastAPI app, router registration, migrations on startup
  config.py        # Settings (reads .env)
  database/        # Engine, session, Base, get_db, Berlin-aware DateTime type, migration helper
  models/          # SQLAlchemy ORM models (Employee, Shift, InventoryItem, InventoryAudit, PurchaseOrder)
  schemas/         # Pydantic request/response models
  routers/         # API endpoints per resource
  utils/           # Berlin clock helpers, delivery-day calculation, restock/pack-size maths
alembic/           # Database migrations (alembic/versions/)
tests/             # pytest suite (in-memory SQLite)
```

## Inventory workflow

- **Stock can go negative.** POS mis-rings and unrecorded waste are corrected by the next count.
- **Audits:** `POST /inventory/audit` with `audit_type` `daily` or `weekly`. Daily audits may only
  contain Key Items (`is_daily_tracked`, see `GET /inventory/daily-items`); anything else is a 400. Each counted item's stock is set to the physical count and the variance
  (`counted - expected`) is logged. History: `GET /inventory/audits`.
- **Pack sizes:** each item has a `pack_size` (units per supplier pack, default `1.0`; e.g. French
  Fries come in 15 kg boxes, so `pack_size=15`). Stock, reorder levels and audits are always in the
  item's `unit`; purchase orders are always in whole packs.
- **Purchase orders (Bestellung):** `POST /purchase-orders/` with
  `{"items": [{"item_id": 8, "packs": 5}]}` (whole packs, not units). Each line stores the item's
  `pack_size` at order time and reports `quantity = packs * pack_size` in units, so changing an item's
  pack size later doesn't change what an open order delivers. The order gets status `pending` and the
  expected delivery date. Deliveries are Tuesday, Thursday and Saturday; an order makes a delivery only if
  placed before 14:00 the day before (e.g. Monday 15:00 misses Tuesday and arrives Thursday).
  `POST /purchase-orders/{id}/receive` marks it `received` and adds all quantities to stock in one
  transaction; receiving twice returns 400.
- **Auto-suggest:** `POST /purchase-orders/auto-suggest` drafts an order for every low-stock item
  (saves nothing). Per item: `needed = 2 * reorder_level - quantity - on_order` (units still
  arriving in pending orders), then rounded **up** to whole packs. Example: Fries at -4.5 kg with a
  reorder level of 30 kg need 64.5 kg; in 15 kg boxes that's `packs: 5` (`quantity: 75`). Items whose
  need is fully covered by pending orders are left out. Submit the draft's `items` as-is to
  `POST /purchase-orders/` (display fields are ignored).

## Staff & shifts

- **Roles:** `role` is `shift_manager` or `crew`; anything else is a 422.
- **Shift rules** (create and update):
  - `end_time` must be strictly after `start_time` (422).
  - A shift may last at most **10 hours** (German Working Hours Act, ArbZG § 3) (422). Duration is
    real elapsed time in Europe/Berlin, so a 22:00-08:00 night shift across the October DST change
    counts as 11 h and is rejected.
  - An employee can't have overlapping shifts: creating, moving or reassigning a shift so that it
    overlaps another shift of the same employee returns **400** naming the clashing shift.
    Back-to-back shifts (one ends exactly when the next starts) are fine.

## Time zone

All business times are **Europe/Berlin**, whatever the server's clock is set to. Datetimes are
stored as UTC and returned with their Berlin offset (e.g. `2026-10-07T09:00:00+02:00`). Input
without an offset is taken as Berlin local time; input with one (e.g. `Z`) is converted.

## Database migrations (Alembic)

The app applies pending migrations on startup (`MIGRATE_ON_STARTUP`). After changing a model:

```bash
alembic revision --autogenerate -m "describe the change"   # review the generated file!
alembic upgrade head                                       # or just restart the app
```

Autogenerate can't migrate data: when a change affects existing rows (e.g. a new NOT NULL column),
edit the script to backfill them, as `ac9056a13672_pack_sizes_and_employee_roles` does (existing
roles are mapped to `shift_manager`/`crew`; existing order lines keep the same unit quantity).
`alembic downgrade -1` rolls back one step. On SQLite, each upgrade runs in a single transaction,
so a failing migration leaves the database untouched. `tests/test_migrations.py` fails if models
and migrations drift apart.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
copy .env.example .env         # optional
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs for the interactive API docs.

### Sample data

```bash
python seed.py
```

Run from the project root. It applies migrations, then adds 3 employees (1 shift manager, 2 crew),
18 daily-tracked Key Items and 10 other inventory items, each with a realistic supplier pack size. It's safe to run again: rows that already
exist (matched by employee email / item name) are skipped and never overwritten, so live stock
levels, reorder levels and roles are kept. The one exception: an existing item whose `pack_size`
is still the default `1.0` (e.g. created before pack sizes existed) gets its seed pack size.

## Tests

```bash
pytest
```
