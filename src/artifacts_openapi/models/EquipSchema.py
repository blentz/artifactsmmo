from typing import *

from pydantic import BaseModel, Field


class EquipSchema(BaseModel):
    """
    EquipSchema model

    """

    code: str = Field(alias="code")

    slot: str = Field(alias="slot")
