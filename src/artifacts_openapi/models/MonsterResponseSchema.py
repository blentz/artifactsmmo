from typing import *

from pydantic import BaseModel, Field

from .MonsterSchema import MonsterSchema


class MonsterResponseSchema(BaseModel):
    """
    MonsterResponseSchema model

    """

    data: MonsterSchema = Field(alias="data")
