from typing import *

from pydantic import BaseModel, Field

from .GEItemSchema import GEItemSchema
from .ItemSchema import ItemSchema


class SingleItemSchema(BaseModel):
    """
    SingleItemSchema model

    """

    item: ItemSchema = Field(alias="item")

    ge: Optional[Union[GEItemSchema, None]] = Field(alias="ge", default=None)
