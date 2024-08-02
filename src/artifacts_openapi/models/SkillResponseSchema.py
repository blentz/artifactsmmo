from typing import *

from pydantic import BaseModel, Field

from .SkillDataSchema import SkillDataSchema


class SkillResponseSchema(BaseModel):
    """
    SkillResponseSchema model

    """

    data: SkillDataSchema = Field(alias="data")
