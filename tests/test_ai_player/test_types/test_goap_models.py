"""
Tests for GOAP Pydantic Models

This module tests the type-safe Pydantic models used in the unified sub-goal architecture
that eliminates dict and Any types throughout the GOAP system.
"""


import pytest
from pydantic import ValidationError

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


class TestGOAPTargetState:
    """Test GOAPTargetState Pydantic model."""

    def test_empty_target_state_creation(self):
        """Test creating empty GOAPTargetState."""
        target_state = GOAPTargetState()

        assert target_state.target_states == {}
        assert target_state.priority == 5  # Default value
        assert target_state.timeout_seconds is None

    def test_target_state_with_data(self):
        """Test creating GOAPTargetState with target states."""
        target_states = {
            GameState.CHARACTER_LEVEL: 10,
            GameState.HP_CURRENT: 100,
            GameState.COOLDOWN_READY: True,
            GameState.AT_TARGET_LOCATION: False
        }

        target_state = GOAPTargetState(
            target_states=target_states,
            priority=8,
            timeout_seconds=300
        )

        assert target_state.target_states == target_states
        assert target_state.priority == 8
        assert target_state.timeout_seconds == 300

    def test_priority_validation(self):
        """Test priority field validation (1-10 range)."""
        # Valid priorities
        for priority in [1, 5, 10]:
            target_state = GOAPTargetState(priority=priority)
            assert target_state.priority == priority

        # Invalid priorities should raise ValidationError
        with pytest.raises(ValidationError):
            GOAPTargetState(priority=0)  # Below minimum

        with pytest.raises(ValidationError):
            GOAPTargetState(priority=11)  # Above maximum

        with pytest.raises(ValidationError):
            GOAPTargetState(priority=-1)  # Negative

    def test_target_states_type_validation(self):
        """Test target_states accepts valid types."""
        valid_target_states = {
            GameState.CHARACTER_LEVEL: 5,           # int
            GameState.CHARACTER_GOLD: 100.5,        # float
            GameState.COOLDOWN_READY: True,         # bool
            GameState.CHARACTER_XP: 1000            # int
        }

        target_state = GOAPTargetState(target_states=valid_target_states)
        assert target_state.target_states == valid_target_states

    def test_pydantic_model_dump(self):
        """Test Pydantic model serialization."""
        target_states = {
            GameState.CHARACTER_LEVEL: 10,
            GameState.COOLDOWN_READY: True
        }

        target_state = GOAPTargetState(
            target_states=target_states,
            priority=7,
            timeout_seconds=180
        )

        dumped = target_state.model_dump()

        assert isinstance(dumped, dict)
        assert 'target_states' in dumped
        assert 'priority' in dumped
        assert 'timeout_seconds' in dumped
        assert dumped['priority'] == 7
        assert dumped['timeout_seconds'] == 180

    def test_model_copy(self):
        """Test Pydantic model copying."""
        original = GOAPTargetState(
            target_states={GameState.CHARACTER_LEVEL: 5},
            priority=6,
            timeout_seconds=120
        )

        # Create copy with updates
        copy = original.model_copy(update={'priority': 9})

        assert copy.priority == 9
        assert copy.timeout_seconds == 120  # Unchanged
        assert original.priority == 6  # Original unchanged


class TestGOAPAction:
    """Test GOAPAction Pydantic model."""

    def test_goap_action_creation(self):
        """Test creating GOAPAction with required fields."""
        action = GOAPAction(
            name="move_to_location",
            action_type="movement"
        )

        assert action.name == "move_to_location"
        assert action.action_type == "movement"
        assert action.parameters == {}  # Default empty dict
        assert action.cost == 1  # Default cost
        assert action.estimated_duration == 1.0  # Default duration

    def test_goap_action_with_parameters(self):
        """Test GOAPAction with parameters."""
        parameters = {
            "target_x": 10,
            "target_y": 20,
            "move_urgently": True,
            "travel_speed": 1.5
        }

        action = GOAPAction(
            name="move_with_params",
            action_type="movement",
            parameters=parameters,
            cost=3,
            estimated_duration=5.5
        )

        assert action.parameters == parameters
        assert action.cost == 3
        assert action.estimated_duration == 5.5

    def test_cost_validation(self):
        """Test cost field validation (>= 0)."""
        # Valid costs
        for cost in [0, 1, 10, 100]:
            action = GOAPAction(name="test", action_type="test", cost=cost)
            assert action.cost == cost

        # Invalid costs should raise ValidationError
        with pytest.raises(ValidationError):
            GOAPAction(name="test", action_type="test", cost=-1)

    def test_estimated_duration_validation(self):
        """Test estimated_duration field validation (>= 0)."""
        # Valid durations
        for duration in [0.0, 1.0, 5.5, 100.0]:
            action = GOAPAction(name="test", action_type="test", estimated_duration=duration)
            assert action.estimated_duration == duration

        # Invalid durations should raise ValidationError
        with pytest.raises(ValidationError):
            GOAPAction(name="test", action_type="test", estimated_duration=-0.1)

    def test_parameters_type_validation(self):
        """Test parameters accepts valid types."""
        valid_parameters = {
            "int_param": 42,
            "float_param": 3.14,
            "bool_param": False,
            "str_param": "value"
        }

        action = GOAPAction(
            name="test",
            action_type="test",
            parameters=valid_parameters
        )

        assert action.parameters == valid_parameters


class TestGOAPActionPlan:
    """Test GOAPActionPlan Pydantic model."""

    def test_empty_action_plan(self):
        """Test creating empty GOAPActionPlan."""
        plan = GOAPActionPlan(plan_id="test_plan")

        assert plan.actions == []
        assert plan.total_cost == 0
        assert plan.estimated_duration == 0.0
        assert plan.plan_id == "test_plan"

    def test_action_plan_with_actions(self):
        """Test GOAPActionPlan with multiple actions."""
        actions = [
            GOAPAction(name="move", action_type="movement", cost=2, estimated_duration=3.0),
            GOAPAction(name="fight", action_type="combat", cost=5, estimated_duration=8.0),
            GOAPAction(name="rest", action_type="recovery", cost=1, estimated_duration=2.0)
        ]

        plan = GOAPActionPlan(
            actions=actions,
            total_cost=8,
            estimated_duration=13.0,
            plan_id="combat_plan"
        )

        assert len(plan.actions) == 3
        assert plan.total_cost == 8
        assert plan.estimated_duration == 13.0
        assert plan.plan_id == "combat_plan"

    def test_total_cost_validation(self):
        """Test total_cost field validation (>= 0)."""
        # Valid costs
        for cost in [0, 10, 100]:
            plan = GOAPActionPlan(total_cost=cost, plan_id="test")
            assert plan.total_cost == cost

        # Invalid costs should raise ValidationError
        with pytest.raises(ValidationError):
            GOAPActionPlan(total_cost=-1, plan_id="test")

    def test_estimated_duration_validation(self):
        """Test estimated_duration field validation (>= 0)."""
        # Valid durations
        for duration in [0.0, 5.5, 100.0]:
            plan = GOAPActionPlan(estimated_duration=duration, plan_id="test")
            assert plan.estimated_duration == duration

        # Invalid durations should raise ValidationError
        with pytest.raises(ValidationError):
            GOAPActionPlan(estimated_duration=-1.0, plan_id="test")

    def test_calculate_plan_metrics(self):
        """Test calculating plan metrics from actions."""
        action1 = GOAPAction(name="action1", action_type="test", cost=3, estimated_duration=2.5)
        action2 = GOAPAction(name="action2", action_type="test", cost=7, estimated_duration=4.0)

        # Test that the plan can hold actions and allow metric calculation
        plan = GOAPActionPlan(
            actions=[action1, action2],
            total_cost=10,  # 3 + 7
            estimated_duration=6.5,  # 2.5 + 4.0
            plan_id="calculated_plan"
        )

        assert plan.total_cost == 10
        assert plan.estimated_duration == 6.5


class TestSubGoalExecutionResult:
    """Test SubGoalExecutionResult Pydantic model."""

    def test_successful_execution_result(self):
        """Test creating successful execution result."""
        mock_character_state = CharacterGameState(
            name="test_char", level=5, xp=1000, gold=100, hp=80, max_hp=100,
            x=10, y=15, cooldown=0, mining_level=3, mining_xp=150,
            woodcutting_level=2, woodcutting_xp=50, fishing_level=1, fishing_xp=0,
            weaponcrafting_level=1, weaponcrafting_xp=0, gearcrafting_level=1, gearcrafting_xp=0,
            jewelrycrafting_level=1, jewelrycrafting_xp=0, cooking_level=1, cooking_xp=0,
            alchemy_level=1, alchemy_xp=0
        )

        result = SubGoalExecutionResult(
            success=True,
            depth_reached=3,
            actions_executed=5,
            execution_time=45.5,
            final_state=mock_character_state
        )

        assert result.success is True
        assert result.depth_reached == 3
        assert result.actions_executed == 5
        assert result.execution_time == 45.5
        assert result.final_state == mock_character_state
        assert result.error_message is None

    def test_failed_execution_result(self):
        """Test creating failed execution result."""
        result = SubGoalExecutionResult(
            success=False,
            depth_reached=2,
            actions_executed=3,
            execution_time=30.0,
            error_message="Max depth exceeded"
        )

        assert result.success is False
        assert result.depth_reached == 2
        assert result.actions_executed == 3
        assert result.execution_time == 30.0
        assert result.final_state is None
        assert result.error_message == "Max depth exceeded"

    def test_depth_validation(self):
        """Test depth_reached field validation (>= 0)."""
        # Valid depths
        for depth in [0, 5, 10]:
            result = SubGoalExecutionResult(
                success=True,
                depth_reached=depth,
                actions_executed=1,
                execution_time=1.0
            )
            assert result.depth_reached == depth

        # Invalid depths should raise ValidationError
        with pytest.raises(ValidationError):
            SubGoalExecutionResult(
                success=True,
                depth_reached=-1,
                actions_executed=1,
                execution_time=1.0
            )

    def test_actions_executed_validation(self):
        """Test actions_executed field validation (>= 0)."""
        # Valid action counts
        for count in [0, 1, 10]:
            result = SubGoalExecutionResult(
                success=True,
                depth_reached=1,
                actions_executed=count,
                execution_time=1.0
            )
            assert result.actions_executed == count

        # Invalid action counts should raise ValidationError
        with pytest.raises(ValidationError):
            SubGoalExecutionResult(
                success=True,
                depth_reached=1,
                actions_executed=-1,
                execution_time=1.0
            )

    def test_execution_time_validation(self):
        """Test execution_time field validation (>= 0)."""
        # Valid execution times
        for time_val in [0.0, 1.5, 100.0]:
            result = SubGoalExecutionResult(
                success=True,
                depth_reached=1,
                actions_executed=1,
                execution_time=time_val
            )
            assert result.execution_time == time_val

        # Invalid execution times should raise ValidationError
        with pytest.raises(ValidationError):
            SubGoalExecutionResult(
                success=True,
                depth_reached=1,
                actions_executed=1,
                execution_time=-0.1
            )


class TestGoalFactoryContext:
    """Test GoalFactoryContext Pydantic model."""

    def test_factory_context_creation(self):
        """Test creating GoalFactoryContext with required fields."""
        mock_character_state = CharacterGameState(
            name="test_char", level=5, xp=1000, gold=100, hp=80, max_hp=100,
            x=10, y=15, cooldown=0, mining_level=3, mining_xp=150,
            woodcutting_level=2, woodcutting_xp=50, fishing_level=1, fishing_xp=0,
            weaponcrafting_level=1, weaponcrafting_xp=0, gearcrafting_level=1, gearcrafting_xp=0,
            jewelrycrafting_level=1, jewelrycrafting_xp=0, cooking_level=1, cooking_xp=0,
            alchemy_level=1, alchemy_xp=0
        )

        mock_game_data = GameData()

        context = GoalFactoryContext(
            character_state=mock_character_state,
            game_data=mock_game_data
        )

        assert context.character_state == mock_character_state
        assert context.game_data == mock_game_data
        assert context.parent_goal_type is None  # Default
        assert context.recursion_depth == 0  # Default
        assert context.max_depth == 10  # Default

    def test_factory_context_with_recursion_info(self):
        """Test GoalFactoryContext with recursion tracking."""
        mock_character_state = CharacterGameState(
            name="test_char", level=5, xp=1000, gold=100, hp=80, max_hp=100,
            x=10, y=15, cooldown=0, mining_level=3, mining_xp=150,
            woodcutting_level=2, woodcutting_xp=50, fishing_level=1, fishing_xp=0,
            weaponcrafting_level=1, weaponcrafting_xp=0, gearcrafting_level=1, gearcrafting_xp=0,
            jewelrycrafting_level=1, jewelrycrafting_xp=0, cooking_level=1, cooking_xp=0,
            alchemy_level=1, alchemy_xp=0
        )

        mock_game_data = GameData()

        context = GoalFactoryContext(
            character_state=mock_character_state,
            game_data=mock_game_data,
            parent_goal_type="CombatGoal",
            recursion_depth=3,
            max_depth=8
        )

        assert context.parent_goal_type == "CombatGoal"
        assert context.recursion_depth == 3
        assert context.max_depth == 8

    def test_recursion_depth_validation(self):
        """Test recursion_depth field validation (>= 0)."""
        mock_character_state = CharacterGameState(
            name="test_char", level=5, xp=1000, gold=100, hp=80, max_hp=100,
            x=10, y=15, cooldown=0, mining_level=3, mining_xp=150,
            woodcutting_level=2, woodcutting_xp=50, fishing_level=1, fishing_xp=0,
            weaponcrafting_level=1, weaponcrafting_xp=0, gearcrafting_level=1, gearcrafting_xp=0,
            jewelrycrafting_level=1, jewelrycrafting_xp=0, cooking_level=1, cooking_xp=0,
            alchemy_level=1, alchemy_xp=0
        )

        mock_game_data = GameData()

        # Valid recursion depths
        for depth in [0, 3, 10]:
            context = GoalFactoryContext(
                character_state=mock_character_state,
                game_data=mock_game_data,
                recursion_depth=depth
            )
            assert context.recursion_depth == depth

        # Invalid recursion depths should raise ValidationError
        with pytest.raises(ValidationError):
            GoalFactoryContext(
                character_state=mock_character_state,
                game_data=mock_game_data,
                recursion_depth=-1
            )

    def test_max_depth_validation(self):
        """Test max_depth field validation (>= 1)."""
        mock_character_state = CharacterGameState(
            name="test_char", level=5, xp=1000, gold=100, hp=80, max_hp=100,
            x=10, y=15, cooldown=0, mining_level=3, mining_xp=150,
            woodcutting_level=2, woodcutting_xp=50, fishing_level=1, fishing_xp=0,
            weaponcrafting_level=1, weaponcrafting_xp=0, gearcrafting_level=1, gearcrafting_xp=0,
            jewelrycrafting_level=1, jewelrycrafting_xp=0, cooking_level=1, cooking_xp=0,
            alchemy_level=1, alchemy_xp=0
        )

        mock_game_data = GameData()

        # Valid max depths
        for max_depth in [1, 5, 15]:
            context = GoalFactoryContext(
                character_state=mock_character_state,
                game_data=mock_game_data,
                max_depth=max_depth
            )
            assert context.max_depth == max_depth

        # Invalid max depths should raise ValidationError
        with pytest.raises(ValidationError):
            GoalFactoryContext(
                character_state=mock_character_state,
                game_data=mock_game_data,
                max_depth=0
            )

    def test_pydantic_model_validation(self):
        """Test overall Pydantic model validation."""
        mock_character_state = CharacterGameState(
            name="test_char", level=5, xp=1000, gold=100, hp=80, max_hp=100,
            x=10, y=15, cooldown=0, mining_level=3, mining_xp=150,
            woodcutting_level=2, woodcutting_xp=50, fishing_level=1, fishing_xp=0,
            weaponcrafting_level=1, weaponcrafting_xp=0, gearcrafting_level=1, gearcrafting_xp=0,
            jewelrycrafting_level=1, jewelrycrafting_xp=0, cooking_level=1, cooking_xp=0,
            alchemy_level=1, alchemy_xp=0
        )

        mock_game_data = GameData()

        # Valid context should not raise exceptions
        context = GoalFactoryContext(
            character_state=mock_character_state,
            game_data=mock_game_data
        )

        # Test serialization
        dumped = context.model_dump()
        assert isinstance(dumped, dict)
        assert 'character_state' in dumped
        assert 'game_data' in dumped
        assert 'recursion_depth' in dumped
        assert 'max_depth' in dumped


class TestModelIntegration:
    """Test integration between different GOAP models."""

    def test_goap_target_state_in_factory_context(self):
        """Test using GOAPTargetState within factory patterns."""
        target_state = GOAPTargetState(
            target_states={
                GameState.CHARACTER_LEVEL: 10,
                GameState.AT_TARGET_LOCATION: True
            },
            priority=8,
            timeout_seconds=300
        )

        # Test that target state can be used in planning context
        assert len(target_state.target_states) == 2
        assert target_state.priority == 8

    def test_goap_action_in_plan(self):
        """Test using GOAPAction within GOAPActionPlan."""
        actions = [
            GOAPAction(name="move", action_type="movement", cost=2),
            GOAPAction(name="fight", action_type="combat", cost=5)
        ]

        plan = GOAPActionPlan(
            actions=actions,
            total_cost=7,
            estimated_duration=10.0,
            plan_id="integration_test"
        )

        assert len(plan.actions) == 2
        assert plan.actions[0].name == "move"
        assert plan.actions[1].name == "fight"

    def test_execution_result_with_character_state(self):
        """Test SubGoalExecutionResult with actual CharacterGameState."""
        final_state = CharacterGameState(
            name="test_char", level=6, xp=1500, gold=150, hp=100, max_hp=100,
            x=20, y=25, cooldown=0, mining_level=4, mining_xp=200,
            woodcutting_level=2, woodcutting_xp=50, fishing_level=1, fishing_xp=0,
            weaponcrafting_level=1, weaponcrafting_xp=0, gearcrafting_level=1, gearcrafting_xp=0,
            jewelrycrafting_level=1, jewelrycrafting_xp=0, cooking_level=1, cooking_xp=0,
            alchemy_level=1, alchemy_xp=0
        )

        result = SubGoalExecutionResult(
            success=True,
            depth_reached=2,
            actions_executed=4,
            execution_time=60.0,
            final_state=final_state
        )

        assert result.final_state.level == 6
        assert result.final_state.name == "test_char"
        assert result.success is True

    def test_type_safety_enforcement(self):
        """Test that Pydantic enforces type safety throughout."""
        # Test that incorrect types are rejected
        with pytest.raises(ValidationError):
            GOAPTargetState(target_states="invalid")  # Should be dict

        with pytest.raises(ValidationError):
            GOAPAction(name=123, action_type="test")  # name should be str

        with pytest.raises(ValidationError):
            GOAPActionPlan(actions="invalid", plan_id="test")  # actions should be list

        with pytest.raises(ValidationError):
            SubGoalExecutionResult(
                success=[1, 2, 3],  # Should be bool, not list
                depth_reached=1,
                actions_executed=1,
                execution_time=1.0
            )
