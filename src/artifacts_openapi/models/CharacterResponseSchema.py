from typing import *

from pydantic import BaseModel, Field

from .CharacterSchema import CharacterSchema


class CharacterResponseSchema(BaseModel):
    """
    CharacterResponseSchema model

    """

    data: CharacterSchema = Field(alias="data")
