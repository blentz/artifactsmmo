from typing import *

from pydantic import BaseModel, Field

from .CharacterSchema import CharacterSchema
from .CooldownSchema import CooldownSchema
from .TaskRewardSchema import TaskRewardSchema


class TaskRewardDataSchema(BaseModel):
    """
    TaskRewardDataSchema model

    """

    cooldown: CooldownSchema = Field(alias="cooldown")

    reward: TaskRewardSchema = Field(alias="reward")

    character: CharacterSchema = Field(alias="character")
