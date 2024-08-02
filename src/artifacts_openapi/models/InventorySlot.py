from typing import *

from pydantic import BaseModel, Field


class InventorySlot(BaseModel):
    """
    InventorySlot model

    """

    slot: int = Field(alias="slot")

    code: str = Field(alias="code")

    quantity: int = Field(alias="quantity")
