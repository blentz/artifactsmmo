from typing import *

from pydantic import BaseModel, Field

from .MapSchema import MapSchema


class ActiveEventSchema(BaseModel):
    """
    ActiveEventSchema model

    """

    name: str = Field(alias="name")

    map: MapSchema = Field(alias="map")

    previous_skin: str = Field(alias="previous_skin")

    duration: int = Field(alias="duration")

    expiration: str = Field(alias="expiration")

    created_at: str = Field(alias="created_at")
