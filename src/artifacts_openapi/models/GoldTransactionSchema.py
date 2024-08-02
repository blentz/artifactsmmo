from typing import *

from pydantic import BaseModel, Field

from .CharacterSchema import CharacterSchema
from .CooldownSchema import CooldownSchema
from .GoldSchema import GoldSchema


class GoldTransactionSchema(BaseModel):
    """
    GoldTransactionSchema model

    """

    cooldown: CooldownSchema = Field(alias="cooldown")

    bank: GoldSchema = Field(alias="bank")

    character: CharacterSchema = Field(alias="character")
