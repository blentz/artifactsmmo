from typing import *

from pydantic import BaseModel, Field

from .CharacterSchema import CharacterSchema
from .CooldownSchema import CooldownSchema
from .MapSchema import MapSchema


class CharacterMovementDataSchema(BaseModel):
    """
    CharacterMovementDataSchema model

    """

    cooldown: CooldownSchema = Field(alias="cooldown")

    destination: MapSchema = Field(alias="destination")

    character: CharacterSchema = Field(alias="character")
