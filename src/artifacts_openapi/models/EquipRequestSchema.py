from typing import *

from pydantic import BaseModel, Field

from .CharacterSchema import CharacterSchema
from .CooldownSchema import CooldownSchema
from .ItemSchema import ItemSchema


class EquipRequestSchema(BaseModel):
    """
    EquipRequestSchema model

    """

    cooldown: CooldownSchema = Field(alias="cooldown")

    slot: str = Field(alias="slot")

    item: ItemSchema = Field(alias="item")

    character: CharacterSchema = Field(alias="character")
