from typing import *

from pydantic import BaseModel, Field


class TokenResponseSchema(BaseModel):
    """
    TokenResponseSchema model

    """

    token: str = Field(alias="token")
