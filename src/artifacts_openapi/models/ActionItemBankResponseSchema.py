from typing import *

from pydantic import BaseModel, Field

from .BankItemSchema import BankItemSchema


class ActionItemBankResponseSchema(BaseModel):
    """
    ActionItemBankResponseSchema model

    """

    data: BankItemSchema = Field(alias="data")
