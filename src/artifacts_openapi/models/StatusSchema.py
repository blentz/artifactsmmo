from typing import *

from pydantic import BaseModel, Field

from .AnnouncementSchema import AnnouncementSchema


class StatusSchema(BaseModel):
    """
    StatusSchema model

    """

    status: str = Field(alias="status")

    version: str = Field(alias="version")

    characters_online: Optional[int] = Field(alias="characters_online", default=None)

    announcements: Optional[List[Optional[AnnouncementSchema]]] = Field(alias="announcements", default=None)

    last_wipe: str = Field(alias="last_wipe")

    next_wipe: str = Field(alias="next_wipe")
