from typing import *

from pydantic import BaseModel, Field

from .CharacterSchema import CharacterSchema


class MyCharactersListSchema(BaseModel):
    """
    MyCharactersListSchema model

    """

    data: List[CharacterSchema] = Field(alias="data")
