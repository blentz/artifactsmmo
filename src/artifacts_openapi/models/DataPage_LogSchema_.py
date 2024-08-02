from typing import *

from pydantic import BaseModel, Field

from .LogSchema import LogSchema


class DataPage_LogSchema_(BaseModel):
    """
    DataPage[LogSchema] model

    """

    data: List[LogSchema] = Field(alias="data")

    total: Union[int, None] = Field(alias="total")

    page: Union[int, None] = Field(alias="page")

    size: Union[int, None] = Field(alias="size")

    pages: Optional[Union[int, None]] = Field(alias="pages", default=None)
