from typing import *

from pydantic import BaseModel, Field

from .GEItemSchema import GEItemSchema


class DataPage_GEItemSchema_(BaseModel):
    """
    DataPage[GEItemSchema] model

    """

    data: List[GEItemSchema] = Field(alias="data")

    total: Union[int, None] = Field(alias="total")

    page: Union[int, None] = Field(alias="page")

    size: Union[int, None] = Field(alias="size")

    pages: Optional[Union[int, None]] = Field(alias="pages", default=None)
