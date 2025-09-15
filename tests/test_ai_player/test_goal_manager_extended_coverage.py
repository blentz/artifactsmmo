"""
Goal Manager Extended Coverage Tests

Targets specific uncovered lines in goal_manager.py to achieve higher coverage.
Focus on exception handling, edge cases, and error scenarios that existing tests miss.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime

from src.ai_player.goal_manager import GoalManager
from src.ai_player.state.game_state import GameState
from src.ai_player.state.character_game_state import CharacterGameState
from src.game_data.game_data import GameData
from src.ai_player.goals.equipment_goal import EquipmentGoal
from src.ai_player.goals.crafting_goal import CraftingGoal
from src.ai_player.goals.gathering_goal import GatheringGoal
from src.ai_player.goals.movement_goal import MovementGoal
from src.ai_player.goals.combat_goal import CombatGoal
from src.ai_player.types.goap_models import GOAPActionPlan, GOAPAction, SubGoalExecutionResult, GoalFactoryContext
from src.ai_player.exceptions import SubGoalExecutionError


class TestGoalManagerExtendedCoverage:
    """Extended coverage tests targeting specific uncovered lines in goal_manager.py"""

    @pytest.fixture
    def mock_cache_manager(self):
        """Create a mock cache manager for testing"""
        cache_manager = AsyncMock()
        
        # Mock cache manager methods to trigger line 86-92 coverage
        cache_manager.get_all_maps.return_value = [Mock(code="test_map")]
        cache_manager.get_all_monsters.return_value = [Mock(code="test_monster")]
        cache_manager.get_all_resources.return_value = [Mock(code="test_resource")]
        cache_manager.get_all_npcs.return_value = [Mock(code="test_npc")]
        cache_manager.get_all_items.return_value = [Mock(code="test_item")]
        
        return cache_manager

    @pytest.fixture
    def mock_action_registry(self):
        """Create a mock action registry"""
        action_registry = Mock()
        action_registry.generate_actions_for_state.return_value = []
        return action_registry

    @pytest.fixture
    def mock_cooldown_manager(self):
        """Create a mock cooldown manager"""
        cooldown_manager = Mock()
        return cooldown_manager

    @pytest.fixture
    def goal_manager(self, mock_cache_manager, mock_action_registry, mock_cooldown_manager):
        """Create goal manager with mocked dependencies"""
        return GoalManager(
            action_registry=mock_action_registry,
            cooldown_manager=mock_cooldown_manager,
            cache_manager=mock_cache_manager
        )

    # Use the common valid_character_state fixture from conftest.py
    # @pytest.fixture
    # def valid_character_state(self):
    #     """Use common valid_valid_character_state fixture instead"""
    #     pass

    async def test_get_game_data_cache_manager_exception_handling(self, goal_manager):
        """Test get_game_data method exception handling - covers lines 86-92"""
        # Mock cache manager to raise exception on get_all_maps
        goal_manager.cache_manager.get_all_maps.side_effect = Exception("Cache error")
        
        result = await goal_manager.get_game_data()
        assert result is None

    async def test_get_game_data_without_cache_manager(self):
        """Test get_game_data when cache_manager is None - covers lines 83-84"""
        action_registry = Mock()
        cooldown_manager = Mock()
        goal_manager = GoalManager(
            action_registry=action_registry,
            cooldown_manager=cooldown_manager,
            cache_manager=None
        )
        
        result = await goal_manager.get_game_data()
        assert result is None

    async def test_get_game_data_successful_case(self, goal_manager):
        """Test successful get_game_data execution - covers lines 88-91"""
        result = await goal_manager.get_game_data()
        
        assert result is not None
        assert isinstance(result, GameData)
        
        # Verify all cache manager methods were called
        goal_manager.cache_manager.get_all_maps.assert_called_once()
        goal_manager.cache_manager.get_all_monsters.assert_called_once()
        goal_manager.cache_manager.get_all_resources.assert_called_once()
        goal_manager.cache_manager.get_all_npcs.assert_called_once()
        goal_manager.cache_manager.get_all_items.assert_called_once()

    async def test_evaluate_goals_with_empty_selected_goals(self, goal_manager, valid_character_state):
        """Test evaluate_goals with no selected goals - covers line 104"""
        goal_manager.goal_selector.select_goals.return_value = []
        
        result = await goal_manager.evaluate_goals(valid_character_state)
        
        assert result == []

    async def test_evaluate_goals_with_goal_selector_exception(self, goal_manager, valid_character_state):
        """Test evaluate_goals when goal_selector raises exception - covers lines 106-111"""
        goal_manager.goal_selector.select_goals.side_effect = Exception("Selector error")
        
        with pytest.raises(Exception, match="Selector error"):
            await goal_manager.evaluate_goals(valid_character_state)

    async def test_find_best_goal_with_invalid_goal_risk(self, goal_manager, valid_character_state):
        """Test find_best_goal with goal that has invalid risk estimate - covers line 141"""
        mock_goal = Mock()
        mock_goal.estimate_error_risk.side_effect = Exception("Risk calculation error")
        mock_goal.goal_priority = 10
        
        goals = [mock_goal]
        
        # Should handle exception and continue
        result = await goal_manager.find_best_goal(goals, valid_character_state)
        assert result is None

    async def test_find_best_goal_empty_goals_list(self, goal_manager, valid_character_state):
        """Test find_best_goal with empty goals list - covers line 160"""
        result = await goal_manager.find_best_goal([], valid_character_state)
        assert result is None

    async def test_select_best_plan_with_empty_plans(self, goal_manager):
        """Test select_best_plan with empty plans list - covers line 171"""
        result = goal_manager.select_best_plan([])
        assert result is None

    async def test_execute_goal_plan_with_none_plan(self, goal_manager, valid_character_state):
        """Test execute_goal_plan with None plan - covers line 194"""
        result = await goal_manager.execute_goal_plan(None, valid_character_state)
        
        assert isinstance(result, SubGoalExecutionResult)
        assert not result.success
        assert "No plan provided" in result.failure_reason

    async def test_execute_goal_plan_with_empty_base_actions(self, goal_manager, valid_character_state):
        """Test execute_goal_plan with plan that has no base actions - covers lines 205, 224"""
        mock_plan = Mock(spec=GOAPActionPlan)
        mock_plan.to_base_actions.return_value = []
        mock_plan.action_sequence = []
        
        result = await goal_manager.execute_goal_plan(mock_plan, valid_character_state)
        
        assert isinstance(result, SubGoalExecutionResult)
        assert not result.success
        assert "No actions in plan" in result.failure_reason

    async def test_execute_goal_plan_action_execution_failure(self, goal_manager, valid_character_state):
        """Test execute_goal_plan when action execution fails - covers lines 227-232"""
        mock_action = Mock()
        mock_action.execute.side_effect = Exception("Action execution failed")
        mock_action.name = "test_action"
        
        mock_plan = Mock(spec=GOAPActionPlan)
        mock_plan.to_base_actions.return_value = [mock_action]
        mock_plan.action_sequence = [mock_action]
        
        result = await goal_manager.execute_goal_plan(mock_plan, valid_character_state)
        
        assert isinstance(result, SubGoalExecutionResult)
        assert not result.success
        assert "Action execution failed" in result.failure_reason

    async def test_execute_goal_plan_action_result_failure(self, goal_manager, valid_character_state):
        """Test execute_goal_plan when action returns failure result - covers lines 240-251"""
        mock_action_result = Mock()
        mock_action_result.success = False
        mock_action_result.message = "Action failed"
        
        mock_action = Mock()
        mock_action.execute.return_value = mock_action_result
        mock_action.name = "test_action"
        
        mock_plan = Mock(spec=GOAPActionPlan)
        mock_plan.to_base_actions.return_value = [mock_action]
        mock_plan.action_sequence = [mock_action]
        
        result = await goal_manager.execute_goal_plan(mock_plan, valid_character_state)
        
        assert isinstance(result, SubGoalExecutionResult)
        assert not result.success
        assert "Action failed" in result.failure_reason

    async def test_execute_goal_plan_valid_character_state_update_exception(self, goal_manager, valid_character_state):
        """Test execute_goal_plan when character state update fails - covers line 255"""
        mock_action_result = Mock()
        mock_action_result.success = True
        mock_action_result.state_changes = {GameState.CHARACTER_LEVEL: 20}
        
        mock_action = Mock()
        mock_action.execute.return_value = mock_action_result
        mock_action.name = "test_action"
        
        mock_plan = Mock(spec=GOAPActionPlan)
        mock_plan.to_base_actions.return_value = [mock_action]
        mock_plan.action_sequence = [mock_action]
        
        # Mock valid_character_state.update_from_dict to raise exception
        with patch.object(valid_character_state, 'update_from_dict', side_effect=Exception("State update failed")):
            result = await goal_manager.execute_goal_plan(mock_plan, valid_character_state)
            
            assert isinstance(result, SubGoalExecutionResult)
            assert not result.success
            assert "State update failed" in result.failure_reason

    async def test_generate_movement_plan_with_none_game_data(self, goal_manager, valid_character_state):
        """Test generate_movement_plan with None game_data - covers line 306"""
        with patch.object(goal_manager, 'get_game_data', return_value=None):
            result = await goal_manager.generate_movement_plan(valid_character_state, 10, 10)
            assert result is None

    async def test_generate_movement_plan_with_planner_exception(self, goal_manager, valid_character_state):
        """Test generate_movement_plan when planner raises exception - covers line 309"""
        game_data = GameData(maps=[], monsters=[], resources=[], npcs=[], items=[])
        
        with patch.object(goal_manager, 'get_game_data', return_value=game_data):
            with patch('src.ai_player.goal_manager.GOAPPlanner') as mock_planner_class:
                mock_planner = Mock()
                mock_planner.plan.side_effect = Exception("Planning failed")
                mock_planner_class.return_value = mock_planner
                
                result = await goal_manager.generate_movement_plan(valid_character_state, 10, 10)
                assert result is None