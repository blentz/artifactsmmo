from typing import *

from pydantic import BaseModel, Field


class RecyclingSchema(BaseModel):
    """
    RecyclingSchema model

    """

    code: str = Field(alias="code")

    quantity: Optional[int] = Field(alias="quantity", default=None)
