from typing import *

from pydantic import BaseModel, Field

from .SimpleItemSchema import SimpleItemSchema


class CraftSchema(BaseModel):
    """
    CraftSchema model

    """

    skill: Optional[Union[str, None]] = Field(alias="skill", default=None)

    level: Optional[Union[int, None]] = Field(alias="level", default=None)

    items: Optional[List[Optional[SimpleItemSchema]]] = Field(alias="items", default=None)

    quantity: Optional[Union[int, None]] = Field(alias="quantity", default=None)
