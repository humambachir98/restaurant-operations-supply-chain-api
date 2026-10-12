from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.inventory import InventoryItem


class MenuItem(Base):
    """A product sold to guests (e.g. Whopper), built from inventory items by its recipe."""

    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)

    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="menu_item", cascade="all, delete-orphan", lazy="selectin"
    )


class RecipeIngredient(Base):
    """One line of a menu item's bill of materials: how much of an inventory item one unit uses."""

    __tablename__ = "recipe_ingredients"

    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), primary_key=True)
    inventory_item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"), primary_key=True, index=True)
    quantity_needed: Mapped[float]  # in the inventory item's stock unit, per menu item

    menu_item: Mapped[MenuItem] = relationship(back_populates="ingredients")
    item: Mapped["InventoryItem"] = relationship(lazy="joined")

    @property
    def item_name(self) -> str:
        return self.item.name

    @property
    def unit(self) -> str:
        return self.item.unit
