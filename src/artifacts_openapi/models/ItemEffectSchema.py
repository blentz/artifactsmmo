from typing import *

from pydantic import BaseModel, Field


class ItemEffectSchema(BaseModel):
    """
    ItemEffectSchema model

    """

    name: str = Field(alias="name")

    value: int = Field(alias="value")
