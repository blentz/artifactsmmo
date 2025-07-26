"""
Comprehensive tests for tests.fixtures.api_responses module

This module provides complete test coverage for all API response fixture
classes and convenience functions to ensure they generate valid mock data.
"""

import pytest
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import Mock

from tests.fixtures.api_responses import (
    APIResponseFixtures,
    GameDataFixtures,
    ErrorResponseFixtures,
    APIResponseSequences,
    get_mock_character,
    get_mock_action_response,
    get_mock_error
)
from src.lib.httpstatus import ArtifactsHTTPStatus


class TestAPIResponseFixtures:
    """Test suite for APIResponseFixtures class"""

    def test_get_character_response_default(self):
        """Test get_character_response with default parameters"""
        character = APIResponseFixtures.get_character_response()
        
        # Basic attributes
        assert character.name == "test_character"
        assert character.level == 10
        assert character.xp == 2500  # level * 250
        assert character.max_xp == 2750  # (level + 1) * 250
        assert character.gold == 1000  # level * 100
        assert character.hp == 120  # 80 + (level * 4)
        assert character.max_hp == 140  # 100 + (level * 4)
        assert character.x == 20  # 10 + level
        assert character.y == 25  # 15 + level
        assert character.cooldown == 0
        assert character.cooldown_expiration is None
        assert character.server == "1"
        assert character.account == "test_account"
        assert character.skin == "men1"
        
        # Skills - should be level-appropriate
        assert character.mining_level == 8  # max(1, level - 2)
        assert character.woodcutting_level == 7  # max(1, level - 3)
        assert character.fishing_level == 6  # max(1, level - 4)
        
        # Equipment - level-appropriate
        assert character.weapon_slot == "iron_sword"  # level >= 5
        assert character.helmet_slot == "leather_helmet"  # level >= 3
        assert character.body_armor_slot == "iron_chestplate"  # level >= 7
        assert character.leg_armor_slot == "leather_pants"  # level >= 4
        assert character.boots_slot == "leather_boots"  # level >= 2
        
        # Inventory
        assert character.inventory_max_items == 22  # 20 + (level // 5)
        assert len(character.inventory) == 3  # level >= 5
        
        # Bank
        assert character.bank_max_items == 55  # 50 + (level // 2)
        assert character.bank_gold == 500  # level * 50

    def test_get_character_response_custom_level(self):
        """Test get_character_response with custom level"""
        character = APIResponseFixtures.get_character_response(level=1)
        
        assert character.level == 1
        assert character.xp == 250
        assert character.max_xp == 500
        assert character.mining_level == 1  # max(1, 1-2) = max(1, -1) = 1
        assert character.weapon_slot is None  # level < 5
        assert character.helmet_slot is None  # level < 3
        assert character.inventory == []  # level < 5

    def test_get_character_response_with_customizations(self):
        """Test get_character_response with customizations"""
        customizations = {
            "name": "custom_char",
            "gold": 5000,
            "hp": 50
        }
        character = APIResponseFixtures.get_character_response(
            name="overridden_name", 
            level=15, 
            customizations=customizations
        )
        
        assert character.name == "custom_char"  # Customization overrides
        assert character.level == 15
        assert character.gold == 5000  # Customized
        assert character.hp == 50  # Customized

    def test_get_character_on_cooldown(self):
        """Test get_character_on_cooldown"""
        character = APIResponseFixtures.get_character_on_cooldown(
            name="cooldown_char",
            cooldown_seconds=45,
            reason="mining"
        )
        
        assert character.name == "cooldown_char"
        assert character.cooldown == 45
        assert character.cooldown_expiration is not None
        
        # Check cooldown details
        assert hasattr(character, 'cooldown_details')
        assert character.cooldown_details.total_seconds == 45
        assert character.cooldown_details.remaining_seconds == 45
        assert character.cooldown_details.reason.value == "mining"
        
        # Verify expiration time is in the future
        expiration = datetime.fromisoformat(character.cooldown_expiration)
        assert expiration > datetime.now()

    def test_get_fight_response_default(self):
        """Test get_fight_response with default parameters"""
        response = APIResponseFixtures.get_fight_response()
        
        assert response.data.xp == 150
        assert response.data.gold == 25
        assert response.data.hp == 80  # 90 - 10 hp_lost
        assert response.data.fight.result == "win"
        assert response.data.fight.xp == 150
        assert response.data.fight.gold == 25
        assert len(response.data.fight.drops) == 1
        assert response.data.fight.drops[0]["code"] == "feather"
        assert response.data.fight.logs == ["You fought a monster and win!"]
        
        # Cooldown
        assert response.data.cooldown.total_seconds == 8
        assert response.data.cooldown.remaining_seconds == 8
        assert response.data.cooldown.reason.value == "fight"

    def test_get_fight_response_custom(self):
        """Test get_fight_response with custom parameters"""
        custom_drops = [
            {"code": "gold_coin", "quantity": 5},
            {"code": "potion", "quantity": 1}
        ]
        response = APIResponseFixtures.get_fight_response(
            result="lose",
            xp_gained=0,
            gold_gained=0,
            hp_lost=40,
            drops=custom_drops
        )
        
        assert response.data.fight.result == "lose"
        assert response.data.xp == 0
        assert response.data.gold == 0
        assert response.data.hp == 50  # 90 - 40
        assert response.data.fight.drops == custom_drops
        assert response.data.fight.logs == ["You fought a monster and lose!"]

    def test_get_move_response(self):
        """Test get_move_response"""
        response = APIResponseFixtures.get_move_response(25, 35)
        
        assert response.data.x == 25
        assert response.data.y == 35
        assert response.data.cooldown.total_seconds == 3
        assert response.data.cooldown.remaining_seconds == 3
        assert response.data.cooldown.reason.value == "move"

    def test_get_gather_response_default(self):
        """Test get_gather_response with default parameters"""
        response = APIResponseFixtures.get_gather_response()
        
        assert response.data.xp == 50
        assert response.data.item.code == "copper_ore"
        assert response.data.item.quantity == 1
        assert response.data.cooldown.total_seconds == 5
        assert response.data.cooldown.reason.value == "gathering"

    def test_get_gather_response_custom(self):
        """Test get_gather_response with custom parameters"""
        response = APIResponseFixtures.get_gather_response(
            resource_code="iron_ore",
            quantity=3,
            xp_gained=75
        )
        
        assert response.data.xp == 75
        assert response.data.item.code == "iron_ore"
        assert response.data.item.quantity == 3

    def test_get_craft_response_default(self):
        """Test get_craft_response with default parameters"""
        response = APIResponseFixtures.get_craft_response()
        
        assert response.data.xp == 100
        assert response.data.item.code == "iron_sword"
        assert response.data.item.quantity == 1
        assert response.data.cooldown.total_seconds == 10
        assert response.data.cooldown.reason.value == "crafting"

    def test_get_craft_response_custom(self):
        """Test get_craft_response with custom parameters"""
        response = APIResponseFixtures.get_craft_response(
            item_code="leather_boots",
            quantity=2,
            xp_gained=75
        )
        
        assert response.data.xp == 75
        assert response.data.item.code == "leather_boots"
        assert response.data.item.quantity == 2

    def test_get_rest_response_default(self):
        """Test get_rest_response with default parameters"""
        response = APIResponseFixtures.get_rest_response()
        
        assert response.data.hp == 100
        assert response.data.hp_restored == 50
        assert response.data.cooldown.total_seconds == 2
        assert response.data.cooldown.reason.value == "rest"

    def test_get_rest_response_custom(self):
        """Test get_rest_response with custom parameters"""
        response = APIResponseFixtures.get_rest_response(hp_recovered=25)
        
        assert response.data.hp_restored == 25


class TestGameDataFixtures:
    """Test suite for GameDataFixtures class"""

    def test_get_items_data(self):
        """Test get_items_data returns valid item data"""
        items = GameDataFixtures.get_items_data()
        
        assert isinstance(items, list)
        assert len(items) >= 4  # We expect at least 4 items
        
        # Check first item (Copper Ore)
        copper_ore = items[0]
        assert copper_ore["name"] == "Copper Ore"
        assert copper_ore["code"] == "copper_ore"
        assert copper_ore["level"] == 1
        assert copper_ore["type"] == "resource"
        assert copper_ore["subtype"] == "mining"
        assert copper_ore["craft"] is None
        
        # Check weapon item (Iron Sword)
        iron_sword = next(item for item in items if item["code"] == "iron_sword")
        assert iron_sword["name"] == "Iron Sword"
        assert iron_sword["type"] == "weapon"
        assert iron_sword["level"] == 5
        assert len(iron_sword["effects"]) == 1
        assert iron_sword["effects"][0]["name"] == "attack"
        assert iron_sword["craft"] is not None
        assert iron_sword["craft"]["skill"] == "weaponcrafting"

    def test_get_monsters_data(self):
        """Test get_monsters_data returns valid monster data"""
        monsters = GameDataFixtures.get_monsters_data()
        
        assert isinstance(monsters, list)
        assert len(monsters) >= 3  # We expect at least 3 monsters
        
        # Check first monster (Chicken)
        chicken = monsters[0]
        assert chicken["name"] == "Chicken"
        assert chicken["code"] == "chicken"
        assert chicken["level"] == 1
        assert chicken["hp"] == 10
        assert chicken["min_gold"] == 1
        assert chicken["max_gold"] == 3
        assert len(chicken["drops"]) == 2
        
        # Check high-level monster (Ancient Dragon)
        dragon = next(monster for monster in monsters if monster["code"] == "ancient_dragon")
        assert dragon["name"] == "Ancient Dragon"
        assert dragon["level"] == 45
        assert dragon["hp"] == 5000
        assert dragon["min_gold"] == 1000
        assert dragon["max_gold"] == 2500

    def test_get_resources_data(self):
        """Test get_resources_data returns valid resource data"""
        resources = GameDataFixtures.get_resources_data()
        
        assert isinstance(resources, list)
        assert len(resources) >= 4  # We expect at least 4 resources
        
        # Check mining resource
        copper_rocks = resources[0]
        assert copper_rocks["name"] == "Copper Rocks"
        assert copper_rocks["code"] == "copper_rocks"
        assert copper_rocks["skill"] == "mining"
        assert copper_rocks["level"] == 1
        assert len(copper_rocks["drops"]) == 1
        
        # Check fishing resource
        pond = next(resource for resource in resources if resource["code"] == "pond")
        assert pond["skill"] == "fishing"
        assert len(pond["drops"]) == 2  # Multiple possible fish

    def test_get_maps_data(self):
        """Test get_maps_data returns valid map data"""
        maps = GameDataFixtures.get_maps_data()
        
        assert isinstance(maps, list)
        assert len(maps) >= 5  # We expect at least 5 map locations
        
        # Check spawn location
        spawn = maps[0]
        assert spawn["name"] == "Spawn Island"
        assert spawn["x"] == 0
        assert spawn["y"] == 0
        assert spawn["content"]["type"] == "spawn"
        
        # Check resource location
        copper_mine = next(location for location in maps if location["name"] == "Copper Mine")
        assert copper_mine["content"]["type"] == "resource"
        assert copper_mine["content"]["code"] == "copper_rocks"


class TestErrorResponseFixtures:
    """Test suite for ErrorResponseFixtures class"""

    def test_get_character_not_found_error(self):
        """Test get_character_not_found_error"""
        error = ErrorResponseFixtures.get_character_not_found_error()
        
        assert error.status_code == 404
        assert error.detail == "Character not found"

    def test_get_character_cooldown_error(self):
        """Test get_character_cooldown_error"""
        error = ErrorResponseFixtures.get_character_cooldown_error(60)
        
        assert error.status_code == ArtifactsHTTPStatus["CHARACTER_COOLDOWN"]
        assert "60 seconds" in error.detail
        assert error.cooldown.remaining_seconds == 60
        assert error.cooldown.total_seconds == 70  # remaining + 10
        
        # Verify expiration is in the future
        expiration = datetime.fromisoformat(error.cooldown.expiration)
        assert expiration > datetime.now()

    def test_get_inventory_full_error(self):
        """Test get_inventory_full_error"""
        error = ErrorResponseFixtures.get_inventory_full_error()
        
        assert error.status_code == ArtifactsHTTPStatus["INVENTORY_FULL"]
        assert error.detail == "Inventory is full"

    def test_get_rate_limit_error(self):
        """Test get_rate_limit_error"""
        error = ErrorResponseFixtures.get_rate_limit_error(120)
        
        assert error.status_code == 429
        assert error.detail == "Too many requests"
        assert error.headers["Retry-After"] == "120"

    def test_get_server_error(self):
        """Test get_server_error"""
        error = ErrorResponseFixtures.get_server_error()
        
        assert error.status_code == 500
        assert error.detail == "Internal server error"


class TestAPIResponseSequences:
    """Test suite for APIResponseSequences class"""

    def test_get_character_progression_sequence(self):
        """Test get_character_progression_sequence"""
        sequence = APIResponseSequences.get_character_progression_sequence()
        
        assert isinstance(sequence, list)
        assert len(sequence) == 5  # Levels 1-5
        
        # Verify progression
        for i, character in enumerate(sequence):
            expected_level = i + 1
            assert character.level == expected_level
            assert character.name == "progression_char"
        
        # Check XP progression
        assert sequence[1].xp == 500  # Level 2
        assert sequence[2].xp == 750  # Level 3
        assert sequence[4].xp == 1250  # Level 5

    def test_get_combat_sequence(self):
        """Test get_combat_sequence"""
        sequence = APIResponseSequences.get_combat_sequence()
        
        assert isinstance(sequence, list)
        assert len(sequence) == 5
        
        # First two should be wins
        assert sequence[0].data.fight.result == "win"
        assert sequence[1].data.fight.result == "win"
        
        # Third should be a loss
        assert sequence[2].data.fight.result == "lose"
        assert sequence[2].data.xp == 0
        assert sequence[2].data.gold == 0
        
        # Fourth should be rest response
        assert hasattr(sequence[3].data, 'hp_restored')
        
        # Fifth should be another win
        assert sequence[4].data.fight.result == "win"

    def test_get_gathering_and_crafting_sequence(self):
        """Test get_gathering_and_crafting_sequence"""
        sequence = APIResponseSequences.get_gathering_and_crafting_sequence()
        
        assert isinstance(sequence, list)
        assert len(sequence) == 4
        
        # First three should be gathering
        assert sequence[0].data.item.code == "copper_ore"
        assert sequence[1].data.item.code == "copper_ore"
        assert sequence[2].data.item.code == "ash_wood"
        
        # Fourth should be crafting
        assert sequence[3].data.item.code == "iron_sword"


class TestConvenienceFunctions:
    """Test suite for convenience functions"""

    def test_get_mock_character(self):
        """Test get_mock_character convenience function"""
        # Default usage
        character = get_mock_character()
        assert character.level == 10
        
        # Custom level
        character_level_5 = get_mock_character(level=5)
        assert character_level_5.level == 5
        
        # Custom attributes
        character_custom = get_mock_character(level=15, name="custom_char")
        assert character_custom.level == 15
        assert character_custom.name == "custom_char"

    def test_get_mock_action_response_valid_actions(self):
        """Test get_mock_action_response with valid action types"""
        # Fight action
        fight_response = get_mock_action_response("fight")
        assert hasattr(fight_response.data, 'fight')
        
        # Move action
        move_response = get_mock_action_response("move", x=10, y=15)
        assert move_response.data.x == 10
        assert move_response.data.y == 15
        
        # Gather action
        gather_response = get_mock_action_response("gather")
        assert hasattr(gather_response.data, 'item')
        
        # Craft action
        craft_response = get_mock_action_response("craft")
        assert hasattr(craft_response.data, 'item')
        
        # Rest action
        rest_response = get_mock_action_response("rest")
        assert hasattr(rest_response.data, 'hp_restored')

    def test_get_mock_action_response_invalid_action(self):
        """Test get_mock_action_response with invalid action type"""
        with pytest.raises(ValueError, match="Unknown action type: invalid_action"):
            get_mock_action_response("invalid_action")

    def test_get_mock_error_valid_types(self):
        """Test get_mock_error with valid error types"""
        # Character not found
        error = get_mock_error("character_not_found")
        assert error.status_code == 404
        
        # Cooldown error
        cooldown_error = get_mock_error("cooldown", seconds=45)
        assert cooldown_error.cooldown.remaining_seconds == 45
        
        # Inventory full
        inventory_error = get_mock_error("inventory_full")
        assert inventory_error.status_code == ArtifactsHTTPStatus["INVENTORY_FULL"]
        
        # Rate limit
        rate_limit_error = get_mock_error("rate_limit", retry_after=90)
        assert rate_limit_error.headers["Retry-After"] == "90"
        
        # Server error
        server_error = get_mock_error("server_error")
        assert server_error.status_code == 500

    def test_get_mock_error_invalid_type(self):
        """Test get_mock_error with invalid error type"""
        with pytest.raises(ValueError, match="Unknown error type: invalid_error"):
            get_mock_error("invalid_error")


class TestMockObjectProperties:
    """Test suite to verify mock objects have proper structure"""

    def test_character_mock_attributes(self):
        """Test that character mocks have all expected attributes"""
        character = APIResponseFixtures.get_character_response()
        
        # Basic character attributes
        required_attrs = [
            'name', 'level', 'xp', 'max_xp', 'gold', 'hp', 'max_hp',
            'x', 'y', 'cooldown', 'cooldown_expiration', 'server', 'account', 'skin'
        ]
        for attr in required_attrs:
            assert hasattr(character, attr), f"Missing attribute: {attr}"
        
        # Skill attributes
        skill_attrs = [
            'mining_level', 'mining_xp', 'mining_max_xp',
            'woodcutting_level', 'woodcutting_xp', 'woodcutting_max_xp',
            'fishing_level', 'fishing_xp', 'fishing_max_xp'
        ]
        for attr in skill_attrs:
            assert hasattr(character, attr), f"Missing skill attribute: {attr}"
        
        # Equipment slots
        equipment_attrs = [
            'weapon_slot', 'shield_slot', 'helmet_slot', 'body_armor_slot',
            'leg_armor_slot', 'boots_slot', 'ring1_slot', 'ring2_slot',
            'amulet_slot', 'artifact1_slot', 'artifact2_slot', 'artifact3_slot',
            'consumable1_slot', 'consumable2_slot'
        ]
        for attr in equipment_attrs:
            assert hasattr(character, attr), f"Missing equipment attribute: {attr}"

    def test_action_response_structure(self):
        """Test that action responses have proper structure"""
        fight_response = APIResponseFixtures.get_fight_response()
        
        # Data object exists
        assert hasattr(fight_response, 'data')
        
        # Fight-specific data
        assert hasattr(fight_response.data, 'fight')
        assert hasattr(fight_response.data.fight, 'result')
        assert hasattr(fight_response.data.fight, 'xp')
        assert hasattr(fight_response.data.fight, 'gold')
        assert hasattr(fight_response.data.fight, 'drops')
        assert hasattr(fight_response.data.fight, 'logs')
        
        # Cooldown structure
        assert hasattr(fight_response.data, 'cooldown')
        assert hasattr(fight_response.data.cooldown, 'total_seconds')
        assert hasattr(fight_response.data.cooldown, 'remaining_seconds')
        assert hasattr(fight_response.data.cooldown, 'expiration')
        assert hasattr(fight_response.data.cooldown, 'reason')
        assert hasattr(fight_response.data.cooldown.reason, 'value')

    def test_error_response_structure(self):
        """Test that error responses have proper structure"""
        cooldown_error = ErrorResponseFixtures.get_character_cooldown_error()
        
        assert hasattr(cooldown_error, 'status_code')
        assert hasattr(cooldown_error, 'detail')
        assert hasattr(cooldown_error, 'cooldown')
        assert hasattr(cooldown_error.cooldown, 'remaining_seconds')
        assert hasattr(cooldown_error.cooldown, 'total_seconds')
        assert hasattr(cooldown_error.cooldown, 'expiration')


class TestDataConsistency:
    """Test suite to verify data consistency across fixtures"""

    def test_character_level_consistency(self):
        """Test that character attributes are consistent with level"""
        # Test low level character
        low_level = APIResponseFixtures.get_character_response(level=1)
        assert low_level.mining_level == 1  # Should be 1 due to max(1, level-2)
        assert low_level.weapon_slot is None  # Too low level for weapon
        
        # Test higher level character
        high_level = APIResponseFixtures.get_character_response(level=20)
        assert high_level.mining_level == 18  # level - 2
        assert high_level.weapon_slot == "iron_sword"  # High enough for weapon

    def test_cooldown_consistency(self):
        """Test that cooldown data is consistent"""
        character = APIResponseFixtures.get_character_on_cooldown(cooldown_seconds=30)
        
        # Cooldown value should match
        assert character.cooldown == 30
        assert character.cooldown_details.remaining_seconds == 30
        assert character.cooldown_details.total_seconds == 30
        
        # Expiration should be approximately 30 seconds from now
        expiration = datetime.fromisoformat(character.cooldown_expiration)
        now = datetime.now()
        time_diff = (expiration - now).total_seconds()
        assert 25 <= time_diff <= 35  # Allow some tolerance for execution time

    def test_game_data_structure_consistency(self):
        """Test that game data has consistent structure"""
        items = GameDataFixtures.get_items_data()
        
        for item in items:
            # All items should have basic fields
            assert "name" in item
            assert "code" in item
            assert "level" in item
            assert "type" in item
            assert "description" in item
            
            # Items with craft should have proper structure
            if item["craft"] is not None:
                assert "skill" in item["craft"]
                assert "level" in item["craft"]
                assert "items" in item["craft"]
                assert isinstance(item["craft"]["items"], list)