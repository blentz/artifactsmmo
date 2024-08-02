from typing import *

from pydantic import BaseModel, Field

from .TaskRewardDataSchema import TaskRewardDataSchema


class TaskRewardResponseSchema(BaseModel):
    """
    TaskRewardResponseSchema model

    """

    data: TaskRewardDataSchema = Field(alias="data")
