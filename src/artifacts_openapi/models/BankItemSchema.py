from typing import *

from pydantic import BaseModel, Field

from .CharacterSchema import CharacterSchema
from .CooldownSchema import CooldownSchema
from .ItemSchema import ItemSchema
from .SimpleItemSchema import SimpleItemSchema


class BankItemSchema(BaseModel):
    """
    BankItemSchema model

    """

    cooldown: CooldownSchema = Field(alias="cooldown")

    item: ItemSchema = Field(alias="item")

    bank: List[SimpleItemSchema] = Field(alias="bank")

    character: CharacterSchema = Field(alias="character")
