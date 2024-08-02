from typing import *

from pydantic import BaseModel, Field

from .DropSchema import DropSchema


class SkillInfoSchema(BaseModel):
    """
    SkillInfoSchema model

    """

    xp: int = Field(alias="xp")

    items: List[DropSchema] = Field(alias="items")
