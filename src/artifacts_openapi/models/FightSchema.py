from typing import *

from pydantic import BaseModel, Field

from .BlockedHitsSchema import BlockedHitsSchema
from .DropSchema import DropSchema


class FightSchema(BaseModel):
    """
    FightSchema model

    """

    xp: int = Field(alias="xp")

    gold: int = Field(alias="gold")

    drops: List[DropSchema] = Field(alias="drops")

    turns: int = Field(alias="turns")

    monster_blocked_hits: BlockedHitsSchema = Field(alias="monster_blocked_hits")

    player_blocked_hits: BlockedHitsSchema = Field(alias="player_blocked_hits")

    logs: List[str] = Field(alias="logs")

    result: str = Field(alias="result")
