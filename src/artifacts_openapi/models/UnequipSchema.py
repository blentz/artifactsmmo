from typing import *

from pydantic import BaseModel, Field


class UnequipSchema(BaseModel):
    """
    UnequipSchema model

    """

    slot: str = Field(alias="slot")
