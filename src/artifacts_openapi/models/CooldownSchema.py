from typing import *

from pydantic import BaseModel, Field


class CooldownSchema(BaseModel):
    """
    CooldownSchema model

    """

    total_seconds: int = Field(alias="total_seconds")

    remaining_seconds: int = Field(alias="remaining_seconds")

    started_at: str = Field(alias="started_at")

    expiration: str = Field(alias="expiration")

    reason: str = Field(alias="reason")
