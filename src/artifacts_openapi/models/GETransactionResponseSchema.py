from typing import *

from pydantic import BaseModel, Field

from .GETransactionListSchema import GETransactionListSchema


class GETransactionResponseSchema(BaseModel):
    """
    GETransactionResponseSchema model

    """

    data: GETransactionListSchema = Field(alias="data")
