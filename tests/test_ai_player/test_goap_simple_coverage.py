"""
Simple Coverage Tests for GOAP Models - Final Lines

This module contains minimal tests to hit the final uncovered lines.
"""

from unittest.mock import Mock

from src.ai_player.types.goap_models import (
    GOAPTargetState, 
    GOAPActionPlan
)
from src.ai_player.state.game_state import GameState


class TestFinalCoverage:
    """Test final uncovered lines."""
    
    def test_goap_target_state_to_goap_dict(self):
        """Test to_goap_dict method - covers line 28."""
        target_state = GOAPTargetState(
            target_states={
                GameState.CURRENT_X: 5,
                GameState.CURRENT_Y: 10
            },
            priority=3
        )
        
        result = target_state.to_goap_dict()
        
        assert result == {"current_x": 5, "current_y": 10}
    
    def test_goap_target_state_bool(self):
        """Test __bool__ method - covers line 32."""
        empty_target = GOAPTargetState()
        assert bool(empty_target) == False
        
        non_empty_target = GOAPTargetState(
            target_states={GameState.CURRENT_X: 5}
        )
        assert bool(non_empty_target) == True
    
    def test_goap_action_plan_is_empty(self):
        """Test is_empty property - covers line 80."""
        empty_plan = GOAPActionPlan(
            actions=[],
            plan_id="empty_plan"
        )
        assert empty_plan.is_empty == True
        
        from src.ai_player.types.goap_models import GOAPAction
        non_empty_plan = GOAPActionPlan(
            actions=[GOAPAction(name="test", action_type="test")],
            plan_id="non_empty_plan"
        )
        assert non_empty_plan.is_empty == False
    
    def test_goap_action_plan_successful_action_lookup(self):
        """Test to_base_actions with successful lookup - covers lines 116-117."""
        from src.ai_player.types.goap_models import GOAPAction
        
        mock_registry = Mock()
        mock_action = Mock()
        mock_registry.get_action_by_name = Mock(return_value=mock_action)
        
        mock_character_state = Mock()
        mock_game_data = Mock()
        
        plan = GOAPActionPlan(
            actions=[GOAPAction(name="valid_action", action_type="test", cost=1)],
            total_cost=1,
            plan_id="test_plan"
        )
        
        result = plan.to_base_actions(mock_registry, mock_character_state, mock_game_data)
        
        # Should return list with the found action
        assert result == [mock_action]
        # Method is called with action name and parameters
        mock_registry.get_action_by_name.assert_called()