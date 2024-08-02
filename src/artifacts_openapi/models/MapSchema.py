from typing import *

from pydantic import BaseModel, Field

from .MapContentSchema import MapContentSchema


class MapSchema(BaseModel):
    """
    MapSchema model

    """

    name: str = Field(alias="name")

    skin: str = Field(alias="skin")

    x: int = Field(alias="x")

    y: int = Field(alias="y")

    content: Union[MapContentSchema, None] = Field(alias="content")
