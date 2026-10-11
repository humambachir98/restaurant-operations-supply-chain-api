from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import seed
from app.database import Base
from app.models import Employee, EmployeeRole, InventoryItem


def _count(db, *where):
    return db.scalar(select(func.count()).select_from(InventoryItem).where(*where))


def test_seed_inserts_expected_data_and_is_idempotent():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        first = seed.seed(db)
        db.commit()
        assert (first.employees_added, first.items_added) == (3, 28)

        roles = sorted(db.scalars(select(Employee.role)))
        assert roles == [EmployeeRole.crew, EmployeeRole.crew, EmployeeRole.shift_manager]
        fries_pack = db.scalar(select(InventoryItem.pack_size).where(InventoryItem.name == "French Fries"))
        assert fries_pack == 15
        assert _count(db, InventoryItem.pack_size <= 0) == 0
        assert _count(db, InventoryItem.is_daily_tracked.is_(True)) == 18
        assert _count(db, InventoryItem.is_daily_tracked.is_(False)) == 10

        # A live stock change must survive a re-run.
        fries = db.scalar(select(InventoryItem).where(InventoryItem.name == "French Fries"))
        fries.quantity = -3
        db.commit()

        second = seed.seed(db)
        db.commit()
        assert (second.employees_added, second.items_added) == (0, 0)
        assert db.scalar(select(func.count()).select_from(Employee)) == 3
        assert _count(db) == 28
        db.refresh(fries)
        assert fries.quantity == -3


def test_seed_fills_in_only_missing_rows():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        db.add(InventoryItem(name="Napkins", unit="pcs", quantity=42))
        db.commit()

        result = seed.seed(db)
        db.commit()
        assert result.items_added == 27
        assert db.scalar(select(InventoryItem.quantity).where(InventoryItem.name == "Napkins")) == 42


def test_seed_sets_pack_size_only_where_still_default():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        # Existed before pack sizes: default 1.0, live stock and a custom reorder level.
        db.add(InventoryItem(name="French Fries", unit="kg", quantity=7, reorder_level=99))
        # Pack size already chosen by a manager: keep it.
        db.add(InventoryItem(name="Lettuce", unit="kg", quantity=3, pack_size=4))
        db.commit()

        result = seed.seed(db)
        db.commit()
        assert result.pack_sizes_set == 1
        fries = db.scalar(select(InventoryItem).where(InventoryItem.name == "French Fries"))
        assert (fries.pack_size, fries.quantity, fries.reorder_level) == (15, 7, 99)
        assert db.scalar(select(InventoryItem.pack_size).where(InventoryItem.name == "Lettuce")) == 4

        assert seed.seed(db).pack_sizes_set == 0  # idempotent
