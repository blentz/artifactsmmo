from typing import *

from pydantic import BaseModel, Field


class DestinationSchema(BaseModel):
    """
    DestinationSchema model

    """

    x: int = Field(alias="x")

    y: int = Field(alias="y")
