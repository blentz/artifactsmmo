from typing import *

from pydantic import BaseModel, Field


class DropRateSchema(BaseModel):
    """
    DropRateSchema model

    """

    code: str = Field(alias="code")

    rate: int = Field(alias="rate")

    min_quantity: int = Field(alias="min_quantity")

    max_quantity: int = Field(alias="max_quantity")
