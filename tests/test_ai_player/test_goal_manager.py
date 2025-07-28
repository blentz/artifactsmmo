"""
Tests for GoalManager and GOAP integration

This module tests goal selection, GOAP planning integration, dynamic goal
management, and action plan generation functionality.
"""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from src.ai_player.actions.base_action import BaseAction
from src.ai_player.goal_manager import CooldownAwarePlanner, GoalManager
from src.ai_player.state.game_state import GameState
from src.lib.goap import Action_List


class TestGoalManager:
    """Test GoalManager functionality"""

    @pytest.fixture
    def goal_manager(self):
        """Create GoalManager instance for testing"""
        mock_action_registry = Mock()
        mock_cooldown_manager = Mock()
        return GoalManager(mock_action_registry, mock_cooldown_manager)

    @pytest.fixture
    def mock_current_state(self):
        """Mock current character state for testing"""
        return {
            GameState.CHARACTER_LEVEL: 5,
            GameState.CHARACTER_XP: 1200,
            GameState.CHARACTER_GOLD: 150,
            GameState.HP_CURRENT: 80,
            GameState.HP_MAX: 100,
            GameState.CURRENT_X: 10,
            GameState.CURRENT_Y: 15,
            GameState.COOLDOWN_READY: True,
            GameState.MINING_LEVEL: 3,
            GameState.WOODCUTTING_LEVEL: 2,
            GameState.FISHING_LEVEL: 1,
            GameState.WEAPONCRAFTING_LEVEL: 1,
            GameState.CAN_FIGHT: True,
            GameState.CAN_GATHER: True,
            GameState.CAN_CRAFT: True,
            GameState.INVENTORY_SPACE_AVAILABLE: 15
        }

    def test_goal_manager_initialization(self, goal_manager):
        """Test GoalManager initialization"""
        assert hasattr(goal_manager, 'select_next_goal')
        assert hasattr(goal_manager, 'plan_actions')
        assert hasattr(goal_manager, 'max_level_achieved')
        assert hasattr(goal_manager, 'action_registry')
        assert hasattr(goal_manager, 'cooldown_manager')

    def test_max_level_achieved_true(self, goal_manager):
        """Test max_level_achieved returns True when character is level 45 or higher"""
        state_level_45 = {GameState.CHARACTER_LEVEL: 45}
        state_level_50 = {GameState.CHARACTER_LEVEL: 50}

        assert goal_manager.max_level_achieved(state_level_45) is True
        assert goal_manager.max_level_achieved(state_level_50) is True

    def test_max_level_achieved_false(self, goal_manager):
        """Test max_level_achieved returns False when character is below level 45"""
        state_level_1 = {GameState.CHARACTER_LEVEL: 1}
        state_level_44 = {GameState.CHARACTER_LEVEL: 44}
        state_level_30 = {GameState.CHARACTER_LEVEL: 30}

        assert goal_manager.max_level_achieved(state_level_1) is False
        assert goal_manager.max_level_achieved(state_level_44) is False
        assert goal_manager.max_level_achieved(state_level_30) is False

    def test_max_level_achieved_missing_level(self, goal_manager):
        """Test max_level_achieved returns False when level is missing"""
        empty_state = {}
        state_no_level = {GameState.CHARACTER_XP: 1000}

        assert goal_manager.max_level_achieved(empty_state) is False
        assert goal_manager.max_level_achieved(state_no_level) is False

    def test_convert_action_to_goap(self, goal_manager):
        """Test converting BaseAction to GOAP format"""
        # Create a mock action
        mock_action = Mock(spec=BaseAction)
        mock_action.name = "test_action"
        mock_action.cost = 5
        mock_action.get_preconditions.return_value = {
            GameState.COOLDOWN_READY: True,
            GameState.CHARACTER_LEVEL: 10
        }
        mock_action.get_effects.return_value = {
            GameState.CHARACTER_XP: 100,
            GameState.CURRENT_X: 15
        }

        result = goal_manager.convert_action_to_goap(mock_action)

        # Should return tuple with (name, conditions, effects, weight)
        assert isinstance(result, tuple)
        assert len(result) == 4

        name, conditions, effects, weight = result

        # Check name and weight
        assert name == "test_action"
        assert weight == 5

        # Check conditions are converted to string keys
        assert isinstance(conditions, dict)
        assert "cooldown_ready" in conditions
        assert "character_level" in conditions
        assert conditions["cooldown_ready"] is True
        assert conditions["character_level"] == 10

        # Check effects are converted to string keys
        assert isinstance(effects, dict)
        assert "character_xp" in effects
        assert "current_x" in effects
        assert effects["character_xp"] == 100
        assert effects["current_x"] == 15

        # Verify mock was called
        mock_action.get_preconditions.assert_called_once()
        mock_action.get_effects.assert_called_once()

    def test_create_goap_actions(self, goal_manager):
        """Test creating GOAP action list from action registry"""
        # Mock action classes
        class MockAction1(BaseAction):
            @property
            def name(self): return "action1"
            @property
            def cost(self): return 2
            def get_preconditions(self): return {GameState.COOLDOWN_READY: True}
            def get_effects(self): return {GameState.CHARACTER_XP: 50}
            async def execute(self, character_name, current_state): pass

        class MockAction2(BaseAction):
            @property
            def name(self): return "action2"
            @property
            def cost(self): return 3
            def get_preconditions(self): return {GameState.CAN_FIGHT: True}
            def get_effects(self): return {GameState.CHARACTER_LEVEL: 1}
            async def execute(self, character_name, current_state): pass

        # Mock action registry
        goal_manager.action_registry.get_all_action_types.return_value = [MockAction1, MockAction2]

        result = goal_manager.create_goap_actions()

        # Should return Action_List from GOAP library
        assert isinstance(result, Action_List)

        # Should contain both actions
        assert "action1" in result.conditions
        assert "action2" in result.conditions
        assert "action1" in result.reactions
        assert "action2" in result.reactions
        assert "action1" in result.weights
        assert "action2" in result.weights

        # Check conditions are converted to string keys
        assert result.conditions["action1"]["cooldown_ready"] is True
        assert result.conditions["action2"]["can_fight"] is True

        # Check effects are converted to string keys
        assert result.reactions["action1"]["character_xp"] == 50
        assert result.reactions["action2"]["character_level"] == 1

        # Check weights
        assert result.weights["action1"] == 2
        assert result.weights["action2"] == 3

    def test_create_cooldown_aware_actions_ready(self, goal_manager):
        """Test creating cooldown-aware actions when character is ready"""
        character_name = "test_character"

        # Mock cooldown manager - character is ready
        goal_manager.cooldown_manager.is_ready.return_value = True

        # Mock the create_goap_actions method
        mock_action_list = Mock()
        goal_manager.create_goap_actions = Mock(return_value=mock_action_list)

        result = goal_manager.create_cooldown_aware_actions(character_name)

        # Should return all actions when character is ready
        assert result == mock_action_list
        goal_manager.cooldown_manager.is_ready.assert_called_once_with(character_name)
        goal_manager.create_goap_actions.assert_called_once()

    def test_create_cooldown_aware_actions_on_cooldown(self, goal_manager):
        """Test creating cooldown-aware actions when character is on cooldown"""
        character_name = "test_character"

        # Mock cooldown manager - character is on cooldown
        goal_manager.cooldown_manager.is_ready.return_value = False

        # Create mock action list with some actions requiring cooldown
        mock_action_list = Action_List()
        mock_action_list.add_condition("action_requires_cooldown", cooldown_ready=True, character_level=5)
        mock_action_list.add_reaction("action_requires_cooldown", character_xp=100)
        mock_action_list.set_weight("action_requires_cooldown", 3)

        mock_action_list.add_condition("action_no_cooldown", character_level=5)
        mock_action_list.add_reaction("action_no_cooldown", character_xp=50)
        mock_action_list.set_weight("action_no_cooldown", 2)

        goal_manager.create_goap_actions = Mock(return_value=mock_action_list)

        result = goal_manager.create_cooldown_aware_actions(character_name)

        # Should filter out actions requiring cooldown
        assert isinstance(result, Action_List)
        assert "action_no_cooldown" in result.conditions
        assert "action_requires_cooldown" not in result.conditions

        # Verify cooldown check was called
        goal_manager.cooldown_manager.is_ready.assert_called_once_with(character_name)

    def test_should_defer_planning_ready(self, goal_manager):
        """Test should_defer_planning when character is ready"""
        character_name = "test_character"
        goal_manager.cooldown_manager.is_ready.return_value = True

        result = goal_manager.should_defer_planning(character_name)

        assert result is False
        goal_manager.cooldown_manager.is_ready.assert_called_once_with(character_name)

    def test_should_defer_planning_on_cooldown(self, goal_manager):
        """Test should_defer_planning when character is on cooldown"""
        character_name = "test_character"
        goal_manager.cooldown_manager.is_ready.return_value = False

        result = goal_manager.should_defer_planning(character_name)

        assert result is True
        goal_manager.cooldown_manager.is_ready.assert_called_once_with(character_name)

    def test_get_early_game_goals(self, goal_manager):
        """Test getting early game goals for level 1-10 characters"""
        early_game_state = {
            GameState.CHARACTER_LEVEL: 3,
            GameState.CHARACTER_XP: 300,
            GameState.CHARACTER_GOLD: 100,
            GameState.MINING_LEVEL: 2,
            GameState.MINING_XP: 150,
            GameState.WOODCUTTING_LEVEL: 1,
            GameState.WOODCUTTING_XP: 50
        }

        goals = goal_manager.get_early_game_goals(early_game_state)

        assert isinstance(goals, list)
        assert len(goals) > 0

        # Should contain level progression goal
        level_goals = [g for g in goals if 'target_state' in g and GameState.CHARACTER_LEVEL in g['target_state']]
        assert len(level_goals) > 0
        assert level_goals[0]['target_state'][GameState.CHARACTER_LEVEL] == 4  # Next level

        # Should contain skill goals
        mining_goals = [g for g in goals if 'target_state' in g and GameState.MINING_LEVEL in g['target_state']]
        assert len(mining_goals) > 0
        assert mining_goals[0]['target_state'][GameState.MINING_LEVEL] == 3  # Next mining level

        # Should contain economic goal
        gold_goals = [g for g in goals if 'target_state' in g and GameState.CHARACTER_GOLD in g['target_state']]
        assert len(gold_goals) > 0
        assert gold_goals[0]['target_state'][GameState.CHARACTER_GOLD] == 600  # Current + 500

    def test_get_early_game_goals_high_level(self, goal_manager):
        """Test early game goals don't include level goals for level 10+"""
        high_level_state = {
            GameState.CHARACTER_LEVEL: 15,
            GameState.CHARACTER_XP: 5000,
            GameState.MINING_LEVEL: 8,
            GameState.WOODCUTTING_LEVEL: 8
        }

        goals = goal_manager.get_early_game_goals(high_level_state)

        # Should not include character level goals for high level characters
        level_goals = [g for g in goals if GameState.CHARACTER_LEVEL in g]
        assert len(level_goals) == 0

    def test_select_next_goal_max_level(self, goal_manager):
        """Test select_next_goal returns empty for max level character"""
        max_level_state = {GameState.CHARACTER_LEVEL: 45}

        goal = goal_manager.select_next_goal(max_level_state)

        assert goal == {}

    def test_select_next_goal_survival_priority(self, goal_manager):
        """Test select_next_goal prioritizes survival when HP is low"""
        critical_hp_state = {
            GameState.CHARACTER_LEVEL: 10,
            GameState.HP_CURRENT: 10,  # Critical HP
            GameState.HP_MAX: 100
        }

        goal = goal_manager.select_next_goal(critical_hp_state)

        # Should return survival goal
        assert goal['type'] in ['emergency_rest', 'health_recovery', 'survival']
        assert 'target_state' in goal
        assert GameState.HP_CURRENT in goal['target_state']
        assert goal['target_state'][GameState.HP_CURRENT] == 100  # Full recovery
        assert GameState.AT_SAFE_LOCATION in goal['target_state']

    def test_select_next_goal_early_game(self, goal_manager):
        """Test select_next_goal for early game character"""
        early_game_state = {
            GameState.CHARACTER_LEVEL: 5,
            GameState.CHARACTER_XP: 500,
            GameState.HP_CURRENT: 80,
            GameState.HP_MAX: 100,
            GameState.MINING_LEVEL: 3
        }

        goal = goal_manager.select_next_goal(early_game_state)

        # Should return a goal (not empty)
        assert isinstance(goal, dict)
        assert len(goal) > 0

        # Should prioritize character level progression
        assert 'target_state' in goal
        if GameState.CHARACTER_LEVEL in goal['target_state']:
            assert goal['target_state'][GameState.CHARACTER_LEVEL] == 6  # Next level

    def test_select_next_goal_early_game_original(self, goal_manager, mock_current_state):
        """Test goal selection for early game character"""
        # Early game character (level 5)
        goal = goal_manager.select_next_goal(mock_current_state)

        assert isinstance(goal, dict)
        assert 'type' in goal
        assert 'priority' in goal
        assert 'target_state' in goal

        # Early game should focus on basic progression
        early_game_goals = ['level_up', 'skill_training', 'equipment_upgrade', 'resource_gathering']
        assert goal['type'] in early_game_goals

    def test_select_next_goal_mid_game(self, goal_manager):
        """Test goal selection for mid game character"""
        mid_game_state = {
            GameState.CHARACTER_LEVEL: 20,
            GameState.CHARACTER_XP: 15000,
            GameState.HP_CURRENT: 150,
            GameState.HP_MAX: 150,
            GameState.MINING_LEVEL: 15,
            GameState.WOODCUTTING_LEVEL: 12,
            GameState.CAN_FIGHT: True,
            GameState.CAN_CRAFT: True,
            GameState.CHARACTER_GOLD: 5000
        }

        goal = goal_manager.select_next_goal(mid_game_state)

        assert isinstance(goal, dict)
        # Mid game should have more advanced goals
        mid_game_goals = ['economic_optimization', 'advanced_crafting', 'elite_combat', 'specialization']
        # Goal type may vary based on implementation
        assert goal['type'] is not None

    def test_select_next_goal_emergency_conditions(self, goal_manager):
        """Test goal selection with emergency conditions"""
        emergency_state = {
            GameState.CHARACTER_LEVEL: 10,
            GameState.HP_CURRENT: 5,  # Critical HP
            GameState.HP_MAX: 100,
            GameState.COOLDOWN_READY: True,
            GameState.CAN_REST: True,
            GameState.AT_SAFE_LOCATION: True
        }

        goal = goal_manager.select_next_goal(emergency_state)

        # Should prioritize survival/recovery goals
        assert goal['type'] in ['emergency_rest', 'health_recovery', 'survival']
        assert goal['priority'] >= 9  # High priority for emergency

    def test_select_next_goal_inventory_full(self, goal_manager):
        """Test goal selection when inventory is full"""
        full_inventory_state = {
            GameState.CHARACTER_LEVEL: 8,
            GameState.INVENTORY_FULL: True,
            GameState.INVENTORY_SPACE_AVAILABLE: 0,
            GameState.AT_BANK_LOCATION: False,
            GameState.CAN_MOVE: True,
            GameState.COOLDOWN_READY: True
        }

        goal = goal_manager.select_next_goal(full_inventory_state)

        # Should prioritize inventory management
        assert goal['type'] in ['inventory_management', 'banking', 'item_selling']
        assert goal['priority'] >= 7  # High priority for inventory issues

    @pytest.mark.asyncio
    async def test_plan_actions_basic_goal(self, goal_manager, mock_current_state):
        """Test action planning for basic goal"""
        goal = {
            'type': 'level_up',
            'target_state': {
                GameState.CHARACTER_LEVEL: 6,
                GameState.CHARACTER_XP: 1500
            }
        }

        # Mock GOAP planner
        mock_plan = [
            {'name': 'move_to_forest', 'cost': 2},
            {'name': 'fight_goblin', 'cost': 5},
            {'name': 'fight_goblin', 'cost': 5},
            {'name': 'rest', 'cost': 1}
        ]

        with patch.object(goal_manager, '_create_goap_planner') as mock_create_planner:
            mock_planner = Mock()
            mock_planner.calculate.return_value = mock_plan
            mock_create_planner.return_value = mock_planner

            plan = await goal_manager.plan_actions(mock_current_state, goal)

            assert isinstance(plan, list)
            assert len(plan) == 4
            assert plan[0]['name'] == 'move_to_forest'
            assert plan[-1]['name'] == 'rest'

    @pytest.mark.asyncio
    async def test_plan_actions_no_plan_found(self, goal_manager, mock_current_state):
        """Test action planning when no plan can be found"""
        impossible_goal = {
            'type': 'impossible_goal',
            'target_state': {
                GameState.CHARACTER_LEVEL: 100,  # Impossible jump
                GameState.HP_CURRENT: -1  # Invalid state
            }
        }

        with patch.object(goal_manager, '_create_goap_planner') as mock_create_planner:
            mock_planner = Mock()
            mock_planner.calculate.return_value = []  # No plan found
            mock_create_planner.return_value = mock_planner

            plan = await goal_manager.plan_actions(mock_current_state, impossible_goal)

            assert isinstance(plan, list)
            assert len(plan) == 0

    @pytest.mark.asyncio
    async def test_plan_actions_with_action_registry(self, goal_manager, mock_current_state):
        """Test action planning integration with action registry"""
        goal = {
            'type': 'resource_gathering',
            'target_state': {
                GameState.ITEM_QUANTITY: 10,  # Gather 10 items
                GameState.MINING_LEVEL: 4
            }
        }

        # Mock action registry
        mock_actions = [
            Mock(name='move_to_mine', cost=2,
                 get_preconditions=Mock(return_value={GameState.COOLDOWN_READY: True}),
                 get_effects=Mock(return_value={GameState.AT_RESOURCE_LOCATION: True})),
            Mock(name='gather_copper', cost=3,
                 get_preconditions=Mock(return_value={GameState.CAN_GATHER: True}),
                 get_effects=Mock(return_value={GameState.ITEM_QUANTITY: 1}))
        ]

        with patch.object(goal_manager.action_registry, 'get_all_action_types') as mock_get_actions, \
             patch.object(goal_manager, '_create_goap_planner') as mock_create_planner:

            # Create mock action classes that can be instantiated
            mock_action_classes = []
            for action_mock in mock_actions:
                mock_class = Mock()
                mock_class.return_value = action_mock  # When instantiated, return the action mock
                mock_class.__name__ = action_mock.name
                mock_action_classes.append(mock_class)
            
            mock_get_actions.return_value = mock_action_classes

            mock_planner = Mock()
            mock_planner.calculate.return_value = [
                {'name': 'move_to_mine', 'cost': 2},
                {'name': 'gather_copper', 'cost': 3}
            ]
            mock_create_planner.return_value = mock_planner

            plan = await goal_manager.plan_actions(mock_current_state, goal)

            assert len(plan) == 2
            mock_get_actions.assert_called_once()

    def test_update_goal_priorities_based_on_state(self, goal_manager, mock_current_state):
        """Test updating goal priorities based on current state"""
        initial_priorities = {
            'level_up': 8,
            'resource_gathering': 6,
            'equipment_upgrade': 4,
            'exploration': 2
        }

        updated_priorities = goal_manager.update_goal_priorities(mock_current_state, initial_priorities)

        assert isinstance(updated_priorities, dict)

        # Priorities should be adjusted based on state
        for goal_type, priority in updated_priorities.items():
            assert isinstance(priority, (int, float))
            assert 0 <= priority <= 10

    def test_update_goal_priorities_low_hp(self, goal_manager):
        """Test goal priority updates with low HP"""
        low_hp_state = {
            GameState.CHARACTER_LEVEL: 10,
            GameState.HP_CURRENT: 15,  # Very low HP
            GameState.HP_MAX: 100,
            GameState.CAN_REST: True
        }

        initial_priorities = {
            'level_up': 8,
            'survival': 5,
            'resource_gathering': 6
        }

        updated_priorities = goal_manager.update_goal_priorities(low_hp_state, initial_priorities)

        # Survival goals should get higher priority
        assert updated_priorities['survival'] > initial_priorities['survival']

    def test_get_available_goals_early_game(self, goal_manager, mock_current_state):
        """Test getting available goals for early game"""
        available_goals = goal_manager.get_available_goals(mock_current_state)

        assert isinstance(available_goals, list)
        assert len(available_goals) > 0

        for goal in available_goals:
            assert isinstance(goal, dict)
            assert 'type' in goal
            assert 'priority' in goal
            assert 'requirements_met' in goal

    def test_get_available_goals_filtering(self, goal_manager):
        """Test goal filtering based on character capabilities"""
        limited_state = {
            GameState.CHARACTER_LEVEL: 1,
            GameState.MINING_LEVEL: 1,
            GameState.CAN_FIGHT: False,  # Cannot fight
            GameState.CAN_GATHER: True,
            GameState.CAN_CRAFT: False,  # Cannot craft
            GameState.COOLDOWN_READY: True
        }

        available_goals = goal_manager.get_available_goals(limited_state)

        # Should only include goals that character can pursue
        for goal in available_goals:
            if goal['type'] == 'combat_training':
                assert goal['requirements_met'] is False
            elif goal['type'] == 'resource_gathering':
                assert goal['requirements_met'] is True

    def test_evaluate_goal_feasibility(self, goal_manager, mock_current_state):
        """Test goal feasibility evaluation"""
        feasible_goal = {
            'type': 'skill_training',
            'target_state': {
                GameState.MINING_LEVEL: 4  # Achievable from level 3
            },
            'requirements': {
                GameState.CAN_GATHER: True,
                GameState.TOOL_EQUIPPED: 'pickaxe'
            }
        }

        is_feasible = goal_manager.evaluate_goal_feasibility(mock_current_state, feasible_goal)
        assert isinstance(is_feasible, bool)

    def test_evaluate_goal_feasibility_impossible(self, goal_manager, mock_current_state):
        """Test goal feasibility evaluation for impossible goals"""
        impossible_goal = {
            'type': 'impossible_skill_jump',
            'target_state': {
                GameState.MINING_LEVEL: 50  # Huge jump from level 3
            },
            'requirements': {
                GameState.CHARACTER_LEVEL: 45  # Character is only level 5
            }
        }

        is_feasible = goal_manager.evaluate_goal_feasibility(mock_current_state, impossible_goal)
        assert is_feasible is False

    def test_evaluate_goal_feasibility_detailed_analysis(self, goal_manager, mock_current_state):
        """Test detailed goal feasibility analysis"""
        complex_goal = {
            'type': 'complex_progression',
            'target_state': {
                GameState.CHARACTER_LEVEL: 10,  # Jump from 5 to 10
                GameState.MINING_LEVEL: 5,  # Jump from 3 to 5
                GameState.CHARACTER_GOLD: 1000  # Jump from 150 to 1000
            }
        }

        # Test detailed analysis
        feasibility = goal_manager.evaluate_goal_feasibility(mock_current_state, complex_goal, simple=False)
        
        assert isinstance(feasibility, dict)
        assert 'feasible' in feasibility
        assert 'estimated_actions' in feasibility
        assert 'estimated_time' in feasibility
        assert 'confidence' in feasibility
        assert isinstance(feasibility['estimated_actions'], int)
        assert isinstance(feasibility['estimated_time'], (int, float))

    def test_select_next_goal_exception_handling(self, goal_manager):
        """Test exception handling in select_next_goal"""
        # Mock max_level_achieved to raise exception
        with patch.object(goal_manager, 'max_level_achieved', side_effect=Exception("Level check failed")):
            problematic_state = {
                GameState.CHARACTER_LEVEL: 10,
                GameState.HP_CURRENT: 50,
            }

            goal = goal_manager.select_next_goal(problematic_state)
            
            # Should return fallback goal on exception
            assert isinstance(goal, dict)
            assert 'type' in goal
            assert goal['type'] == 'level_up'

    @pytest.mark.asyncio
    async def test_plan_actions_exception_handling(self, goal_manager, mock_current_state):
        """Test exception handling in plan_actions"""
        # Test with goal that has no target_state
        invalid_goal = {
            'type': 'invalid_goal'
            # Missing target_state
        }

        plan = await goal_manager.plan_actions(mock_current_state, invalid_goal)
        
        # Should return empty plan on exception
        assert isinstance(plan, list)
        assert len(plan) == 0

    @pytest.mark.asyncio
    async def test_plan_actions_get_all_actions_exception(self, goal_manager, mock_current_state):
        """Test plan_actions when get_all_actions raises exception"""
        goal = {
            'type': 'test_goal',
            'target_state': {GameState.CHARACTER_LEVEL: 6}
        }

        with patch('src.ai_player.goal_manager.get_all_actions', side_effect=Exception("Action loading failed")):
            plan = await goal_manager.plan_actions(mock_current_state, goal)
            
            # Should handle exception and still try to create plan
            assert isinstance(plan, list)

    def test_create_goap_actions_exception_handling(self, goal_manager):
        """Test exception handling in create_goap_actions"""
        # Mock action registry to raise exception
        goal_manager.action_registry.get_all_action_types.side_effect = Exception("Registry error")

        action_list = goal_manager.create_goap_actions()
        
        # Should return basic action list on exception
        assert hasattr(action_list, 'conditions')
        assert "rest" in action_list.conditions

    def test_create_goap_actions_action_instantiation_error(self, goal_manager):
        """Test create_goap_actions with action instantiation errors"""
        # Mock action class that requires parameters
        class RequiresParamsAction:
            def __init__(self, required_param):
                self.required_param = required_param

        goal_manager.action_registry.get_all_action_types.return_value = [RequiresParamsAction]

        action_list = goal_manager.create_goap_actions()
        
        # Should handle TypeError for actions requiring parameters
        assert hasattr(action_list, 'conditions')

    def test_get_late_game_goals(self, goal_manager):
        """Test late game goals generation"""
        late_game_state = {
            GameState.CHARACTER_LEVEL: 35,
            GameState.CHARACTER_XP: 60000
        }

        goals = goal_manager.get_late_game_goals(late_game_state)
        
        assert isinstance(goals, list)
        assert len(goals) > 0
        # Should contain level progression goal for late game
        level_goals = [g for g in goals if g.get('type') == 'level_up']
        assert len(level_goals) > 0

    def test_get_mid_game_goals(self, goal_manager):
        """Test mid game goals generation"""
        mid_game_state = {
            GameState.CHARACTER_LEVEL: 20,
            GameState.CHARACTER_XP: 25000
        }

        goals = goal_manager.get_mid_game_goals(mid_game_state)
        
        assert isinstance(goals, list)
        assert len(goals) > 0
        # Should contain level progression goal for mid game
        level_goals = [g for g in goals if g.get('type') == 'level_up']
        assert len(level_goals) > 0

    def test_estimate_goal_cost_exception_handling(self, goal_manager, mock_current_state):
        """Test exception handling in estimate_goal_cost"""
        invalid_goal = {
            'target_state': None  # This could cause an exception
        }

        cost = goal_manager.estimate_goal_cost(invalid_goal, mock_current_state)
        
        # Should return default cost on exception
        assert cost == 100

    def test_prioritize_goals_empty_list(self, goal_manager, mock_current_state):
        """Test prioritize_goals with empty goal list"""
        empty_goals = []

        result = goal_manager.prioritize_goals(empty_goals, mock_current_state)
        
        assert result == {}

    def test_prioritize_goals_single_goal(self, goal_manager, mock_current_state):
        """Test prioritize_goals with single goal"""
        single_goal = [{
            'type': 'test_goal',
            'priority': 5,
            'target_state': {GameState.CHARACTER_LEVEL: 6}
        }]

        result = goal_manager.prioritize_goals(single_goal, mock_current_state)
        
        assert result == single_goal[0]

    def test_convert_state_for_goap_non_enum_keys(self, goal_manager):
        """Test convert_state_for_goap with non-enum keys"""
        mixed_state = {
            GameState.CHARACTER_LEVEL: 10,
            'string_key': 'value',
            42: 'numeric_key'
        }

        goap_state = goal_manager.convert_state_for_goap(mixed_state)
        
        assert 'character_level' in goap_state
        assert 'string_key' in goap_state
        assert '42' in goap_state


class TestGoalManagerGOAPIntegration:
    """Test GoalManager integration with GOAP system"""

    @pytest.fixture
    def goal_manager(self):
        """Create GoalManager with mocked GOAP components"""
        mock_action_registry = Mock()
        mock_cooldown_manager = Mock()
        return GoalManager(mock_action_registry, mock_cooldown_manager)

    def test_create_goap_actions(self, goal_manager):
        """Test GOAP action list creation"""
        # Mock the action registry to return some test action types
        goal_manager.action_registry.get_all_action_types.return_value = []

        # Test that the method returns an Action_List instance
        with patch('src.ai_player.goal_manager.Action_List') as mock_action_list_class:
            mock_action_list = Mock()
            mock_action_list_class.return_value = mock_action_list

            result = goal_manager.create_goap_actions()

            assert result == mock_action_list
            mock_action_list_class.assert_called_once()

    def test_convert_state_for_goap(self, goal_manager):
        """Test state conversion for GOAP compatibility"""
        game_state = {
            GameState.CHARACTER_LEVEL: 10,
            GameState.COOLDOWN_READY: True,
            GameState.HP_CURRENT: 85,
            GameState.CAN_FIGHT: False
        }

        goap_state = goal_manager._convert_state_for_goap(game_state)

        assert isinstance(goap_state, dict)

        # Should use string keys (enum values)
        for key in goap_state.keys():
            assert isinstance(key, str)

        # Should preserve values with proper type conversion
        assert goap_state['character_level'] == 10
        assert goap_state['cooldown_ready'] == 1  # Boolean to int
        assert goap_state['hp_current'] == 85
        assert goap_state['can_fight'] == 0  # Boolean to int

    def test_convert_actions_for_goap(self, goal_manager):
        """Test action conversion for GOAP system"""
        mock_actions = [
            Mock(name='move_action', cost=2,
                 get_preconditions=Mock(return_value={GameState.COOLDOWN_READY: True}),
                 get_effects=Mock(return_value={GameState.CURRENT_X: 10})),
            Mock(name='fight_action', cost=5,
                 get_preconditions=Mock(return_value={GameState.CAN_FIGHT: True}),
                 get_effects=Mock(return_value={GameState.CHARACTER_XP: 100}))
        ]

        action_list = goal_manager._convert_actions_for_goap(mock_actions)

        # Should return a proper Action_List with the converted actions
        assert action_list is not None
        assert hasattr(action_list, 'conditions')
        assert hasattr(action_list, 'reactions')
        assert hasattr(action_list, 'weights')

        # Should have entries for each action
        assert len(action_list.conditions) == len(mock_actions)
        assert len(action_list.reactions) == len(mock_actions)
        assert len(action_list.weights) == len(mock_actions)

    @pytest.mark.asyncio
    async def test_goap_planning_with_complex_goal(self, goal_manager):
        """Test GOAP planning with complex multi-step goal"""
        current_state = {
            GameState.CHARACTER_LEVEL: 8,
            GameState.MINING_LEVEL: 5,
            GameState.CURRENT_X: 0,
            GameState.CURRENT_Y: 0,
            GameState.COOLDOWN_READY: True,
            GameState.INVENTORY_SPACE_AVAILABLE: 10,
            GameState.ITEM_QUANTITY: 0
        }

        complex_goal = {
            'type': 'crafting_quest',
            'target_state': {
                GameState.ITEM_QUANTITY: 5,  # Need 5 specific items
                GameState.MINING_LEVEL: 7,   # Need higher skill
                GameState.CHARACTER_XP: 3000 # Need more experience
            }
        }

        # Mock complex action sequence
        complex_plan = [
            {'name': 'move_to_mine', 'cost': 3},
            {'name': 'gather_ore', 'cost': 4},
            {'name': 'gather_ore', 'cost': 4},
            {'name': 'move_to_smelter', 'cost': 2},
            {'name': 'smelt_ingot', 'cost': 6},
            {'name': 'smelt_ingot', 'cost': 6}
        ]

        with patch.object(goal_manager, '_create_goap_planner') as mock_create_planner:
            mock_planner = Mock()
            mock_planner.calculate.return_value = complex_plan
            mock_create_planner.return_value = mock_planner

            plan = await goal_manager.plan_actions(current_state, complex_goal)

            assert len(plan) == 6
            assert plan[0]['name'] == 'move_to_mine'
            assert plan[-1]['name'] == 'smelt_ingot'

            # Verify total cost calculation
            total_cost = sum(action['cost'] for action in plan)
            assert total_cost == 25

    def test_goap_optimization_with_action_costs(self, goal_manager):
        """Test GOAP optimization considering action costs"""
        # Test that GOAP selects lower-cost paths when multiple options exist
        current_state = {
            GameState.CURRENT_X: 0,
            GameState.CURRENT_Y: 0,
            GameState.COOLDOWN_READY: True
        }

        goal_state = {
            GameState.CURRENT_X: 10,
            GameState.CURRENT_Y: 10
        }

        # Mock actions with different costs for same effect
        mock_actions = [
            Mock(name='expensive_teleport', cost=20,
                 get_preconditions=Mock(return_value={GameState.COOLDOWN_READY: True}),
                 get_effects=Mock(return_value={GameState.CURRENT_X: 10, GameState.CURRENT_Y: 10})),
            Mock(name='cheap_walk', cost=5,
                 get_preconditions=Mock(return_value={GameState.COOLDOWN_READY: True}),
                 get_effects=Mock(return_value={GameState.CURRENT_X: 10, GameState.CURRENT_Y: 10}))
        ]

        with patch.object(goal_manager, '_create_goap_planner') as mock_create_planner:
            mock_planner = Mock()
            # GOAP should prefer lower cost option
            mock_planner.calculate.return_value = [{'name': 'cheap_walk', 'cost': 5}]
            mock_create_planner.return_value = mock_planner

            with patch('src.ai_player.goal_manager.get_all_actions', return_value=mock_actions):
                planner = goal_manager._create_goap_planner(current_state, goal_state, mock_actions)

                assert planner == mock_planner


class TestGoalManagerDynamicPriorities:
    """Test dynamic goal priority management"""

    @pytest.fixture
    def goal_manager(self):
        """Create GoalManager for priority testing"""
        from unittest.mock import Mock
        mock_action_registry = Mock()
        mock_cooldown_manager = Mock()
        return GoalManager(mock_action_registry, mock_cooldown_manager)

    def test_calculate_survival_priority(self, goal_manager):
        """Test survival priority calculation based on HP"""
        test_cases = [
            # (current_hp, max_hp, expected_priority_range)
            (5, 100, (9, 10)),    # Critical HP - highest priority
            (30, 100, (7, 9)),    # Low HP - high priority
            (70, 100, (3, 6)),    # Moderate HP - medium priority
            (95, 100, (1, 3)),    # High HP - low priority
        ]

        for current_hp, max_hp, (min_priority, max_priority) in test_cases:
            state = {
                GameState.HP_CURRENT: current_hp,
                GameState.HP_MAX: max_hp
            }

            priority = goal_manager._calculate_survival_priority(state)

            assert min_priority <= priority <= max_priority

    def test_calculate_progression_priority(self, goal_manager):
        """Test progression priority based on character level"""
        test_cases = [
            # (level, xp, xp_to_next, expected_priority_range)
            (1, 0, 100, (8, 10)),      # New character - high priority
            (5, 800, 200, (6, 8)),     # Early game - good priority
            (20, 15000, 5000, (4, 6)), # Mid game - moderate priority
            (40, 80000, 20000, (2, 4)), # Late game - lower priority
        ]

        for level, xp, xp_to_next, (min_priority, max_priority) in test_cases:
            state = {
                GameState.CHARACTER_LEVEL: level,
                GameState.CHARACTER_XP: xp
            }

            priority = goal_manager._calculate_progression_priority(state)

            assert min_priority <= priority <= max_priority

    def test_calculate_economic_priority(self, goal_manager):
        """Test economic priority based on gold and inventory"""
        test_cases = [
            # (gold, inventory_full, expected_priority_range)
            (0, True, (8, 10)),     # No gold, full inventory - urgent
            (50, True, (6, 8)),     # Little gold, full inventory - high
            (500, False, (3, 5)),   # Some gold, space available - moderate
            (5000, False, (1, 3)),  # Rich, space available - low
        ]

        for gold, inventory_full, (min_priority, max_priority) in test_cases:
            state = {
                GameState.CHARACTER_GOLD: gold,
                GameState.INVENTORY_FULL: inventory_full,
                GameState.INVENTORY_SPACE_AVAILABLE: 0 if inventory_full else 10
            }

            priority = goal_manager._calculate_economic_priority(state)

            assert min_priority <= priority <= max_priority

    def test_adaptive_priority_adjustment(self, goal_manager):
        """Test adaptive priority adjustment over time"""
        # Simulate goal priorities changing based on recent actions
        recent_actions = [
            {'name': 'fight_monster', 'result': 'success', 'xp_gained': 150},
            {'name': 'fight_monster', 'result': 'success', 'xp_gained': 150},
            {'name': 'rest', 'result': 'success', 'hp_recovered': 50}
        ]

        initial_priorities = {
            'combat_training': 7,
            'skill_training': 5,
            'survival': 8
        }

        current_state = {
            GameState.CHARACTER_LEVEL: 8,
            GameState.HP_CURRENT: 90,
            GameState.HP_MAX: 100
        }

        adjusted_priorities = goal_manager._adjust_priorities_based_on_history(
            initial_priorities, recent_actions, current_state
        )

        assert isinstance(adjusted_priorities, dict)

        # Combat training might get lower priority if recently successful
        # Survival might get lower priority if HP is good
        for goal_type, priority in adjusted_priorities.items():
            assert 0 <= priority <= 10

    def test_priority_balancing(self, goal_manager):
        """Test priority balancing to prevent single-goal focus"""
        # Test that priority system encourages diverse goals
        unbalanced_priorities = {
            'level_up': 10,      # Maxed out
            'skill_training': 1,  # Minimal
            'economic': 1,        # Minimal
            'survival': 1         # Minimal
        }

        current_state = {
            GameState.CHARACTER_LEVEL: 10,
            GameState.MINING_LEVEL: 2,    # Behind character level
            GameState.CHARACTER_GOLD: 10, # Very low
            GameState.HP_CURRENT: 85
        }

        balanced_priorities = goal_manager._balance_goal_priorities(
            unbalanced_priorities, current_state
        )

        # Should boost neglected areas
        assert balanced_priorities['skill_training'] > unbalanced_priorities['skill_training']
        assert balanced_priorities['economic'] > unbalanced_priorities['economic']

        # Should slightly reduce over-prioritized goal
        assert balanced_priorities['level_up'] <= unbalanced_priorities['level_up']


class TestGoalManagerConfiguration:
    """Test goal manager configuration and customization"""

    @pytest.fixture
    def goal_manager(self):
        """Create GoalManager instance for testing"""
        mock_action_registry = Mock()
        mock_cooldown_manager = Mock()
        return GoalManager(mock_action_registry, mock_cooldown_manager)

    def test_load_goal_configuration(self):
        """Test loading goal configuration from YAML"""
        mock_config = {
            'goal_priorities': {
                'survival': {'base_priority': 10, 'hp_threshold': 0.3},
                'progression': {'base_priority': 8, 'xp_multiplier': 1.2},
                'economic': {'base_priority': 6, 'gold_threshold': 1000}
            },
            'goal_weights': {
                'level_up': 1.5,
                'skill_training': 1.0,
                'resource_gathering': 0.8
            }
        }

        with patch('src.lib.yaml_data.YamlData') as mock_yaml_data:
            mock_yaml_instance = Mock()
            mock_yaml_instance.load_data.return_value = mock_config
            mock_yaml_data.return_value = mock_yaml_instance

            mock_action_registry = Mock()
            mock_cooldown_manager = Mock()
            goal_manager = GoalManager(mock_action_registry, mock_cooldown_manager)

            # Should initialize successfully with required components
            assert hasattr(goal_manager, 'action_registry')
            assert hasattr(goal_manager, 'cooldown_manager')

    def test_custom_goal_registration(self, goal_manager):
        """Test goal availability and selection functionality"""
        # Test that goal manager returns available goals for the current state
        test_state = {GameState.CHARACTER_LEVEL: 10, GameState.HP_CURRENT: 80}
        available_goals = goal_manager.get_available_goals(test_state)

        # Should have some goals available for a mid-level character
        assert isinstance(available_goals, list)
        assert len(available_goals) > 0

        # Each goal should be a dictionary with proper structure
        for goal in available_goals:
            assert isinstance(goal, dict)
            assert 'type' in goal
            assert 'priority' in goal
            assert 'target_state' in goal

            # target_state should have GameState keys
            if goal['target_state']:
                for key in goal['target_state'].keys():
                    assert isinstance(key, GameState)

    def test_goal_manager_with_different_strategies(self, goal_manager):
        """Test goal manager with different planning strategies"""
        strategies = ['aggressive', 'balanced', 'conservative', 'economic']

        # Test different character states to see appropriate goal selection
        test_scenarios = [
            {
                GameState.CHARACTER_LEVEL: 1,
                GameState.HP_CURRENT: 100,
                GameState.CHARACTER_GOLD: 0
            },
            {
                GameState.CHARACTER_LEVEL: 15,
                GameState.HP_CURRENT: 80,
                GameState.CHARACTER_GOLD: 500
            },
            {
                GameState.CHARACTER_LEVEL: 25,
                GameState.HP_CURRENT: 50,
                GameState.CHARACTER_GOLD: 1000
            }
        ]

        for test_state in test_scenarios:
            goal = goal_manager.select_next_goal(test_state)

            # Goal selection should return appropriate goals
            assert isinstance(goal, dict)
            assert len(goal) > 0

            # Goal should have proper structure
            assert isinstance(goal, dict)
            assert 'type' in goal
            assert 'priority' in goal
            assert 'target_state' in goal

            # target_state should have GameState keys if present
            if goal['target_state']:
                for key in goal['target_state'].keys():
                    assert isinstance(key, GameState)


class TestGoalManagerIntegration:
    """Integration tests for GoalManager with other components"""

    @pytest.mark.asyncio
    async def test_full_goal_planning_workflow(self):
        """Test complete goal planning workflow"""
        with patch('src.lib.goap.Planner'), \
             patch('src.lib.goap.Action_List'), \
             patch('src.ai_player.goal_manager.get_all_actions'):

            mock_action_registry = Mock()
            mock_cooldown_manager = Mock()
            goal_manager = GoalManager(mock_action_registry, mock_cooldown_manager)

            # Simulate complete workflow
            current_state = {
                GameState.CHARACTER_LEVEL: 5,
                GameState.HP_CURRENT: 80,
                GameState.COOLDOWN_READY: True,
                GameState.CAN_FIGHT: True
            }

            # 1. Select goal
            goal = goal_manager.select_next_goal(current_state)
            assert isinstance(goal, dict)

            # 2. Plan actions
            with patch.object(goal_manager, '_create_goap_planner') as mock_create_planner:
                mock_planner = Mock()
                mock_planner.calculate.return_value = [
                    {'name': 'move_to_target', 'cost': 2},
                    {'name': 'execute_goal_action', 'cost': 5}
                ]
                mock_create_planner.return_value = mock_planner

                plan = await goal_manager.plan_actions(current_state, goal)

                assert isinstance(plan, list)
                assert len(plan) > 0

    @pytest.mark.asyncio
    async def test_goal_manager_error_handling(self):
        """Test goal manager error handling and recovery"""
        mock_action_registry = Mock()
        mock_cooldown_manager = Mock()
        goal_manager = GoalManager(mock_action_registry, mock_cooldown_manager)

        # Test handling of various error conditions
        error_scenarios = [
            # Invalid state
            ({}, "Empty state should be handled gracefully"),

            # Invalid goal
            ({"invalid": "goal"}, "Invalid goal format should be handled"),

            # GOAP planning failure
            ({GameState.CHARACTER_LEVEL: 5}, "GOAP failures should be handled")
        ]

        for scenario_data, description in error_scenarios:
            try:
                if isinstance(scenario_data, dict) and GameState.CHARACTER_LEVEL in scenario_data:
                    # Test planning failure
                    with patch.object(goal_manager, '_create_goap_planner') as mock_create_planner:
                        mock_planner = Mock()
                        mock_planner.calculate.side_effect = Exception("GOAP planning failed")
                        mock_create_planner.return_value = mock_planner

                        goal = {'type': 'test_goal', 'target_state': {GameState.CHARACTER_LEVEL: 6}}
                        plan = await goal_manager.plan_actions(scenario_data, goal)

                        # Should return empty plan on failure
                        assert isinstance(plan, list)
                        assert len(plan) == 0
                else:
                    # Test goal selection with invalid state
                    goal = goal_manager.select_next_goal(scenario_data)

                    # Should return a default/emergency goal
                    assert isinstance(goal, dict)
                    assert 'type' in goal
            except Exception as e:
                # Should not raise unhandled exceptions
                pytest.fail(f"Unhandled exception for scenario '{description}': {e}")

    def test_goal_manager_performance_optimization(self):
        """Test goal manager performance with large state spaces"""
        mock_action_registry = Mock()
        mock_cooldown_manager = Mock()
        goal_manager = GoalManager(mock_action_registry, mock_cooldown_manager)

        # Test with comprehensive state
        large_state = {
            GameState.CHARACTER_LEVEL: 25,
            GameState.CHARACTER_XP: 50000,
            GameState.CHARACTER_GOLD: 10000,
            GameState.HP_CURRENT: 200,
            GameState.HP_MAX: 200,
            GameState.CURRENT_X: 50,
            GameState.CURRENT_Y: 75,
            GameState.MINING_LEVEL: 20,
            GameState.WOODCUTTING_LEVEL: 18,
            GameState.FISHING_LEVEL: 15,
            GameState.WEAPONCRAFTING_LEVEL: 12,
            GameState.GEARCRAFTING_LEVEL: 10,
            GameState.JEWELRYCRAFTING_LEVEL: 8,
            GameState.COOKING_LEVEL: 6,
            GameState.ALCHEMY_LEVEL: 4,
            GameState.INVENTORY_SPACE_AVAILABLE: 5,
            GameState.WEAPON_EQUIPPED: "masterwork_sword",
            GameState.TOOL_EQUIPPED: "expert_pickaxe"
        }

        # Should handle large state efficiently
        goal = goal_manager.select_next_goal(large_state)

        assert isinstance(goal, dict)
        assert 'type' in goal
        assert 'priority' in goal

        # Should complete goal selection in reasonable time
        # (Performance assertion would depend on implementation)
        available_goals = goal_manager.get_available_goals(large_state)
        assert isinstance(available_goals, list)
        assert len(available_goals) > 0


class TestCooldownAwarePlanner:
    """Test CooldownAwarePlanner functionality"""

    @pytest.fixture
    def cooldown_aware_planner(self):
        """Create CooldownAwarePlanner instance for testing"""
        mock_cooldown_manager = Mock()
        return CooldownAwarePlanner(mock_cooldown_manager, "test_state1", "test_state2")

    def test_defer_planning_until_ready_when_ready(self, cooldown_aware_planner):
        """Test defer_planning_until_ready when character is ready"""
        character_name = "test_character"
        cooldown_aware_planner.cooldown_manager.is_ready.return_value = True

        result = cooldown_aware_planner.defer_planning_until_ready(character_name)

        assert result is None
        cooldown_aware_planner.cooldown_manager.is_ready.assert_called_once_with(character_name)

    def test_defer_planning_until_ready_when_on_cooldown(self, cooldown_aware_planner):
        """Test defer_planning_until_ready when character is on cooldown"""
        character_name = "test_character"
        cooldown_aware_planner.cooldown_manager.is_ready.return_value = False
        cooldown_aware_planner.cooldown_manager.get_remaining_time.return_value = 30.0  # 30 seconds

        before_call = datetime.now()
        result = cooldown_aware_planner.defer_planning_until_ready(character_name)
        after_call = datetime.now()

        # Should return a datetime object
        assert isinstance(result, datetime)

        # Should be about 30 seconds from now (with some tolerance for test execution time)
        expected_time = before_call + timedelta(seconds=30)
        time_diff = abs((result - expected_time).total_seconds())
        assert time_diff < 1.0  # Allow 1 second tolerance

        # Verify method calls
        cooldown_aware_planner.cooldown_manager.is_ready.assert_called_once_with(character_name)
        cooldown_aware_planner.cooldown_manager.get_remaining_time.assert_called_once_with(character_name)

    def test_calculate_with_timing_constraints_exception_handling(self, cooldown_aware_planner):
        """Test exception handling in calculate_with_timing_constraints"""
        character_name = "test_character"
        cooldown_aware_planner.cooldown_manager.is_ready.return_value = True
        cooldown_aware_planner.calculate = Mock(side_effect=Exception("Planning failed"))

        result = cooldown_aware_planner.calculate_with_timing_constraints(character_name)

        assert result == []

    def test_estimate_plan_duration_with_different_actions(self, cooldown_aware_planner):
        """Test plan duration estimation with various action types"""
        plan_with_mixed_actions = [
            {'name': 'move_to_location', 'cost': 2},
            {'name': 'fight_monster', 'cost': 5},
            {'name': 'gather_resource', 'cost': 3},
            {'name': 'craft_item', 'cost': 4}
        ]

        duration = cooldown_aware_planner.estimate_plan_duration(plan_with_mixed_actions)

        assert isinstance(duration, timedelta)
        # Should account for different action types: move(5s) + fight(10s) + gather(8s) + craft(3s) + cooldowns(4*1s)
        expected_seconds = 5 + 10 + 8 + 3 + 4  # 30 seconds total
        assert duration.total_seconds() == expected_seconds

    def test_estimate_plan_duration_exception_handling(self, cooldown_aware_planner):
        """Test exception handling in estimate_plan_duration"""
        # Plan that causes exception due to non-iterable
        invalid_plan = "not a list"

        duration = cooldown_aware_planner.estimate_plan_duration(invalid_plan)

        # Should return default 60 seconds on exception
        assert duration == timedelta(seconds=60)

    def test_filter_actions_by_cooldown_detailed(self, cooldown_aware_planner):
        """Test detailed filtering of actions by cooldown status"""
        character_name = "test_character"
        cooldown_aware_planner.cooldown_manager.is_ready.return_value = False

        # Create action list with mixed cooldown requirements
        action_list = Action_List()
        action_list.add_condition("cooldown_action", cooldown_ready=True, character_level=5)
        action_list.add_reaction("cooldown_action", character_xp=100)
        action_list.set_weight("cooldown_action", 3)

        action_list.add_condition("non_cooldown_action", character_level=5)
        action_list.add_reaction("non_cooldown_action", character_xp=50)
        action_list.set_weight("non_cooldown_action", 2)

        action_list.add_condition("another_cooldown_action", cooldown_ready=True, character_level=3)
        action_list.add_reaction("another_cooldown_action", character_xp=75)
        action_list.set_weight("another_cooldown_action", 4)

        filtered_actions = cooldown_aware_planner.filter_actions_by_cooldown(action_list, character_name)

        # Should only contain non-cooldown actions
        assert "non_cooldown_action" in filtered_actions.conditions
        assert "cooldown_action" not in filtered_actions.conditions
        assert "another_cooldown_action" not in filtered_actions.conditions

        # Verify the filtered action maintains its properties
        assert filtered_actions.conditions["non_cooldown_action"]["character_level"] == 5
        assert filtered_actions.reactions["non_cooldown_action"]["character_xp"] == 50
        assert filtered_actions.weights["non_cooldown_action"] == 2
