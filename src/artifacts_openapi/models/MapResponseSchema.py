from typing import *

from pydantic import BaseModel, Field

from .MapSchema import MapSchema


class MapResponseSchema(BaseModel):
    """
    MapResponseSchema model

    """

    data: MapSchema = Field(alias="data")
