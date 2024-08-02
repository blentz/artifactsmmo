from typing import *

from pydantic import BaseModel, Field

from .ItemSchema import ItemSchema


class DataPage_ItemSchema_(BaseModel):
    """
    DataPage[ItemSchema] model

    """

    data: List[ItemSchema] = Field(alias="data")

    total: Union[int, None] = Field(alias="total")

    page: Union[int, None] = Field(alias="page")

    size: Union[int, None] = Field(alias="size")

    pages: Optional[Union[int, None]] = Field(alias="pages", default=None)
