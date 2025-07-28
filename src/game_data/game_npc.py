"""
Game NPC Model

This module defines the GameNPC Pydantic model for internal representation
of game NPCs throughout the AI player system.
"""

from typing import Any
from pydantic import BaseModel, Field


class GameNPC(BaseModel):
    """Internal Pydantic model for game NPCs"""
    code: str = Field(description="Unique NPC identifier")
    name: str = Field(description="NPC display name")
    skin: str = Field(description="NPC visual appearance")
    level: int = Field(ge=1, description="NPC level")
    hp: int = Field(ge=1, description="NPC health points")
    attack_fire: int = Field(ge=0, description="Fire attack damage")
    attack_earth: int = Field(ge=0, description="Earth attack damage")
    attack_water: int = Field(ge=0, description="Water attack damage")
    attack_air: int = Field(ge=0, description="Air attack damage")
    res_fire: int = Field(ge=0, description="Fire resistance")
    res_earth: int = Field(ge=0, description="Earth resistance")
    res_water: int = Field(ge=0, description="Water resistance")
    res_air: int = Field(ge=0, description="Air resistance")
    min_gold: int = Field(ge=0, description="Minimum gold in transactions")
    max_gold: int = Field(ge=0, description="Maximum gold in transactions")
    drops: list[dict[str, Any]] = Field(default_factory=list, description="NPC drops/trades")

    @classmethod
    def from_api_npc(cls, api_npc: Any) -> 'GameNPC':
        """Transform API NPCSchema to internal GameNPC model"""
        return cls(
            code=api_npc.code,
            name=api_npc.name,
            skin=api_npc.skin,
            level=api_npc.level,
            hp=api_npc.hp,
            attack_fire=api_npc.attack_fire,
            attack_earth=api_npc.attack_earth,
            attack_water=api_npc.attack_water,
            attack_air=api_npc.attack_air,
            res_fire=api_npc.res_fire,
            res_earth=api_npc.res_earth,
            res_water=api_npc.res_water,
            res_air=api_npc.res_air,
            min_gold=api_npc.min_gold,
            max_gold=api_npc.max_gold,
            drops=[drop.to_dict() if hasattr(drop, 'to_dict') else drop for drop in (api_npc.drops or [])]
        )