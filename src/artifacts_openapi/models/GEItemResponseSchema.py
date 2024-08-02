from typing import *

from pydantic import BaseModel, Field

from .GEItemSchema import GEItemSchema


class GEItemResponseSchema(BaseModel):
    """
    GEItemResponseSchema model

    """

    data: GEItemSchema = Field(alias="data")
