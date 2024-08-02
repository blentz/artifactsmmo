from typing import *

from pydantic import BaseModel, Field

from .DeleteItemSchema import DeleteItemSchema


class DeleteItemResponseSchema(BaseModel):
    """
    DeleteItemResponseSchema model

    """

    data: DeleteItemSchema = Field(alias="data")
