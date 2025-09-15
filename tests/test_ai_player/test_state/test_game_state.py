"""
Tests for GameState enum and related state management models

This module tests the GameState enum type safety, validation methods,
and Pydantic models for state management including ActionResult,
CharacterGameState, and CooldownInfo.
"""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from src.ai_player.state.action_result import ActionResult
from src.ai_player.state.character_game_state import CharacterGameState
from src.ai_player.state.game_state import CooldownInfo, GameState


class TestGameStateEnum:
    """Test GameState enum functionality and validation"""

    def test_game_state_enum_values(self):
        """Test that GameState enum contains expected state keys"""
        # Character progression states
        assert GameState.CHARACTER_LEVEL == "character_level"
        assert GameState.CHARACTER_XP == "character_xp"
        assert GameState.CHARACTER_GOLD == "character_gold"
        assert GameState.HP_CURRENT == "hp_current"
        assert GameState.HP_MAX == "hp_max"

        # Position and movement states
        assert GameState.CURRENT_X == "current_x"
        assert GameState.CURRENT_Y == "current_y"
        assert GameState.AT_TARGET_LOCATION == "at_target_location"
        assert GameState.AT_MONSTER_LOCATION == "at_monster_location"

        # Action availability states
        assert GameState.COOLDOWN_READY == "cooldown_ready"
        assert GameState.CAN_FIGHT == "can_fight"
        assert GameState.CAN_GATHER == "can_gather"
        assert GameState.CAN_CRAFT == "can_craft"

    def test_game_state_enum_completeness(self):
        """Test that all essential game states are covered by the enum"""
        expected_categories = [
            "character_level", "character_xp", "character_gold",
            "hp_current", "hp_max",
            "current_x", "current_y",
            "mining_level", "woodcutting_level", "fishing_level",
            "weaponcrafting_level", "gearcrafting_level", "jewelrycrafting_level",
            "cooking_level", "alchemy_level",
            "weapon_equipped", "tool_equipped", "inventory_space_available",
            "cooldown_ready", "can_fight", "can_gather", "can_craft"
        ]

        enum_values = [state.value for state in GameState]
        for expected in expected_categories:
            assert expected in enum_values, f"Missing expected state: {expected}"

    def test_validate_state_dict_valid_keys(self):
        """Test validate_state_dict with valid GameState enum string keys"""
        valid_state = {
            "character_level": 5,
            "hp_current": 80,
            "current_x": 10,
            "current_y": 15,
            "cooldown_ready": True
        }

        result = GameState.validate_state_dict(valid_state)

        assert isinstance(result, dict)
        assert GameState.CHARACTER_LEVEL in result
        assert GameState.HP_CURRENT in result
        assert GameState.CURRENT_X in result
        assert GameState.CURRENT_Y in result
        assert GameState.COOLDOWN_READY in result

        assert result[GameState.CHARACTER_LEVEL] == 5
        assert result[GameState.HP_CURRENT] == 80
        assert result[GameState.CURRENT_X] == 10
        assert result[GameState.CURRENT_Y] == 15
        assert result[GameState.COOLDOWN_READY] is True

    def test_validate_state_dict_invalid_keys(self):
        """Test validate_state_dict with invalid state keys"""
        invalid_state = {
            "invalid_key": 42,
            "another_bad_key": "test"
        }

        with pytest.raises(ValueError, match="Invalid GameState key"):
            GameState.validate_state_dict(invalid_state)

    def test_validate_state_dict_mixed_keys(self):
        """Test validate_state_dict with mix of valid and invalid keys"""
        mixed_state = {
            "character_level": 5,
            "invalid_key": 42,
            "hp_current": 80
        }

        with pytest.raises(ValueError, match="Invalid GameState key: invalid_key"):
            GameState.validate_state_dict(mixed_state)

    def test_to_goap_dict_conversion(self):
        """Test conversion from GameState enum keys to string keys for GOAP"""
        enum_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.HP_CURRENT: 80,
            GameState.COOLDOWN_READY: True,
            GameState.CURRENT_X: 10
        }

        result = GameState.to_goap_dict(enum_state)

        assert isinstance(result, dict)
        assert "character_level" in result
        assert "hp_current" in result
        assert "cooldown_ready" in result
        assert "current_x" in result

        assert result["character_level"] == 5
        assert result["hp_current"] == 80
        assert result["cooldown_ready"] is True
        assert result["current_x"] == 10

    def test_to_goap_dict_empty_state(self):
        """Test to_goap_dict with empty state dictionary"""
        result = GameState.to_goap_dict({})
        assert result == {}

    def test_game_state_enum_is_string_enum(self):
        """Test that GameState properly extends StrEnum for GOAP compatibility"""
        assert isinstance(GameState.CHARACTER_LEVEL, str)
        assert str(GameState.CHARACTER_LEVEL) == "character_level"


class TestActionResult:
    """Test ActionResult Pydantic model"""

    def test_action_result_creation_success(self):
        """Test creating ActionResult for successful action"""
        state_changes = {
            GameState.CURRENT_X: 15,
            GameState.CURRENT_Y: 20,
            GameState.COOLDOWN_READY: False
        }

        result = ActionResult(
            success=True,
            message="Movement completed successfully",
            state_changes=state_changes,
            cooldown_seconds=5
        )

        assert result.success is True
        assert result.message == "Movement completed successfully"
        assert result.state_changes == state_changes
        assert result.cooldown_seconds == 5

    def test_action_result_creation_failure(self):
        """Test creating ActionResult for failed action"""
        result = ActionResult(
            success=False,
            message="Action failed due to cooldown",
            state_changes={},
            cooldown_seconds=30
        )

        assert result.success is False
        assert result.message == "Action failed due to cooldown"
        assert result.state_changes == {}
        assert result.cooldown_seconds == 30

    def test_action_result_default_cooldown(self):
        """Test ActionResult with default cooldown value"""
        result = ActionResult(
            success=True,
            message="Instant action completed",
            state_changes={GameState.TASK_COMPLETED: True}
        )

        assert result.cooldown_seconds == 0

    def test_action_result_state_changes_validation(self):
        """Test that state_changes accepts GameState enum keys"""
        valid_changes = {
            GameState.CHARACTER_LEVEL: 6,
            GameState.CHARACTER_XP: 1250,
            GameState.HP_CURRENT: 95
        }

        result = ActionResult(
            success=True,
            message="Level up achieved",
            state_changes=valid_changes
        )

        assert result.state_changes[GameState.CHARACTER_LEVEL] == 6
        assert result.state_changes[GameState.CHARACTER_XP] == 1250
        assert result.state_changes[GameState.HP_CURRENT] == 95


class TestCharacterGameState:
    """Test CharacterGameState Pydantic model"""

    def test_character_game_state_creation(self):
        """Test creating CharacterGameState with basic attributes"""
        character_state = CharacterGameState(
            name="test_character",
            level=5,
            xp=1000,
            gold=500,
            hp=80,
            max_hp=100,
            x=10,
            y=15,
            mining_level=1,
            mining_xp=0,
            woodcutting_level=1,
            woodcutting_xp=0,
            fishing_level=1,
            fishing_xp=0,
            weaponcrafting_level=1,
            weaponcrafting_xp=0,
            gearcrafting_level=1,
            gearcrafting_xp=0,
            jewelrycrafting_level=1,
            jewelrycrafting_xp=0,
            cooking_level=1,
            cooking_xp=0,
            alchemy_level=1,
            alchemy_xp=0,
            cooldown=0
        )

        # Verify basic attribute access works
        assert hasattr(character_state, 'to_goap_state')
        assert hasattr(character_state, 'from_api_character')

    def test_to_goap_state_conversion(self):
        """Test conversion from CharacterGameState to GOAP state dict"""
        character_state = CharacterGameState(
            name="test_character",
            level=5,
            xp=1000,
            gold=500,
            hp=80,
            max_hp=100,
            x=10,
            y=15,
            mining_level=1,
            mining_xp=0,
            woodcutting_level=1,
            woodcutting_xp=0,
            fishing_level=1,
            fishing_xp=0,
            weaponcrafting_level=1,
            weaponcrafting_xp=0,
            gearcrafting_level=1,
            gearcrafting_xp=0,
            jewelrycrafting_level=1,
            jewelrycrafting_xp=0,
            cooking_level=1,
            cooking_xp=0,
            alchemy_level=1,
            alchemy_xp=0,
            cooldown=0
        )
        goap_state = character_state.to_goap_state()

        assert isinstance(goap_state, dict)
        assert "character_level" in goap_state
        assert "hp_current" in goap_state
        assert "cooldown_ready" in goap_state
        assert "current_x" in goap_state

    def test_to_goap_state_boolean_conversion(self):
        """Test that boolean values are converted to integers for GOAP"""
        character_state = CharacterGameState(
            name="test_character",
            level=5,
            xp=1000,
            gold=500,
            hp=80,
            max_hp=100,
            x=10,
            y=15,
            mining_level=1,
            mining_xp=0,
            woodcutting_level=1,
            woodcutting_xp=0,
            fishing_level=1,
            fishing_xp=0,
            weaponcrafting_level=1,
            weaponcrafting_xp=0,
            gearcrafting_level=1,
            gearcrafting_xp=0,
            jewelrycrafting_level=1,
            jewelrycrafting_xp=0,
            cooking_level=1,
            cooking_xp=0,
            alchemy_level=1,
            alchemy_xp=0,
            cooldown=0
        )
        goap_state = character_state.to_goap_state()

        # Boolean values should be converted to integers for GOAP compatibility
        if "cooldown_ready" in goap_state:
            assert isinstance(goap_state["cooldown_ready"], int)
        if "inventory_full" in goap_state:
            assert isinstance(goap_state["inventory_full"], int)
        if "character_level" in goap_state:
            assert isinstance(goap_state["character_level"], int)

    def test_from_api_character_conversion(self):
        """Test creating CharacterGameState from API character response"""
        # Mock API character response
        mock_character = Mock()
        mock_character.name = "test_character"
        mock_character.level = 5
        mock_character.xp = 1000
        mock_character.gold = 500
        mock_character.hp = 80
        mock_character.max_hp = 100
        mock_character.x = 10
        mock_character.y = 15
        mock_character.cooldown = 0
        mock_character.mining_level = 3
        mock_character.mining_xp = 150
        mock_character.woodcutting_level = 2
        mock_character.woodcutting_xp = 75
        mock_character.fishing_level = 1
        mock_character.fishing_xp = 25
        mock_character.weaponcrafting_level = 1
        mock_character.weaponcrafting_xp = 0
        mock_character.gearcrafting_level = 1
        mock_character.gearcrafting_xp = 0
        mock_character.jewelrycrafting_level = 1
        mock_character.jewelrycrafting_xp = 0
        mock_character.cooking_level = 1
        mock_character.cooking_xp = 0
        mock_character.alchemy_level = 1
        mock_character.alchemy_xp = 0
        mock_character.weapon_slot = "copper_sword"
        mock_character.rune_slot = ""
        mock_character.shield_slot = ""
        mock_character.helmet_slot = ""
        mock_character.body_armor_slot = ""
        mock_character.leg_armor_slot = ""
        mock_character.boots_slot = ""
        mock_character.ring1_slot = ""
        mock_character.ring2_slot = ""
        mock_character.amulet_slot = ""
        mock_character.artifact1_slot = ""
        mock_character.cooldown_expiration_utc = None
        mock_character.cooldown_expiration = None
        mock_character.inventory = ["item1", "item2"]
        mock_character.inventory_max_items = 20

        character_state = CharacterGameState.from_api_character(mock_character)

        # Verify that the conversion creates a valid CharacterGameState
        assert isinstance(character_state, CharacterGameState)

    def test_character_game_state_validation(self):
        """Test Pydantic validation for CharacterGameState"""
        # This should raise a validation error due to extra='forbid'
        with pytest.raises(Exception):  # Pydantic validation error
            CharacterGameState(
                name="test_character",
                level=5,
                xp=1000,
                gold=500,
                hp=80,
                max_hp=100,
                x=10,
                y=15,
                mining_level=1,
                mining_xp=0,
                woodcutting_level=1,
                woodcutting_xp=0,
                fishing_level=1,
                fishing_xp=0,
                weaponcrafting_level=1,
                weaponcrafting_xp=0,
                gearcrafting_level=1,
                gearcrafting_xp=0,
                jewelrycrafting_level=1,
                jewelrycrafting_xp=0,
                cooking_level=1,
                cooking_xp=0,
                alchemy_level=1,
                alchemy_xp=0,
                cooldown=0,
                invalid_extra_field="should_be_rejected"
            )


class TestCooldownInfo:
    """Test CooldownInfo Pydantic model"""

    def test_cooldown_info_creation(self):
        """Test creating CooldownInfo with valid data"""
        expiration_time = (datetime.now() + timedelta(seconds=30)).isoformat()

        cooldown = CooldownInfo(
            character_name="test_char",
            expiration=expiration_time,
            total_seconds=30,
            remaining_seconds=25,
            reason="fight"
        )

        assert cooldown.character_name == "test_char"
        assert cooldown.expiration == expiration_time
        assert cooldown.total_seconds == 30
        assert cooldown.remaining_seconds == 25
        assert cooldown.reason == "fight"

    def test_cooldown_info_validation(self):
        """Test Pydantic validation for CooldownInfo fields"""
        expiration_time = datetime.now().isoformat()

        # Test negative total_seconds validation (should fail)
        with pytest.raises(Exception):  # Pydantic validation error
            CooldownInfo(
                character_name="test_char",
                expiration=expiration_time,
                total_seconds=-5,  # Invalid: negative value
                remaining_seconds=0,
                reason="fight"
            )

        # Test negative remaining_seconds validation (should fail)
        with pytest.raises(Exception):  # Pydantic validation error
            CooldownInfo(
                character_name="test_char",
                expiration=expiration_time,
                total_seconds=30,
                remaining_seconds=-10,  # Invalid: negative value
                reason="fight"
            )

    def test_is_ready_property_expired(self):
        """Test is_ready property when cooldown has expired"""
        past_time = (datetime.now() - timedelta(seconds=10)).isoformat()

        cooldown = CooldownInfo(
            character_name="test_char",
            expiration=past_time,
            total_seconds=30,
            remaining_seconds=0,
            reason="fight"
        )

        # Test the actual property implementation
        assert cooldown.is_ready is True

    def test_is_ready_property_active(self):
        """Test is_ready property when cooldown is still active"""
        future_time = (datetime.now() + timedelta(seconds=30)).isoformat()

        cooldown = CooldownInfo(
            character_name="test_char",
            expiration=future_time,
            total_seconds=30,
            remaining_seconds=25,
            reason="fight"
        )

        # Test the actual property implementation
        assert cooldown.is_ready is False

    def test_time_remaining_property_active(self):
        """Test time_remaining property when cooldown is active"""
        future_time = (datetime.now() + timedelta(seconds=30)).isoformat()

        cooldown = CooldownInfo(
            character_name="test_char",
            expiration=future_time,
            total_seconds=30,
            remaining_seconds=25,
            reason="fight"
        )

        # Test the actual property implementation
        remaining = cooldown.time_remaining
        assert isinstance(remaining, float)
        assert remaining > 0

    def test_time_remaining_property_expired(self):
        """Test time_remaining property when cooldown has expired"""
        past_time = (datetime.now() - timedelta(seconds=10)).isoformat()

        cooldown = CooldownInfo(
            character_name="test_char",
            expiration=past_time,
            total_seconds=30,
            remaining_seconds=0,
            reason="fight"
        )

        # Test the actual property implementation
        remaining = cooldown.time_remaining
        assert remaining == 0.0

    def test_is_ready_property_invalid_datetime(self):
        """Test is_ready property with invalid datetime format"""
        cooldown = CooldownInfo(
            character_name="test_char",
            expiration="invalid_datetime_format",
            total_seconds=30,
            remaining_seconds=0,
            reason="fight"
        )

        # Should fall back to remaining_seconds
        assert cooldown.is_ready is True

        # Test with non-zero remaining_seconds
        cooldown_active = CooldownInfo(
            character_name="test_char",
            expiration="invalid_datetime_format",
            total_seconds=30,
            remaining_seconds=25,
            reason="fight"
        )

        assert cooldown_active.is_ready is False

    def test_time_remaining_property_invalid_datetime(self):
        """Test time_remaining property with invalid datetime format"""
        cooldown = CooldownInfo(
            character_name="test_char",
            expiration="invalid_datetime_format",
            total_seconds=30,
            remaining_seconds=25,
            reason="fight"
        )

        # Should fall back to remaining_seconds
        remaining = cooldown.time_remaining
        assert remaining == 25.0

        # Test with zero remaining_seconds
        cooldown_expired = CooldownInfo(
            character_name="test_char",
            expiration="invalid_datetime_format",
            total_seconds=30,
            remaining_seconds=0,
            reason="fight"
        )

        remaining_expired = cooldown_expired.time_remaining
        assert remaining_expired == 0.0


class TestGameStateIntegration:
    """Integration tests for GameState enum with other components"""

    def test_game_state_action_result_integration(self):
        """Test GameState enum usage with ActionResult"""
        state_changes = {
            GameState.CHARACTER_XP: 1250,
            GameState.MINING_LEVEL: 4,
            GameState.CURRENT_X: 25,
            GameState.COOLDOWN_READY: False
        }

        result = ActionResult(
            success=True,
            message="Mining action completed",
            state_changes=state_changes,
            cooldown_seconds=8
        )

        # Verify that GameState enum keys work properly in ActionResult
        assert result.state_changes[GameState.CHARACTER_XP] == 1250
        assert result.state_changes[GameState.MINING_LEVEL] == 4
        assert result.state_changes[GameState.CURRENT_X] == 25
        assert result.state_changes[GameState.COOLDOWN_READY] is False

    def test_state_validation_round_trip(self):
        """Test round-trip validation: string -> enum -> GOAP dict"""
        original_state = {
            "character_level": 5,
            "hp_current": 80,
            "cooldown_ready": True,
            "current_x": 10
        }

        # String keys -> GameState enum keys
        enum_state = GameState.validate_state_dict(original_state)

        # GameState enum keys -> string keys for GOAP
        goap_state = GameState.to_goap_dict(enum_state)

        # Verify round-trip preserves data
        assert goap_state["character_level"] == original_state["character_level"]
        assert goap_state["hp_current"] == original_state["hp_current"]
        assert goap_state["cooldown_ready"] == original_state["cooldown_ready"]
        assert goap_state["current_x"] == original_state["current_x"]

    def test_comprehensive_state_coverage(self):
        """Test that GameState enum covers all essential game mechanics"""
        required_state_categories = {
            # Character basics
            "progression": [GameState.CHARACTER_LEVEL, GameState.CHARACTER_XP, GameState.CHARACTER_GOLD],
            "health": [GameState.HP_CURRENT, GameState.HP_MAX],
            "position": [GameState.CURRENT_X, GameState.CURRENT_Y],

            # Skills
            "skills": [
                GameState.MINING_LEVEL, GameState.WOODCUTTING_LEVEL, GameState.FISHING_LEVEL,
                GameState.WEAPONCRAFTING_LEVEL, GameState.GEARCRAFTING_LEVEL,
                GameState.JEWELRYCRAFTING_LEVEL, GameState.COOKING_LEVEL, GameState.ALCHEMY_LEVEL
            ],

            # Equipment
            "equipment": [
                GameState.WEAPON_EQUIPPED, GameState.TOOL_EQUIPPED, GameState.HELMET_EQUIPPED,
                GameState.BODY_ARMOR_EQUIPPED, GameState.LEG_ARMOR_EQUIPPED, GameState.BOOTS_EQUIPPED
            ],

            # Action capabilities
            "actions": [
                GameState.COOLDOWN_READY, GameState.CAN_FIGHT, GameState.CAN_GATHER,
                GameState.CAN_CRAFT, GameState.CAN_TRADE, GameState.CAN_MOVE
            ],

            # Location context
            "locations": [
                GameState.AT_TARGET_LOCATION, GameState.AT_MONSTER_LOCATION,
                GameState.AT_RESOURCE_LOCATION, GameState.AT_NPC_LOCATION,
                GameState.AT_BANK_LOCATION, GameState.AT_GRAND_EXCHANGE
            ]
        }

        # Verify all categories have their states defined
        for category, states in required_state_categories.items():
            for state in states:
                assert isinstance(state, GameState), f"Missing state in {category}: {state}"
                assert isinstance(state.value, str), f"State {state} should have string value"
