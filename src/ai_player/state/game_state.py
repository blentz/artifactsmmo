"""
Game State Enum Definition

This module defines the GameState enum that provides type-safe state management
throughout the AI player system. All state references must use this enum to
prevent string-based errors and ensure GOAP compatibility.

The GameState enum serves as the single source of truth for all possible game
state keys, enabling IDE support, type checking, and validation throughout
the entire architecture.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Import shared models to avoid circular imports
from ...game_data.models import CooldownInfo


class GameState(StrEnum):
    """Global enum defining all possible game state keys.

    Using StrEnum ensures compatibility with GOAP library while providing
    type safety and IDE support for state names. All state references
    throughout the system must use this enum.
    """

    # Character progression states
    CHARACTER_LEVEL = "character_level"
    CHARACTER_XP = "character_xp"
    CHARACTER_GOLD = "character_gold"
    HP_CURRENT = "hp_current"
    HP_MAX = "hp_max"

    # Position and movement states
    CURRENT_X = "current_x"
    CURRENT_Y = "current_y"
    AT_TARGET_LOCATION = "at_target_location"
    AT_MONSTER_LOCATION = "at_monster_location"
    AT_RESOURCE_LOCATION = "at_resource_location"
    AT_NPC_LOCATION = "at_npc_location"
    AT_BANK_LOCATION = "at_bank_location"
    AT_GRAND_EXCHANGE = "at_grand_exchange"
    AT_SAFE_LOCATION = "at_safe_location"
    PATH_CLEAR = "path_clear"

    # Skill progression states
    MINING_LEVEL = "mining_level"
    MINING_XP = "mining_xp"
    WOODCUTTING_LEVEL = "woodcutting_level"
    WOODCUTTING_XP = "woodcutting_xp"
    FISHING_LEVEL = "fishing_level"
    FISHING_XP = "fishing_xp"
    WEAPONCRAFTING_LEVEL = "weaponcrafting_level"
    WEAPONCRAFTING_XP = "weaponcrafting_xp"
    GEARCRAFTING_LEVEL = "gearcrafting_level"
    GEARCRAFTING_XP = "gearcrafting_xp"
    JEWELRYCRAFTING_LEVEL = "jewelrycrafting_level"
    JEWELRYCRAFTING_XP = "jewelrycrafting_xp"
    COOKING_LEVEL = "cooking_level"
    COOKING_XP = "cooking_xp"
    ALCHEMY_LEVEL = "alchemy_level"
    ALCHEMY_XP = "alchemy_xp"

    # Equipment and inventory states
    WEAPON_EQUIPPED = "weapon_equipped"
    TOOL_EQUIPPED = "tool_equipped"
    HELMET_EQUIPPED = "helmet_equipped"
    BODY_ARMOR_EQUIPPED = "body_armor_equipped"
    LEG_ARMOR_EQUIPPED = "leg_armor_equipped"
    BOOTS_EQUIPPED = "boots_equipped"
    RING1_EQUIPPED = "ring1_equipped"
    RING2_EQUIPPED = "ring2_equipped"
    AMULET_EQUIPPED = "amulet_equipped"
    INVENTORY_SPACE_AVAILABLE = "inventory_space_available"
    INVENTORY_SPACE_USED = "inventory_space_used"
    INVENTORY_FULL = "inventory_full"
    BANK_SPACE_AVAILABLE = "bank_space_available"
    BANK_GOLD = "bank_gold"

    # Task and quest states
    ACTIVE_TASK = "active_task"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETED = "task_completed"
    CAN_ACCEPT_TASK = "can_accept_task"
    TASK_REQUIREMENTS_MET = "task_requirements_met"

    # Economic and trading states
    MARKET_ACCESS = "market_access"
    PROFITABLE_TRADE_AVAILABLE = "profitable_trade_available"
    ARBITRAGE_OPPORTUNITY = "arbitrage_opportunity"
    ITEM_PRICE_TREND = "item_price_trend"
    PORTFOLIO_VALUE = "portfolio_value"

    # Resource and item states
    HAS_REQUIRED_ITEMS = "has_required_items"
    HAS_CRAFTING_MATERIALS = "has_crafting_materials"
    HAS_CONSUMABLES = "has_consumables"
    ITEM_QUANTITY = "item_quantity"
    RESOURCE_AVAILABLE = "resource_available"
    RESOURCE_DEPLETED = "resource_depleted"

    # Combat and safety states
    IN_COMBAT = "in_combat"
    HP_LOW = "hp_low"
    HP_CRITICAL = "hp_critical"
    SAFE_TO_FIGHT = "safe_to_fight"
    ENEMY_NEARBY = "enemy_nearby"
    COMBAT_ADVANTAGE = "combat_advantage"

    # Action availability states
    COOLDOWN_READY = "cooldown_ready"
    CAN_FIGHT = "can_fight"
    CAN_GATHER = "can_gather"
    CAN_CRAFT = "can_craft"
    CAN_TRADE = "can_trade"
    CAN_MOVE = "can_move"
    CAN_REST = "can_rest"
    CAN_USE_ITEM = "can_use_item"
    CAN_BANK = "can_bank"

    # Efficiency and optimization states
    OPTIMAL_LOCATION = "optimal_location"
    EFFICIENT_ACTION_AVAILABLE = "efficient_action_available"
    READY_FOR_UPGRADE = "ready_for_upgrade"
    PROGRESSION_BLOCKED = "progression_blocked"
    INVENTORY_OPTIMIZED = "inventory_optimized"

    # Event and time-based states
    EVENT_ACTIVE = "event_active"
    TIME_OF_DAY = "time_of_day"
    RUSH_HOUR = "rush_hour"
    MAINTENANCE_WINDOW = "maintenance_window"

    @classmethod
    def validate_state_dict(cls, state_dict: dict[str, Any]) -> dict['GameState', Any]:
        """Validate and convert string keys to GameState enum values.

        Parameters:
            state_dict: Dictionary with string keys representing game state

        Return values:
            Dictionary with validated GameState enum keys and original values

        This method validates that all string keys in the input dictionary correspond
        to valid GameState enum values, converting them to proper enum keys for
        type-safe state management throughout the GOAP system.
        """
        validated_dict = {}
        valid_enum_values = {state.value for state in cls}

        for key, value in state_dict.items():
            if key not in valid_enum_values:
                raise ValueError(f"Invalid GameState key: {key}")
            # Convert string key to GameState enum
            validated_dict[cls(key)] = value

        return validated_dict

    @classmethod
    def to_goap_dict(cls, state_dict: dict['GameState', Any]) -> dict[str, Any]:
        """Convert enum-keyed state dict to string-keyed dict for GOAP.

        Parameters:
            state_dict: Dictionary with GameState enum keys and state values

        Return values:
            Dictionary with string keys (enum values) and original state values

        This method converts the type-safe GameState enum-keyed dictionary to a
        string-keyed dictionary compatible with the existing GOAP library while
        preserving all state values for planning operations.
        """
        return {key.value: value for key, value in state_dict.items()}


class ActionResult(BaseModel):
    """Result of executing a GOAP action"""
    success: bool
    message: str
    state_changes: dict[GameState, Any]
    cooldown_seconds: int = 0


class CharacterGameState(BaseModel):
    """Pydantic model for character state using GameState enum keys"""
    model_config = ConfigDict(validate_assignment=True, extra='forbid')

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


