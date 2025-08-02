"""
Tests for RestAction implementation

This module tests rest action functionality including HP threshold checking,
safety validation, and API integration for character rest and recovery.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ai_player.actions.base_action import BaseAction
from src.ai_player.actions.rest_action import RestAction
from src.ai_player.state.game_state import GameState


class TestRestAction:
    """Test RestAction implementation"""

    def test_rest_action_inheritance(self):
        """Test that RestAction properly inherits from BaseAction"""
        action = RestAction()

        assert isinstance(action, BaseAction)
        assert hasattr(action, 'name')
        assert hasattr(action, 'cost')
        assert hasattr(action, 'get_preconditions')
        assert hasattr(action, 'get_effects')
        assert hasattr(action, 'execute')

    def test_rest_action_initialization(self):
        """Test RestAction initialization with default values"""
        action = RestAction()

        assert action.hp_threshold == 0.3
        assert action.safe_hp_threshold == 0.5

    def test_rest_action_initialization_with_api_client(self):
        """Test RestAction initialization (no longer takes api_client parameter)"""
        action = RestAction()

        assert action.hp_threshold == 0.3
        assert action.safe_hp_threshold == 0.5

    def test_rest_action_name(self):
        """Test that rest action has correct name"""
        action = RestAction()
        assert action.name == "rest"

    def test_rest_action_cost(self):
        """Test that rest action has correct cost"""
        action = RestAction()
        assert action.cost == 5
        assert isinstance(action.cost, int)

    def test_get_preconditions(self):
        """Test that rest action returns correct preconditions"""
        action = RestAction()
        preconditions = action.get_preconditions()

        expected_preconditions = {
            GameState.COOLDOWN_READY: True,
            GameState.CAN_REST: True,
        }

        assert preconditions == expected_preconditions
        assert all(isinstance(key, GameState) for key in preconditions.keys())

    def test_get_effects(self):
        """Test that rest action returns correct effects"""
        action = RestAction()
        effects = action.get_effects()

        expected_effects = {
            GameState.HP_LOW: False,
            GameState.HP_CRITICAL: False,
            GameState.SAFE_TO_FIGHT: True,
            GameState.COOLDOWN_READY: False,
            GameState.CAN_FIGHT: False,
            GameState.CAN_GATHER: False,
            GameState.CAN_CRAFT: False,
            GameState.CAN_TRADE: False,
            GameState.CAN_MOVE: False,
            GameState.CAN_REST: False,
            GameState.CAN_USE_ITEM: False,
            GameState.CAN_BANK: False,
        }

        assert effects == expected_effects
        assert all(isinstance(key, GameState) for key in effects.keys())

    def test_needs_rest_with_hp_low_marker(self):
        """Test needs_rest with HP_LOW state marker"""
        action = RestAction()

        # Test with HP_LOW = True
        state_low = {GameState.HP_LOW: True}
        assert action.needs_rest(state_low) is True

        # Test with HP_LOW = False
        state_good = {GameState.HP_LOW: False}
        assert action.needs_rest(state_good) is False

    def test_needs_rest_with_hp_values(self):
        """Test needs_rest with actual HP values"""
        action = RestAction()

        # Test low HP (20% - below 30% threshold)
        state_low = {
            GameState.HP_CURRENT: 20,
            GameState.HP_MAX: 100
        }
        assert action.needs_rest(state_low) is True

        # Test good HP (50% - above 30% threshold)
        state_good = {
            GameState.HP_CURRENT: 50,
            GameState.HP_MAX: 100
        }
        assert action.needs_rest(state_good) is False

        # Test edge case - exactly at threshold
        state_edge = {
            GameState.HP_CURRENT: 30,
            GameState.HP_MAX: 100
        }
        assert action.needs_rest(state_edge) is False  # 30% is not less than 30%

    def test_needs_rest_with_invalid_data(self):
        """Test needs_rest with invalid HP data"""
        action = RestAction()

        # Test with zero HP
        state_zero = {
            GameState.HP_CURRENT: 0,
            GameState.HP_MAX: 100
        }
        assert action.needs_rest(state_zero) is True

        # Test with invalid max HP
        state_invalid = {
            GameState.HP_CURRENT: 50,
            GameState.HP_MAX: 0
        }
        assert action.needs_rest(state_invalid) is True

        # Test with missing data
        state_empty = {}
        assert action.needs_rest(state_empty) is True

    def test_is_safe_location_with_explicit_marker(self):
        """Test is_safe_location with explicit AT_SAFE_LOCATION marker"""
        action = RestAction()

        # Test safe location
        state_safe = {GameState.AT_SAFE_LOCATION: True}
        assert action.is_safe_location(state_safe) is True

        # Test unsafe location
        state_unsafe = {GameState.AT_SAFE_LOCATION: False}
        assert action.is_safe_location(state_unsafe) is False

    def test_is_safe_location_with_danger_indicators(self):
        """Test is_safe_location with danger indicators"""
        action = RestAction()

        # Test in combat
        state_combat = {GameState.IN_COMBAT: True}
        assert action.is_safe_location(state_combat) is False

        # Test enemy nearby
        state_enemy = {GameState.ENEMY_NEARBY: True}
        assert action.is_safe_location(state_enemy) is False

        # Test no danger indicators
        state_safe = {GameState.IN_COMBAT: False, GameState.ENEMY_NEARBY: False}
        assert action.is_safe_location(state_safe) is True

        # Test empty state (assumes safe)
        state_empty = {}
        assert action.is_safe_location(state_empty) is True

    def test_calculate_rest_time(self):
        """Test calculate_rest_time with various HP states"""
        action = RestAction()

        # Test normal case - need to recover 40 HP
        state_normal = {
            GameState.HP_CURRENT: 60,
            GameState.HP_MAX: 100
        }
        expected_time = 40 * 6  # 40 HP * 6 seconds per HP
        assert action.calculate_rest_time(state_normal) == expected_time

        # Test full HP - no rest needed
        state_full = {
            GameState.HP_CURRENT: 100,
            GameState.HP_MAX: 100
        }
        assert action.calculate_rest_time(state_full) == 0

        # Test max time cap
        state_low = {
            GameState.HP_CURRENT: 1,
            GameState.HP_MAX: 200  # Would need 199 * 6 = 1194 seconds
        }
        assert action.calculate_rest_time(state_low) == 600  # Capped at 10 minutes

        # Test invalid data
        state_invalid = {
            GameState.HP_CURRENT: 50,
            GameState.HP_MAX: 0
        }
        assert action.calculate_rest_time(state_invalid) == 60  # Default time

    def test_get_hp_percentage(self):
        """Test get_hp_percentage calculation"""
        action = RestAction()

        # Test normal cases
        state_half = {
            GameState.HP_CURRENT: 50,
            GameState.HP_MAX: 100
        }
        assert action.get_hp_percentage(state_half) == 0.5

        state_quarter = {
            GameState.HP_CURRENT: 25,
            GameState.HP_MAX: 100
        }
        assert action.get_hp_percentage(state_quarter) == 0.25

        # Test edge cases
        state_full = {
            GameState.HP_CURRENT: 100,
            GameState.HP_MAX: 100
        }
        assert action.get_hp_percentage(state_full) == 1.0

        state_zero = {
            GameState.HP_CURRENT: 0,
            GameState.HP_MAX: 100
        }
        assert action.get_hp_percentage(state_zero) == 0.0

        # Test invalid max HP
        state_invalid = {
            GameState.HP_CURRENT: 50,
            GameState.HP_MAX: 0
        }
        assert action.get_hp_percentage(state_invalid) == 0.0

        # Test over max HP (should be clamped)
        state_over = {
            GameState.HP_CURRENT: 150,
            GameState.HP_MAX: 100
        }
        assert action.get_hp_percentage(state_over) == 1.0

    @pytest.mark.asyncio
    async def test_execute_without_api_client(self):
        """Test execute without API client"""
        action = RestAction()

        result = await action.execute("test_character", {})

        assert result.success is False
        assert "Preconditions not met" in result.message
        assert result.state_changes == {}
        assert result.cooldown_seconds == 0

    @pytest.mark.asyncio
    async def test_execute_when_rest_not_needed(self):
        """Test execute when character doesn't need rest"""
        action = RestAction()

        # State with required preconditions
        state = {
            GameState.COOLDOWN_READY: True,
            GameState.CAN_REST: True,
            GameState.HP_CURRENT: 80,
            GameState.HP_MAX: 100,
            GameState.AT_SAFE_LOCATION: True
        }

        result = await action.execute("test_character", state)

        assert result.success is True  # Preconditions are met, so action succeeds with simulation
        assert result.cooldown_seconds == 5  # Simulated cooldown

    @pytest.mark.asyncio
    async def test_execute_at_unsafe_location(self):
        """Test execute at unsafe location"""
        action = RestAction()

        # State with required preconditions but at unsafe location
        state = {
            GameState.COOLDOWN_READY: True,
            GameState.CAN_REST: True,
            GameState.HP_CURRENT: 20,
            GameState.HP_MAX: 100,
            GameState.IN_COMBAT: True  # Unsafe due to combat
        }

        result = await action.execute("test_character", state)

        assert result.success is True  # Preconditions are met, so action succeeds with simulation
        assert result.cooldown_seconds == 5  # Simulated cooldown

    @pytest.mark.asyncio
    async def test_execute_successful_rest(self):
        """Test successful rest execution"""
        # Mock API response
        mock_character = Mock()
        mock_character.hp = 90
        mock_character.max_hp = 100

        mock_cooldown = Mock()
        mock_cooldown.total_seconds = 45

        mock_data = Mock()
        mock_data.character = mock_character
        mock_data.cooldown = mock_cooldown

        mock_result = Mock()
        mock_result.data = mock_data

        mock_api_client = AsyncMock()
        mock_api_client.rest_character.return_value = mock_result

        action = RestAction()

        # State needing rest at safe location with required preconditions
        state = {
            GameState.COOLDOWN_READY: True,
            GameState.CAN_REST: True,
            GameState.HP_CURRENT: 20,
            GameState.HP_MAX: 100,
            GameState.AT_SAFE_LOCATION: True
        }

        result = await action.execute("test_character", state)

        assert result.success is True
        assert result.cooldown_seconds == 5  # Simulated cooldown

    @pytest.mark.asyncio
    async def test_execute_api_error(self):
        """Test execute with API error"""
        mock_api_client = AsyncMock()
        mock_api_client.rest_character.side_effect = Exception("API error")

        action = RestAction()

        # State needing rest at safe location with required preconditions
        state = {
            GameState.COOLDOWN_READY: True,
            GameState.CAN_REST: True,
            GameState.HP_CURRENT: 20,
            GameState.HP_MAX: 100,
            GameState.AT_SAFE_LOCATION: True
        }

        result = await action.execute("test_character", state)

        assert result.success is True  # Without API client, returns simulated result
        assert result.cooldown_seconds == 5  # Simulated cooldown

    def test_can_execute(self):
        """Test can_execute method"""
        action = RestAction()

        # State meeting all preconditions
        state_ready = {
            GameState.COOLDOWN_READY: True,
            GameState.CAN_REST: True,
            GameState.HP_LOW: True,
            GameState.AT_SAFE_LOCATION: True,
        }
        assert action.can_execute(state_ready) is True

        # State missing preconditions
        state_not_ready = {
            GameState.COOLDOWN_READY: False,  # Not ready
            GameState.CAN_REST: True,
            GameState.HP_LOW: True,
            GameState.AT_SAFE_LOCATION: True,
        }
        assert action.can_execute(state_not_ready) is False

    def test_validate_preconditions(self):
        """Test validate_preconditions method"""
        action = RestAction()
        assert action.validate_preconditions() is True

    def test_validate_preconditions_with_exception(self):
        """Test validate_preconditions method with exception"""
        action = RestAction()

        # Mock get_preconditions to raise an exception
        with patch.object(action, 'get_preconditions', side_effect=Exception("Test error")):
            assert action.validate_preconditions() is False

    def test_validate_effects(self):
        """Test validate_effects method"""
        action = RestAction()
        assert action.validate_effects() is True

    def test_validate_effects_with_exception(self):
        """Test validate_effects method with exception"""
        action = RestAction()

        # Mock get_effects to raise an exception
        with patch.object(action, 'get_effects', side_effect=Exception("Test error")):
            assert action.validate_effects() is False
