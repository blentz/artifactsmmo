from typing import *

from pydantic import BaseModel, Field

from .CharacterMovementDataSchema import CharacterMovementDataSchema


class CharacterMovementResponseSchema(BaseModel):
    """
    CharacterMovementResponseSchema model

    """

    data: CharacterMovementDataSchema = Field(alias="data")
