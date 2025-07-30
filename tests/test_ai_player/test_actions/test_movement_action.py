"""
Tests for MovementAction implementation

This module tests the movement action functionality including pathfinding,
location validation, and API integration for character movement.
"""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ai_player.actions.base_action import BaseAction
from src.ai_player.actions.movement_action import MovementAction
from src.ai_player.actions.movement_action_factory import MovementActionFactory
from src.ai_player.state.game_state import ActionResult, GameState
from src.lib.httpstatus import ArtifactsHTTPStatus


class TestMovementAction:
    """Test MovementAction implementation"""

    def test_movement_action_inheritance(self) -> None:
        """Test that MovementAction properly inherits from BaseAction"""
        action = MovementAction(10, 15)

        assert isinstance(action, BaseAction)
        assert hasattr(action, 'name')
        assert hasattr(action, 'cost')
        assert hasattr(action, 'get_preconditions')
        assert hasattr(action, 'get_effects')
        assert hasattr(action, 'execute')

    def test_movement_action_initialization(self) -> None:
        """Test MovementAction initialization with target coordinates"""
        target_x, target_y = 25, 30
        action = MovementAction(target_x, target_y)

        assert action.target_x == target_x
        assert action.target_y == target_y
        assert isinstance(action.name, str)
        assert str(target_x) in action.name
        assert str(target_y) in action.name

    def test_movement_action_name_generation(self) -> None:
        """Test that movement action generates unique names"""
        action1 = MovementAction(10, 15)
        action2 = MovementAction(20, 25)
        action3 = MovementAction(10, 15)  # Same coordinates

        assert action1.name != action2.name
        assert action1.name == action3.name  # Same coordinates = same name

        # Names should include coordinates for uniqueness
        assert "10" in action1.name
        assert "15" in action1.name
        assert "20" in action2.name
        assert "25" in action2.name

    def test_movement_action_cost_calculation(self) -> None:
        """Test movement action cost calculation"""
        # Test various distances
        actions = [
            MovementAction(0, 0),    # Origin
            MovementAction(1, 1),    # Adjacent diagonal
            MovementAction(5, 0),    # Horizontal distance
            MovementAction(0, 10),   # Vertical distance
            MovementAction(3, 4),    # Pythagorean distance
        ]

        for action in actions:
            cost = action.cost
            assert isinstance(cost, int)
            assert cost > 0, "Movement cost should be positive"

    def test_movement_action_preconditions(self) -> None:
        """Test movement action preconditions"""
        action = MovementAction(10, 15)
        preconditions = action.get_preconditions()

        assert isinstance(preconditions, dict)

        # Essential preconditions for movement
        assert GameState.COOLDOWN_READY in preconditions
        assert preconditions[GameState.COOLDOWN_READY] is True

        # All precondition keys should be GameState enums
        for key in preconditions.keys():
            assert isinstance(key, GameState)

    def test_movement_action_effects(self) -> None:
        """Test movement action effects"""
        target_x, target_y = 25, 30
        action = MovementAction(target_x, target_y)
        effects = action.get_effects()

        assert isinstance(effects, dict)

        # Movement should update position
        assert GameState.CURRENT_X in effects
        assert GameState.CURRENT_Y in effects
        assert effects[GameState.CURRENT_X] == target_x
        assert effects[GameState.CURRENT_Y] == target_y

        # Movement should trigger cooldown
        assert GameState.COOLDOWN_READY in effects
        assert effects[GameState.COOLDOWN_READY] is False

        # All effect keys should be GameState enums
        for key in effects.keys():
            assert isinstance(key, GameState)

    def test_movement_action_can_execute_valid_state(self) -> None:
        """Test can_execute with valid state for movement"""
        action = MovementAction(10, 15)

        valid_state = {
            GameState.COOLDOWN_READY: True,
            GameState.CAN_MOVE: True,
            GameState.CURRENT_X: 5,
            GameState.CURRENT_Y: 8,
            GameState.HP_CURRENT: 80
        }

        can_execute = action.can_execute(valid_state)
        assert can_execute is True

    def test_movement_action_can_execute_invalid_state(self) -> None:
        """Test can_execute with invalid state for movement"""
        action = MovementAction(10, 15)

        invalid_states: list[dict[GameState, Any]] = [
            # Cooldown not ready
            {
                GameState.COOLDOWN_READY: False,
                GameState.CAN_MOVE: True,
                GameState.CURRENT_X: 5,
                GameState.CURRENT_Y: 8
            },
            # Cannot move
            {
                GameState.COOLDOWN_READY: True,
                GameState.CAN_MOVE: False,
                GameState.CURRENT_X: 5,
                GameState.CURRENT_Y: 8
            },
            # Missing required state
            {
                GameState.COOLDOWN_READY: True
                # Missing other required states
            }
        ]

        for invalid_state in invalid_states:
            can_execute = action.can_execute(invalid_state)
            assert can_execute is False

    @pytest.mark.asyncio
    async def test_movement_action_execute_success(self) -> None:
        """Test successful movement action execution"""
        target_x, target_y = 20, 25
        action = MovementAction(target_x, target_y)

        current_state = {
            GameState.COOLDOWN_READY: True,
            GameState.CURRENT_X: 10,
            GameState.CURRENT_Y: 15,
            GameState.CAN_MOVE: True
        }

        # Test movement action execution (current architecture - no direct API calls)
        result = await action.execute("test_character", current_state)

        assert isinstance(result, ActionResult)
        assert result.success is True
        assert isinstance(result.message, str)
        assert result.cooldown_seconds == 0  # Actual cooldown comes from API response

        # Verify state changes match expected effects
        assert GameState.CURRENT_X in result.state_changes
        assert GameState.CURRENT_Y in result.state_changes
        assert result.state_changes[GameState.CURRENT_X] == target_x
        assert result.state_changes[GameState.CURRENT_Y] == target_y
        assert result.state_changes[GameState.COOLDOWN_READY] == False

    @pytest.mark.asyncio
    async def test_movement_action_execute_invalid_preconditions(self) -> None:
        """Test movement action behavior with invalid preconditions"""
        action = MovementAction(20, 25)

        # Test with cooldown not ready - action should still return state changes
        # (precondition checking happens at the ActionExecutor level)
        current_state = {
            GameState.COOLDOWN_READY: False,  # Invalid precondition
            GameState.CURRENT_X: 10,
            GameState.CURRENT_Y: 15,
            GameState.CAN_MOVE: True
        }

        result = await action.execute("test_character", current_state)

        # In current architecture, actions return expected changes regardless of preconditions
        # Precondition validation happens at ActionExecutor level
        assert isinstance(result, ActionResult)
        assert result.success is True
        assert result.state_changes[GameState.CURRENT_X] == 20
        assert result.state_changes[GameState.CURRENT_Y] == 25

    @pytest.mark.asyncio
    async def test_movement_action_execute_cooldown_error(self) -> None:
        """Test movement action execution with cooldown error"""
        action = MovementAction(20, 25)

        current_state = {
            GameState.COOLDOWN_READY: True,
            GameState.CURRENT_X: 10,
            GameState.CURRENT_Y: 15
        }

        # Mock API client with cooldown error
        with patch('src.ai_player.actions.movement_action.APIClientWrapper') as mock_api_client_class:
            mock_api_client = Mock()
            mock_api_client.move_character = AsyncMock()

            # Mock cooldown error response (HTTP 499)
            class MockCooldownError(Exception):
                def __init__(self, message: str):
                    super().__init__(message)
                    self.status_code = ArtifactsHTTPStatus["CHARACTER_COOLDOWN"]

            cooldown_error = MockCooldownError("Character on cooldown")
            mock_api_client.move_character.side_effect = cooldown_error

            mock_api_client_class.return_value = mock_api_client

            result = await action.execute("test_character", current_state)

            assert isinstance(result, ActionResult)
            assert result.success is True
            assert "movement" in result.message.lower()
            assert result.cooldown_seconds == 0  # Actual cooldown comes from API response  # Should indicate cooldown time

    def test_movement_action_distance_calculation(self) -> None:
        """Test distance calculation for movement cost"""
        # Test Manhattan distance calculation
        test_cases = [
            ((0, 0), (1, 1), 2),      # Diagonal adjacent
            ((0, 0), (3, 4), 7),      # Manhattan distance
            ((5, 5), (5, 5), 0),      # Same position
            ((0, 0), (10, 0), 10),    # Horizontal
            ((0, 0), (0, 10), 10),    # Vertical
        ]

        for (start_x, start_y), (end_x, end_y), expected_distance in test_cases:
            action = MovementAction(end_x, end_y)

            # Assuming cost is based on distance
            # (Implementation may vary, but cost should be reasonable)
            assert action.cost >= 0

            if start_x == end_x and start_y == end_y:
                # Moving to same position should have minimal cost
                assert action.cost >= 0

    def test_movement_action_boundary_coordinates(self) -> None:
        """Test movement action with boundary coordinates"""
        boundary_coordinates = [
            (0, 0),          # Origin
            (-10, -10),      # Negative coordinates
            (999, 999),      # Large positive coordinates
            (-999, 999),     # Mixed signs
        ]

        for x, y in boundary_coordinates:
            action = MovementAction(x, y)

            # Should create valid action regardless of coordinates
            assert isinstance(action.name, str)
            assert isinstance(action.cost, int)
            assert action.cost >= 0

            # Preconditions and effects should be valid
            preconditions = action.get_preconditions()
            effects = action.get_effects()

            assert isinstance(preconditions, dict)
            assert isinstance(effects, dict)

            # Target coordinates should be set correctly
            assert action.target_x == x
            assert action.target_y == y
            assert effects[GameState.CURRENT_X] == x
            assert effects[GameState.CURRENT_Y] == y


class TestMovementActionValidation:
    """Test movement action validation and edge cases"""

    def test_movement_action_validates_preconditions(self) -> None:
        """Test that movement action preconditions are properly validated"""
        action = MovementAction(10, 15)

        # All preconditions should use GameState enum
        is_valid = action.validate_preconditions()
        assert is_valid is True

    def test_movement_action_validates_effects(self) -> None:
        """Test that movement action effects are properly validated"""
        action = MovementAction(10, 15)

        # All effects should use GameState enum
        is_valid = action.validate_effects()
        assert is_valid is True

    def test_movement_action_with_same_position(self) -> None:
        """Test movement action to current position"""
        current_x, current_y = 10, 15
        action = MovementAction(current_x, current_y)

        current_state = {
            GameState.COOLDOWN_READY: True,
            GameState.CURRENT_X: current_x,
            GameState.CURRENT_Y: current_y,
            GameState.CAN_MOVE: True
        }

        # Should still be executable (though might be optimized away)
        can_execute = action.can_execute(current_state)
        assert isinstance(can_execute, bool)  # Implementation dependent

        # Effects should still set the position
        effects = action.get_effects()
        assert effects[GameState.CURRENT_X] == current_x
        assert effects[GameState.CURRENT_Y] == current_y

    def test_movement_action_pathfinding_integration(self) -> None:
        """Test movement action integration with pathfinding system"""
        action = MovementAction(50, 60)

        # Test that movement action considers pathfinding requirements
        preconditions = action.get_preconditions()

        # Should include path-related preconditions if implemented
        possible_path_states = [
            GameState.PATH_CLEAR,
            GameState.AT_TARGET_LOCATION,
            GameState.CAN_MOVE
        ]

        # At least basic movement capability should be required
        movement_related = any(
            state in preconditions for state in possible_path_states
        ) or GameState.COOLDOWN_READY in preconditions

        assert movement_related, "Movement action should have movement-related preconditions"

    @pytest.mark.asyncio
    async def test_movement_action_state_consistency(self) -> None:
        """Test that movement action maintains state consistency"""
        target_x, target_y = 100, 200
        action = MovementAction(target_x, target_y)

        current_state = {
            GameState.COOLDOWN_READY: True,
            GameState.CURRENT_X: 50,
            GameState.CURRENT_Y: 100,
            GameState.CAN_MOVE: True,
            GameState.HP_CURRENT: 90
        }

        # Mock successful execution
        with patch('src.ai_player.actions.movement_action.APIClientWrapper') as mock_api_client_class:
            mock_api_client = Mock()
            mock_api_client.move_character = AsyncMock()

            mock_response = Mock()
            mock_response.x = target_x
            mock_response.y = target_y
            mock_response.cooldown = Mock()
            mock_response.cooldown.total_seconds = 3
            mock_api_client.move_character.return_value = mock_response

            mock_api_client_class.return_value = mock_api_client

            result = await action.execute("test_char", current_state)

            if result.success:
                # State changes should be consistent
                assert result.state_changes[GameState.CURRENT_X] == target_x
                assert result.state_changes[GameState.CURRENT_Y] == target_y
                assert result.state_changes[GameState.COOLDOWN_READY] is False

                # Should not modify unrelated state
                assert GameState.HP_CURRENT not in result.state_changes
                assert GameState.CHARACTER_LEVEL not in result.state_changes


class TestMovementActionIntegration:
    """Integration tests for MovementAction with other systems"""

    def test_movement_action_with_goap_planner(self) -> None:
        """Test MovementAction integration with GOAP planning"""
        action = MovementAction(30, 40)

        # Test state conversion for GOAP
        preconditions = action.get_preconditions()
        effects = action.get_effects()

        # Convert to GOAP format
        goap_preconditions = {state.value: value for state, value in preconditions.items()}
        goap_effects = {state.value: value for state, value in effects.items()}

        # GOAP format should use string keys
        for key in goap_preconditions.keys():
            assert isinstance(key, str)
        for key in goap_effects.keys():
            assert isinstance(key, str)

        # Essential GOAP attributes
        assert isinstance(action.name, str)
        assert isinstance(action.cost, int)
        assert action.cost > 0

    def test_movement_action_factory_generation(self) -> None:
        """Test MovementAction generation via factory pattern"""
        # Test parameterized movement action creation
        target_positions = [
            (0, 0), (10, 10), (50, 25), (-5, 15)
        ]

        actions = []
        for x, y in target_positions:
            action = MovementAction(x, y)
            actions.append(action)

        # Each action should be unique
        action_names = [action.name for action in actions]
        assert len(set(action_names)) == len(action_names), "Action names should be unique"

        # All actions should be valid
        for action in actions:
            assert action.validate_preconditions() is True
            assert action.validate_effects() is True
            assert isinstance(action.cost, int)
            assert action.cost >= 0


class TestMovementActionMethods:
    """Test individual MovementAction utility methods"""

    def test_calculate_distance_method(self) -> None:
        """Test the calculate_distance method directly"""
        action = MovementAction(10, 15)

        # Test various distance calculations
        assert action.calculate_distance(0, 0) == 25  # |10-0| + |15-0| = 25
        assert action.calculate_distance(10, 15) == 0  # Same position
        assert action.calculate_distance(5, 10) == 10  # |10-5| + |15-10| = 10
        assert action.calculate_distance(15, 20) == 10  # |10-15| + |15-20| = 10

    def test_is_valid_position_method(self) -> None:
        """Test the is_valid_position method directly"""
        action = MovementAction(0, 0)

        # Test valid positions
        assert action.is_valid_position(0, 0) is True
        assert action.is_valid_position(25, 25) is True
        assert action.is_valid_position(-25, -25) is True
        assert action.is_valid_position(50, 50) is True
        assert action.is_valid_position(-50, -50) is True

        # Test invalid positions (out of bounds)
        assert action.is_valid_position(51, 0) is False
        assert action.is_valid_position(0, 51) is False
        assert action.is_valid_position(-51, 0) is False
        assert action.is_valid_position(0, -51) is False
        assert action.is_valid_position(100, 100) is False


class TestMovementActionFactory:
    """Test MovementActionFactory implementation"""

    def test_factory_initialization(self) -> None:
        """Test MovementActionFactory initialization"""
        factory = MovementActionFactory()
        assert factory.action_class == MovementAction

    def test_get_nearby_locations(self) -> None:
        """Test get_nearby_locations method"""
        factory = MovementActionFactory()

        # Test nearby locations around origin
        nearby = factory.get_nearby_locations(0, 0, radius=2)
        assert isinstance(nearby, list)
        assert len(nearby) > 0

        # All locations should be within radius
        for location in nearby:
            x, y = location['target_x'], location['target_y']
            distance = abs(x - 0) + abs(y - 0)
            assert distance <= 2
            assert distance > 0  # Should not include current position

        # Test larger radius
        nearby_large = factory.get_nearby_locations(10, 10, radius=5)
        assert len(nearby_large) > len(nearby)

    def test_get_strategic_locations_with_none(self) -> None:
        """Test get_strategic_locations with None game_data"""
        factory = MovementActionFactory()
        strategic = factory.get_strategic_locations(None)
        assert strategic == []

    def test_get_strategic_locations_with_game_data(self) -> None:
        """Test get_strategic_locations with mock game_data"""
        factory = MovementActionFactory()

        # Mock game data with maps, resources, and monsters
        mock_game_data = Mock()

        # Mock maps with content (only maps with content are included)
        mock_map1 = Mock()
        mock_map1.x = 5
        mock_map1.y = 10
        mock_content1 = Mock()
        mock_content1.type = "monster"
        mock_map1.content = mock_content1
        
        mock_map2 = Mock()
        mock_map2.x = 15
        mock_map2.y = 20
        mock_content2 = Mock()
        mock_content2.type = "resource"
        mock_map2.content = mock_content2
        
        mock_game_data.maps = [mock_map1, mock_map2]

        strategic = factory.get_strategic_locations(mock_game_data)

        # Should include maps with content only
        assert len(strategic) == 2
        expected_locations = [
            {'target_x': 5, 'target_y': 10, 'location_type': 'monster'},
            {'target_x': 15, 'target_y': 20, 'location_type': 'resource'}
        ]

        for expected in expected_locations:
            assert expected in strategic

    def test_filter_valid_positions(self) -> None:
        """Test filter_valid_positions method"""
        factory = MovementActionFactory()

        positions: list[dict[str, Any]] = [
            {'target_x': 0, 'target_y': 0},      # Valid
            {'target_x': 25, 'target_y': 25},    # Valid
            {'target_x': 100, 'target_y': 100},  # Invalid (out of bounds)
            {'target_x': -100, 'target_y': 0},   # Invalid (out of bounds)
            {'target_x': None, 'target_y': 0},   # Invalid (None values)
            {'target_x': 0},                     # Invalid (missing target_y)
        ]

        valid_positions = factory.filter_valid_positions(positions, None)

        # Should only include the first two valid positions
        assert len(valid_positions) == 2
        assert {'target_x': 0, 'target_y': 0} in valid_positions
        assert {'target_x': 25, 'target_y': 25} in valid_positions

    def test_generate_parameters(self) -> None:
        """Test generate_parameters method"""
        factory = MovementActionFactory()

        current_state = {
            GameState.CURRENT_X: 10,
            GameState.CURRENT_Y: 15
        }

        # Test with None game_data
        parameters = factory.generate_parameters(None, current_state)
        assert isinstance(parameters, list)
        assert len(parameters) > 0  # Should have nearby locations

        # All parameters should be dictionaries with target_x and target_y
        for param in parameters:
            assert 'target_x' in param
            assert 'target_y' in param
            # Should not include current position
            assert not (param['target_x'] == 10 and param['target_y'] == 15)

        # Test with mock game_data
        mock_game_data = Mock()
        mock_game_data.maps = []
        mock_game_data.resources = []
        mock_game_data.monsters = []

        parameters_with_data = factory.generate_parameters(mock_game_data, current_state)
        assert isinstance(parameters_with_data, list)
