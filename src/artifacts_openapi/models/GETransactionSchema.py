from typing import *

from pydantic import BaseModel, Field


class GETransactionSchema(BaseModel):
    """
    GETransactionSchema model

    """

    code: str = Field(alias="code")

    quantity: int = Field(alias="quantity")

    price: int = Field(alias="price")

    total_price: int = Field(alias="total_price")
