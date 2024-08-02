from typing import *

from pydantic import BaseModel, Field

from .StatusSchema import StatusSchema


class StatusResponseSchema(BaseModel):
    """
    StatusResponseSchema model

    """

    data: StatusSchema = Field(alias="data")
