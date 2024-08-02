from typing import *

from pydantic import BaseModel, Field


class TaskSchema(BaseModel):
    """
    TaskSchema model

    """

    code: str = Field(alias="code")

    type: str = Field(alias="type")

    total: int = Field(alias="total")
