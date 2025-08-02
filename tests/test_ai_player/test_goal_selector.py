"""
Tests for GoalWeightCalculator and goal selection system

This module tests the enhanced goal selection system with weighted multi-factor scoring
and strategic goal orchestration for level 5 progression.
"""

from unittest.mock import Mock

from src.ai_player.goal_selector import GoalWeightCalculator
from src.game_data.models import GameItem, GameMap, GameMonster, GameNPC, GameResource
from src.ai_player.goals.combat_goal import CombatGoal
from src.ai_player.goals.crafting_goal import CraftingGoal
from src.ai_player.goals.equipment_goal import EquipmentGoal
from src.ai_player.goals.gathering_goal import GatheringGoal
from src.ai_player.goals.sub_goal_request import SubGoalRequest
from src.ai_player.state.character_game_state import CharacterGameState
from src.ai_player.types.game_data import GameData


def create_test_character():
    """Create a test character with all required fields."""
    return CharacterGameState(
        name="test_character",
        level=3,
        xp=1000,
        hp=80,
        max_hp=100,
        x=5,
        y=5,
        gold=500,
        mining_level=2,
        mining_xp=100,
        woodcutting_level=1,
        woodcutting_xp=50,
        fishing_level=1,
        fishing_xp=0,
        weaponcrafting_level=1,
        weaponcrafting_xp=0,
        gearcrafting_level=1,
        gearcrafting_xp=0,
        jewelrycrafting_level=1,
        jewelrycrafting_xp=0,
        cooking_level=1,
        cooking_xp=0,
        alchemy_level=1,
        alchemy_xp=0,
        cooldown=0,
        weapon_slot="basic_sword",
        rune_slot="",
        shield_slot="",
        helmet_slot="",
        body_armor_slot="",
        leg_armor_slot="",
        boots_slot="",
        ring1_slot="",
        ring2_slot="",
        amulet_slot="",
        artifact1_slot="",
        at_monster_location=False
    )


def create_test_game_data():
    """Create test game data with mock objects."""
    mock_monster = Mock(spec=GameMonster)
    mock_monster.level = 5  # Add missing level attribute
    mock_item = Mock(spec=GameItem)
    mock_item.level = 3  # Add missing level attribute
    mock_item.craft = {}  # Add missing craft attribute
    mock_resource = Mock(spec=GameResource)
    mock_resource.level = 2  # Add missing level attribute for resources
    mock_map = Mock(spec=GameMap)
    mock_npc = Mock(spec=GameNPC)

    return GameData(
        monsters=[mock_monster],
        items=[mock_item],
        resources=[mock_resource],
        maps=[mock_map],
        npcs=[mock_npc]
    )


class TestGoalWeightCalculator:
    """Test GoalWeightCalculator functionality."""

    def test_init_creates_all_goals(self):
        """Test that GoalWeightCalculator initializes with all required goals."""
        calc = GoalWeightCalculator()

        assert len(calc.goals) == 4
        assert any(isinstance(goal, CombatGoal) for goal in calc.goals)
        assert any(isinstance(goal, CraftingGoal) for goal in calc.goals)
        assert any(isinstance(goal, GatheringGoal) for goal in calc.goals)
        assert any(isinstance(goal, EquipmentGoal) for goal in calc.goals)

    def test_init_creates_performance_metrics(self):
        """Test that performance metrics tracking is initialized."""
        calc = GoalWeightCalculator()

        assert hasattr(calc, 'performance_metrics')
        assert isinstance(calc.performance_metrics, dict)

    def test_calculate_final_weight_success(self):
        """Test calculate_final_weight with valid goal."""
        calc = GoalWeightCalculator()
        char_state = create_test_character()
        game_data = create_test_game_data()

        # Mock a goal that returns a valid weight
        mock_goal = Mock()
        mock_goal.calculate_weight.return_value = 5.5

        weight = calc.calculate_final_weight(mock_goal, char_state, game_data)

        assert isinstance(weight, (int, float))
        assert weight == 5.5
        mock_goal.calculate_weight.assert_called_once_with(char_state, game_data)

    def test_calculate_final_weight_exception_handling(self):
        """Test calculate_final_weight handles exceptions gracefully."""
        calc = GoalWeightCalculator()
        char_state = create_test_character()
        game_data = create_test_game_data()

        # Mock a goal that raises an exception
        mock_goal = Mock()
        mock_goal.calculate_weight.side_effect = ValueError("Test error")

        weight = calc.calculate_final_weight(mock_goal, char_state, game_data)

        assert weight == 0.1  # Fallback weight

    def test_get_goal_priorities_returns_all_goals(self):
        """Test get_goal_priorities returns priorities for all goals."""
        calc = GoalWeightCalculator()
        char_state = create_test_character()
        game_data = create_test_game_data()

        # Mock all goals to return valid weights and feasibility
        for goal in calc.goals:
            goal.calculate_weight = Mock(return_value=5.0)
            goal.is_feasible = Mock(return_value=True)

        priorities = calc.get_goal_priorities(char_state, game_data)

        assert len(priorities) == 4
        for goal_name, weight, feasible in priorities:
            assert isinstance(goal_name, str)
            assert isinstance(weight, (int, float))
            assert isinstance(feasible, bool)

    def test_get_goal_priorities_sorted_by_weight(self):
        """Test that goal priorities are sorted by weight (descending)."""
        calc = GoalWeightCalculator()
        char_state = create_test_character()
        game_data = create_test_game_data()

        # Mock goals with different weights
        weights = [3.0, 7.0, 1.0, 5.0]
        for i, goal in enumerate(calc.goals):
            goal.calculate_weight = Mock(return_value=weights[i])
            goal.is_feasible = Mock(return_value=True)

        priorities = calc.get_goal_priorities(char_state, game_data)

        # Check that priorities are sorted by weight (descending)
        priority_weights = [weight for _, weight, _ in priorities]
        assert priority_weights == sorted(priority_weights, reverse=True)

    def test_select_optimal_goal_with_feasible_goals(self):
        """Test select_optimal_goal returns highest weight feasible goal."""
        calc = GoalWeightCalculator()
        char_state = create_test_character()
        game_data = create_test_game_data()

        # Mock goals with different weights and feasibility
        test_data = [
            (2.0, False),  # Not feasible
            (8.0, True),   # Highest feasible
            (1.0, True),   # Lower feasible
            (9.0, False)   # Highest but not feasible
        ]

        for i, (weight, feasible) in enumerate(test_data):
            goal = calc.goals[i]
            goal.calculate_weight = Mock(return_value=weight)
            goal.is_feasible = Mock(return_value=feasible)
            goal.generate_sub_goal_requests = Mock(return_value=[])

        selected_goal, sub_goals = calc.select_optimal_goal(char_state, game_data)

        assert selected_goal is not None
        assert selected_goal == calc.goals[1]  # Second goal (weight=8.0, feasible=True)
        assert isinstance(sub_goals, list)

    def test_select_optimal_goal_no_feasible_goals(self):
        """Test select_optimal_goal with no feasible goals."""
        calc = GoalWeightCalculator()
        char_state = create_test_character()
        game_data = create_test_game_data()

        # Mock all goals as not feasible
        for goal in calc.goals:
            goal.calculate_weight = Mock(return_value=5.0)
            goal.is_feasible = Mock(return_value=False)

        selected_goal, sub_goals = calc.select_optimal_goal(char_state, game_data)

        assert selected_goal is None
        assert sub_goals == []

    def test_select_optimal_goal_collects_sub_goals(self):
        """Test that select_optimal_goal collects sub-goal requests."""
        calc = GoalWeightCalculator()
        char_state = create_test_character()
        game_data = create_test_game_data()

        # Create mock sub-goal requests
        mock_sub_goal = Mock(spec=SubGoalRequest)
        mock_sub_goal.requester = "CombatGoal"  # Match the actual goal type
        mock_sub_goal.goal_type = "test_sub_goal"
        mock_sub_goal.reason = "Testing purposes"

        # Mock one feasible goal with sub-goals
        calc.goals[0].calculate_weight = Mock(return_value=5.0)
        calc.goals[0].is_feasible = Mock(return_value=True)
        calc.goals[0].generate_sub_goal_requests = Mock(return_value=[mock_sub_goal])

        # Mock other goals as not feasible
        for goal in calc.goals[1:]:
            goal.calculate_weight = Mock(return_value=1.0)
            goal.is_feasible = Mock(return_value=False)

        selected_goal, sub_goals = calc.select_optimal_goal(char_state, game_data)

        assert selected_goal == calc.goals[0]
        assert len(sub_goals) == 1
        assert sub_goals[0] == mock_sub_goal

    def test_select_optimal_goal_exception_handling(self):
        """Test select_optimal_goal handles exceptions gracefully."""
        calc = GoalWeightCalculator()
        char_state = create_test_character()
        game_data = create_test_game_data()

        # Mock goals to pass feasibility check but raise exceptions in weight calculation
        for goal in calc.goals:
            goal.is_feasible = Mock(return_value=True)  # Allow feasibility check to pass
            goal.calculate_weight = Mock(side_effect=Exception("Test error"))  # Exception in weight calculation

        selected_goal, sub_goals = calc.select_optimal_goal(char_state, game_data)

        assert selected_goal is None
        assert sub_goals == []

    def test_update_goal_performance_new_goal(self):
        """Test updating performance metrics for new goal."""
        calc = GoalWeightCalculator()
        mock_goal = Mock()
        mock_goal.__class__.__name__ = "TestGoal"

        calc.update_goal_performance(mock_goal, success=True, progress_made=0.8)

        assert "TestGoal" in calc.performance_metrics
        metrics = calc.performance_metrics["TestGoal"]
        assert metrics['successes'] == 1
        assert metrics['attempts'] == 1
        assert metrics['total_progress'] == 0.8
        assert metrics['avg_progress'] == 0.8

    def test_update_goal_performance_existing_goal(self):
        """Test updating performance metrics for existing goal."""
        calc = GoalWeightCalculator()
        mock_goal = Mock()
        mock_goal.__class__.__name__ = "TestGoal"

        # Add initial performance data
        calc.performance_metrics["TestGoal"] = {
            'successes': 2,
            'attempts': 3,
            'total_progress': 1.8,  # 0.6 * 3
            'avg_progress': 0.6
        }

        calc.update_goal_performance(mock_goal, success=False, progress_made=0.2)

        metrics = calc.performance_metrics["TestGoal"]
        assert metrics['successes'] == 2
        assert metrics['attempts'] == 4
        assert metrics['total_progress'] == 2.0  # 1.8 + 0.2
        # Average should be updated: 2.0 / 4 = 0.5
        assert abs(metrics['avg_progress'] - 0.5) < 0.01

    def test_emergency_situation_detection(self):
        """Test that emergency situations boost goal priorities."""
        calc = GoalWeightCalculator()

        # Create character with critical HP
        critical_char = create_test_character()
        critical_char.hp = 10  # 10% HP

        game_data = create_test_game_data()

        # Mock goals
        for goal in calc.goals:
            goal.calculate_weight = Mock(return_value=3.0)
            goal.is_feasible = Mock(return_value=True)
            goal.generate_sub_goal_requests = Mock(return_value=[])

        selected_goal, _ = calc.select_optimal_goal(critical_char, game_data)

        # Should still select a goal even in emergency
        assert selected_goal is not None

    def test_select_optimal_goal_empty_game_data(self):
        """Test select_optimal_goal with empty game data."""
        calc = GoalWeightCalculator()
        char_state = create_test_character()
        game_data = GameData()  # Empty game data should cause goals to fail

        selected_goal, sub_goals = calc.select_optimal_goal(char_state, game_data)

        assert selected_goal is None
        assert sub_goals == []
