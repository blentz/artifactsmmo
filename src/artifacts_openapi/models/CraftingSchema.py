from typing import *

from pydantic import BaseModel, Field


class CraftingSchema(BaseModel):
    """
    CraftingSchema model

    """

    code: str = Field(alias="code")

    quantity: Optional[int] = Field(alias="quantity", default=None)
