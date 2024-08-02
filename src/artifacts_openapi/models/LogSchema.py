from typing import *

from pydantic import BaseModel, Field


class LogSchema(BaseModel):
    """
    LogSchema model

    """

    character: str = Field(alias="character")

    account: str = Field(alias="account")

    type: str = Field(alias="type")

    description: str = Field(alias="description")

    content: Any = Field(alias="content")

    cooldown: int = Field(alias="cooldown")

    cooldown_expiration: str = Field(alias="cooldown_expiration")

    created_at: str = Field(alias="created_at")
