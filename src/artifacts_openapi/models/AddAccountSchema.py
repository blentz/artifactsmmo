from typing import *

from pydantic import BaseModel, Field


class AddAccountSchema(BaseModel):
    """
    AddAccountSchema model

    """

    username: str = Field(alias="username")

    password: str = Field(alias="password")

    email: str = Field(alias="email")
