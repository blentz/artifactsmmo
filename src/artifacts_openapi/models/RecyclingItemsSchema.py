from typing import *

from pydantic import BaseModel, Field

from .DropSchema import DropSchema


class RecyclingItemsSchema(BaseModel):
    """
    RecyclingItemsSchema model

    """

    items: List[DropSchema] = Field(alias="items")
