from typing import *

from pydantic import BaseModel, Field


class ResponseSchema(BaseModel):
    """
    ResponseSchema model

    """

    message: str = Field(alias="message")
