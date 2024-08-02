from typing import *

from pydantic import BaseModel, Field

from .DropRateSchema import DropRateSchema


class MonsterSchema(BaseModel):
    """
    MonsterSchema model

    """

    name: str = Field(alias="name")

    code: str = Field(alias="code")

    level: int = Field(alias="level")

    hp: int = Field(alias="hp")

    attack_fire: int = Field(alias="attack_fire")

    attack_earth: int = Field(alias="attack_earth")

    attack_water: int = Field(alias="attack_water")

    attack_air: int = Field(alias="attack_air")

    res_fire: int = Field(alias="res_fire")

    res_earth: int = Field(alias="res_earth")

    res_water: int = Field(alias="res_water")

    res_air: int = Field(alias="res_air")

    min_gold: int = Field(alias="min_gold")

    max_gold: int = Field(alias="max_gold")

    drops: List[DropRateSchema] = Field(alias="drops")
