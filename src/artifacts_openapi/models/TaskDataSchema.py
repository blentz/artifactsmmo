from typing import *

from pydantic import BaseModel, Field

from .CharacterSchema import CharacterSchema
from .CooldownSchema import CooldownSchema
from .TaskSchema import TaskSchema


class TaskDataSchema(BaseModel):
    """
    TaskDataSchema model

    """

    cooldown: CooldownSchema = Field(alias="cooldown")

    task: TaskSchema = Field(alias="task")

    character: CharacterSchema = Field(alias="character")
