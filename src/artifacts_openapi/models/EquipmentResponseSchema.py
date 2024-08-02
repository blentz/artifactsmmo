from typing import *

from pydantic import BaseModel, Field

from .EquipRequestSchema import EquipRequestSchema


class EquipmentResponseSchema(BaseModel):
    """
    EquipmentResponseSchema model

    """

    data: EquipRequestSchema = Field(alias="data")
