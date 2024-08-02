from typing import *

from pydantic import BaseModel, Field


class ChangePassword(BaseModel):
    """
    ChangePassword model

    """

    password: str = Field(alias="password")
