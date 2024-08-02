from typing import *

from pydantic import BaseModel, Field

from .CharacterSchema import CharacterSchema
from .CooldownSchema import CooldownSchema
from .RecyclingItemsSchema import RecyclingItemsSchema


class RecyclingDataSchema(BaseModel):
    """
    RecyclingDataSchema model

    """

    cooldown: CooldownSchema = Field(alias="cooldown")

    details: RecyclingItemsSchema = Field(alias="details")

    character: CharacterSchema = Field(alias="character")
