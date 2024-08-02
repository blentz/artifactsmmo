from typing import *

from pydantic import BaseModel, Field


class DepositWithdrawGoldSchema(BaseModel):
    """
    DepositWithdrawGoldSchema model

    """

    quantity: int = Field(alias="quantity")
