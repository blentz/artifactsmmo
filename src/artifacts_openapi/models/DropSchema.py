from typing import *

from pydantic import BaseModel, Field


class DropSchema(BaseModel):
    """
    DropSchema model

    """

    code: str = Field(alias="code")

    quantity: int = Field(alias="quantity")
