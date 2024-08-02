from typing import *

from pydantic import BaseModel, Field


class SimpleItemSchema(BaseModel):
    """
    SimpleItemSchema model

    """

    code: str = Field(alias="code")

    quantity: int = Field(alias="quantity")
