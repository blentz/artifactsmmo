from typing import *

from pydantic import BaseModel, Field

from .GoldSchema import GoldSchema


class GoldBankResponseSchema(BaseModel):
    """
    GoldBankResponseSchema model

    """

    data: GoldSchema = Field(alias="data")
