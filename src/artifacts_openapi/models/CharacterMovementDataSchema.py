from typing import *

from pydantic import BaseModel, Field

from .CharacterSchema import CharacterSchema
from .CooldownSchema import CooldownSchema
from .DestinationResponseSchema import DestinationResponseSchema


class CharacterMovementDataSchema(BaseModel):
    """
    CharacterMovementDataSchema model

    """

    cooldown: CooldownSchema = Field(alias="cooldown")

    destination: DestinationResponseSchema = Field(alias="destination")

    character: CharacterSchema = Field(alias="character")
