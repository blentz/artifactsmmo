from typing import *

from pydantic import BaseModel, Field

from .MapSchema import MapSchema


class DataPage_MapSchema_(BaseModel):
    """
    DataPage[MapSchema] model

    """

    data: List[MapSchema] = Field(alias="data")

    total: Union[int, None] = Field(alias="total")

    page: Union[int, None] = Field(alias="page")

    size: Union[int, None] = Field(alias="size")

    pages: Optional[Union[int, None]] = Field(alias="pages", default=None)
