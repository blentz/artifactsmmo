from typing import *

from pydantic import BaseModel, Field


class BlockedHitsSchema(BaseModel):
    """
    BlockedHitsSchema model

    """

    fire: int = Field(alias="fire")

    earth: int = Field(alias="earth")

    water: int = Field(alias="water")

    air: int = Field(alias="air")

    total: int = Field(alias="total")
