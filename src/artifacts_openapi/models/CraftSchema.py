from typing import *

from pydantic import BaseModel, Field

from .SimpleItemSchema import SimpleItemSchema


class CraftSchema(BaseModel):
    """
    CraftSchema model

    """

    skill: Optional[str] = Field(alias="skill", default=None)

    level: Optional[int] = Field(alias="level", default=None)

    items: Optional[List[Optional[SimpleItemSchema]]] = Field(
        alias="items", default=None
    )

    quantity: Optional[int] = Field(alias="quantity", default=None)
