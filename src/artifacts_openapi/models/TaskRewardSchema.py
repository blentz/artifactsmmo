from typing import *

from pydantic import BaseModel, Field


class TaskRewardSchema(BaseModel):
    """
    TaskRewardSchema model

    """

    code: str = Field(alias="code")

    quantity: int = Field(alias="quantity")
