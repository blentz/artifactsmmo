"""
Tests for integration test utilities and fixtures

This module tests the utilities provided by the integration test __init__.py module
including mock factories, test mixins, workflow helpers, and mock coordinators.
"""

from unittest.mock import AsyncMock, Mock

from src.ai_player.action_executor import ActionExecutor
from src.ai_player.goal_manager import GoalManager
from src.ai_player.inventory_optimizer import InventoryOptimizer
from src.ai_player.state.game_state import ActionResult, GameState
from src.ai_player.state.state_manager import StateManager
from src.game_data.api_client import APIClientWrapper, CooldownManager
from src.game_data.cache_manager import CacheManager
from tests.test_integration import (
    IntegrationTestConfig,
    IntegrationTestMixin,
    MockCoordinator,
    MockFactory,
    WorkflowTestHelpers,
)


class TestMockFactory:
    """Test the MockFactory class and its methods"""

    def test_create_api_client_mock(self):
        """Test creation of API client mock"""
        mock_client = MockFactory.create_api_client_mock()

        # Verify it's a Mock with the correct spec
        assert isinstance(mock_client, Mock)
        assert mock_client._spec_class == APIClientWrapper

        # Verify all required async methods are present
        async_methods = [
            'get_character', 'move_character', 'fight_monster',
            'gather_resource', 'rest_character', 'craft_item',
            'get_cooldown_info', 'get_my_characters', 'create_character',
            'delete_character'
        ]

        for method_name in async_methods:
            method = getattr(mock_client, method_name)
            assert isinstance(method, AsyncMock), f"{method_name} should be AsyncMock"

        # Verify non-async methods
        assert hasattr(mock_client, 'extract_character_state')
        assert isinstance(mock_client.extract_character_state, Mock)

    def test_create_cache_manager_mock(self):
        """Test creation of cache manager mock"""
        mock_cache = MockFactory.create_cache_manager_mock()

        assert isinstance(mock_cache, Mock)
        assert mock_cache._spec_class == CacheManager

        async_methods = [
            'get_character_data', 'cache_character_data', 'get_game_data',
            'invalidate_character_cache', 'clear_cache', 'get_cache_stats'
        ]

        for method_name in async_methods:
            method = getattr(mock_cache, method_name)
            assert isinstance(method, AsyncMock), f"{method_name} should be AsyncMock"

    def test_create_state_manager_mock(self):
        """Test creation of state manager mock"""
        mock_state_manager = MockFactory.create_state_manager_mock()

        assert isinstance(mock_state_manager, Mock)
        assert mock_state_manager._spec_class == StateManager

        async_methods = [
            'get_current_state', 'update_state', 'validate_state',
            'check_state_consistency', 'apply_action_result',
            'sync_with_api', 'validate_state_consistency'
        ]

        for method_name in async_methods:
            method = getattr(mock_state_manager, method_name)
            assert isinstance(method, AsyncMock), f"{method_name} should be AsyncMock"

    def test_create_goal_manager_mock(self):
        """Test creation of goal manager mock"""
        mock_goal_manager = MockFactory.create_goal_manager_mock()

        assert isinstance(mock_goal_manager, Mock)
        assert mock_goal_manager._spec_class == GoalManager

        async_methods = [
            'set_primary_goal', 'get_current_goals', 'plan_actions',
            'evaluate_progress', 'adapt_goals'
        ]

        for method_name in async_methods:
            method = getattr(mock_goal_manager, method_name)
            assert isinstance(method, AsyncMock), f"{method_name} should be AsyncMock"

        # Verify sync methods
        assert hasattr(mock_goal_manager, 'select_next_goal')
        assert isinstance(mock_goal_manager.select_next_goal, Mock)

    def test_create_inventory_optimizer_mock(self):
        """Test creation of inventory optimizer mock"""
        mock_optimizer = MockFactory.create_inventory_optimizer_mock()

        assert isinstance(mock_optimizer, Mock)
        assert mock_optimizer._spec_class == InventoryOptimizer

        async_methods = [
            'optimize_inventory', 'should_bank_items', 'should_sell_items',
            'get_optimization_plan'
        ]

        for method_name in async_methods:
            method = getattr(mock_optimizer, method_name)
            assert isinstance(method, AsyncMock), f"{method_name} should be AsyncMock"

    def test_create_action_executor_mock(self):
        """Test creation of action executor mock"""
        mock_executor = MockFactory.create_action_executor_mock()

        assert isinstance(mock_executor, Mock)
        assert mock_executor._spec_class == ActionExecutor

        async_methods = ['execute_action', 'execute_plan']

        for method_name in async_methods:
            method = getattr(mock_executor, method_name)
            assert isinstance(method, AsyncMock), f"{method_name} should be AsyncMock"

        # Verify sync methods
        assert hasattr(mock_executor, 'get_action_by_name')
        assert isinstance(mock_executor.get_action_by_name, Mock)

    def test_create_cooldown_manager_mock(self):
        """Test creation of cooldown manager mock"""
        mock_cooldown = MockFactory.create_cooldown_manager_mock()

        assert isinstance(mock_cooldown, Mock)
        assert mock_cooldown._spec_class == CooldownManager

        # Test async methods
        assert isinstance(mock_cooldown.get_remaining_cooldown, AsyncMock)
        assert isinstance(mock_cooldown.wait_for_cooldown, AsyncMock)

        # Test sync methods with default return values
        assert isinstance(mock_cooldown.is_ready, Mock)
        assert mock_cooldown.is_ready.return_value is True

    def test_create_success_action_result(self):
        """Test creation of successful ActionResult"""
        result = MockFactory.create_success_action_result()

        assert isinstance(result, ActionResult)
        assert result.success is True
        assert result.message == "Action completed successfully"
        assert result.state_changes == {}
        assert result.cooldown_seconds == 0

        # Test with custom parameters
        custom_changes = {GameState.CHARACTER_XP: 100}
        custom_result = MockFactory.create_success_action_result(
            message="Custom success",
            state_changes=custom_changes,
            cooldown_seconds=5.0
        )

        assert custom_result.success is True
        assert custom_result.message == "Custom success"
        assert custom_result.state_changes == custom_changes
        assert custom_result.cooldown_seconds == 5.0

    def test_create_failure_action_result(self):
        """Test creation of failed ActionResult"""
        result = MockFactory.create_failure_action_result()

        assert isinstance(result, ActionResult)
        assert result.success is False
        assert result.message == "Action failed"
        assert result.state_changes == {}
        assert result.cooldown_seconds == 0

        # Test with custom parameters
        custom_result = MockFactory.create_failure_action_result(
            message="Custom failure",
            cooldown_seconds=3.0
        )

        assert custom_result.success is False
        assert custom_result.message == "Custom failure"
        assert custom_result.cooldown_seconds == 3.0


class TestIntegrationTestMixin(IntegrationTestMixin):
    """Test the IntegrationTestMixin class"""

    def test_mock_api_client_fixture(self, mock_api_client):
        """Test the mock_api_client fixture"""
        assert isinstance(mock_api_client, Mock)
        assert mock_api_client._spec_class == APIClientWrapper
        assert hasattr(mock_api_client, 'get_character')
        assert isinstance(mock_api_client.get_character, AsyncMock)

    def test_mock_cache_manager_fixture(self, mock_cache_manager):
        """Test the mock_cache_manager fixture"""
        assert isinstance(mock_cache_manager, Mock)
        assert mock_cache_manager._spec_class == CacheManager
        assert hasattr(mock_cache_manager, 'get_character_data')
        assert isinstance(mock_cache_manager.get_character_data, AsyncMock)

    def test_mock_state_manager_fixture(self, mock_state_manager, mock_api_client, mock_cache_manager):
        """Test the mock_state_manager fixture with dependencies"""
        assert isinstance(mock_state_manager, Mock)
        assert mock_state_manager._spec_class == StateManager

        # Verify dependencies are wired
        assert mock_state_manager.api_client == mock_api_client
        assert mock_state_manager.cache_manager == mock_cache_manager

        assert hasattr(mock_state_manager, 'get_current_state')
        assert isinstance(mock_state_manager.get_current_state, AsyncMock)

    def test_mock_goal_manager_fixture(self, mock_goal_manager):
        """Test the mock_goal_manager fixture"""
        assert isinstance(mock_goal_manager, Mock)
        assert mock_goal_manager._spec_class == GoalManager
        assert hasattr(mock_goal_manager, 'plan_actions')
        assert isinstance(mock_goal_manager.plan_actions, AsyncMock)

    def test_mock_inventory_optimizer_fixture(self, mock_inventory_optimizer):
        """Test the mock_inventory_optimizer fixture"""
        assert isinstance(mock_inventory_optimizer, Mock)
        assert mock_inventory_optimizer._spec_class == InventoryOptimizer
        assert hasattr(mock_inventory_optimizer, 'optimize_inventory')
        assert isinstance(mock_inventory_optimizer.optimize_inventory, AsyncMock)

    def test_mock_action_executor_fixture(self, mock_action_executor, mock_api_client):
        """Test the mock_action_executor fixture with dependencies"""
        assert isinstance(mock_action_executor, Mock)
        assert mock_action_executor._spec_class == ActionExecutor

        # Verify dependencies are wired
        assert mock_action_executor.api_client == mock_api_client

        assert hasattr(mock_action_executor, 'execute_action')
        assert isinstance(mock_action_executor.execute_action, AsyncMock)

    def test_mock_cooldown_manager_fixture(self, mock_cooldown_manager):
        """Test the mock_cooldown_manager fixture"""
        assert isinstance(mock_cooldown_manager, Mock)
        assert mock_cooldown_manager._spec_class == CooldownManager
        assert hasattr(mock_cooldown_manager, 'wait_for_cooldown')
        assert isinstance(mock_cooldown_manager.wait_for_cooldown, AsyncMock)


class TestWorkflowTestHelpers:
    """Test the WorkflowTestHelpers class"""

    def test_setup_successful_workflow_mocks(self):
        """Test setup of successful workflow mocks"""
        mock_state_manager = MockFactory.create_state_manager_mock()
        mock_goal_manager = MockFactory.create_goal_manager_mock()
        mock_action_executor = MockFactory.create_action_executor_mock()

        initial_state = {GameState.CHARACTER_LEVEL: 10}
        goal = {'type': 'level_up', 'target_level': 11}
        actions = [{'name': 'fight_goblin', 'cost': 5}]

        WorkflowTestHelpers.setup_successful_workflow_mocks(
            mock_state_manager, mock_goal_manager, mock_action_executor,
            initial_state, goal, actions
        )

        # Verify mocks were configured correctly
        assert mock_state_manager.get_current_state.return_value == initial_state
        assert mock_goal_manager.select_next_goal.return_value == goal
        assert mock_goal_manager.plan_actions.return_value == actions

        # Verify action executor was configured for success
        result = mock_action_executor.execute_action.return_value
        assert isinstance(result, ActionResult)
        assert result.success is True

        assert mock_action_executor.execute_plan.return_value is True

    def test_setup_failure_recovery_mocks(self):
        """Test setup of failure recovery mocks"""
        mock_action_executor = MockFactory.create_action_executor_mock()

        WorkflowTestHelpers.setup_failure_recovery_mocks(
            mock_action_executor, failures_before_success=3
        )

        # Verify side_effect was set correctly
        side_effects = list(mock_action_executor.execute_action.side_effect)
        assert len(side_effects) == 4  # 3 failures + 1 success

        # Check first three are failures
        for i in range(3):
            result = side_effects[i]
            assert isinstance(result, ActionResult)
            assert result.success is False
            assert result.message == f"Failure {i + 1}"

        # Check last one is success
        final_result = side_effects[3]
        assert isinstance(final_result, ActionResult)
        assert final_result.success is True
        assert final_result.message == "Action completed after recovery"

    def test_setup_emergency_scenario_mocks(self):
        """Test setup of emergency scenario mocks"""
        mock_state_manager = MockFactory.create_state_manager_mock()
        mock_goal_manager = MockFactory.create_goal_manager_mock()

        emergency_state = {GameState.HP_CURRENT: 10, GameState.HP_CRITICAL: True}
        recovery_state = {GameState.HP_CURRENT: 100, GameState.HP_CRITICAL: False}

        WorkflowTestHelpers.setup_emergency_scenario_mocks(
            mock_state_manager, mock_goal_manager,
            emergency_state, recovery_state
        )

        # Verify state transitions
        state_effects = list(mock_state_manager.get_current_state.side_effect)
        assert state_effects[0] == emergency_state
        assert state_effects[1] == recovery_state

        # Verify emergency goal selection
        emergency_goal = mock_goal_manager.select_next_goal.return_value
        assert emergency_goal['type'] == 'emergency_survival'
        assert emergency_goal['priority'] == 10

        # Verify emergency action plan
        emergency_actions = mock_goal_manager.plan_actions.return_value
        assert len(emergency_actions) == 2
        assert emergency_actions[0]['name'] == 'move_to_safe_area'
        assert emergency_actions[1]['name'] == 'rest'

    def test_create_progression_sequence(self):
        """Test creation of progression sequences"""
        base_state = {
            GameState.CHARACTER_LEVEL: 10,
            GameState.CHARACTER_XP: 2000,
            GameState.HP_CURRENT: 100
        }

        progression_steps = [
            {GameState.CHARACTER_XP: 2100},  # Gained 100 XP
            {GameState.CHARACTER_XP: 2200, GameState.CHARACTER_LEVEL: 11},  # Level up
            {GameState.CHARACTER_XP: 2300, GameState.HP_CURRENT: 110}  # More progress
        ]

        sequence = WorkflowTestHelpers.create_progression_sequence(
            base_state, progression_steps
        )

        assert len(sequence) == 4  # Base + 3 steps

        # Verify base state
        assert sequence[0] == base_state

        # Verify progression
        assert sequence[1][GameState.CHARACTER_XP] == 2100
        assert sequence[1][GameState.CHARACTER_LEVEL] == 10  # No level change yet

        assert sequence[2][GameState.CHARACTER_XP] == 2200
        assert sequence[2][GameState.CHARACTER_LEVEL] == 11  # Level up

        assert sequence[3][GameState.CHARACTER_XP] == 2300
        assert sequence[3][GameState.HP_CURRENT] == 110
        assert sequence[3][GameState.CHARACTER_LEVEL] == 11  # Level maintained


class TestMockCoordinator:
    """Test the MockCoordinator class"""

    def test_setup_full_ai_player_stack(self):
        """Test setup of full AI player mock stack"""
        coordinator = MockCoordinator()
        character_name = "test_character"

        mocks = coordinator.setup_full_ai_player_stack(character_name)

        # Verify all expected mocks are present
        expected_mocks = [
            'api_client', 'cache_manager', 'state_manager',
            'goal_manager', 'inventory_optimizer', 'action_executor',
            'cooldown_manager'
        ]

        for mock_name in expected_mocks:
            assert mock_name in mocks
            assert isinstance(mocks[mock_name], Mock)

        # Verify dependencies are wired correctly
        assert mocks['state_manager'].api_client == mocks['api_client']
        assert mocks['state_manager'].cache_manager == mocks['cache_manager']
        assert mocks['action_executor'].api_client == mocks['api_client']

        # Verify mocks are stored internally
        stored_mocks = coordinator.get_mocks_for_character(character_name)
        assert stored_mocks == mocks

    def test_get_mocks_for_character(self):
        """Test retrieval of mocks for specific character"""
        coordinator = MockCoordinator()
        character_name = "test_character"

        # Test empty case
        empty_mocks = coordinator.get_mocks_for_character(character_name)
        assert empty_mocks == {}

        # Setup mocks and test retrieval
        setup_mocks = coordinator.setup_full_ai_player_stack(character_name)
        retrieved_mocks = coordinator.get_mocks_for_character(character_name)
        assert retrieved_mocks == setup_mocks

    def test_reset_all_mocks(self):
        """Test resetting all mocks"""
        coordinator = MockCoordinator()

        # Setup mocks for multiple characters
        character1 = "character1"
        character2 = "character2"

        mocks1 = coordinator.setup_full_ai_player_stack(character1)
        mocks2 = coordinator.setup_full_ai_player_stack(character2)

        # Call some methods to change mock state
        mocks1['api_client'].get_character.call_count = 1
        mocks2['goal_manager'].select_next_goal.call_count = 1

        # Verify calls were made
        assert mocks1['api_client'].get_character.call_count == 1
        assert mocks2['goal_manager'].select_next_goal.call_count == 1

        # Reset all mocks
        coordinator.reset_all_mocks()

        # Verify all mocks were reset
        assert mocks1['api_client'].get_character.call_count == 0
        assert mocks2['goal_manager'].select_next_goal.call_count == 0

    def test_multiple_character_coordination(self):
        """Test coordination of mocks for multiple characters"""
        coordinator = MockCoordinator()

        character1 = "character1"
        character2 = "character2"

        mocks1 = coordinator.setup_full_ai_player_stack(character1)
        mocks2 = coordinator.setup_full_ai_player_stack(character2)

        # Verify different mock instances for different characters
        assert mocks1['api_client'] != mocks2['api_client']
        assert mocks1['state_manager'] != mocks2['state_manager']

        # Verify both are stored correctly
        assert coordinator.get_mocks_for_character(character1) == mocks1
        assert coordinator.get_mocks_for_character(character2) == mocks2


class TestIntegrationTestConfig:
    """Test the IntegrationTestConfig class"""

    def test_character_names(self):
        """Test character name constants"""
        assert IntegrationTestConfig.DEFAULT_CHARACTER == "integration_test_character"
        assert IntegrationTestConfig.EMERGENCY_CHARACTER == "emergency_test_character"
        assert IntegrationTestConfig.PROGRESSION_CHARACTER == "progression_test_character"

    def test_timeouts(self):
        """Test timeout constants"""
        assert IntegrationTestConfig.DEFAULT_TIMEOUT == 30.0
        assert IntegrationTestConfig.LONG_RUNNING_TIMEOUT == 120.0
        assert isinstance(IntegrationTestConfig.DEFAULT_TIMEOUT, float)
        assert isinstance(IntegrationTestConfig.LONG_RUNNING_TIMEOUT, float)

    def test_action_limits(self):
        """Test action limit constants"""
        assert IntegrationTestConfig.DEFAULT_MAX_ACTIONS == 10
        assert IntegrationTestConfig.EXTENDED_MAX_ACTIONS == 50
        assert isinstance(IntegrationTestConfig.DEFAULT_MAX_ACTIONS, int)
        assert isinstance(IntegrationTestConfig.EXTENDED_MAX_ACTIONS, int)

    def test_performance_thresholds(self):
        """Test performance threshold constants"""
        assert IntegrationTestConfig.MIN_ACTIONS_PER_SECOND == 10.0
        assert IntegrationTestConfig.MAX_EXECUTION_TIME == 5.0
        assert isinstance(IntegrationTestConfig.MIN_ACTIONS_PER_SECOND, float)
        assert isinstance(IntegrationTestConfig.MAX_EXECUTION_TIME, float)


class TestIntegrationUtilitiesIntegration:
    """Test integration of all utilities working together"""

    def test_factory_and_coordinator_integration(self):
        """Test MockFactory and MockCoordinator working together"""
        coordinator = MockCoordinator()
        character_name = "integration_test"

        # Setup using coordinator
        coordinator_mocks = coordinator.setup_full_ai_player_stack(character_name)

        # Create individual mocks using factory
        factory_api_client = MockFactory.create_api_client_mock()
        factory_state_manager = MockFactory.create_state_manager_mock()

        # Verify same spec classes
        assert (coordinator_mocks['api_client']._spec_class ==
                factory_api_client._spec_class)
        assert (coordinator_mocks['state_manager']._spec_class ==
                factory_state_manager._spec_class)

    def test_helpers_and_factory_integration(self):
        """Test WorkflowTestHelpers and MockFactory working together"""
        # Create mocks using factory
        mock_state_manager = MockFactory.create_state_manager_mock()
        mock_goal_manager = MockFactory.create_goal_manager_mock()
        mock_action_executor = MockFactory.create_action_executor_mock()

        # Use helpers to configure mocks
        initial_state = {GameState.CHARACTER_LEVEL: 5}
        goal = {'type': 'level_up'}
        actions = [{'name': 'fight', 'cost': 3}]

        WorkflowTestHelpers.setup_successful_workflow_mocks(
            mock_state_manager, mock_goal_manager, mock_action_executor,
            initial_state, goal, actions
        )

        # Verify configuration worked
        assert mock_state_manager.get_current_state.return_value == initial_state
        assert mock_goal_manager.select_next_goal.return_value == goal

        # Create ActionResults using factory
        success_result = MockFactory.create_success_action_result(
            message="Test success"
        )
        failure_result = MockFactory.create_failure_action_result(
            message="Test failure"
        )

        # Verify ActionResult creation
        assert success_result.success is True
        assert success_result.message == "Test success"
        assert failure_result.success is False
        assert failure_result.message == "Test failure"

    def test_mixin_and_config_integration(self):
        """Test IntegrationTestMixin and IntegrationTestConfig working together"""
        # Verify config constants can be used in test scenarios
        character_name = IntegrationTestConfig.DEFAULT_CHARACTER
        max_actions = IntegrationTestConfig.DEFAULT_MAX_ACTIONS
        timeout = IntegrationTestConfig.DEFAULT_TIMEOUT

        # Verify values are sensible for testing
        assert isinstance(character_name, str)
        assert len(character_name) > 0
        assert max_actions > 0
        assert timeout > 0.0

        # Verify config values work with test patterns
        coordinator = MockCoordinator()
        mocks = coordinator.setup_full_ai_player_stack(character_name)

        # Should be able to use config values with mocks
        assert character_name in coordinator.mocks
        assert len(mocks) > 0
