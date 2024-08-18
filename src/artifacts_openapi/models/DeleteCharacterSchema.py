from typing import *

from pydantic import BaseModel, Field


class DeleteCharacterSchema(BaseModel):
    """
    DeleteCharacterSchema model

    """

    name: str = Field(alias="name")
