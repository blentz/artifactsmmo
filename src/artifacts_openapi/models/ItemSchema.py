from typing import *

from pydantic import BaseModel, Field

from .CraftSchema import CraftSchema
from .ItemEffectSchema import ItemEffectSchema


class ItemSchema(BaseModel):
    """
    ItemSchema model

    """

    name: str = Field(alias="name")

    code: str = Field(alias="code")

    level: int = Field(alias="level")

    type: str = Field(alias="type")

    subtype: str = Field(alias="subtype")

    description: str = Field(alias="description")

    effects: Optional[List[Optional[ItemEffectSchema]]] = Field(
        alias="effects", default=None
    )

    craft: Optional[Union[CraftSchema, None]] = Field(alias="craft", default=None)
