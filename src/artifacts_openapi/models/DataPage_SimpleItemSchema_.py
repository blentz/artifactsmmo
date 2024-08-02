from typing import *

from pydantic import BaseModel, Field

from .SimpleItemSchema import SimpleItemSchema


class DataPage_SimpleItemSchema_(BaseModel):
    """
    DataPage[SimpleItemSchema] model

    """

    data: List[SimpleItemSchema] = Field(alias="data")

    total: Union[int, None] = Field(alias="total")

    page: Union[int, None] = Field(alias="page")

    size: Union[int, None] = Field(alias="size")

    pages: Optional[Union[int, None]] = Field(alias="pages", default=None)
