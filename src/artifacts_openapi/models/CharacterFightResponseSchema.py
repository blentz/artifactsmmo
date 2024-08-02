from typing import *

from pydantic import BaseModel, Field

from .CharacterFightDataSchema import CharacterFightDataSchema


class CharacterFightResponseSchema(BaseModel):
    """
    CharacterFightResponseSchema model

    """

    data: CharacterFightDataSchema = Field(alias="data")
