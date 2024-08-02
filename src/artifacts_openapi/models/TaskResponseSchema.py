from typing import *

from pydantic import BaseModel, Field

from .TaskDataSchema import TaskDataSchema


class TaskResponseSchema(BaseModel):
    """
    TaskResponseSchema model

    """

    data: TaskDataSchema = Field(alias="data")
