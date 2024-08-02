from typing import *

from pydantic import BaseModel, Field

from .MonsterSchema import MonsterSchema


class DataPage_MonsterSchema_(BaseModel):
    """
    DataPage[MonsterSchema] model

    """

    data: List[MonsterSchema] = Field(alias="data")

    total: Union[int, None] = Field(alias="total")

    page: Union[int, None] = Field(alias="page")

    size: Union[int, None] = Field(alias="size")

    pages: Optional[Union[int, None]] = Field(alias="pages", default=None)
