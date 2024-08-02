from typing import *

from pydantic import BaseModel, Field

from .ResourceSchema import ResourceSchema


class DataPage_ResourceSchema_(BaseModel):
    """
    DataPage[ResourceSchema] model

    """

    data: List[ResourceSchema] = Field(alias="data")

    total: Union[int, None] = Field(alias="total")

    page: Union[int, None] = Field(alias="page")

    size: Union[int, None] = Field(alias="size")

    pages: Optional[Union[int, None]] = Field(alias="pages", default=None)
