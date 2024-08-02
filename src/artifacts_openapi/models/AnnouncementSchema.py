from typing import *

from pydantic import BaseModel, Field


class AnnouncementSchema(BaseModel):
    """
    AnnouncementSchema model

    """

    message: str = Field(alias="message")

    created_at: Optional[str] = Field(alias="created_at", default=None)
