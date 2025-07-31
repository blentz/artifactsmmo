"""
Monster Data Models

Pydantic models for monster data that align with MonsterSchema and related
models from the artifactsmmo-api-client. Provides type safety and validation
while maintaining exact field name compatibility.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DropRate(BaseModel):
    """Monster drop rate data aligned with DropRateSchema"""
    model_config = ConfigDict(validate_assignment=True)

    code: str  # Item code
    rate: int = Field(ge=1, le=100000)  # Drop rate (per 100,000)
    min_quantity: int = Field(ge=1)
    max_quantity: int = Field(ge=1)


class MonsterEffect(BaseModel):
    """Monster effect data aligned with SimpleEffectSchema"""
    model_config = ConfigDict(validate_assignment=True)

    name: str
    value: int


class Monster(BaseModel):
    """Monster model aligned with artifactsmmo-api-client MonsterSchema"""
    model_config = ConfigDict(validate_assignment=True)

    # Basic monster info - exact field names from API
    name: str
    code: str  # Unique identifier
    level: int = Field(ge=1, le=45)
    hp: int = Field(ge=1)

    # Attack stats - exact field names from API
    attack_fire: int = Field(ge=0)
    attack_earth: int = Field(ge=0)
    attack_water: int = Field(ge=0)
    attack_air: int = Field(ge=0)

    # Resistance stats - exact field names from API
    res_fire: int = Field(ge=0)
    res_earth: int = Field(ge=0)
    res_water: int = Field(ge=0)
    res_air: int = Field(ge=0)

    # Other combat stats
    critical_strike: int = Field(ge=0)

    # Loot data - exact field names from API
    min_gold: int = Field(ge=0)
    max_gold: int = Field(ge=0)
    drops: list[DropRate]

    # Optional effects
    effects: list[MonsterEffect] | None = None

    @classmethod
    def from_api_monster(cls, api_monster: Any) -> "Monster":
        """Create Monster from API MonsterSchema

        Args:
            api_monster: MonsterSchema instance from artifactsmmo-api-client

        Returns:
            Monster instance with all fields mapped from API response
        """
        # Map drop rates
        drops = [
            DropRate(
                code=drop.code,
                rate=drop.rate,
                min_quantity=drop.min_quantity,
                max_quantity=drop.max_quantity
            )
            for drop in api_monster.drops
        ]

        # Map effects if present
        effects = None
        if hasattr(api_monster, 'effects') and api_monster.effects:
            effects = [
                MonsterEffect(
                    name=effect.name,
                    value=effect.value
                )
                for effect in api_monster.effects
            ]

        return cls(
            name=api_monster.name,
            code=api_monster.code,
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
            critical_strike=api_monster.critical_strike,
            min_gold=api_monster.min_gold,
            max_gold=api_monster.max_gold,
            drops=drops,
            effects=effects,
        )

    @property
    def total_attack(self) -> int:
        """Calculate total attack power across all elements"""
        return self.attack_fire + self.attack_earth + self.attack_water + self.attack_air

    @property
    def total_resistance(self) -> int:
        """Calculate total resistance across all elements"""
        return self.res_fire + self.res_earth + self.res_water + self.res_air

    @property
    def average_gold_drop(self) -> float:
        """Calculate average gold drop"""
        return (self.min_gold + self.max_gold) / 2.0

    @property
    def has_drops(self) -> bool:
        """Check if monster has item drops"""
        return len(self.drops) > 0

    def get_drop_by_code(self, item_code: str) -> DropRate | None:
        """Get drop rate for specific item code

        Args:
            item_code: Item code to search for

        Returns:
            DropRate for the item, or None if not found
        """
        for drop in self.drops:
            if drop.code == item_code:
                return drop
        return None

    def can_defeat_with_level(self, character_level: int, level_tolerance: int = 2) -> bool:
        """Check if character can reasonably defeat this monster

        Args:
            character_level: Character's combat level
            level_tolerance: How many levels below monster is acceptable

        Returns:
            True if character should be able to defeat monster
        """
        return character_level >= (self.level - level_tolerance)
