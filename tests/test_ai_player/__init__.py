"""
AI Player component tests

Tests for the core AI player components including state management,
action system, goal management, and GOAP integration.

This package provides specialized test utilities, mock factories, and
assertion helpers for comprehensive testing of AI Player functionality.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from unittest.mock import AsyncMock, Mock

import pytest

from src.ai_player.state.game_state import ActionResult, GameState


class AIPlayerMockFactory:
    """Factory for creating AI Player specific mock objects"""

    @staticmethod
    def create_game_state_mock(
        character_level: int = 1,
        current_x: int = 0,
        current_y: int = 0,
        hp_current: int = 100,
        hp_max: int = 100,
        **kwargs
    ) -> dict[GameState, Any]:
        """Create a mock game state dictionary with GameState enum keys"""
        state = {
            GameState.CHARACTER_LEVEL: character_level,
            GameState.CURRENT_X: current_x,
            GameState.CURRENT_Y: current_y,
            GameState.HP_CURRENT: hp_current,
            GameState.HP_MAX: hp_max,
            GameState.CHARACTER_XP: kwargs.get('character_xp', character_level * 250),
            GameState.CHARACTER_GOLD: kwargs.get('character_gold', character_level * 100),
            GameState.MINING_LEVEL: kwargs.get('mining_level', 1),
            GameState.WOODCUTTING_LEVEL: kwargs.get('woodcutting_level', 1),
            GameState.FISHING_LEVEL: kwargs.get('fishing_level', 1),
            GameState.WEAPONCRAFTING_LEVEL: kwargs.get('weaponcrafting_level', 1),
            GameState.GEARCRAFTING_LEVEL: kwargs.get('gearcrafting_level', 1),
            GameState.JEWELRYCRAFTING_LEVEL: kwargs.get('jewelrycrafting_level', 1),
            GameState.COOKING_LEVEL: kwargs.get('cooking_level', 1),
            GameState.INVENTORY_SPACE_AVAILABLE: kwargs.get('inventory_space_available', 100),
            GameState.INVENTORY_SPACE_USED: kwargs.get('inventory_space_used', 0),
            GameState.RESOURCE_AVAILABLE: kwargs.get('resource_available', True),
        }

        # Add any additional state keys from kwargs
        for key, value in kwargs.items():
            if key.startswith('character_') or key in ['current_map', 'available_monsters', 'available_resources']:
                continue
            if isinstance(key, GameState):
                state[key] = value

        return state

    @staticmethod
    def create_action_result_mock(
        success: bool = True,
        message: str = "Action completed successfully",
        data: dict[str, Any] | None = None,
        cooldown_seconds: int = 0,
        **kwargs
    ) -> ActionResult:
        """Create a mock ActionResult object"""
        result = Mock(spec=ActionResult)
        result.success = success
        result.message = message
        result.data = data or {}
        result.cooldown_seconds = cooldown_seconds
        result.timestamp = kwargs.get('timestamp', datetime.now())
        result.action_type = kwargs.get('action_type', "test_action")
        result.character_state = kwargs.get('character_state', {})
        return result

    @staticmethod
    def create_base_action_mock(
        name: str = "test_action",
        preconditions: dict[GameState, Any] | None = None,
        effects: dict[GameState, Any] | None = None,
        cost: int = 1,
        **kwargs
    ) -> Mock:
        """Create a mock BaseAction object"""
        action = Mock()
        action.name = name
        action.preconditions = preconditions or {}
        action.effects = effects or {}
        action.cost = cost
        action.priority = kwargs.get('priority', 1)
        action.cooldown = kwargs.get('cooldown', 0)
        action.is_valid = Mock(return_value=True)
        action.execute = AsyncMock(return_value=AIPlayerMockFactory.create_action_result_mock())
        action.get_preconditions = Mock(return_value=action.preconditions)
        action.get_effects = Mock(return_value=action.effects)
        action.get_cost = Mock(return_value=action.cost)
        return action

    @staticmethod
    def create_goal_mock(
        name: str = "test_goal",
        target_state: dict[GameState, Any] | None = None,
        priority: int = 1,
        **kwargs
    ) -> Mock:
        """Create a mock Goal object"""
        goal = Mock()
        goal.name = name
        goal.target_state = target_state or {GameState.CHARACTER_LEVEL: 2}
        goal.priority = priority
        goal.is_achievable = Mock(return_value=True)
        goal.is_achieved = Mock(return_value=False)
        goal.get_distance_to_goal = Mock(return_value=1)
        goal.description = kwargs.get('description', f"Goal: {name}")
        return goal

    @staticmethod
    def create_plan_mock(
        actions: list[Mock] | None = None,
        cost: int = 1,
        **kwargs
    ) -> Mock:
        """Create a mock GOAP plan object"""
        plan = Mock()
        plan.actions = actions if actions is not None else [AIPlayerMockFactory.create_base_action_mock()]
        plan.total_cost = cost
        plan.estimated_time = kwargs.get('estimated_time', 10.0)
        plan.is_valid = Mock(return_value=True)
        plan.get_next_action = Mock(return_value=plan.actions[0] if plan.actions else None)
        return plan

    @staticmethod
    def create_state_manager_mock() -> Mock:
        """Create a mock StateManager object"""
        state_manager = Mock()
        state_manager.current_state = AIPlayerMockFactory.create_game_state_mock()
        state_manager.get_current_state = Mock(return_value=state_manager.current_state)
        state_manager.update_state = AsyncMock()
        state_manager.validate_state = Mock(return_value=True)
        state_manager.sync_with_api = AsyncMock()
        return state_manager

    @staticmethod
    def create_goal_manager_mock() -> Mock:
        """Create a mock GoalManager object"""
        goal_manager = Mock()
        goal_manager.current_goal = AIPlayerMockFactory.create_goal_mock()
        goal_manager.get_current_goal = Mock(return_value=goal_manager.current_goal)
        goal_manager.set_goal = Mock()
        goal_manager.evaluate_goals = Mock(return_value=[goal_manager.current_goal])
        goal_manager.is_goal_achieved = Mock(return_value=False)
        return goal_manager

    @staticmethod
    def create_action_executor_mock() -> Mock:
        """Create a mock ActionExecutor object"""
        action_executor = Mock()
        action_executor.execute_action = AsyncMock(
            return_value=AIPlayerMockFactory.create_action_result_mock()
        )
        action_executor.validate_action = Mock(return_value=True)
        action_executor.get_action_cooldown = Mock(return_value=0)
        return action_executor

    @staticmethod
    def create_ai_player_mock(character_name: str = "test_character") -> Mock:
        """Create a mock AIPlayer object with all dependencies"""
        ai_player = Mock()
        ai_player.character_name = character_name
        ai_player.state_manager = AIPlayerMockFactory.create_state_manager_mock()
        ai_player.goal_manager = AIPlayerMockFactory.create_goal_manager_mock()
        ai_player.action_executor = AIPlayerMockFactory.create_action_executor_mock()
        ai_player._running = False
        ai_player._stop_requested = False
        ai_player.start = AsyncMock()
        ai_player.stop = AsyncMock()
        ai_player.set_goal = Mock()
        ai_player.get_status = Mock(return_value="idle")
        return ai_player


class AIPlayerTestAssertions:
    """Assertion helpers specific to AI Player testing"""

    @staticmethod
    def assert_game_state_keys(
        state: dict[GameState, Any],
        expected_keys: list[GameState]
    ):
        """Assert that game state contains expected GameState enum keys"""
        for key in expected_keys:
            assert key in state, f"GameState key {key} not found in state"
            assert isinstance(key, GameState), f"Key {key} is not a GameState enum"

    @staticmethod
    def assert_action_result_success(
        result: ActionResult,
        expected_message: str | None = None
    ):
        """Assert that an ActionResult indicates success"""
        assert result.success, f"Action failed: {result.message}"
        if expected_message:
            assert expected_message in result.message, (
                f"Expected message '{expected_message}' not in '{result.message}'"
            )

    @staticmethod
    def assert_action_result_failure(
        result: ActionResult,
        expected_error: str | None = None
    ):
        """Assert that an ActionResult indicates failure"""
        assert not result.success, f"Expected action failure but got success: {result.message}"
        if expected_error:
            assert expected_error in result.message, (
                f"Expected error '{expected_error}' not in '{result.message}'"
            )

    @staticmethod
    def assert_plan_validity(
        plan: Mock,
        min_actions: int = 1,
        max_cost: int | None = None
    ):
        """Assert that a GOAP plan is valid and meets criteria"""
        assert plan.is_valid(), "Plan is not valid"
        assert len(plan.actions) >= min_actions, (
            f"Plan has {len(plan.actions)} actions, expected at least {min_actions}"
        )
        if max_cost is not None:
            assert plan.total_cost <= max_cost, (
                f"Plan cost {plan.total_cost} exceeds maximum {max_cost}"
            )

    @staticmethod
    def assert_goal_state_achievable(
        goal: Mock,
        current_state: dict[GameState, Any]
    ):
        """Assert that a goal is achievable from current state"""
        assert goal.is_achievable(), f"Goal {goal.name} is not achievable"
        distance = goal.get_distance_to_goal()
        assert distance >= 0, f"Goal distance {distance} should be non-negative"

    @staticmethod
    def assert_action_preconditions_met(
        action: Mock,
        current_state: dict[GameState, Any]
    ):
        """Assert that action preconditions are met by current state"""
        preconditions = action.get_preconditions()
        for state_key, required_value in preconditions.items():
            assert state_key in current_state, (
                f"State missing required key {state_key} for action {action.name}"
            )
            actual_value = current_state[state_key]
            assert actual_value >= required_value, (
                f"State {state_key} value {actual_value} does not meet "
                f"requirement {required_value} for action {action.name}"
            )


class AIPlayerTestHelpers:
    """Helper functions for AI Player testing scenarios"""

    @staticmethod
    def create_progression_scenario(
        start_level: int = 1,
        target_level: int = 2,
        steps: int = 5
    ) -> list[dict[GameState, Any]]:
        """Create a progression scenario with multiple game states"""
        states = []
        level_increment = (target_level - start_level) / steps

        for i in range(steps + 1):
            current_level = start_level + (level_increment * i)
            state = AIPlayerMockFactory.create_game_state_mock(
                character_level=int(current_level),
                character_xp=int(current_level * 250),
                character_gold=int(current_level * 100)
            )
            states.append(state)

        return states

    @staticmethod
    def create_combat_scenario(
        player_hp: int = 100,
        monster_hp: int = 50,
        player_damage: int = 20
    ) -> dict[str, Any]:
        """Create a combat scenario with player and monster stats"""
        return {
            'player_state': AIPlayerMockFactory.create_game_state_mock(
                hp_current=player_hp,
                hp_max=100
            ),
            'monster': {
                'hp': monster_hp,
                'max_hp': monster_hp,
                'damage': 15,
                'level': 1
            },
            'expected_damage': player_damage,
            'estimated_turns': max(1, monster_hp // player_damage)
        }

    @staticmethod
    def create_gathering_scenario(
        resource_type: str = "iron_ore",
        skill_level: int = 1,
        required_level: int = 1
    ) -> dict[str, Any]:
        """Create a gathering scenario with resource and skill requirements"""
        skill_map = {
            'iron_ore': GameState.MINING_LEVEL,
            'wood': GameState.WOODCUTTING_LEVEL,
            'fish': GameState.FISHING_LEVEL
        }

        state = AIPlayerMockFactory.create_game_state_mock()
        skill_key = skill_map.get(resource_type, GameState.MINING_LEVEL)
        state[skill_key] = skill_level

        return {
            'player_state': state,
            'resource': {
                'type': resource_type,
                'skill_required': skill_key,
                'level_required': required_level,
                'location': {'x': 0, 'y': 0}
            },
            'can_gather': skill_level >= required_level
        }

    @staticmethod
    async def simulate_action_execution(
        action: Mock,
        state: dict[GameState, Any],
        expected_result: bool = True
    ) -> ActionResult:
        """Simulate executing an action and return result"""
        if action.is_valid(state):
            result = await action.execute(state)
            result.success = expected_result
            return result
        else:
            return AIPlayerMockFactory.create_action_result_mock(
                success=False,
                message="Action preconditions not met"
            )

    @staticmethod
    def validate_action_chain(
        actions: list[Mock],
        initial_state: dict[GameState, Any]
    ) -> bool:
        """Validate that a chain of actions can be executed sequentially"""
        current_state = initial_state.copy()

        for action in actions:
            if not action.is_valid(current_state):
                return False

            # Apply action effects to state
            effects = action.get_effects()
            for state_key, effect_value in effects.items():
                current_state[state_key] = effect_value

        return True


# Common fixtures for AI Player tests
@pytest.fixture
def ai_player_mock_factory():
    """Provide AIPlayerMockFactory for tests"""
    return AIPlayerMockFactory


@pytest.fixture
def ai_player_assertions():
    """Provide AIPlayerTestAssertions for tests"""
    return AIPlayerTestAssertions


@pytest.fixture
def ai_player_helpers():
    """Provide AIPlayerTestHelpers for tests"""
    return AIPlayerTestHelpers


@pytest.fixture
def sample_game_state():
    """Provide a sample game state for testing"""
    return AIPlayerMockFactory.create_game_state_mock()


@pytest.fixture
def sample_action():
    """Provide a sample action for testing"""
    return AIPlayerMockFactory.create_base_action_mock()


@pytest.fixture
def sample_goal():
    """Provide a sample goal for testing"""
    return AIPlayerMockFactory.create_goal_mock()


@pytest.fixture
def sample_ai_player():
    """Provide a sample AI player for testing"""
    return AIPlayerMockFactory.create_ai_player_mock()


# Test configuration specific to AI Player
AI_PLAYER_TEST_TIMEOUT = 10.0
ASYNC_TEST_TIMEOUT = 5.0
