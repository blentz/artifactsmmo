from typing import *

from pydantic import BaseModel, Field


class GEItemSchema(BaseModel):
    """
    GEItemSchema model

    """

    code: str = Field(alias="code")

    stock: int = Field(alias="stock")

    sell_price: Optional[int] = Field(alias="sell_price", default=None)

    buy_price: Optional[int] = Field(alias="buy_price", default=None)
