from typing import *

from pydantic import BaseModel, Field

from .ActiveEventSchema import ActiveEventSchema


class DataPage_ActiveEventSchema_(BaseModel):
    """
    DataPage[ActiveEventSchema] model

    """

    data: List[ActiveEventSchema] = Field(alias="data")

    total: Union[int, None] = Field(alias="total")

    page: Union[int, None] = Field(alias="page")

    size: Union[int, None] = Field(alias="size")

    pages: Optional[Union[int, None]] = Field(alias="pages", default=None)
