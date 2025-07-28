"""
Game State Enum Definition

This module defines the GameState enum that provides type-safe state management
throughout the AI player system. All state references must use this enum to
prevent string-based errors and ensure GOAP compatibility.

The GameState enum serves as the single source of truth for all possible game
state keys, enabling IDE support, type checking, and validation throughout
the entire architecture.
"""

from enum import StrEnum
from typing import Any


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