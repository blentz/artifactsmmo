from typing import *

from pydantic import BaseModel, Field

from .CharacterSchema import CharacterSchema
from .CooldownSchema import CooldownSchema
from .SimpleItemSchema import SimpleItemSchema


class DeleteItemSchema(BaseModel):
    """
    DeleteItemSchema model

    """

    cooldown: CooldownSchema = Field(alias="cooldown")

    item: SimpleItemSchema = Field(alias="item")

    character: CharacterSchema = Field(alias="character")
