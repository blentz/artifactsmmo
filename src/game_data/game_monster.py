"""
Game Monster Model

This module defines the GameMonster Pydantic model for internal representation
of game monsters throughout the AI player system.
"""

from typing import Any
from pydantic import BaseModel, Field


class GameMonster(BaseModel):
    """Internal Pydantic model for game monsters"""
    code: str = Field(description="Unique monster identifier")
    name: str = Field(description="Monster display name")
    level: int = Field(ge=1, description="Monster level")
    hp: int = Field(ge=1, description="Monster health points")
    attack_fire: int = Field(ge=0, description="Fire attack damage")
    attack_earth: int = Field(ge=0, description="Earth attack damage") 
    attack_water: int = Field(ge=0, description="Water attack damage")
    attack_air: int = Field(ge=0, description="Air attack damage")
    res_fire: int = Field(ge=0, description="Fire resistance")
    res_earth: int = Field(ge=0, description="Earth resistance")
    res_water: int = Field(ge=0, description="Water resistance")
    res_air: int = Field(ge=0, description="Air resistance")
    min_gold: int = Field(ge=0, description="Minimum gold dropped")
    max_gold: int = Field(ge=0, description="Maximum gold dropped")
    drops: list[dict[str, Any]] = Field(default_factory=list, description="Item drops")

    @classmethod
    def from_api_monster(cls, api_monster: Any) -> 'GameMonster':
        """Transform API MonsterSchema to internal GameMonster model"""
        return cls(
            code=api_monster.code,
            name=api_monster.name,
            level=api_monster.level,
            hp=api_monster.hp,
            attack_fire=api_monster.attack_fire,
            attack_earth=api_monster.attack_earth,
            attack_water=api_monster.attack_water,
            attack_air=api_monster.attack_air,
            res_fire=api_monster.res_fire,
            res_earth=api_monster.res_earth,
            res_water=api_monster.res_water,
            res_air=api_monster.res_air,
            min_gold=api_monster.min_gold,
            max_gold=api_monster.max_gold,
            drops=[drop.to_dict() if hasattr(drop, 'to_dict') else drop for drop in (api_monster.drops or [])]
        )