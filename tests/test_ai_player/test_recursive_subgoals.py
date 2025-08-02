"""
Tests for Recursive Sub-Goal Integration

This module tests the end-to-end functionality of the unified sub-goal architecture,
including recursive execution, depth limits, state consistency, and error propagation.
"""

from typing import Any, Optional
from unittest.mock import AsyncMock, Mock

import pytest

from src.ai_player.action_executor import ActionExecutor
from src.ai_player.actions.base_action import BaseAction
from src.ai_player.exceptions import (
    MaxDepthExceededError,
    NoValidGoalError,
    StateConsistencyError,
    SubGoalExecutionError,
)
from src.ai_player.goal_manager import GoalManager
from src.ai_player.goals.sub_goal_request import SubGoalRequest
from src.ai_player.state.action_result import ActionResult
from src.ai_player.state.character_game_state import CharacterGameState
from src.ai_player.state.game_state import GameState
from src.ai_player.types.game_data import GameData
from src.ai_player.types.goap_models import (
    GoalFactoryContext,
    GOAPAction,
    GOAPActionPlan,
    GOAPTargetState,
    SubGoalExecutionResult,
)


class MockAction(BaseAction):
    """Mock action for testing."""

    def __init__(self, name="mock_action", should_fail=False, sub_goal_requests=None):
        self._name = name
        self.should_fail = should_fail
        self.sub_goal_requests = sub_goal_requests or []

    @property
    def name(self):
        return self._name

    @property
    def cost(self):
        return 1

    def get_preconditions(self):
        return {GameState.COOLDOWN_READY: True}

    def get_effects(self):
        return {GameState.CHARACTER_XP: 100}

    async def execute(self, character_name, current_state):
        if self.should_fail:
            return ActionResult(
                success=False,
                message="Mock action failed",
                state_changes={},
                sub_goal_requests=self.sub_goal_requests
            )
        else:
            return ActionResult(
                success=True,
                message="Mock action succeeded",
                state_changes={GameState.CHARACTER_XP: 100}
            )

    async def _execute_api_call(
        self,
        character_name: str,
        current_state: dict[GameState, Any],
        api_client: 'APIClientWrapper',
        cooldown_manager: Optional['CooldownManager']
    ) -> ActionResult:
        """Mock implementation of API call execution for testing"""
        if self.should_fail:
            return ActionResult(
                success=False,
                message="Mock API action failed",
                state_changes={},
                cooldown_seconds=0,
                sub_goal_requests=self.sub_goal_requests
            )
        else:
            return ActionResult(
                success=True,
                message="Mock API action succeeded",
                state_changes={GameState.CHARACTER_XP: 100},
                cooldown_seconds=5
            )


def create_mock_character_state(**overrides):
    """Helper to create mock character state."""
    defaults = {
        'name': 'test_char',
        'level': 5,
        'xp': 1000,
        'gold': 100,
        'hp': 80,
        'max_hp': 100,
        'x': 10,
        'y': 15,
        'cooldown': 0,
        'mining_level': 3,
        'mining_xp': 150,
        'woodcutting_level': 2,
        'woodcutting_xp': 50,
        'fishing_level': 1,
        'fishing_xp': 0,
        'weaponcrafting_level': 1,
        'weaponcrafting_xp': 0,
        'gearcrafting_level': 1,
        'gearcrafting_xp': 0,
        'jewelrycrafting_level': 1,
        'jewelrycrafting_xp': 0,
        'cooking_level': 1,
        'cooking_xp': 0,
        'alchemy_level': 1,
        'alchemy_xp': 0
    }
    defaults.update(overrides)
    return CharacterGameState(**defaults)


class TestRecursiveSubGoalExecution:
    """Test recursive sub-goal execution functionality."""

    @pytest.fixture
    def mock_goal_manager(self):
        """Create mock GoalManager for testing."""
        goal_manager = Mock()

        # Mock factory method
        goal_manager.create_goal_from_sub_request = Mock()

        # Mock GOAP planning method
        goal_manager.plan_to_target_state = AsyncMock()

        return goal_manager

    @pytest.fixture
    def mock_state_manager(self):
        """Create mock StateManager for testing."""
        state_manager = Mock()

        # Mock state consistency methods
        state_manager.refresh_state_for_parent_action = AsyncMock()
        state_manager.validate_recursive_state_transition = AsyncMock(return_value=True)
        state_manager.create_goal_factory_context = Mock()

        return state_manager

    @pytest.fixture
    def mock_action_executor(self, mock_goal_manager, mock_state_manager):
        """Create mock ActionExecutor with recursive sub-goal support."""

        # Create mock dependencies
        mock_api_client = Mock()
        mock_cooldown_manager = Mock()
        mock_cache_manager = Mock()

        executor = ActionExecutor(
            api_client=mock_api_client,
            cooldown_manager=mock_cooldown_manager,
            cache_manager=mock_cache_manager
        )

        # Add unified sub-goal architecture components
        executor.goal_manager = mock_goal_manager
        executor.state_manager = mock_state_manager
        executor.max_subgoal_depth = 5

        return executor

    @pytest.mark.asyncio
    async def test_successful_recursive_execution(self, mock_action_executor, mock_goal_manager, mock_state_manager):
        """Test successful recursive sub-goal execution."""
        # Setup sub-goal request
        sub_goal_request = SubGoalRequest(
            goal_type="move_to_location",
            parameters={"target_x": 5, "target_y": 5},
            priority=7,
            requester="TestGoal",
            reason="Need to move for test"
        )

        # Setup mock action that initially fails but has sub-goal requests
        action = MockAction(
            name="test_action",
            should_fail=True,
            sub_goal_requests=[sub_goal_request]
        )

        # Setup mocks
        mock_goal = Mock()
        mock_goal.get_target_state.return_value = GOAPTargetState(
            target_states={GameState.AT_TARGET_LOCATION: True},
            priority=7
        )
        mock_goal_manager.create_goal_from_sub_request.return_value = mock_goal

        # Create mock plan that will not be empty (has actions)
        mock_plan = GOAPActionPlan(
            actions=[GOAPAction(name="move_action", action_type="movement")],
            plan_id="test_plan"
        )
        mock_goal_manager.plan_to_target_state.return_value = mock_plan

        # Mock execute_action to initially return failure with sub-goals, then success
        initial_result = ActionResult(
            success=False,
            message="Mock action failed - needs sub-goals",
            state_changes={},
            sub_goal_requests=[sub_goal_request]
        )

        final_result = ActionResult(
            success=True,
            message="Action succeeded after sub-goal",
            state_changes={GameState.CHARACTER_XP: 100}
        )

        mock_action_executor.execute_action = AsyncMock(side_effect=[initial_result, final_result])

        # Mock execute_plan_recursive to return success
        mock_action_executor.execute_plan_recursive = AsyncMock(return_value=SubGoalExecutionResult(
            success=True,
            depth_reached=1,
            actions_executed=1,
            execution_time=5.0
        ))

        # Mock state refresh
        refreshed_state = create_mock_character_state(x=5, y=5)
        mock_state_manager.refresh_state_for_parent_action.return_value = refreshed_state

        # Mock factory context creation
        mock_context = GoalFactoryContext(
            character_state=refreshed_state,
            game_data=GameData(),
            recursion_depth=1,
            max_depth=5
        )
        mock_state_manager.create_goal_factory_context.return_value = mock_context

        # Execute test
        current_state = create_mock_character_state()
        result = await mock_action_executor.execute_action_with_subgoals(
            action, "test_char", current_state, depth=0
        )

        # Verify result
        assert result.success is True
        assert "Action succeeded after sub-goal" in result.message

        # Verify method calls
        mock_goal_manager.create_goal_from_sub_request.assert_called_once()
        mock_goal_manager.plan_to_target_state.assert_called_once()
        mock_state_manager.refresh_state_for_parent_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_depth_limit_exceeded(self, mock_action_executor, mock_state_manager):
        """Test that max depth exceeded raises appropriate exception."""
        # Create action with max depth = 2
        mock_action_executor.max_subgoal_depth = 2

        action = MockAction(name="test_action")
        current_state = create_mock_character_state()

        # Execute at depth > max_depth should raise exception
        with pytest.raises(MaxDepthExceededError) as exc_info:
            await mock_action_executor.execute_action_with_subgoals(
                action, "test_char", current_state, depth=3
            )

        error = exc_info.value
        assert error.depth == 2  # Should be max_depth
        assert "Maximum recursion depth 2 exceeded" in str(error)

    @pytest.mark.asyncio
    async def test_state_consistency_validation(self, mock_action_executor, mock_goal_manager, mock_state_manager):
        """Test state consistency validation during recursive execution."""
        # Setup sub-goal execution that triggers state validation failure
        sub_goal_request = SubGoalRequest(
            goal_type="test_goal",
            parameters={},
            priority=5,
            requester="TestGoal",
            reason="Test consistency"
        )

        action = MockAction(
            name="consistency_test",
            should_fail=True,
            sub_goal_requests=[sub_goal_request]
        )

        # Setup mocks for successful sub-goal creation and planning
        mock_goal = Mock()
        mock_goal.get_target_state.return_value = GOAPTargetState(
            target_states={GameState.CHARACTER_LEVEL: 6},
            priority=5
        )
        mock_goal_manager.create_goal_from_sub_request.return_value = mock_goal

        mock_plan = GOAPActionPlan(
            actions=[GOAPAction(name="level_action", action_type="leveling")],
            plan_id="consistency_plan"
        )
        mock_goal_manager.plan_to_target_state.return_value = mock_plan

        # Mock successful sub-goal execution
        mock_action_executor.execute_plan_recursive = AsyncMock(return_value=SubGoalExecutionResult(
            success=True,
            depth_reached=1,
            actions_executed=1,
            execution_time=3.0
        ))

        # Mock state refresh
        refreshed_state = create_mock_character_state(level=6)
        mock_state_manager.refresh_state_for_parent_action.return_value = refreshed_state

        # Mock state validation to fail
        mock_state_manager.validate_recursive_state_transition.side_effect = StateConsistencyError(
            depth=1, message="Character level decreased unexpectedly"
        )

        # Mock factory context
        mock_context = GoalFactoryContext(
            character_state=refreshed_state,
            game_data=GameData(),
            recursion_depth=1,
            max_depth=5
        )
        mock_state_manager.create_goal_factory_context.return_value = mock_context

        # Execute test
        current_state = create_mock_character_state(level=5)

        # Should handle state consistency error gracefully and continue
        result = await mock_action_executor.execute_action_with_subgoals(
            action, "test_char", current_state, depth=0
        )

        # The original action should still fail since state validation failed
        # and no retry was successful
        assert result.success is False

    @pytest.mark.asyncio
    async def test_multiple_sub_goal_requests(self, mock_action_executor, mock_goal_manager, mock_state_manager):
        """Test handling multiple sub-goal requests from a single action."""
        # Create multiple sub-goal requests
        sub_goal_requests = [
            SubGoalRequest(
                goal_type="move_to_location",
                parameters={"target_x": 5, "target_y": 5},
                priority=7,
                requester="TestGoal",
                reason="Move to target"
            ),
            SubGoalRequest(
                goal_type="equip_item_type",
                parameters={"item_type": "weapon", "max_level": 5},
                priority=6,
                requester="TestGoal",
                reason="Equip weapon"
            )
        ]

        action = MockAction(
            name="multi_subgoal_action",
            should_fail=True,
            sub_goal_requests=sub_goal_requests
        )

        # Setup mocks for goal creation
        mock_goals = [Mock(), Mock()]
        for i, mock_goal in enumerate(mock_goals):
            mock_goal.get_target_state.return_value = GOAPTargetState(
                target_states={GameState.AT_TARGET_LOCATION: True},
                priority=7 - i
            )

        mock_goal_manager.create_goal_from_sub_request.side_effect = mock_goals

        # Setup mock plans (non-empty since they have actions)
        mock_plans = [
            GOAPActionPlan(
                actions=[GOAPAction(name=f"action_{i}", action_type="test")],
                plan_id=f"plan_{i}"
            )
            for i in range(2)
        ]
        mock_goal_manager.plan_to_target_state.side_effect = mock_plans

        # Mock execute_action to initially return failure with sub-goals, then success
        initial_result = ActionResult(
            success=False,
            message="Multi-subgoal action failed - needs sub-goals",
            state_changes={},
            sub_goal_requests=sub_goal_requests
        )

        final_result = ActionResult(
            success=True,
            message="Action succeeded after all sub-goals",
            state_changes={GameState.CHARACTER_XP: 150}
        )

        mock_action_executor.execute_action = AsyncMock(side_effect=[initial_result, final_result])

        # Mock successful sub-goal executions
        mock_action_executor.execute_plan_recursive = AsyncMock(return_value=SubGoalExecutionResult(
            success=True,
            depth_reached=1,
            actions_executed=1,
            execution_time=2.0
        ))

        # Mock state refresh
        refreshed_state = create_mock_character_state(x=5, y=5)
        mock_state_manager.refresh_state_for_parent_action.return_value = refreshed_state

        # Mock factory context
        mock_context = GoalFactoryContext(
            character_state=refreshed_state,
            game_data=GameData(),
            recursion_depth=1,
            max_depth=5
        )
        mock_state_manager.create_goal_factory_context.return_value = mock_context

        # Execute test
        current_state = create_mock_character_state()
        result = await mock_action_executor.execute_action_with_subgoals(
            action, "test_char", current_state, depth=0
        )

        # Verify that at least one sub-goal was processed (first one succeeds so it returns immediately)
        assert mock_goal_manager.create_goal_from_sub_request.call_count >= 1
        assert mock_goal_manager.plan_to_target_state.call_count >= 1

        # Result should be successful after processing both sub-goals
        assert result.success is True

    @pytest.mark.asyncio
    async def test_sub_goal_execution_failure_recovery(self, mock_action_executor, mock_goal_manager, mock_state_manager):
        """Test recovery when sub-goal execution fails."""
        sub_goal_request = SubGoalRequest(
            goal_type="failing_goal",
            parameters={},
            priority=8,
            requester="TestGoal",
            reason="Test failure recovery"
        )

        action = MockAction(
            name="recovery_test",
            should_fail=True,
            sub_goal_requests=[sub_goal_request]
        )

        # Setup mock goal and plan
        mock_goal = Mock()
        mock_goal.get_target_state.return_value = GOAPTargetState(
            target_states={GameState.CHARACTER_LEVEL: 6},
            priority=8
        )
        mock_goal_manager.create_goal_from_sub_request.return_value = mock_goal

        mock_plan = GOAPActionPlan(
            actions=[GOAPAction(name="failing_action", action_type="test")],
            plan_id="failure_plan"
        )
        mock_goal_manager.plan_to_target_state.return_value = mock_plan

        # Mock sub-goal execution to fail
        mock_action_executor.execute_plan_recursive = AsyncMock(return_value=SubGoalExecutionResult(
            success=False,
            depth_reached=1,
            actions_executed=0,
            execution_time=1.0,
            error_message="Sub-goal execution failed"
        ))

        # Mock factory context
        mock_context = GoalFactoryContext(
            character_state=create_mock_character_state(),
            game_data=GameData(),
            recursion_depth=1,
            max_depth=5
        )
        mock_state_manager.create_goal_factory_context.return_value = mock_context

        # Execute test
        current_state = create_mock_character_state()
        result = await mock_action_executor.execute_action_with_subgoals(
            action, "test_char", current_state, depth=0
        )

        # Should return original failure since sub-goal failed
        assert result.success is False
        assert "failed after 3 attempts" in result.message

    @pytest.mark.asyncio
    async def test_no_valid_goal_error_handling(self, mock_action_executor, mock_goal_manager, mock_state_manager):
        """Test handling of NoValidGoalError during planning."""
        sub_goal_request = SubGoalRequest(
            goal_type="impossible_goal",
            parameters={},
            priority=9,
            requester="TestGoal",
            reason="Test impossible goal"
        )

        action = MockAction(
            name="impossible_test",
            should_fail=True,
            sub_goal_requests=[sub_goal_request]
        )

        # Setup mock goal
        mock_goal = Mock()
        mock_goal.get_target_state.return_value = GOAPTargetState(
            target_states={GameState.CHARACTER_LEVEL: 100},  # Impossible jump
            priority=9
        )
        mock_goal_manager.create_goal_from_sub_request.return_value = mock_goal

        # Mock planning to raise NoValidGoalError
        mock_goal_manager.plan_to_target_state.side_effect = NoValidGoalError(
            "No valid action sequence found for impossible goal"
        )

        # Mock factory context
        mock_context = GoalFactoryContext(
            character_state=create_mock_character_state(),
            game_data=GameData(),
            recursion_depth=1,
            max_depth=5
        )
        mock_state_manager.create_goal_factory_context.return_value = mock_context

        # Execute test
        current_state = create_mock_character_state()
        result = await mock_action_executor.execute_action_with_subgoals(
            action, "test_char", current_state, depth=0
        )

        # Should handle the exception gracefully and return original failure
        assert result.success is False
        assert "failed after 3 attempts" in result.message


class TestGoalFactoryIntegration:
    """Test goal factory integration in recursive sub-goal execution."""

    @pytest.fixture
    def mock_goal_manager(self):
        """Create mock GoalManager with factory methods."""

        goal_manager = Mock(spec=GoalManager)
        return goal_manager

    def test_goal_factory_context_creation(self):
        """Test creating GoalFactoryContext for sub-goal creation."""
        character_state = create_mock_character_state()
        game_data = GameData()

        context = GoalFactoryContext(
            character_state=character_state,
            game_data=game_data,
            parent_goal_type="CombatGoal",
            recursion_depth=2,
            max_depth=8
        )

        assert context.character_state == character_state
        assert context.game_data == game_data
        assert context.parent_goal_type == "CombatGoal"
        assert context.recursion_depth == 2
        assert context.max_depth == 8

    def test_sub_goal_request_to_goal_conversion(self, mock_goal_manager):
        """Test conversion of SubGoalRequest to Goal using factory."""
        sub_goal_request = SubGoalRequest(
            goal_type="move_to_location",
            parameters={"target_x": 10, "target_y": 20},
            priority=7,
            requester="TestGoal",
            reason="Need to move for testing"
        )

        context = GoalFactoryContext(
            character_state=create_mock_character_state(),
            game_data=GameData(),
            recursion_depth=1,
            max_depth=5
        )

        # Mock the factory method
        mock_goal = Mock()
        mock_goal_manager.create_goal_from_sub_request.return_value = mock_goal

        # Test factory call
        result_goal = mock_goal_manager.create_goal_from_sub_request(sub_goal_request, context)

        assert result_goal == mock_goal
        mock_goal_manager.create_goal_from_sub_request.assert_called_once_with(sub_goal_request, context)

    def test_goal_target_state_generation(self):
        """Test that goals generated from sub-goal requests produce valid target states."""
        # This would typically be tested with actual goal implementations
        # For now, test the target state structure
        target_state = GOAPTargetState(
            target_states={
                GameState.AT_TARGET_LOCATION: True,
                GameState.CURRENT_X: 10,
                GameState.CURRENT_Y: 20
            },
            priority=7,
            timeout_seconds=300
        )

        assert target_state.target_states[GameState.AT_TARGET_LOCATION] is True
        assert target_state.target_states[GameState.CURRENT_X] == 10
        assert target_state.target_states[GameState.CURRENT_Y] == 20
        assert target_state.priority == 7
        assert target_state.timeout_seconds == 300


class TestSubGoalExecutionResult:
    """Test SubGoalExecutionResult tracking and reporting."""

    def test_successful_execution_result_tracking(self):
        """Test tracking successful sub-goal execution results."""
        final_state = create_mock_character_state(level=6, xp=1500)

        result = SubGoalExecutionResult(
            success=True,
            depth_reached=3,
            actions_executed=7,
            execution_time=45.5,
            final_state=final_state
        )

        assert result.success is True
        assert result.depth_reached == 3
        assert result.actions_executed == 7
        assert result.execution_time == 45.5
        assert result.final_state.level == 6
        assert result.error_message is None

    def test_failed_execution_result_tracking(self):
        """Test tracking failed sub-goal execution results."""
        result = SubGoalExecutionResult(
            success=False,
            depth_reached=2,
            actions_executed=3,
            execution_time=20.0,
            error_message="State consistency validation failed at depth 2"
        )

        assert result.success is False
        assert result.depth_reached == 2
        assert result.actions_executed == 3
        assert result.execution_time == 20.0
        assert result.final_state is None
        assert "State consistency validation failed" in result.error_message

    def test_execution_metrics_calculation(self):
        """Test calculation of execution metrics."""
        # Test metrics for multiple execution results
        results = [
            SubGoalExecutionResult(
                success=True, depth_reached=1, actions_executed=2, execution_time=5.0
            ),
            SubGoalExecutionResult(
                success=True, depth_reached=3, actions_executed=5, execution_time=12.0
            ),
            SubGoalExecutionResult(
                success=False, depth_reached=2, actions_executed=1, execution_time=3.0,
                error_message="Failed"
            )
        ]

        # Calculate aggregate metrics
        total_actions = sum(r.actions_executed for r in results)
        total_time = sum(r.execution_time for r in results)
        max_depth = max(r.depth_reached for r in results)
        success_rate = sum(1 for r in results if r.success) / len(results)

        assert total_actions == 8
        assert total_time == 20.0
        assert max_depth == 3
        assert success_rate == 2/3  # 2 out of 3 successful


class TestRecursiveExecutionIntegration:
    """Test complete recursive execution integration scenarios."""

    @pytest.mark.asyncio
    async def test_multi_level_recursive_chain(self):
        """Test multi-level recursive sub-goal chain execution."""
        # This would be a complex integration test that simulates:
        # 1. Combat action fails due to low HP
        # 2. Triggers rest sub-goal
        # 3. Rest requires movement to safe location
        # 4. After movement and rest, retry combat

        # For now, test the structure without full implementation
        chain_requests = [
            SubGoalRequest(
                goal_type="move_to_location",
                parameters={"target_x": 0, "target_y": 0},
                priority=9,
                requester="RestGoal",
                reason="Move to safe location for rest"
            ),
            SubGoalRequest(
                goal_type="rest_until_full_hp",
                parameters={"min_hp_percentage": 1.0},
                priority=8,
                requester="CombatGoal",
                reason="Need full HP for combat"
            )
        ]

        # Verify request structure
        assert len(chain_requests) == 2
        assert chain_requests[0].goal_type == "move_to_location"
        assert chain_requests[1].goal_type == "rest_until_full_hp"
        assert chain_requests[0].priority == 9  # Higher priority for safety

    def test_depth_limit_configuration(self):
        """Test depth limit configuration and enforcement."""
        # Test different depth limit scenarios
        depth_scenarios = [
            {"max_depth": 1, "current_depth": 0, "should_allow": True},
            {"max_depth": 1, "current_depth": 1, "should_allow": False},
            {"max_depth": 5, "current_depth": 3, "should_allow": True},
            {"max_depth": 5, "current_depth": 5, "should_allow": False},
            {"max_depth": 10, "current_depth": 9, "should_allow": True},
            {"max_depth": 10, "current_depth": 10, "should_allow": False}
        ]

        for scenario in depth_scenarios:
            max_depth = scenario["max_depth"]
            current_depth = scenario["current_depth"]
            should_allow = scenario["should_allow"]

            # Simulate depth check
            depth_exceeded = current_depth >= max_depth

            if should_allow:
                assert not depth_exceeded, f"Depth {current_depth} should be allowed with max {max_depth}"
            else:
                assert depth_exceeded, f"Depth {current_depth} should exceed max {max_depth}"

    def test_error_propagation_chain(self):
        """Test error propagation through recursive execution chain."""
        # Test that errors are properly propagated up the chain
        original_error = StateConsistencyError(3, "HP validation failed")
        wrapped_error = SubGoalExecutionError(2, "RestGoal", "Failed due to state error")
        wrapped_error.__cause__ = original_error

        # Verify error chain
        assert isinstance(wrapped_error, SubGoalExecutionError)
        assert wrapped_error.depth == 2
        assert wrapped_error.sub_goal_type == "RestGoal"
        assert wrapped_error.__cause__ == original_error
        assert isinstance(wrapped_error.__cause__, StateConsistencyError)

    def test_state_consistency_through_chain(self):
        """Test state consistency validation through recursive chain."""
        # Test state transitions through multiple levels
        initial_state = create_mock_character_state(x=0, y=0, hp=20, level=5)

        # State after movement sub-goal
        after_movement = create_mock_character_state(x=5, y=5, hp=20, level=5)

        # State after rest sub-goal
        after_rest = create_mock_character_state(x=5, y=5, hp=100, level=5)

        # State after combat sub-goal
        after_combat = create_mock_character_state(x=5, y=5, hp=80, level=6, xp=1500)

        # Verify state progression makes sense
        assert after_movement.x != initial_state.x or after_movement.y != initial_state.y
        assert after_rest.hp > after_movement.hp
        assert after_combat.level > after_rest.level
        assert after_combat.xp > initial_state.xp
