from typing import *

from pydantic import BaseModel, Field

from .SingleItemSchema import SingleItemSchema


class ItemResponseSchema(BaseModel):
    """
    ItemResponseSchema model

    """

    data: SingleItemSchema = Field(alias="data")
