from typing import *

from pydantic import BaseModel, Field

from .CharacterSchema import CharacterSchema
from .CooldownSchema import CooldownSchema
from .FightSchema import FightSchema


class CharacterFightDataSchema(BaseModel):
    """
    CharacterFightDataSchema model

    """

    cooldown: CooldownSchema = Field(alias="cooldown")

    fight: FightSchema = Field(alias="fight")

    character: CharacterSchema = Field(alias="character")
