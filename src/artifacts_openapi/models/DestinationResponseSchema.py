from typing import *

from pydantic import BaseModel, Field


class DestinationResponseSchema(BaseModel):
    """
    DestinationResponseSchema model

    """

    name: str = Field(alias="name")

    x: int = Field(alias="x")

    y: int = Field(alias="y")

    content: Any = Field(alias="content")
