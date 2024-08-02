from typing import *

from pydantic import BaseModel, Field

from .CharacterSchema import CharacterSchema
from .CooldownSchema import CooldownSchema
from .SkillInfoSchema import SkillInfoSchema


class SkillDataSchema(BaseModel):
    """
    SkillDataSchema model

    """

    cooldown: CooldownSchema = Field(alias="cooldown")

    details: SkillInfoSchema = Field(alias="details")

    character: CharacterSchema = Field(alias="character")
