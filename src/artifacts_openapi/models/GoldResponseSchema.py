from typing import *

from pydantic import BaseModel, Field

from .GoldTransactionSchema import GoldTransactionSchema


class GoldResponseSchema(BaseModel):
    """
    GoldResponseSchema model

    """

    data: GoldTransactionSchema = Field(alias="data")
