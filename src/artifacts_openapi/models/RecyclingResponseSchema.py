from typing import *

from pydantic import BaseModel, Field

from .RecyclingDataSchema import RecyclingDataSchema


class RecyclingResponseSchema(BaseModel):
    """
    RecyclingResponseSchema model

    """

    data: RecyclingDataSchema = Field(alias="data")
