from typing import *

from pydantic import BaseModel, Field

from .DropRateSchema import DropRateSchema


class ResourceSchema(BaseModel):
    """
    ResourceSchema model

    """

    name: str = Field(alias="name")

    code: str = Field(alias="code")

    skill: str = Field(alias="skill")

    level: int = Field(alias="level")

    drops: List[DropRateSchema] = Field(alias="drops")
