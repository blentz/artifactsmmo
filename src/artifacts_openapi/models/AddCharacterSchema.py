from typing import *

from pydantic import BaseModel, Field


class AddCharacterSchema(BaseModel):
    """
    AddCharacterSchema model

    """

    name: str = Field(alias="name")

    skin: str = Field(alias="skin")
