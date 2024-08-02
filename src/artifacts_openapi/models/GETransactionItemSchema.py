from typing import *

from pydantic import BaseModel, Field


class GETransactionItemSchema(BaseModel):
    """
    GETransactionItemSchema model

    """

    code: str = Field(alias="code")

    quantity: int = Field(alias="quantity")

    price: int = Field(alias="price")
