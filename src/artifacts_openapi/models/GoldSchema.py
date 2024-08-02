from typing import *

from pydantic import BaseModel, Field


class GoldSchema(BaseModel):
    """
    GoldSchema model

    """

    quantity: int = Field(alias="quantity")
