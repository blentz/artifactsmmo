from typing import *

from pydantic import BaseModel, Field

from .ResourceSchema import ResourceSchema


class ResourceResponseSchema(BaseModel):
    """
    ResourceResponseSchema model

    """

    data: ResourceSchema = Field(alias="data")
