"""
Integration tests for end-to-end workflows

This module provides comprehensive integration tests that validate
complete workflows across the AI player system including character
management, AI player execution, and diagnostic operations.

This module provides utilities and base classes for integration testing including:
- Mock factory functions for AI player components
- Integration test base classes with common fixtures
- Workflow test helpers for common testing patterns
- Mock coordination helpers for multi-component scenarios
"""

from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock

import pytest

from src.ai_player.action_executor import ActionExecutor
from src.ai_player.ai_player import AIPlayer
from src.ai_player.goal_manager import GoalManager
from src.ai_player.inventory_optimizer import InventoryOptimizer
from src.ai_player.state.game_state import ActionResult, GameState
from src.ai_player.state.state_manager import StateManager
from src.game_data.api_client import APIClientWrapper, CooldownManager
from src.game_data.cache_manager import CacheManager


class MockFactory:
    """Factory for creating standardized mocks for integration testing"""

    @staticmethod
    def create_api_client_mock() -> Mock:
        """Create a standardized mock APIClientWrapper for integration tests"""
        client = Mock(spec=APIClientWrapper)

        # Core async methods
        client.get_character = AsyncMock()
        client.get_characters = AsyncMock()
        client.create_character = AsyncMock()
        client.delete_character = AsyncMock()
        client.move_character = AsyncMock()
        client.fight_monster = AsyncMock()
        client.gather_resource = AsyncMock()
        client.craft_item = AsyncMock()
        client.rest_character = AsyncMock()
        client.equip_item = AsyncMock()
        client.unequip_item = AsyncMock()

        # Required attributes from APIClientWrapper.__init__
        client.cooldown_manager = MockFactory.create_cooldown_manager_mock()

        # Data retrieval methods
        client.get_all_items = AsyncMock()
        client.get_all_monsters = AsyncMock()
        client.get_all_maps = AsyncMock()
        client.get_map = AsyncMock()
        client.get_all_resources = AsyncMock()
        client.get_all_npcs = AsyncMock()

        # Internal methods
        client._handle_rate_limit = AsyncMock()
        client._process_response = AsyncMock()
        client.extract_cooldown = Mock()
        client.get_cooldown_info = AsyncMock()
        client.get_my_characters = AsyncMock()
        client.extract_character_state = Mock()

        # Required attributes
        client.cooldown_manager = Mock()
        client.cooldown_manager.update_from_character = Mock()
        client.cooldown_manager.is_ready = Mock(return_value=True)
        client.cooldown_manager.get_remaining_time = Mock(return_value=0.0)
        client.cooldown_manager.update_cooldown = Mock()
        client.cooldown_manager.wait_for_cooldown = AsyncMock()
        client.cooldown_manager.clear_cooldown = Mock()
        client.cooldown_manager.clear_all_cooldowns = Mock()
        client.cooldown_manager.get_cooldown_info = Mock(return_value=None)
        client.cooldown_manager.clear_expired_cooldowns = Mock()

        client.client = Mock()  # Underlying authenticated client
        client.token_config = Mock()
        client.status_codes = Mock()

        return client

    @staticmethod
    def create_cache_manager_mock() -> Mock:
        """Create a standardized mock CacheManager for integration tests"""
        cache = Mock(spec=CacheManager)
        cache.get_character_data = AsyncMock()
        cache.cache_character_data = AsyncMock()
        cache.get_game_data = AsyncMock()
        cache.invalidate_character_cache = AsyncMock()
        cache.clear_cache = AsyncMock()
        cache.get_cache_stats = AsyncMock()
        return cache

    @staticmethod
    def create_state_manager_mock() -> Mock:
        """Create a standardized mock StateManager for integration tests"""
        state_manager = Mock(spec=StateManager)
        state_manager.get_current_state = AsyncMock()
        state_manager.update_state = AsyncMock()
        state_manager.validate_state = AsyncMock()
        state_manager.check_state_consistency = AsyncMock()
        state_manager.apply_action_result = AsyncMock()
        state_manager.sync_with_api = AsyncMock()
        state_manager.validate_state_consistency = AsyncMock()
        return state_manager

    @staticmethod
    def create_goal_manager_mock() -> Mock:
        """Create a standardized mock GoalManager for integration tests"""
        goal_manager = Mock(spec=GoalManager)
        goal_manager.set_primary_goal = AsyncMock()
        goal_manager.get_current_goals = AsyncMock()
        goal_manager.plan_actions = AsyncMock()
        goal_manager.evaluate_progress = AsyncMock()
        goal_manager.adapt_goals = AsyncMock()
        goal_manager.select_next_goal = Mock()
        return goal_manager

    @staticmethod
    def create_inventory_optimizer_mock() -> Mock:
        """Create a standardized mock InventoryOptimizer for integration tests"""
        optimizer = Mock(spec=InventoryOptimizer)
        optimizer.optimize_inventory = AsyncMock()
        optimizer.should_bank_items = AsyncMock()
        optimizer.should_sell_items = AsyncMock()
        optimizer.get_optimization_plan = AsyncMock()
        return optimizer

    @staticmethod
    def create_action_executor_mock() -> Mock:
        """Create a standardized mock ActionExecutor for integration tests"""
        executor = Mock(spec=ActionExecutor)
        executor.execute_action = AsyncMock()
        executor.execute_plan = AsyncMock()
        executor.get_action_by_name = Mock()
        return executor

    @staticmethod
    def create_cooldown_manager_mock() -> Mock:
        """Create a standardized mock CooldownManager for integration tests"""
        cooldown_manager = Mock(spec=CooldownManager)
        cooldown_manager.get_remaining_cooldown = AsyncMock(return_value=0.0)
        cooldown_manager.is_ready = Mock(return_value=True)
        cooldown_manager.wait_for_cooldown = AsyncMock()
        return cooldown_manager

    @staticmethod
    def create_success_action_result(
        message: str = "Action completed successfully",
        state_changes: dict[GameState, Any] | None = None,
        cooldown_seconds: float = 0
    ) -> ActionResult:
        """Create a successful ActionResult for testing"""
        return ActionResult(
            success=True,
            message=message,
            state_changes=state_changes or {},
            cooldown_seconds=cooldown_seconds
        )

    @staticmethod
    def create_failure_action_result(
        message: str = "Action failed",
        cooldown_seconds: float = 0
    ) -> ActionResult:
        """Create a failed ActionResult for testing"""
        return ActionResult(
            success=False,
            message=message,
            state_changes={},
            cooldown_seconds=cooldown_seconds
        )


class IntegrationTestMixin:
    """Mixin class providing common integration test utilities"""

    @pytest.fixture
    def mock_api_client(self):
        """Fixture providing a mock API client"""
        return MockFactory.create_api_client_mock()

    @pytest.fixture
    def mock_cache_manager(self):
        """Fixture providing a mock cache manager"""
        return MockFactory.create_cache_manager_mock()

    @pytest.fixture
    def mock_state_manager(self, mock_api_client, mock_cache_manager):
        """Fixture providing a mock state manager with dependencies"""
        state_manager = MockFactory.create_state_manager_mock()
        state_manager.api_client = mock_api_client
        state_manager.cache_manager = mock_cache_manager
        return state_manager

    @pytest.fixture
    def mock_goal_manager(self):
        """Fixture providing a mock goal manager"""
        return MockFactory.create_goal_manager_mock()

    @pytest.fixture
    def mock_inventory_optimizer(self):
        """Fixture providing a mock inventory optimizer"""
        return MockFactory.create_inventory_optimizer_mock()

    @pytest.fixture
    def mock_action_executor(self, mock_api_client):
        """Fixture providing a mock action executor with dependencies"""
        executor = MockFactory.create_action_executor_mock()
        executor.api_client = mock_api_client
        return executor

    @pytest.fixture
    def mock_cooldown_manager(self):
        """Fixture providing a mock cooldown manager"""
        return MockFactory.create_cooldown_manager_mock()


class WorkflowTestHelpers:
    """Helper functions for common workflow testing patterns"""

    @staticmethod
    def setup_successful_workflow_mocks(
        mock_state_manager: Mock,
        mock_goal_manager: Mock,
        mock_action_executor: Mock,
        initial_state: dict[GameState, Any],
        goal: dict[str, Any],
        actions: list[dict[str, Any]]
    ) -> None:
        """Set up mocks for a successful workflow test"""
        # Configure state manager
        mock_state_manager.get_current_state.return_value = initial_state

        # Configure goal manager
        mock_goal_manager.select_next_goal.return_value = goal
        mock_goal_manager.plan_actions.return_value = actions

        # Configure action executor for success
        success_result = MockFactory.create_success_action_result()
        mock_action_executor.execute_action.return_value = success_result
        mock_action_executor.execute_plan.return_value = True

    @staticmethod
    def setup_failure_recovery_mocks(
        mock_action_executor: Mock,
        failures_before_success: int = 2
    ) -> None:
        """Set up mocks for failure recovery testing"""
        results = []
        # Add failures
        for i in range(failures_before_success):
            failure = MockFactory.create_failure_action_result(
                message=f"Failure {i + 1}"
            )
            results.append(failure)

        # Add final success
        success = MockFactory.create_success_action_result(
            message="Action completed after recovery"
        )
        results.append(success)

        mock_action_executor.execute_action.side_effect = results

    @staticmethod
    def setup_emergency_scenario_mocks(
        mock_state_manager: Mock,
        mock_goal_manager: Mock,
        emergency_state: dict[GameState, Any],
        recovery_state: dict[GameState, Any]
    ) -> None:
        """Set up mocks for emergency scenario testing"""
        # State transitions: emergency -> recovery
        mock_state_manager.get_current_state.side_effect = [
            emergency_state, recovery_state
        ]

        # Emergency goal selection
        emergency_goal = {
            'type': 'emergency_survival',
            'priority': 10,
            'target_state': {
                GameState.HP_CURRENT: 100,
                GameState.AT_SAFE_LOCATION: True
            }
        }
        mock_goal_manager.select_next_goal.return_value = emergency_goal

        # Emergency action plan
        emergency_actions = [
            {'name': 'move_to_safe_area', 'cost': 2},
            {'name': 'rest', 'cost': 1}
        ]
        mock_goal_manager.plan_actions.return_value = emergency_actions

    @staticmethod
    def create_progression_sequence(
        base_state: dict[GameState, Any],
        progression_steps: list[dict[GameState, Any]]
    ) -> list[dict[GameState, Any]]:
        """Create a sequence of states showing character progression"""
        states = [base_state.copy()]

        for step in progression_steps:
            next_state = states[-1].copy()
            next_state.update(step)
            states.append(next_state)

        return states


class MockCoordinator:
    """Coordinates complex mock setups for multi-component scenarios"""

    def __init__(self):
        self.mocks = {}

    def setup_full_ai_player_stack(
        self,
        character_name: str = "test_character"
    ) -> dict[str, Mock]:
        """Set up a complete mock stack for AI player testing"""
        mocks = {
            'api_client': MockFactory.create_api_client_mock(),
            'cache_manager': MockFactory.create_cache_manager_mock(),
            'state_manager': MockFactory.create_state_manager_mock(),
            'goal_manager': MockFactory.create_goal_manager_mock(),
            'inventory_optimizer': MockFactory.create_inventory_optimizer_mock(),
            'action_executor': MockFactory.create_action_executor_mock(),
            'cooldown_manager': MockFactory.create_cooldown_manager_mock()
        }

        # Wire up dependencies
        mocks['state_manager'].api_client = mocks['api_client']
        mocks['state_manager'].cache_manager = mocks['cache_manager']
        mocks['action_executor'].api_client = mocks['api_client']

        self.mocks[character_name] = mocks
        return mocks

    def get_mocks_for_character(self, character_name: str) -> dict[str, Mock]:
        """Get the mock stack for a specific character"""
        return self.mocks.get(character_name, {})

    def reset_all_mocks(self) -> None:
        """Reset all mocks to their initial state"""
        for character_mocks in self.mocks.values():
            for mock in character_mocks.values():
                mock.reset_mock()


# Integration test configuration constants
class IntegrationTestConfig:
    """Configuration constants for integration tests"""

    # Test character names for different scenarios
    DEFAULT_CHARACTER = "integration_test_character"
    EMERGENCY_CHARACTER = "emergency_test_character"
    PROGRESSION_CHARACTER = "progression_test_character"

    # Common test timeouts (in seconds)
    DEFAULT_TIMEOUT = 30.0
    LONG_RUNNING_TIMEOUT = 120.0

    # Test action limits
    DEFAULT_MAX_ACTIONS = 10
    EXTENDED_MAX_ACTIONS = 50

    # Performance thresholds
    MIN_ACTIONS_PER_SECOND = 10.0
    MAX_EXECUTION_TIME = 5.0
