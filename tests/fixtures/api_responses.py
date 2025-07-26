"""
API response fixtures for testing

This module provides mock API responses for the ArtifactsMMO API
including character data, game data, and various response scenarios
for comprehensive testing.
"""

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import Mock

from src.lib.httpstatus import ArtifactsHTTPStatus


class APIResponseFixtures:
    """Collection of mock API responses for testing"""

    @staticmethod
    def get_character_response(
        name: str = "test_character",
        level: int = 10,
        customizations: dict[str, Any] | None = None
    ) -> Mock:
        """Create mock character API response"""
        base_response = {
            "name": name,
            "level": level,
            "xp": level * 250,
            "max_xp": (level + 1) * 250,
            "gold": level * 100,
            "hp": 80 + (level * 4),
            "max_hp": 100 + (level * 4),
            "x": 10 + level,
            "y": 15 + level,
            "cooldown": 0,
            "cooldown_expiration": None,
            "server": "1",
            "account": "test_account",
            "skin": "men1",

            # Skills
            "mining_level": max(1, level - 2),
            "mining_xp": max(0, (level - 2) * 200),
            "mining_max_xp": max(200, (level - 1) * 200),
            "woodcutting_level": max(1, level - 3),
            "woodcutting_xp": max(0, (level - 3) * 180),
            "woodcutting_max_xp": max(180, (level - 2) * 180),
            "fishing_level": max(1, level - 4),
            "fishing_xp": max(0, (level - 4) * 160),
            "fishing_max_xp": max(160, (level - 3) * 160),
            "weaponcrafting_level": max(1, level - 5),
            "weaponcrafting_xp": max(0, (level - 5) * 140),
            "weaponcrafting_max_xp": max(140, (level - 4) * 140),
            "gearcrafting_level": max(1, level - 6),
            "gearcrafting_xp": max(0, (level - 6) * 120),
            "gearcrafting_max_xp": max(120, (level - 5) * 120),
            "jewelrycrafting_level": max(1, level - 7),
            "jewelrycrafting_xp": max(0, (level - 7) * 100),
            "jewelrycrafting_max_xp": max(100, (level - 6) * 100),
            "cooking_level": max(1, level - 8),
            "cooking_xp": max(0, (level - 8) * 80),
            "cooking_max_xp": max(80, (level - 7) * 80),
            "alchemy_level": max(1, level - 9),
            "alchemy_xp": max(0, (level - 9) * 60),
            "alchemy_max_xp": max(60, (level - 8) * 60),

            # Equipment slots
            "weapon_slot": "iron_sword" if level >= 5 else None,
            "shield_slot": None,
            "helmet_slot": "leather_helmet" if level >= 3 else None,
            "body_armor_slot": "iron_chestplate" if level >= 7 else None,
            "leg_armor_slot": "leather_pants" if level >= 4 else None,
            "boots_slot": "leather_boots" if level >= 2 else None,
            "ring1_slot": None,
            "ring2_slot": None,
            "amulet_slot": None,
            "artifact1_slot": None,
            "artifact2_slot": None,
            "artifact3_slot": None,
            "consumable1_slot": None,
            "consumable1_slot_quantity": 0,
            "consumable2_slot": None,
            "consumable2_slot_quantity": 0,

            # Inventory
            "inventory_max_items": 20 + (level // 5),
            "inventory": [
                {"slot": 1, "code": "copper_ore", "quantity": 5},
                {"slot": 2, "code": "ash_wood", "quantity": 3},
                {"slot": 3, "code": "cooked_gudgeon", "quantity": 2}
            ] if level >= 5 else [],

            # Bank
            "bank_max_items": 50 + (level // 2),
            "bank_gold": level * 50,

            # Tasks
            "task": None,
            "task_type": None,
            "task_progress": 0,
            "task_total": 0
        }

        # Apply customizations
        if customizations:
            base_response.update(customizations)

        # Create mock object with attributes
        mock_character = Mock()
        for key, value in base_response.items():
            setattr(mock_character, key, value)

        return mock_character

    @staticmethod
    def get_character_on_cooldown(
        name: str = "cooldown_character",
        cooldown_seconds: int = 30,
        reason: str = "fight"
    ) -> Mock:
        """Create mock character response with active cooldown"""
        expiration_time = datetime.now() + timedelta(seconds=cooldown_seconds)

        character = APIResponseFixtures.get_character_response(name)
        character.cooldown = cooldown_seconds
        character.cooldown_expiration = expiration_time.isoformat()

        # Add cooldown details
        cooldown_mock = Mock()
        cooldown_mock.total_seconds = cooldown_seconds
        cooldown_mock.remaining_seconds = cooldown_seconds
        cooldown_mock.expiration = expiration_time
        cooldown_mock.reason = Mock()
        cooldown_mock.reason.value = reason

        character.cooldown_details = cooldown_mock

        return character

    @staticmethod
    def get_fight_response(
        result: str = "win",
        xp_gained: int = 150,
        gold_gained: int = 25,
        hp_lost: int = 10,
        drops: list[dict[str, Any]] | None = None
    ) -> Mock:
        """Create mock fight action response"""
        fight_result = Mock()
        fight_result.result = result
        fight_result.xp = xp_gained
        fight_result.gold = gold_gained
        fight_result.drops = drops or [{"code": "feather", "quantity": 1}]
        fight_result.logs = [f"You fought a monster and {result}!"]

        response = Mock()
        response.data = Mock()
        response.data.xp = xp_gained
        response.data.gold = gold_gained
        response.data.hp = 90 - hp_lost  # Assuming started with 100 HP
        response.data.fight = fight_result
        response.data.cooldown = Mock()
        response.data.cooldown.total_seconds = 8
        response.data.cooldown.remaining_seconds = 8
        response.data.cooldown.expiration = (datetime.now() + timedelta(seconds=8)).isoformat()
        response.data.cooldown.reason = Mock()
        response.data.cooldown.reason.value = "fight"

        return response

    @staticmethod
    def get_move_response(target_x: int, target_y: int) -> Mock:
        """Create mock move action response"""
        response = Mock()
        response.data = Mock()
        response.data.x = target_x
        response.data.y = target_y
        response.data.cooldown = Mock()
        response.data.cooldown.total_seconds = 3
        response.data.cooldown.remaining_seconds = 3
        response.data.cooldown.expiration = (datetime.now() + timedelta(seconds=3)).isoformat()
        response.data.cooldown.reason = Mock()
        response.data.cooldown.reason.value = "move"

        return response

    @staticmethod
    def get_gather_response(
        resource_code: str = "copper_ore",
        quantity: int = 1,
        xp_gained: int = 50
    ) -> Mock:
        """Create mock gathering action response"""
        response = Mock()
        response.data = Mock()
        response.data.xp = xp_gained
        response.data.item = Mock()
        response.data.item.code = resource_code
        response.data.item.quantity = quantity
        response.data.cooldown = Mock()
        response.data.cooldown.total_seconds = 5
        response.data.cooldown.remaining_seconds = 5
        response.data.cooldown.expiration = (datetime.now() + timedelta(seconds=5)).isoformat()
        response.data.cooldown.reason = Mock()
        response.data.cooldown.reason.value = "gathering"

        return response

    @staticmethod
    def get_craft_response(
        item_code: str = "iron_sword",
        quantity: int = 1,
        xp_gained: int = 100
    ) -> Mock:
        """Create mock crafting action response"""
        response = Mock()
        response.data = Mock()
        response.data.xp = xp_gained
        response.data.item = Mock()
        response.data.item.code = item_code
        response.data.item.quantity = quantity
        response.data.cooldown = Mock()
        response.data.cooldown.total_seconds = 10
        response.data.cooldown.remaining_seconds = 10
        response.data.cooldown.expiration = (datetime.now() + timedelta(seconds=10)).isoformat()
        response.data.cooldown.reason = Mock()
        response.data.cooldown.reason.value = "crafting"

        return response

    @staticmethod
    def get_rest_response(hp_recovered: int = 50) -> Mock:
        """Create mock rest action response"""
        response = Mock()
        response.data = Mock()
        response.data.hp = 100  # Assuming full recovery for simplicity
        response.data.hp_restored = hp_recovered
        response.data.cooldown = Mock()
        response.data.cooldown.total_seconds = 2
        response.data.cooldown.remaining_seconds = 2
        response.data.cooldown.expiration = (datetime.now() + timedelta(seconds=2)).isoformat()
        response.data.cooldown.reason = Mock()
        response.data.cooldown.reason.value = "rest"

        return response


class GameDataFixtures:
    """Collection of mock game data for testing"""

    @staticmethod
    def get_items_data() -> list[dict[str, Any]]:
        """Get mock items data"""
        return [
            {
                "name": "Copper Ore",
                "code": "copper_ore",
                "level": 1,
                "type": "resource",
                "subtype": "mining",
                "description": "A common ore used in crafting.",
                "effects": [],
                "craft": None
            },
            {
                "name": "Iron Sword",
                "code": "iron_sword",
                "level": 5,
                "type": "weapon",
                "subtype": "sword",
                "description": "A sturdy iron sword.",
                "effects": [
                    {"name": "attack", "value": 15}
                ],
                "craft": {
                    "skill": "weaponcrafting",
                    "level": 5,
                    "items": [
                        {"code": "iron_bar", "quantity": 2},
                        {"code": "ash_wood", "quantity": 1}
                    ]
                }
            },
            {
                "name": "Health Potion",
                "code": "health_potion",
                "level": 1,
                "type": "consumable",
                "subtype": "potion",
                "description": "Restores 50 HP when consumed.",
                "effects": [
                    {"name": "heal", "value": 50}
                ],
                "craft": {
                    "skill": "alchemy",
                    "level": 3,
                    "items": [
                        {"code": "red_berry", "quantity": 3},
                        {"code": "water", "quantity": 1}
                    ]
                }
            },
            {
                "name": "Mithril Pickaxe",
                "code": "mithril_pickaxe",
                "level": 20,
                "type": "tool",
                "subtype": "pickaxe",
                "description": "An advanced mining tool.",
                "effects": [
                    {"name": "mining_efficiency", "value": 25}
                ],
                "craft": {
                    "skill": "gearcrafting",
                    "level": 20,
                    "items": [
                        {"code": "mithril_bar", "quantity": 3},
                        {"code": "hardwood", "quantity": 2}
                    ]
                }
            }
        ]

    @staticmethod
    def get_monsters_data() -> list[dict[str, Any]]:
        """Get mock monsters data"""
        return [
            {
                "name": "Chicken",
                "code": "chicken",
                "level": 1,
                "hp": 10,
                "attack_fire": 0,
                "attack_earth": 5,
                "attack_water": 0,
                "attack_air": 0,
                "res_fire": 0,
                "res_earth": 0,
                "res_water": 0,
                "res_air": 0,
                "min_gold": 1,
                "max_gold": 3,
                "drops": [
                    {"code": "feather", "rate": 50, "min_quantity": 1, "max_quantity": 2},
                    {"code": "raw_chicken", "rate": 100, "min_quantity": 1, "max_quantity": 1}
                ]
            },
            {
                "name": "Goblin",
                "code": "goblin",
                "level": 8,
                "hp": 80,
                "attack_fire": 10,
                "attack_earth": 15,
                "attack_water": 5,
                "attack_air": 0,
                "res_fire": 5,
                "res_earth": 10,
                "res_water": 0,
                "res_air": 0,
                "min_gold": 15,
                "max_gold": 30,
                "drops": [
                    {"code": "goblin_ear", "rate": 25, "min_quantity": 1, "max_quantity": 1},
                    {"code": "copper_ore", "rate": 40, "min_quantity": 1, "max_quantity": 3}
                ]
            },
            {
                "name": "Ancient Dragon",
                "code": "ancient_dragon",
                "level": 45,
                "hp": 5000,
                "attack_fire": 200,
                "attack_earth": 150,
                "attack_water": 100,
                "attack_air": 250,
                "res_fire": 50,
                "res_earth": 40,
                "res_water": 30,
                "res_air": 60,
                "min_gold": 1000,
                "max_gold": 2500,
                "drops": [
                    {"code": "dragon_scale", "rate": 100, "min_quantity": 5, "max_quantity": 10},
                    {"code": "legendary_gem", "rate": 5, "min_quantity": 1, "max_quantity": 1}
                ]
            }
        ]

    @staticmethod
    def get_resources_data() -> list[dict[str, Any]]:
        """Get mock resources data"""
        return [
            {
                "name": "Copper Rocks",
                "code": "copper_rocks",
                "skill": "mining",
                "level": 1,
                "drops": [
                    {"code": "copper_ore", "rate": 100, "min_quantity": 1, "max_quantity": 2}
                ]
            },
            {
                "name": "Iron Rocks",
                "code": "iron_rocks",
                "skill": "mining",
                "level": 10,
                "drops": [
                    {"code": "iron_ore", "rate": 100, "min_quantity": 1, "max_quantity": 2}
                ]
            },
            {
                "name": "Ash Tree",
                "code": "ash_tree",
                "skill": "woodcutting",
                "level": 1,
                "drops": [
                    {"code": "ash_wood", "rate": 100, "min_quantity": 1, "max_quantity": 3}
                ]
            },
            {
                "name": "Pond",
                "code": "pond",
                "skill": "fishing",
                "level": 1,
                "drops": [
                    {"code": "gudgeon", "rate": 80, "min_quantity": 1, "max_quantity": 1},
                    {"code": "trout", "rate": 20, "min_quantity": 1, "max_quantity": 1}
                ]
            }
        ]

    @staticmethod
    def get_maps_data() -> list[dict[str, Any]]:
        """Get mock maps data"""
        return [
            {
                "name": "Spawn Island",
                "skin": "grass1",
                "x": 0,
                "y": 0,
                "content": {
                    "type": "spawn",
                    "code": "spawn"
                }
            },
            {
                "name": "Copper Mine",
                "skin": "cave1",
                "x": 2,
                "y": 0,
                "content": {
                    "type": "resource",
                    "code": "copper_rocks"
                }
            },
            {
                "name": "Goblin Forest",
                "skin": "forest1",
                "x": 1,
                "y": 1,
                "content": {
                    "type": "monster",
                    "code": "goblin"
                }
            },
            {
                "name": "Town Bank",
                "skin": "bank1",
                "x": -1,
                "y": 0,
                "content": {
                    "type": "bank",
                    "code": "bank"
                }
            },
            {
                "name": "Grand Exchange",
                "skin": "market1",
                "x": -2,
                "y": 0,
                "content": {
                    "type": "grand_exchange",
                    "code": "grand_exchange"
                }
            }
        ]


class ErrorResponseFixtures:
    """Collection of mock error responses for testing"""

    @staticmethod
    def get_character_not_found_error() -> Mock:
        """Character not found error (404)"""
        error = Mock()
        error.status_code = 404
        error.detail = "Character not found"
        return error

    @staticmethod
    def get_character_cooldown_error(remaining_seconds: int = 30) -> Mock:
        """Character on cooldown error (499)"""

        error = Mock()
        error.status_code = ArtifactsHTTPStatus["CHARACTER_COOLDOWN"]
        error.detail = f"Character is on cooldown for {remaining_seconds} seconds"
        error.cooldown = Mock()
        error.cooldown.remaining_seconds = remaining_seconds
        error.cooldown.total_seconds = remaining_seconds + 10
        error.cooldown.expiration = (datetime.now() + timedelta(seconds=remaining_seconds)).isoformat()
        return error

    @staticmethod
    def get_inventory_full_error() -> Mock:
        """Inventory full error (497)"""

        error = Mock()
        error.status_code = ArtifactsHTTPStatus["INVENTORY_FULL"]
        error.detail = "Inventory is full"
        return error

    @staticmethod
    def get_rate_limit_error(retry_after: int = 60) -> Mock:
        """Rate limit error (429)"""
        error = Mock()
        error.status_code = 429
        error.detail = "Too many requests"
        error.headers = {"Retry-After": str(retry_after)}
        return error

    @staticmethod
    def get_server_error() -> Mock:
        """Internal server error (500)"""
        error = Mock()
        error.status_code = 500
        error.detail = "Internal server error"
        return error


class APIResponseSequences:
    """Collections of API response sequences for testing workflows"""

    @staticmethod
    def get_character_progression_sequence() -> list[Mock]:
        """Sequence showing character progression from level 1 to 5"""
        return [
            APIResponseFixtures.get_character_response("progression_char", 1),
            APIResponseFixtures.get_character_response("progression_char", 2, {"xp": 500}),
            APIResponseFixtures.get_character_response("progression_char", 3, {"xp": 750}),
            APIResponseFixtures.get_character_response("progression_char", 4, {"xp": 1000}),
            APIResponseFixtures.get_character_response("progression_char", 5, {"xp": 1250})
        ]

    @staticmethod
    def get_combat_sequence() -> list[Mock]:
        """Sequence of combat responses showing wins and losses"""
        return [
            APIResponseFixtures.get_fight_response("win", 100, 20, 5),
            APIResponseFixtures.get_fight_response("win", 120, 25, 8),
            APIResponseFixtures.get_fight_response("lose", 0, 0, 30),  # Character lost
            APIResponseFixtures.get_rest_response(30),  # Recovery
            APIResponseFixtures.get_fight_response("win", 150, 30, 10)
        ]

    @staticmethod
    def get_gathering_and_crafting_sequence() -> list[Mock]:
        """Sequence showing resource gathering and crafting workflow"""
        return [
            APIResponseFixtures.get_gather_response("copper_ore", 1, 25),
            APIResponseFixtures.get_gather_response("copper_ore", 1, 25),
            APIResponseFixtures.get_gather_response("ash_wood", 1, 20),
            APIResponseFixtures.get_craft_response("iron_sword", 1, 100)
        ]


# Convenience functions for test usage
def get_mock_character(level: int = 10, **kwargs: Any) -> Mock:
    """Get a mock character with specified level and customizations"""
    return APIResponseFixtures.get_character_response(level=level, customizations=kwargs)


def get_mock_action_response(action_type: str, **kwargs: Any) -> Mock:
    """Get a mock action response by type"""
    if action_type == "fight":
        return APIResponseFixtures.get_fight_response(**kwargs)
    elif action_type == "move":
        return APIResponseFixtures.get_move_response(kwargs.get('x', 10), kwargs.get('y', 15))
    elif action_type == "gather":
        return APIResponseFixtures.get_gather_response(**kwargs)
    elif action_type == "craft":
        return APIResponseFixtures.get_craft_response(**kwargs)
    elif action_type == "rest":
        return APIResponseFixtures.get_rest_response(**kwargs)
    else:
        raise ValueError(f"Unknown action type: {action_type}")


def get_mock_error(error_type: str, **kwargs: Any) -> Mock:
    """Get a mock error response by type"""
    if error_type == "character_not_found":
        return ErrorResponseFixtures.get_character_not_found_error()
    elif error_type == "cooldown":
        return ErrorResponseFixtures.get_character_cooldown_error(kwargs.get('seconds', 30))
    elif error_type == "inventory_full":
        return ErrorResponseFixtures.get_inventory_full_error()
    elif error_type == "rate_limit":
        return ErrorResponseFixtures.get_rate_limit_error(kwargs.get('retry_after', 60))
    elif error_type == "server_error":
        return ErrorResponseFixtures.get_server_error()
    else:
        raise ValueError(f"Unknown error type: {error_type}")
