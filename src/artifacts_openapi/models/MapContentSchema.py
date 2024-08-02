from typing import *

from pydantic import BaseModel, Field


class MapContentSchema(BaseModel):
    """
    MapContentSchema model

    """

    type: str = Field(alias="type")

    code: str = Field(alias="code")
