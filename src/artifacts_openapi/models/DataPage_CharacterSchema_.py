from typing import *

from pydantic import BaseModel, Field

from .CharacterSchema import CharacterSchema


class DataPage_CharacterSchema_(BaseModel):
    """
    DataPage[CharacterSchema] model

    """

    data: List[CharacterSchema] = Field(alias="data")

    total: Union[int, None] = Field(alias="total")

    page: Union[int, None] = Field(alias="page")

    size: Union[int, None] = Field(alias="size")

    pages: Optional[Union[int, None]] = Field(alias="pages", default=None)
