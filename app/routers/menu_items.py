from collections.abc import Iterable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MenuItem, RecipeIngredient
from app.routers.inventory import get_items_or_400
from app.schemas import MenuItemCreate, MenuItemRead

router = APIRouter(prefix="/menu-items", tags=["menu items"])


def get_menu_items_or_400(db: Session, menu_item_ids: Iterable[int]) -> dict[int, MenuItem]:
    """Load menu items (with their recipes) by id, failing with 400 if any id doesn't exist."""
    ids = set(menu_item_ids)
    menu_items = {m.id: m for m in db.scalars(select(MenuItem).where(MenuItem.id.in_(ids)))}
    missing = sorted(ids - menu_items.keys())
    if missing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown menu item id(s): {missing}")
    return menu_items


@router.get("/", response_model=list[MenuItemRead])
def list_menu_items(db: Session = Depends(get_db)):
    """Menu items with their recipes (bill of materials)."""
    return db.scalars(select(MenuItem).order_by(MenuItem.name)).all()


@router.post("/", response_model=MenuItemRead, status_code=status.HTTP_201_CREATED)
def create_menu_item(payload: MenuItemCreate, db: Session = Depends(get_db)):
    get_items_or_400(db, (i.item_id for i in payload.ingredients))
    menu_item = MenuItem(
        name=payload.name,
        ingredients=[
            RecipeIngredient(inventory_item_id=i.item_id, quantity_needed=i.quantity_needed)
            for i in payload.ingredients
        ],
    )
    db.add(menu_item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"A menu item named {payload.name!r} already exists")
    db.refresh(menu_item)
    return menu_item
