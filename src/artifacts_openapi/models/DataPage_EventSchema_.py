from typing import *

from pydantic import BaseModel, Field

from .EventSchema import EventSchema


class DataPage_EventSchema_(BaseModel):
    """
    DataPage[EventSchema] model

    """

    data: List[EventSchema] = Field(alias="data")

    total: Union[int, None] = Field(alias="total")

    page: Union[int, None] = Field(alias="page")

    size: Union[int, None] = Field(alias="size")

    pages: Optional[Union[int, None]] = Field(alias="pages", default=None)
