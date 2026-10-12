from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import seed
from app.database import Base
from app.models import Employee, EmployeeRole, InventoryItem, MenuItem


def _count(db, *where):
    return db.scalar(select(func.count()).select_from(InventoryItem).where(*where))


def test_seed_inserts_expected_data_and_is_idempotent():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        first = seed.seed(db)
        db.commit()
        assert (first.employees_added, first.items_added) == (6, 28)
        assert (first.menu_items_added, first.packaging_set) == (len(seed.MENU_ITEMS), 0)  # new items aren't counted

        roles = sorted(db.scalars(select(Employee.role)))
        assert roles == [EmployeeRole.crew] * 4 + [EmployeeRole.shift_manager] * 2  # 4 Mitarbeiter, 2 Schichtführer
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
        assert second == seed.SeedResult(0, 0)
        assert db.scalar(select(func.count()).select_from(MenuItem)) == len(seed.MENU_ITEMS)
        assert db.scalar(select(func.count()).select_from(Employee)) == 6
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


def test_seed_packaging_and_recipes():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        seed.seed(db)
        db.commit()

        patties = db.scalar(select(InventoryItem).where(InventoryItem.name == "Whopper Patties"))
        assert (patties.units_per_carton, patties.units_per_subpackage) == (48, 12)
        fries = db.scalar(select(InventoryItem).where(InventoryItem.name == "French Fries"))
        assert (fries.units_per_carton, fries.units_per_subpackage) == (None, None)  # loose kg goods
        # A carton is one supplier pack, and divides evenly into bags.
        for name, (per_carton, per_sub) in seed.PACKAGING.items():
            item = db.scalar(select(InventoryItem).where(InventoryItem.name == name))
            assert item.pack_size == per_carton and per_carton % per_sub == 0, name

        cheeseburger = db.scalar(select(MenuItem).where(MenuItem.name == "Cheeseburger"))
        assert sorted((i.item_name, i.quantity_needed) for i in cheeseburger.ingredients) == [
            ("Cheese Slices", 1), ("Hamburger Patties", 1), ("Regular Buns", 1),
        ]
        whopper = db.scalar(select(MenuItem).where(MenuItem.name == "Whopper"))
        assert sorted((i.item_name, i.quantity_needed) for i in whopper.ingredients) == [
            ("Sesame Buns", 1), ("Whopper Patties", 1),
        ]


def test_seed_fills_packaging_only_where_unset():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        db.add(InventoryItem(name="Sesame Buns", unit="pcs", quantity=10))  # no packaging yet
        db.add(InventoryItem(name="Regular Buns", unit="pcs", units_per_carton=40, units_per_subpackage=10))
        db.commit()

        assert seed.seed(db).packaging_set == 1
        db.commit()
        buns = db.scalar(select(InventoryItem).where(InventoryItem.name == "Regular Buns"))
        assert (buns.units_per_carton, buns.units_per_subpackage) == (40, 10)  # a manager's choice is kept
        assert seed.seed(db).packaging_set == 0
