"""Seed the database with realistic starter data for a fast-food restaurant.

Usage (from the project root, with the virtualenv active):

    python seed.py

Safe to run repeatedly: each employee (by email) and inventory item (by name) is only
inserted if it doesn't exist yet. Existing rows are never otherwise modified, so live stock
levels, reorder levels and roles are not reset. The one exception: an existing item whose
pack_size is still the default 1.0 (e.g. created before pack sizes existed) gets its seed
pack size.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.database.migrations import upgrade_to_head
from app.models import Employee, EmployeeRole, InventoryItem

EMPLOYEES = [
    {"name": "Sabine Krüger", "role": EmployeeRole.shift_manager, "email": "sabine.krueger@example.com"},
    {"name": "Jonas Weber", "role": EmployeeRole.crew, "email": "jonas.weber@example.com"},
    {"name": "Aylin Demir", "role": EmployeeRole.crew, "email": "aylin.demir@example.com"},
]

# (name, unit, starting quantity, reorder level, pack size = units per supplier pack)
KEY_ITEMS = [
    ("Whopper Patties", "pcs", 240, 120, 48),
    ("Hamburger Patties", "pcs", 400, 200, 96),
    ("Chicken Patties", "pcs", 160, 80, 48),
    ("Chicken Nuggets", "kg", 15, 8, 5),
    ("Sesame Buns", "pcs", 240, 120, 30),
    ("Regular Buns", "pcs", 400, 200, 48),
    ("Long Buns", "pcs", 150, 80, 24),
    ("French Fries", "kg", 120, 60, 15),
    ("Onion Rings", "kg", 20, 10, 5),
    ("Frying Oil", "L", 60, 30, 10),
    ("Lettuce", "kg", 12, 6, 2),
    ("Tomatoes", "kg", 10, 5, 5),
    ("Onions", "kg", 8, 4, 5),
    ("Pickles", "kg", 6, 3, 3),
    ("Cheese Slices", "pcs", 600, 300, 200),
    ("Bacon Strips", "pcs", 300, 150, 150),
    ("Soft-Serve Mix", "L", 40, 20, 10),
    ("Cola Syrup", "L", 60, 30, 20),
]

NON_KEY_ITEMS = [
    ("Ketchup Packets", "pcs", 2000, 500, 1000),
    ("Mayonnaise", "L", 10, 4, 5),
    ("BBQ Sauce Dips", "pcs", 800, 200, 200),
    ("Napkins", "pcs", 5000, 1500, 2500),
    ("Drink Cups 0.4 L", "pcs", 1500, 500, 500),
    ("Drink Lids", "pcs", 1500, 500, 500),
    ("Paper Straws", "pcs", 2000, 600, 1000),
    ("Burger Wrappers", "pcs", 3000, 1000, 1000),
    ("Takeaway Bags", "pcs", 1000, 300, 250),
    ("Cleaning Supplies (Degreaser)", "L", 20, 5, 5),
]


DEFAULT_PACK_SIZE = 1.0  # what the migration gave items that existed before pack sizes


@dataclass
class SeedResult:
    employees_added: int
    items_added: int
    pack_sizes_set: int = 0


def seed(db: Session) -> SeedResult:
    """Insert any seed rows that are missing and fill in unset pack sizes. The caller commits."""
    existing_emails = set(db.scalars(select(Employee.email)))
    new_employees = [Employee(**e) for e in EMPLOYEES if e["email"] not in existing_emails]

    existing = {item.name: item for item in db.scalars(select(InventoryItem))}
    pack_sizes_set = 0
    for name, *_, pack in KEY_ITEMS + NON_KEY_ITEMS:
        item = existing.get(name)
        if item is not None and item.pack_size == DEFAULT_PACK_SIZE and pack != DEFAULT_PACK_SIZE:
            item.pack_size = pack
            pack_sizes_set += 1

    new_items = [
        InventoryItem(
            name=name, unit=unit, quantity=qty, reorder_level=reorder, pack_size=pack, is_daily_tracked=daily
        )
        for rows, daily in ((KEY_ITEMS, True), (NON_KEY_ITEMS, False))
        for name, unit, qty, reorder, pack in rows
        if name not in existing
    ]

    db.add_all(new_employees + new_items)
    return SeedResult(
        employees_added=len(new_employees), items_added=len(new_items), pack_sizes_set=pack_sizes_set
    )


def main() -> None:
    upgrade_to_head()  # make sure the schema exists and is current
    with SessionLocal() as db, db.begin():
        result = seed(db)

    if result == SeedResult(0, 0, 0):
        print("Database already seeded; nothing to do.")
    else:
        print(
            f"Seeded {result.employees_added} employee(s) and {result.items_added} inventory item(s); "
            f"set the pack size on {result.pack_sizes_set} existing item(s)."
        )


if __name__ == "__main__":
    main()
