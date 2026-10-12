from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.common import ensure_unique

MenuItemName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class RecipeIngredientCreate(BaseModel):
    item_id: int
    quantity_needed: float = Field(gt=0, description="Per menu item, in the inventory item's stock unit")


class MenuItemCreate(BaseModel):
    name: MenuItemName = Field(examples=["Whopper"])
    ingredients: list[RecipeIngredientCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def check_unique_items(self):
        ensure_unique((i.item_id for i in self.ingredients), "item_id")
        return self


class RecipeIngredientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: int = Field(validation_alias="inventory_item_id")
    item_name: str
    unit: str
    quantity_needed: float


class MenuItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    ingredients: list[RecipeIngredientRead]
