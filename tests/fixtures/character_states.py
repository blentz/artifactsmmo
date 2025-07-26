"""
Character state fixtures for testing

This module provides various character state scenarios for comprehensive
testing of the AI player system including different levels, conditions,
and game situations.
"""

import json
from datetime import datetime, timedelta
from typing import Any

from src.ai_player.state.game_state import CooldownInfo, GameState


class CharacterStateFixtures:
    """Collection of character state fixtures for testing"""

    @staticmethod
    def get_level_1_starter() -> dict[GameState, Any]:
        """Fresh level 1 character state"""
        return {
            GameState.CHARACTER_LEVEL: 1,
            GameState.CHARACTER_XP: 0,
            GameState.CHARACTER_GOLD: 0,
            GameState.HP_CURRENT: 100,
            GameState.HP_MAX: 100,
            GameState.CURRENT_X: 0,
            GameState.CURRENT_Y: 0,

            # All skills start at level 1
            GameState.MINING_LEVEL: 1,
            GameState.MINING_XP: 0,
            GameState.WOODCUTTING_LEVEL: 1,
            GameState.WOODCUTTING_XP: 0,
            GameState.FISHING_LEVEL: 1,
            GameState.FISHING_XP: 0,
            GameState.WEAPONCRAFTING_LEVEL: 1,
            GameState.WEAPONCRAFTING_XP: 0,
            GameState.GEARCRAFTING_LEVEL: 1,
            GameState.GEARCRAFTING_XP: 0,
            GameState.JEWELRYCRAFTING_LEVEL: 1,
            GameState.JEWELRYCRAFTING_XP: 0,
            GameState.COOKING_LEVEL: 1,
            GameState.COOKING_XP: 0,
            GameState.ALCHEMY_LEVEL: 1,
            GameState.ALCHEMY_XP: 0,

            # No equipment
            GameState.WEAPON_EQUIPPED: None,
            GameState.TOOL_EQUIPPED: None,
            GameState.HELMET_EQUIPPED: None,
            GameState.BODY_ARMOR_EQUIPPED: None,
            GameState.LEG_ARMOR_EQUIPPED: None,
            GameState.BOOTS_EQUIPPED: None,
            GameState.RING1_EQUIPPED: None,
            GameState.RING2_EQUIPPED: None,
            GameState.AMULET_EQUIPPED: None,

            # Empty inventory
            GameState.INVENTORY_SPACE_AVAILABLE: 20,
            GameState.INVENTORY_SPACE_USED: 0,
            GameState.INVENTORY_FULL: False,

            # Basic capabilities
            GameState.COOLDOWN_READY: True,
            GameState.CAN_FIGHT: True,
            GameState.CAN_GATHER: True,
            GameState.CAN_CRAFT: True,
            GameState.CAN_TRADE: True,
            GameState.CAN_MOVE: True,
            GameState.CAN_REST: True,
            GameState.CAN_USE_ITEM: True,
            GameState.CAN_BANK: True,

            # Location states
            GameState.AT_TARGET_LOCATION: False,
            GameState.AT_MONSTER_LOCATION: False,
            GameState.AT_RESOURCE_LOCATION: False,
            GameState.AT_NPC_LOCATION: False,
            GameState.AT_BANK_LOCATION: False,
            GameState.AT_GRAND_EXCHANGE: False,
            GameState.AT_SAFE_LOCATION: True,
            GameState.PATH_CLEAR: True,

            # Combat and safety
            GameState.IN_COMBAT: False,
            GameState.HP_LOW: False,
            GameState.HP_CRITICAL: False,
            GameState.SAFE_TO_FIGHT: True,
            GameState.ENEMY_NEARBY: False,
            GameState.COMBAT_ADVANTAGE: True,

            # Resource states
            GameState.HAS_REQUIRED_ITEMS: False,
            GameState.HAS_CRAFTING_MATERIALS: False,
            GameState.HAS_CONSUMABLES: False,
            GameState.RESOURCE_AVAILABLE: True,
            GameState.RESOURCE_DEPLETED: False,

            # Task states
            GameState.ACTIVE_TASK: None,
            GameState.TASK_PROGRESS: 0,
            GameState.TASK_COMPLETED: False,
            GameState.CAN_ACCEPT_TASK: True,
            GameState.TASK_REQUIREMENTS_MET: False,

            # Optimization states
            GameState.OPTIMAL_LOCATION: False,
            GameState.EFFICIENT_ACTION_AVAILABLE: True,
            GameState.READY_FOR_UPGRADE: False,
            GameState.PROGRESSION_BLOCKED: False,
            GameState.INVENTORY_OPTIMIZED: True
        }

    @staticmethod
    def get_level_10_experienced() -> dict[GameState, Any]:
        """Experienced level 10 character state"""
        return {
            GameState.CHARACTER_LEVEL: 10,
            GameState.CHARACTER_XP: 2500,
            GameState.CHARACTER_GOLD: 1500,
            GameState.HP_CURRENT: 120,
            GameState.HP_MAX: 120,
            GameState.CURRENT_X: 15,
            GameState.CURRENT_Y: 20,

            # Improved skills
            GameState.MINING_LEVEL: 8,
            GameState.MINING_XP: 1800,
            GameState.WOODCUTTING_LEVEL: 6,
            GameState.WOODCUTTING_XP: 1200,
            GameState.FISHING_LEVEL: 4,
            GameState.FISHING_XP: 800,
            GameState.WEAPONCRAFTING_LEVEL: 5,
            GameState.WEAPONCRAFTING_XP: 1000,
            GameState.GEARCRAFTING_LEVEL: 3,
            GameState.GEARCRAFTING_XP: 600,
            GameState.JEWELRYCRAFTING_LEVEL: 2,
            GameState.JEWELRYCRAFTING_XP: 400,
            GameState.COOKING_LEVEL: 3,
            GameState.COOKING_XP: 600,
            GameState.ALCHEMY_LEVEL: 2,
            GameState.ALCHEMY_XP: 400,

            # Basic equipment
            GameState.WEAPON_EQUIPPED: "iron_sword",
            GameState.TOOL_EQUIPPED: "iron_pickaxe",
            GameState.HELMET_EQUIPPED: "leather_helmet",
            GameState.BODY_ARMOR_EQUIPPED: "iron_chestplate",
            GameState.LEG_ARMOR_EQUIPPED: "leather_pants",
            GameState.BOOTS_EQUIPPED: "leather_boots",
            GameState.RING1_EQUIPPED: None,
            GameState.RING2_EQUIPPED: None,
            GameState.AMULET_EQUIPPED: None,

            # Partially filled inventory
            GameState.INVENTORY_SPACE_AVAILABLE: 12,
            GameState.INVENTORY_SPACE_USED: 8,
            GameState.INVENTORY_FULL: False,

            # All capabilities available
            GameState.COOLDOWN_READY: True,
            GameState.CAN_FIGHT: True,
            GameState.CAN_GATHER: True,
            GameState.CAN_CRAFT: True,
            GameState.CAN_TRADE: True,
            GameState.CAN_MOVE: True,
            GameState.CAN_REST: True,
            GameState.CAN_USE_ITEM: True,
            GameState.CAN_BANK: True,

            # Location states
            GameState.AT_TARGET_LOCATION: True,
            GameState.AT_MONSTER_LOCATION: False,
            GameState.AT_RESOURCE_LOCATION: True,
            GameState.AT_NPC_LOCATION: False,
            GameState.AT_BANK_LOCATION: False,
            GameState.AT_GRAND_EXCHANGE: False,
            GameState.AT_SAFE_LOCATION: True,
            GameState.PATH_CLEAR: True,

            # Combat states
            GameState.IN_COMBAT: False,
            GameState.HP_LOW: False,
            GameState.HP_CRITICAL: False,
            GameState.SAFE_TO_FIGHT: True,
            GameState.ENEMY_NEARBY: False,
            GameState.COMBAT_ADVANTAGE: True,

            # Resource states
            GameState.HAS_REQUIRED_ITEMS: True,
            GameState.HAS_CRAFTING_MATERIALS: True,
            GameState.HAS_CONSUMABLES: True,
            GameState.RESOURCE_AVAILABLE: True,
            GameState.RESOURCE_DEPLETED: False,

            # Task states
            GameState.ACTIVE_TASK: "gather_iron_ore",
            GameState.TASK_PROGRESS: 5,
            GameState.TASK_COMPLETED: False,
            GameState.CAN_ACCEPT_TASK: False,
            GameState.TASK_REQUIREMENTS_MET: True,

            # Optimization states
            GameState.OPTIMAL_LOCATION: True,
            GameState.EFFICIENT_ACTION_AVAILABLE: True,
            GameState.READY_FOR_UPGRADE: True,
            GameState.PROGRESSION_BLOCKED: False,
            GameState.INVENTORY_OPTIMIZED: False
        }

    @staticmethod
    def get_level_25_advanced() -> dict[GameState, Any]:
        """Advanced level 25 character state"""
        return {
            GameState.CHARACTER_LEVEL: 25,
            GameState.CHARACTER_XP: 15000,
            GameState.CHARACTER_GOLD: 10000,
            GameState.HP_CURRENT: 180,
            GameState.HP_MAX: 200,
            GameState.CURRENT_X: 45,
            GameState.CURRENT_Y: 60,

            # High-level skills
            GameState.MINING_LEVEL: 22,
            GameState.MINING_XP: 8500,
            GameState.WOODCUTTING_LEVEL: 20,
            GameState.WOODCUTTING_XP: 7800,
            GameState.FISHING_LEVEL: 18,
            GameState.FISHING_XP: 7000,
            GameState.WEAPONCRAFTING_LEVEL: 16,
            GameState.WEAPONCRAFTING_XP: 6200,
            GameState.GEARCRAFTING_LEVEL: 14,
            GameState.GEARCRAFTING_XP: 5500,
            GameState.JEWELRYCRAFTING_LEVEL: 12,
            GameState.JEWELRYCRAFTING_XP: 4800,
            GameState.COOKING_LEVEL: 15,
            GameState.COOKING_XP: 5800,
            GameState.ALCHEMY_LEVEL: 10,
            GameState.ALCHEMY_XP: 4000,

            # Advanced equipment
            GameState.WEAPON_EQUIPPED: "mithril_sword",
            GameState.TOOL_EQUIPPED: "mithril_pickaxe",
            GameState.HELMET_EQUIPPED: "steel_helmet",
            GameState.BODY_ARMOR_EQUIPPED: "mithril_chestplate",
            GameState.LEG_ARMOR_EQUIPPED: "steel_pants",
            GameState.BOOTS_EQUIPPED: "steel_boots",
            GameState.RING1_EQUIPPED: "copper_ring",
            GameState.RING2_EQUIPPED: "iron_ring",
            GameState.AMULET_EQUIPPED: "silver_amulet",

            # Nearly full inventory
            GameState.INVENTORY_SPACE_AVAILABLE: 3,
            GameState.INVENTORY_SPACE_USED: 27,
            GameState.INVENTORY_FULL: False,

            # All capabilities available
            GameState.COOLDOWN_READY: True,
            GameState.CAN_FIGHT: True,
            GameState.CAN_GATHER: True,
            GameState.CAN_CRAFT: True,
            GameState.CAN_TRADE: True,
            GameState.CAN_MOVE: True,
            GameState.CAN_REST: True,
            GameState.CAN_USE_ITEM: True,
            GameState.CAN_BANK: True,

            # Advanced location capabilities
            GameState.AT_TARGET_LOCATION: False,
            GameState.AT_MONSTER_LOCATION: False,
            GameState.AT_RESOURCE_LOCATION: False,
            GameState.AT_NPC_LOCATION: False,
            GameState.AT_BANK_LOCATION: True,
            GameState.AT_GRAND_EXCHANGE: False,
            GameState.AT_SAFE_LOCATION: True,
            GameState.PATH_CLEAR: True,

            # Combat ready
            GameState.IN_COMBAT: False,
            GameState.HP_LOW: False,
            GameState.HP_CRITICAL: False,
            GameState.SAFE_TO_FIGHT: True,
            GameState.ENEMY_NEARBY: False,
            GameState.COMBAT_ADVANTAGE: True,

            # Resource rich
            GameState.HAS_REQUIRED_ITEMS: True,
            GameState.HAS_CRAFTING_MATERIALS: True,
            GameState.HAS_CONSUMABLES: True,
            GameState.RESOURCE_AVAILABLE: True,
            GameState.RESOURCE_DEPLETED: False,

            # Advanced task
            GameState.ACTIVE_TASK: "craft_mithril_equipment",
            GameState.TASK_PROGRESS: 8,
            GameState.TASK_COMPLETED: False,
            GameState.CAN_ACCEPT_TASK: False,
            GameState.TASK_REQUIREMENTS_MET: True,

            # Economic optimization
            GameState.OPTIMAL_LOCATION: False,
            GameState.EFFICIENT_ACTION_AVAILABLE: True,
            GameState.READY_FOR_UPGRADE: True,
            GameState.PROGRESSION_BLOCKED: False,
            GameState.INVENTORY_OPTIMIZED: False,

            # Economic states
            GameState.MARKET_ACCESS: True,
            GameState.PROFITABLE_TRADE_AVAILABLE: True,
            GameState.ARBITRAGE_OPPORTUNITY: False,
            GameState.PORTFOLIO_VALUE: 25000
        }

    @staticmethod
    def get_emergency_low_hp() -> dict[GameState, Any]:
        """Character in emergency low HP situation"""
        state = CharacterStateFixtures.get_level_10_experienced()

        # Emergency modifications
        state.update({
            GameState.HP_CURRENT: 15,  # Critically low HP
            GameState.HP_MAX: 120,
            GameState.HP_LOW: True,
            GameState.HP_CRITICAL: True,
            GameState.SAFE_TO_FIGHT: False,
            GameState.IN_COMBAT: True,
            GameState.ENEMY_NEARBY: True,
            GameState.COMBAT_ADVANTAGE: False,
            GameState.CAN_FIGHT: False,  # Too dangerous
            GameState.AT_SAFE_LOCATION: False,
            GameState.PROGRESSION_BLOCKED: True
        })

        return state

    @staticmethod
    def get_inventory_full() -> dict[GameState, Any]:
        """Character with full inventory needing management"""
        state = CharacterStateFixtures.get_level_10_experienced()

        # Full inventory modifications
        state.update({
            GameState.INVENTORY_SPACE_AVAILABLE: 0,
            GameState.INVENTORY_SPACE_USED: 20,
            GameState.INVENTORY_FULL: True,
            GameState.CAN_GATHER: False,  # Cannot gather more
            GameState.HAS_REQUIRED_ITEMS: True,
            GameState.HAS_CRAFTING_MATERIALS: True,
            GameState.INVENTORY_OPTIMIZED: False,
            GameState.EFFICIENT_ACTION_AVAILABLE: False,
            GameState.PROGRESSION_BLOCKED: True
        })

        return state

    @staticmethod
    def get_character_on_cooldown() -> dict[GameState, Any]:
        """Character currently on cooldown"""
        state = CharacterStateFixtures.get_level_10_experienced()

        # Cooldown modifications
        state.update({
            GameState.COOLDOWN_READY: False,
            GameState.CAN_FIGHT: False,
            GameState.CAN_GATHER: False,
            GameState.CAN_CRAFT: False,
            GameState.CAN_MOVE: False,
            GameState.CAN_TRADE: False,
            GameState.CAN_USE_ITEM: False,
            GameState.EFFICIENT_ACTION_AVAILABLE: False
        })

        return state

    @staticmethod
    def get_resource_depleted_area() -> dict[GameState, Any]:
        """Character in area where resources are depleted"""
        state = CharacterStateFixtures.get_level_10_experienced()

        # Resource depletion modifications
        state.update({
            GameState.AT_RESOURCE_LOCATION: True,
            GameState.RESOURCE_AVAILABLE: False,
            GameState.RESOURCE_DEPLETED: True,
            GameState.CAN_GATHER: False,
            GameState.OPTIMAL_LOCATION: False,
            GameState.EFFICIENT_ACTION_AVAILABLE: False,
            GameState.PROGRESSION_BLOCKED: True
        })

        return state

    @staticmethod
    def get_wealthy_trader() -> dict[GameState, Any]:
        """Wealthy character focused on trading"""
        state = CharacterStateFixtures.get_level_25_advanced()

        # Trading focus modifications
        state.update({
            GameState.CHARACTER_GOLD: 50000,
            GameState.AT_GRAND_EXCHANGE: True,
            GameState.MARKET_ACCESS: True,
            GameState.PROFITABLE_TRADE_AVAILABLE: True,
            GameState.ARBITRAGE_OPPORTUNITY: True,
            GameState.PORTFOLIO_VALUE: 100000,
            GameState.ITEM_PRICE_TREND: "bullish",
            GameState.INVENTORY_OPTIMIZED: True,
            GameState.BANK_GOLD: 25000,
            GameState.BANK_SPACE_AVAILABLE: 50
        })

        return state

    @staticmethod
    def get_max_level_endgame() -> dict[GameState, Any]:
        """Maximum level character in endgame"""
        return {
            GameState.CHARACTER_LEVEL: 45,
            GameState.CHARACTER_XP: 100000,
            GameState.CHARACTER_GOLD: 100000,
            GameState.HP_CURRENT: 300,
            GameState.HP_MAX: 300,
            GameState.CURRENT_X: 100,
            GameState.CURRENT_Y: 100,

            # Maxed skills
            GameState.MINING_LEVEL: 45,
            GameState.MINING_XP: 50000,
            GameState.WOODCUTTING_LEVEL: 45,
            GameState.WOODCUTTING_XP: 50000,
            GameState.FISHING_LEVEL: 45,
            GameState.FISHING_XP: 50000,
            GameState.WEAPONCRAFTING_LEVEL: 45,
            GameState.WEAPONCRAFTING_XP: 50000,
            GameState.GEARCRAFTING_LEVEL: 45,
            GameState.GEARCRAFTING_XP: 50000,
            GameState.JEWELRYCRAFTING_LEVEL: 45,
            GameState.JEWELRYCRAFTING_XP: 50000,
            GameState.COOKING_LEVEL: 45,
            GameState.COOKING_XP: 50000,
            GameState.ALCHEMY_LEVEL: 45,
            GameState.ALCHEMY_XP: 50000,

            # Legendary equipment
            GameState.WEAPON_EQUIPPED: "legendary_sword",
            GameState.TOOL_EQUIPPED: "legendary_pickaxe",
            GameState.HELMET_EQUIPPED: "legendary_helmet",
            GameState.BODY_ARMOR_EQUIPPED: "legendary_chestplate",
            GameState.LEG_ARMOR_EQUIPPED: "legendary_pants",
            GameState.BOOTS_EQUIPPED: "legendary_boots",
            GameState.RING1_EQUIPPED: "legendary_ring",
            GameState.RING2_EQUIPPED: "legendary_ring",
            GameState.AMULET_EQUIPPED: "legendary_amulet",

            # Optimized inventory
            GameState.INVENTORY_SPACE_AVAILABLE: 10,
            GameState.INVENTORY_SPACE_USED: 40,
            GameState.INVENTORY_FULL: False,
            GameState.INVENTORY_OPTIMIZED: True,

            # All capabilities mastered
            GameState.COOLDOWN_READY: True,
            GameState.CAN_FIGHT: True,
            GameState.CAN_GATHER: True,
            GameState.CAN_CRAFT: True,
            GameState.CAN_TRADE: True,
            GameState.CAN_MOVE: True,
            GameState.CAN_REST: True,
            GameState.CAN_USE_ITEM: True,
            GameState.CAN_BANK: True,

            # Endgame location access
            GameState.AT_TARGET_LOCATION: True,
            GameState.AT_SAFE_LOCATION: True,
            GameState.PATH_CLEAR: True,
            GameState.OPTIMAL_LOCATION: True,

            # Combat mastery
            GameState.IN_COMBAT: False,
            GameState.HP_LOW: False,
            GameState.HP_CRITICAL: False,
            GameState.SAFE_TO_FIGHT: True,
            GameState.COMBAT_ADVANTAGE: True,

            # Resource mastery
            GameState.HAS_REQUIRED_ITEMS: True,
            GameState.HAS_CRAFTING_MATERIALS: True,
            GameState.HAS_CONSUMABLES: True,
            GameState.RESOURCE_AVAILABLE: True,

            # Endgame economy
            GameState.MARKET_ACCESS: True,
            GameState.PROFITABLE_TRADE_AVAILABLE: True,
            GameState.PORTFOLIO_VALUE: 500000,
            GameState.BANK_GOLD: 200000,
            GameState.BANK_SPACE_AVAILABLE: 100,

            # Optimization achieved
            GameState.EFFICIENT_ACTION_AVAILABLE: True,
            GameState.READY_FOR_UPGRADE: False,  # Already maxed
            GameState.PROGRESSION_BLOCKED: False
        }


class CooldownFixtures:
    """Collection of cooldown state fixtures"""

    @staticmethod
    def get_no_cooldown() -> CooldownInfo:
        """Character with no active cooldown"""
        return CooldownInfo(
            character_name="ready_character",
            expiration=(datetime.now() - timedelta(seconds=10)).isoformat(),
            total_seconds=0,
            remaining_seconds=0,
            reason="none"
        )

    @staticmethod
    def get_short_cooldown() -> CooldownInfo:
        """Character with short active cooldown"""
        return CooldownInfo(
            character_name="short_cooldown_character",
            expiration=(datetime.now() + timedelta(seconds=5)).isoformat(),
            total_seconds=5,
            remaining_seconds=5,
            reason="move"
        )

    @staticmethod
    def get_medium_cooldown() -> CooldownInfo:
        """Character with medium active cooldown"""
        return CooldownInfo(
            character_name="medium_cooldown_character",
            expiration=(datetime.now() + timedelta(seconds=30)).isoformat(),
            total_seconds=30,
            remaining_seconds=30,
            reason="fight"
        )

    @staticmethod
    def get_long_cooldown() -> CooldownInfo:
        """Character with long active cooldown"""
        return CooldownInfo(
            character_name="long_cooldown_character",
            expiration=(datetime.now() + timedelta(minutes=5)).isoformat(),
            total_seconds=300,
            remaining_seconds=300,
            reason="craft"
        )


class CharacterStateJSON:
    """JSON serializable character states for file-based testing"""

    @staticmethod
    def save_state_to_json(state: dict[GameState, Any], filename: str) -> str:
        """Save character state to JSON file format"""
        # Convert GameState enum keys to strings for JSON serialization
        json_state = {key.value: value for key, value in state.items()}

        state_json = {
            "character_state": json_state,
            "timestamp": datetime.now().isoformat(),
            "version": "1.0"
        }

        return json.dumps(state_json, indent=2)

    @staticmethod
    def load_state_from_json(json_str: str) -> dict[GameState, Any]:
        """Load character state from JSON string"""
        data = json.loads(json_str)
        json_state = data["character_state"]

        # Convert string keys back to GameState enums
        state = {}
        for key_str, value in json_state.items():
            try:
                game_state_key = GameState(key_str)
                state[game_state_key] = value
            except ValueError:
                # Skip invalid keys
                continue

        return state

    @staticmethod
    def get_all_test_states() -> dict[str, str]:
        """Get all test states as JSON strings"""
        states = {
            "level_1_starter": CharacterStateFixtures.get_level_1_starter(),
            "level_10_experienced": CharacterStateFixtures.get_level_10_experienced(),
            "level_25_advanced": CharacterStateFixtures.get_level_25_advanced(),
            "emergency_low_hp": CharacterStateFixtures.get_emergency_low_hp(),
            "inventory_full": CharacterStateFixtures.get_inventory_full(),
            "character_on_cooldown": CharacterStateFixtures.get_character_on_cooldown(),
            "resource_depleted": CharacterStateFixtures.get_resource_depleted_area(),
            "wealthy_trader": CharacterStateFixtures.get_wealthy_trader(),
            "max_level_endgame": CharacterStateFixtures.get_max_level_endgame()
        }

        json_states = {}
        for name, state in states.items():
            json_states[name] = CharacterStateJSON.save_state_to_json(state, f"{name}.json")

        return json_states


# Convenience functions for test usage
def get_test_character_state(scenario: str = "level_10_experienced") -> dict[GameState, Any]:
    """Get a test character state by scenario name"""
    fixtures_map = {
        "level_1_starter": CharacterStateFixtures.get_level_1_starter,
        "level_10_experienced": CharacterStateFixtures.get_level_10_experienced,
        "level_25_advanced": CharacterStateFixtures.get_level_25_advanced,
        "emergency_low_hp": CharacterStateFixtures.get_emergency_low_hp,
        "inventory_full": CharacterStateFixtures.get_inventory_full,
        "character_on_cooldown": CharacterStateFixtures.get_character_on_cooldown,
        "resource_depleted": CharacterStateFixtures.get_resource_depleted_area,
        "wealthy_trader": CharacterStateFixtures.get_wealthy_trader,
        "max_level_endgame": CharacterStateFixtures.get_max_level_endgame
    }

    if scenario not in fixtures_map:
        raise ValueError(f"Unknown scenario: {scenario}. Available: {list(fixtures_map.keys())}")

    return fixtures_map[scenario]()


def get_test_cooldown(scenario: str = "no_cooldown") -> CooldownInfo:
    """Get a test cooldown by scenario name"""
    cooldown_map = {
        "no_cooldown": CooldownFixtures.get_no_cooldown,
        "short_cooldown": CooldownFixtures.get_short_cooldown,
        "medium_cooldown": CooldownFixtures.get_medium_cooldown,
        "long_cooldown": CooldownFixtures.get_long_cooldown
    }

    if scenario not in cooldown_map:
        raise ValueError(f"Unknown cooldown scenario: {scenario}. Available: {list(cooldown_map.keys())}")

    return cooldown_map[scenario]()


def get_state_transition_sequence() -> list[dict[GameState, Any]]:
    """Get a sequence of character states showing progression"""
    return [
        CharacterStateFixtures.get_level_1_starter(),
        CharacterStateFixtures.get_level_10_experienced(),
        CharacterStateFixtures.get_level_25_advanced(),
        CharacterStateFixtures.get_max_level_endgame()
    ]
