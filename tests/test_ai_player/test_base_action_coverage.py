"""
Base Action Coverage Tests

Targets specific uncovered lines in base_action.py to achieve higher coverage.
Focus on exception handling, edge cases, and helper methods that existing tests miss.
"""

import pytest
from typing import Any, Optional
from unittest.mock import Mock, patch

from src.ai_player.actions.base_action import BaseAction
from src.ai_player.state.game_state import GameState
from src.ai_player.state.action_result import ActionResult


class TestAction(BaseAction):
    """Test implementation of BaseAction for testing"""

    @property
    def name(self) -> str:
        return "test_action"

    @property
    def cost(self) -> int:
        return 1

    def get_preconditions(self) -> dict[GameState, Any]:
        return {GameState.CHARACTER_LEVEL: 10}

    def get_effects(self) -> dict[GameState, Any]:
        return {GameState.CHARACTER_XP: 100}

    async def _execute_api_call(
        self,
        character_name: str,
        current_state: dict[GameState, Any],
        api_client: "APIClientWrapper",
        cooldown_manager: Optional["CooldownManager"],
    ) -> ActionResult:
        return ActionResult(success=True, message="Test execution", state_changes={}, cooldown_seconds=0)


class TestBaseActionCoverage:
    """Coverage tests targeting specific uncovered lines in base_action.py"""

    def test_extract_state_changes_from_character_minimal_attributes(self):
        """Test extract_state_changes_from_character with minimal character attributes"""
        # Create a mock character with only basic attributes
        character = Mock()
        character.level = 10
        character.xp = 1500
        character.gold = 250
        character.hp = 80
        character.max_hp = 100
        character.inventory = []
        character.inventory_max_items = 20

        # Remove other attributes to test hasattr checks
        delattr(character, "x") if hasattr(character, "x") else None
        delattr(character, "y") if hasattr(character, "y") else None

        action = TestAction()
        result = action._extract_character_state(character)

        # Should contain the basic stats that were present
        assert result[GameState.CHARACTER_LEVEL] == 10
        assert result[GameState.CHARACTER_XP] == 1500
        assert result[GameState.CHARACTER_GOLD] == 250
        assert result[GameState.HP_CURRENT] == 80
        assert result[GameState.HP_MAX] == 100

        # Should not contain position since it wasn't available
        assert GameState.CURRENT_X not in result
        assert GameState.CURRENT_Y not in result

    def test_extract_state_changes_from_character_with_position(self):
        """Test extract_state_changes_from_character with position attributes"""
        # Create a mock character with position attributes
        character = Mock()
        character.level = 10
        character.xp = 1500
        character.gold = 250
        character.hp = 80
        character.max_hp = 100
        character.x = 5
        character.y = 10
        character.inventory = []
        character.inventory_max_items = 20

        action = TestAction()
        result = action._extract_character_state(character)

        # Should contain position information
        assert result[GameState.CURRENT_X] == 5
        assert result[GameState.CURRENT_Y] == 10

    def test_extract_state_changes_from_character_with_skill_levels(self):
        """Test extract_state_changes_from_character with skill attributes"""
        # Create a mock character with skill attributes
        character = Mock()
        character.level = 10
        character.xp = 1500
        character.gold = 250
        character.hp = 80
        character.max_hp = 100
        character.mining_level = 15
        character.mining_xp = 2500
        character.woodcutting_level = 12
        character.woodcutting_xp = 1800
        character.fishing_level = 8
        character.fishing_xp = 900
        character.weaponcrafting_level = 5
        character.weaponcrafting_xp = 300
        character.gearcrafting_level = 7
        character.gearcrafting_xp = 600
        character.jewelrycrafting_level = 3
        character.jewelrycrafting_xp = 150
        character.cooking_level = 6
        character.cooking_xp = 400
        character.alchemy_level = 4
        character.alchemy_xp = 200
        character.inventory = []
        character.inventory_max_items = 20

        action = TestAction()
        result = action._extract_character_state(character)

        # Should contain skill information
        assert result[GameState.MINING_LEVEL] == 15
        assert result[GameState.MINING_XP] == 2500
        assert result[GameState.WOODCUTTING_LEVEL] == 12
        assert result[GameState.WOODCUTTING_XP] == 1800
        assert result[GameState.FISHING_LEVEL] == 8
        assert result[GameState.FISHING_XP] == 900
        assert result[GameState.WEAPONCRAFTING_LEVEL] == 5
        assert result[GameState.WEAPONCRAFTING_XP] == 300
        assert result[GameState.GEARCRAFTING_LEVEL] == 7
        assert result[GameState.GEARCRAFTING_XP] == 600
        assert result[GameState.JEWELRYCRAFTING_LEVEL] == 3
        assert result[GameState.JEWELRYCRAFTING_XP] == 150
        assert result[GameState.COOKING_LEVEL] == 6
        assert result[GameState.COOKING_XP] == 400
        assert result[GameState.ALCHEMY_LEVEL] == 4
        assert result[GameState.ALCHEMY_XP] == 200

    def test_extract_state_changes_from_character_with_equipment(self):
        """Test extract_state_changes_from_character with equipment attributes"""
        # Create a mock character with equipment attributes
        character = Mock()
        character.level = 10
        character.xp = 1500
        character.gold = 250
        character.hp = 80
        character.max_hp = 100
        character.inventory = []
        character.inventory_max_items = 20
        character.weapon_slot = "iron_sword"
        character.shield_slot = "iron_shield"
        character.helmet_slot = "iron_helmet"
        character.body_armor_slot = "iron_plate"
        character.leg_armor_slot = "iron_leggings"
        character.boots_slot = "iron_boots"
        character.ring1_slot = "copper_ring"
        character.ring2_slot = "silver_ring"
        character.amulet_slot = "strength_amulet"

        action = TestAction()
        result = action._extract_character_state(character)

        # Should contain equipment information
        assert result[GameState.WEAPON_EQUIPPED] is True
        assert result[GameState.SHIELD_EQUIPPED] is True
        assert result[GameState.BODY_ARMOR_EQUIPPED] is True
        assert result[GameState.LEG_ARMOR_EQUIPPED] is True
        assert result[GameState.RING1_EQUIPPED] is True
        assert result[GameState.RING2_EQUIPPED] is True
        assert result[GameState.AMULET_EQUIPPED] is True

    def test_extract_state_changes_from_character_missing_optional_attributes(self):
        """Test extract_state_changes_from_character when optional attributes are missing"""
        # Create a minimal character with only required attributes
        character = Mock()
        character.level = 5
        character.hp = 50
        character.inventory = []
        character.inventory_max_items = 20

        # Explicitly remove optional attributes that might exist on Mock
        optional_attrs = [
            "xp",
            "gold",
            "max_hp",
            "x",
            "y",
            "mining_level",
            "mining_xp",
            "woodcutting_level",
            "woodcutting_xp",
            "fishing_level",
            "fishing_xp",
            "weaponcrafting_level",
            "weaponcrafting_xp",
            "gearcrafting_level",
            "gearcrafting_xp",
            "jewelrycrafting_level",
            "jewelrycrafting_xp",
            "cooking_level",
            "cooking_xp",
            "alchemy_level",
            "alchemy_xp",
            "weapon_slot",
            "shield_slot",
            "helmet_slot",
            "body_armor_slot",
            "leg_armor_slot",
            "boots_slot",
            "ring1_slot",
            "ring2_slot",
            "amulet_slot",
        ]

        for attr in optional_attrs:
            if hasattr(character, attr):
                delattr(character, attr)

        action = TestAction()
        result = action._extract_character_state(character)

        # Should only contain the attributes that were present
        assert result[GameState.CHARACTER_LEVEL] == 5
        assert result[GameState.HP_CURRENT] == 50

        # Should not contain any of the optional attributes
        assert GameState.CHARACTER_XP not in result
        assert GameState.CHARACTER_GOLD not in result
        assert GameState.HP_MAX not in result
        assert GameState.CURRENT_X not in result
        assert GameState.CURRENT_Y not in result

    def test_extract_state_changes_from_character_empty_object(self):
        """Test extract_state_changes_from_character with object that has no relevant attributes"""
        # Create an empty object
        character = type("EmptyCharacter", (), {})()

        action = TestAction()
        result = action._extract_character_state(character)

        # Should return empty dictionary since no attributes match
        assert result == {}

    def test_satisfies_precondition_with_none_values(self):
        """Test _satisfies_precondition with None values"""
        action = TestAction()
        result = action._satisfies_precondition(GameState.CHARACTER_LEVEL, None, None)
        assert result is False

    def test_validate_preconditions_edge_cases(self):
        """Test validate_preconditions with edge cases"""
        action = TestAction()

        # Test with valid preconditions
        assert action.validate_preconditions() is True

        # Test with invalid preconditions
        with patch.object(action, "get_preconditions", return_value=None):
            assert action.validate_preconditions() is False

    def test_validate_effects_edge_cases(self):
        """Test validate_effects with edge cases"""
        action = TestAction()

        # Test with valid effects
        assert action.validate_effects() is True

        # Test with invalid effects
        with patch.object(action, "get_effects", return_value=None):
            assert action.validate_effects() is False
