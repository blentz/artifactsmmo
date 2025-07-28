"""
Internal Game Data Models

This module defines internal Pydantic models that represent game data
throughout the system. These models enforce the architectural boundary
by providing type-safe internal representations of all game entities.

API client models must be transformed to these internal models at the
API boundary to maintain clean separation of concerns.
"""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class CooldownInfo(BaseModel):
    """Pydantic model for cooldown information"""
    character_name: str
    expiration: str  # datetime as string
    total_seconds: int = Field(ge=0)
    remaining_seconds: int = Field(ge=0)
    reason: str

    @property
    def is_ready(self) -> bool:
        """Check if cooldown has expired.

        Parameters:
            None (property operates on self)

        Return values:
            Boolean indicating whether the character cooldown has expired

        This property compares the current time with the cooldown expiration time
        to determine if the character is ready to perform actions, enabling
        cooldown-aware planning and execution.
        """
        try:
            expiration_time = datetime.fromisoformat(self.expiration.replace('Z', '+00:00'))
            return datetime.now(expiration_time.tzinfo) >= expiration_time
        except Exception:
            # If parsing fails, use remaining_seconds
            return self.remaining_seconds <= 0

    @property
    def time_remaining(self) -> float:
        """Get remaining cooldown time in seconds.

        Parameters:
            None (property operates on self)

        Return values:
            Float representing seconds remaining until cooldown expires (0.0 if ready)

        This property calculates the exact remaining cooldown time in seconds,
        providing precise timing information for action scheduling and wait
        optimization in the AI player system.
        """
        try:
            expiration_time = datetime.fromisoformat(self.expiration.replace('Z', '+00:00'))
            current_time = datetime.now(expiration_time.tzinfo)
            remaining = (expiration_time - current_time).total_seconds()
            return max(0.0, round(remaining, 6))
        except Exception:
            # If parsing fails, use remaining_seconds
            return max(0.0, float(self.remaining_seconds))


class GameItem(BaseModel):
    """Internal Pydantic model for game items"""
    code: str = Field(description="Unique item identifier")
    name: str = Field(description="Item display name")
    level: int = Field(ge=1, description="Required level to use item")
    type: str = Field(description="Item type/category")
    subtype: str = Field(description="Item subtype/subcategory")
    description: str = Field(description="Item description")
    effects: list[dict[str, Any]] = Field(default_factory=list, description="Item effects and bonuses")
    craft: Optional[dict[str, Any]] = Field(default=None, description="Crafting requirements")
    tradeable: bool = Field(default=True, description="Whether item can be traded")

    @classmethod
    def from_api_item(cls, api_item: Any) -> 'GameItem':
        """Transform API ItemSchema to internal GameItem model"""
        return cls(
            code=api_item.code,
            name=api_item.name,
            level=api_item.level,
            type=api_item.type,
            subtype=api_item.subtype,
            description=api_item.description,
            effects=api_item.effects if hasattr(api_item, 'effects') else [],
            craft=api_item.craft.to_dict() if hasattr(api_item, 'craft') and api_item.craft else None,
            tradeable=api_item.tradeable if hasattr(api_item, 'tradeable') else True
        )


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


class GameMap(BaseModel):
    """Internal Pydantic model for game maps"""
    name: str = Field(description="Map name/identifier")
    skin: str = Field(description="Map visual skin")
    x: int = Field(description="Map X coordinate")
    y: int = Field(description="Map Y coordinate")
    content: Optional[dict[str, Any]] = Field(default=None, description="Map content information")

    @classmethod
    def from_api_map(cls, api_map: Any) -> 'GameMap':
        """Transform API MapSchema to internal GameMap model"""
        return cls(
            name=api_map.name,
            skin=api_map.skin,
            x=api_map.x,
            y=api_map.y,
            content=api_map.content.to_dict() if hasattr(api_map, 'content') and api_map.content else None
        )


class GameResource(BaseModel):
    """Internal Pydantic model for game resources"""
    code: str = Field(description="Unique resource identifier")
    name: str = Field(description="Resource display name")
    skill: str = Field(description="Required skill to gather")
    level: int = Field(ge=1, description="Required skill level")
    drops: list[dict[str, Any]] = Field(default_factory=list, description="Resource drops")

    @classmethod
    def from_api_resource(cls, api_resource: Any) -> 'GameResource':
        """Transform API ResourceSchema to internal GameResource model"""
        return cls(
            code=api_resource.code,
            name=api_resource.name,
            skill=api_resource.skill,
            level=api_resource.level,
            drops=[drop.to_dict() if hasattr(drop, 'to_dict') else drop for drop in (api_resource.drops or [])]
        )


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