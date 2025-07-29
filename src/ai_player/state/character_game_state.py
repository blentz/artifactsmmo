"""
Character Game State Model

This module defines the CharacterGameState class for representing
character state using GameState enum keys with Pydantic validation.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .game_state_enum import GameState


class CharacterGameState(BaseModel):
    """Pydantic model for character state using GameState enum keys"""
    model_config = ConfigDict(validate_assignment=True, extra='forbid')

    # Character identity
    name: str

    # Character progression
    level: int = Field(ge=1, le=45)
    xp: int = Field(ge=0)
    gold: int = Field(ge=0)
    hp: int = Field(ge=0)
    max_hp: int = Field(ge=1)

    # Position
    x: int
    y: int

    # Skills
    mining_level: int = Field(ge=1, le=45)
    mining_xp: int = Field(ge=0)
    woodcutting_level: int = Field(ge=1, le=45)
    woodcutting_xp: int = Field(ge=0)
    fishing_level: int = Field(ge=1, le=45)
    fishing_xp: int = Field(ge=0)
    weaponcrafting_level: int = Field(ge=1, le=45)
    weaponcrafting_xp: int = Field(ge=0)
    gearcrafting_level: int = Field(ge=1, le=45)
    gearcrafting_xp: int = Field(ge=0)
    jewelrycrafting_level: int = Field(ge=1, le=45)
    jewelrycrafting_xp: int = Field(ge=0)
    cooking_level: int = Field(ge=1, le=45)
    cooking_xp: int = Field(ge=0)
    alchemy_level: int = Field(ge=1, le=45)
    alchemy_xp: int = Field(ge=0)

    # Action state
    cooldown: int = Field(ge=0)
    cooldown_ready: bool = True

    def to_goap_state(self) -> dict[str, Any]:
        """Convert to GOAP state dictionary using enum values.

        Parameters:
            None (operates on self)

        Return values:
            Dictionary with string keys (GameState enum values) and state data

        This method converts the character's Pydantic model data to a GOAP-compatible
        state dictionary using GameState enum values as keys, enabling seamless
        integration with the GOAP planning library.
        """
        # Get the raw data dict from the Pydantic model
        raw_dict = self.model_dump()

        # Map the model fields to GameState enum values
        goap_dict = {}

        # Map each model field to corresponding GameState enum
        field_mapping = {
            'level': GameState.CHARACTER_LEVEL,
            'xp': GameState.CHARACTER_XP,
            'gold': GameState.CHARACTER_GOLD,
            'hp': GameState.HP_CURRENT,
            'max_hp': GameState.HP_MAX,
            'x': GameState.CURRENT_X,
            'y': GameState.CURRENT_Y,
            'mining_level': GameState.MINING_LEVEL,
            'mining_xp': GameState.MINING_XP,
            'woodcutting_level': GameState.WOODCUTTING_LEVEL,
            'woodcutting_xp': GameState.WOODCUTTING_XP,
            'fishing_level': GameState.FISHING_LEVEL,
            'fishing_xp': GameState.FISHING_XP,
            'weaponcrafting_level': GameState.WEAPONCRAFTING_LEVEL,
            'weaponcrafting_xp': GameState.WEAPONCRAFTING_XP,
            'gearcrafting_level': GameState.GEARCRAFTING_LEVEL,
            'gearcrafting_xp': GameState.GEARCRAFTING_XP,
            'jewelrycrafting_level': GameState.JEWELRYCRAFTING_LEVEL,
            'jewelrycrafting_xp': GameState.JEWELRYCRAFTING_XP,
            'cooking_level': GameState.COOKING_LEVEL,
            'cooking_xp': GameState.COOKING_XP,
            'alchemy_level': GameState.ALCHEMY_LEVEL,
            'alchemy_xp': GameState.ALCHEMY_XP,
            'cooldown_ready': GameState.COOLDOWN_READY,
        }

        # Map available fields to enum values
        for field_name, enum_key in field_mapping.items():
            if field_name in raw_dict:
                goap_dict[enum_key.value] = raw_dict[field_name]

        return goap_dict

    @classmethod
    def from_api_character(cls, character: Any) -> 'CharacterGameState':
        """Create from API character response with validated state mapping.

        Parameters:
            character: CharacterSchema object from ArtifactsMMO API response

        Return values:
            CharacterGameState instance with validated data mapped to GameState enum keys

        This method creates a type-safe CharacterGameState instance from API response data,
        mapping all relevant character properties to the appropriate GameState enum keys
        while performing Pydantic validation on the data.
        """
        return cls(
            name=character.name,
            level=character.level,
            xp=character.xp,
            gold=character.gold,
            hp=character.hp,
            max_hp=character.max_hp,
            x=character.x,
            y=character.y,
            mining_level=character.mining_level,
            mining_xp=character.mining_xp,
            woodcutting_level=character.woodcutting_level,
            woodcutting_xp=character.woodcutting_xp,
            fishing_level=character.fishing_level,
            fishing_xp=character.fishing_xp,
            weaponcrafting_level=character.weaponcrafting_level,
            weaponcrafting_xp=character.weaponcrafting_xp,
            gearcrafting_level=character.gearcrafting_level,
            gearcrafting_xp=character.gearcrafting_xp,
            jewelrycrafting_level=character.jewelrycrafting_level,
            jewelrycrafting_xp=character.jewelrycrafting_xp,
            cooking_level=character.cooking_level,
            cooking_xp=character.cooking_xp,
            alchemy_level=character.alchemy_level,
            alchemy_xp=character.alchemy_xp,
            cooldown=character.cooldown,
            cooldown_ready=character.cooldown == 0,
        )