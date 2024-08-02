from typing import *

from pydantic import BaseModel, Field

from .CharacterSchema import CharacterSchema
from .CooldownSchema import CooldownSchema
from .GETransactionSchema import GETransactionSchema


class GETransactionListSchema(BaseModel):
    """
    GETransactionListSchema model

    """

    cooldown: CooldownSchema = Field(alias="cooldown")

    transaction: GETransactionSchema = Field(alias="transaction")

    character: CharacterSchema = Field(alias="character")
