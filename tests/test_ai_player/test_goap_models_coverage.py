"""
Coverage Tests for GOAP Models

This module contains tests specifically designed to achieve 100% coverage
for GOAP-related modules by targeting the remaining uncovered lines.
"""

import pytest
from unittest.mock import Mock

from src.ai_player.types.goap_models import (
    GOAPTargetState, 
    GOAPAction, 
    GOAPActionPlan, 
    SubGoalExecutionResult,
    GoalFactoryContext
)
from src.ai_player.state.game_state import GameState


class TestGOAPTargetStateCoverage:
    """Test uncovered lines in GOAPTargetState."""
    
    def test_from_goap_dict_success(self):
        """Test from_goap_dict with valid input - covers lines 37-45."""
        goap_dict = {
            "current_x": 5,
            "current_y": 10,
            "character_gold": 100
        }
        
        result = GOAPTargetState.from_goap_dict(goap_dict, priority=3)
        
        assert result.priority == 3
        assert result.target_states[GameState.CURRENT_X] == 5
        assert result.target_states[GameState.CURRENT_Y] == 10
        assert result.target_states[GameState.CHARACTER_GOLD] == 100
    
    def test_from_goap_dict_invalid_key(self):
        """Test from_goap_dict with invalid key - covers lines 42-43."""
        goap_dict = {"invalid_key": True}
        
        with pytest.raises(ValueError, match="Invalid GameState key: invalid_key"):
            GOAPTargetState.from_goap_dict(goap_dict)


class TestGOAPActionCoverage:
    """Test uncovered lines in GOAPAction."""
    
    def test_to_dict(self):
        """Test to_dict method - covers line 61."""
        action = GOAPAction(
            name="test_action",
            action_type="movement",
            parameters={"x": 5, "y": 10},
            cost=5,
            estimated_duration=2.5
        )
        
        result = action.to_dict()
        
        # Should return a dictionary representation
        assert isinstance(result, dict)
        assert result["name"] == "test_action"
        assert result["type"] == "movement"
        assert result["parameters"] == {"x": 5, "y": 10}
        assert result["cost"] == 5
        assert result["duration"] == 2.5


class TestGOAPActionPlanCoverage:
    """Test uncovered lines in GOAPActionPlan."""
    
    def test_to_legacy_plan(self):
        """Test to_legacy_plan method - covers line 84."""
        plan = GOAPActionPlan(
            actions=[
                GOAPAction(name="move", action_type="movement", cost=3),
                GOAPAction(name="gather", action_type="gathering", cost=2)
            ],
            total_cost=5,
            plan_id="test_plan_001"
        )
        
        result = plan.to_legacy_plan()
        
        # Should return legacy format
        assert isinstance(result, list)
        assert len(result) == 2
    
    def test_to_base_actions_with_invalid_action(self):
        """Test to_base_actions with action not found - covers line 115."""
        registry = Mock()
        registry.get_action_by_name = Mock(return_value=None)  # Action not found
        
        mock_character_state = Mock()
        mock_game_data = Mock()
        
        plan = GOAPActionPlan(
            actions=[GOAPAction(name="nonexistent_action", action_type="nonexistent", cost=1)],
            total_cost=1,
            plan_id="test_plan_002"
        )
        
        result = plan.to_base_actions(registry, mock_character_state, mock_game_data)
        
        # Should return empty list when action not found
        assert result == []


class TestSubGoalExecutionResultCoverage:
    """Test uncovered lines in SubGoalExecutionResult."""
    
    def test_failed_property(self):
        """Test failed property - covers line 132."""
        result = SubGoalExecutionResult(
            success=False,
            depth_reached=1,
            actions_executed=0,
            execution_time=2.5,
            final_state=None
        )
        
        assert result.failed == True
        
        success_result = SubGoalExecutionResult(
            success=True,
            depth_reached=1,
            actions_executed=3,
            execution_time=1.5,
            final_state=None
        )
        
        assert success_result.failed == False
    
    def test_has_error_property(self):
        """Test has_error property - covers line 137."""
        result_with_error = SubGoalExecutionResult(
            success=False,
            depth_reached=1,
            actions_executed=0,
            execution_time=0.5,
            final_state=None,
            error_message="Test error"
        )
        
        assert result_with_error.has_error == True
        
        result_without_error = SubGoalExecutionResult(
            success=True,
            depth_reached=1,
            actions_executed=2,
            execution_time=1.0,
            final_state=None
        )
        
        assert result_without_error.has_error == False


class TestGoalFactoryContextCoverage:
    """Test uncovered lines in GoalFactoryContext."""
    
    def test_at_max_depth(self):
        """Test at_max_depth property - covers line 151."""
        from src.ai_player.state.character_game_state import CharacterGameState
        from src.game_data.game_data import GameData
        
        mock_character_state = Mock(spec=CharacterGameState)
        mock_game_data = Mock(spec=GameData)
        
        context = GoalFactoryContext(
            character_state=mock_character_state,
            game_data=mock_game_data,
            max_depth=3,
            recursion_depth=3
        )
        
        assert context.at_max_depth == True
        
        context_not_max = GoalFactoryContext(
            character_state=mock_character_state,
            game_data=mock_game_data,
            max_depth=3,
            recursion_depth=2
        )
        
        assert context_not_max.at_max_depth == False
    
    def test_can_recurse(self):
        """Test can_recurse property - covers line 156."""
        from src.ai_player.state.character_game_state import CharacterGameState
        from src.game_data.game_data import GameData
        
        mock_character_state = Mock(spec=CharacterGameState)
        mock_game_data = Mock(spec=GameData)
        
        context = GoalFactoryContext(
            character_state=mock_character_state,
            game_data=mock_game_data,
            max_depth=3,
            recursion_depth=2
        )
        
        assert context.can_recurse == True
        
        context_max_depth = GoalFactoryContext(
            character_state=mock_character_state,
            game_data=mock_game_data,
            max_depth=3,
            recursion_depth=3
        )
        
        assert context_max_depth.can_recurse == False
    
    def test_increment_depth(self):
        """Test increment_depth method - covers line 160."""
        from src.ai_player.state.character_game_state import CharacterGameState
        from src.game_data.game_data import GameData
        
        mock_character_state = Mock(spec=CharacterGameState)
        mock_game_data = Mock(spec=GameData)
        
        context = GoalFactoryContext(
            character_state=mock_character_state,
            game_data=mock_game_data,
            max_depth=5,
            recursion_depth=2
        )
        
        new_context = context.increment_depth()
        
        assert new_context.recursion_depth == 3
        assert new_context.max_depth == 5
        assert new_context.character_state == context.character_state
        assert new_context.game_data == context.game_data