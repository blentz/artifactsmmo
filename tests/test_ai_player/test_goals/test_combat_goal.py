"""
Tests for CombatGoal implementation

This module tests intelligent combat goal selection that targets level-appropriate
monsters for optimal XP progression using data-driven analysis.
"""

from unittest.mock import Mock, patch

import pytest

from src.ai_player.goals.combat_goal import CombatGoal
from src.game_data.models import GameItem, GameMap, GameMonster, GameNPC, GameResource
from src.ai_player.state.character_game_state import CharacterGameState
from src.game_data.game_data import GameData
from src.ai_player.types.goap_models import GOAPTargetState


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
    mock_monster.code = "test_monster"
    mock_monster.name = "Test Monster"
    mock_monster.level = 3
    mock_monster.min_gold = 5
    mock_monster.max_gold = 15
    mock_monster.hp = 100
    mock_monster.attack_fire = 10
    mock_monster.attack_earth = 10
    mock_monster.attack_water = 10
    mock_monster.attack_air = 10
    mock_monster.res_fire = 5
    mock_monster.res_earth = 5
    mock_monster.res_water = 5
    mock_monster.res_air = 5

    mock_item = Mock(spec=GameItem)
    mock_resource = Mock(spec=GameResource)

    mock_map = Mock(spec=GameMap)
    mock_map.x = 10
    mock_map.y = 10
    mock_map.content = Mock()
    mock_map.content.code = "test_monster"
    mock_map.content.type = "monster"

    mock_npc = Mock(spec=GameNPC)

    return GameData(
        monsters=[mock_monster],
        items=[mock_item],
        resources=[mock_resource],
        maps=[mock_map],
        npcs=[mock_npc]
    )


class TestCombatGoal:
    """Test CombatGoal functionality."""

    def test_init_default_values(self):
        """Test CombatGoal initialization with default values."""
        goal = CombatGoal()

        assert goal.target_monster_code is None
        assert goal.min_hp_percentage == 0.4
        assert hasattr(goal, 'level_targeting')
        assert hasattr(goal, 'map_analysis')

    def test_init_custom_values(self):
        """Test CombatGoal initialization with custom values."""
        goal = CombatGoal(target_monster_code="test_monster", min_hp_percentage=0.6)

        assert goal.target_monster_code == "test_monster"
        assert goal.min_hp_percentage == 0.6

    def test_calculate_weight_level_5_character(self):
        """Test calculate_weight for character at target level 5."""
        goal = CombatGoal()
        char_state = create_test_character()
        char_state.level = 5
        game_data = create_test_game_data()

        weight = goal.calculate_weight(char_state, game_data)

        assert isinstance(weight, (int, float))
        assert 0 <= weight <= 10

    def test_calculate_weight_low_level_character(self):
        """Test calculate_weight for low level character."""
        goal = CombatGoal()
        char_state = create_test_character()
        char_state.level = 1
        game_data = create_test_game_data()

        weight = goal.calculate_weight(char_state, game_data)

        assert isinstance(weight, (int, float))
        assert weight > 0  # Should have high necessity for low level chars

    def test_calculate_weight_multi_factor_scoring(self):
        """Test that calculate_weight implements multi-factor scoring."""
        goal = CombatGoal()
        char_state = create_test_character()
        game_data = create_test_game_data()

        # Mock the analysis modules to return predictable values
        with patch.object(goal.level_targeting, 'find_optimal_monsters') as mock_find:
            mock_find.return_value = [("monster", "location", 0.8)]

            weight = goal.calculate_weight(char_state, game_data)

            assert isinstance(weight, (int, float))
            assert 0 <= weight <= 10

    def test_is_feasible_sufficient_hp(self):
        """Test is_feasible with sufficient HP."""
        goal = CombatGoal()
        char_state = create_test_character()
        char_state.hp = 80  # 80% HP
        game_data = create_test_game_data()

        with patch.object(goal.level_targeting, 'find_optimal_monsters') as mock_find:
            mock_find.return_value = [("monster", "location", 0.8)]

            feasible = goal.is_feasible(char_state, game_data)

            assert feasible is True

    def test_is_feasible_insufficient_hp(self):
        """Test is_feasible with insufficient HP."""
        goal = CombatGoal()
        char_state = create_test_character()
        char_state.hp = 30  # 30% HP, below 40% threshold
        game_data = create_test_game_data()

        feasible = goal.is_feasible(char_state, game_data)

        assert feasible is False

    def test_is_feasible_no_monsters_available(self):
        """Test is_feasible with no available monsters."""
        goal = CombatGoal()
        char_state = create_test_character()
        game_data = create_test_game_data()

        with patch.object(goal.level_targeting, 'find_optimal_monsters') as mock_find:
            mock_find.return_value = []  # No monsters available

            feasible = goal.is_feasible(char_state, game_data)

            assert feasible is False

    def test_get_target_state_with_target_monster(self):
        """Test get_target_state with specific target monster."""
        goal = CombatGoal(target_monster_code="test_monster")
        char_state = create_test_character()
        game_data = create_test_game_data()

        with patch.object(goal.map_analysis, 'find_content_by_code') as mock_find:
            mock_location = Mock()
            mock_location.x = 10
            mock_location.y = 10
            mock_find.return_value = [mock_location]

            with patch.object(goal.map_analysis, 'calculate_travel_efficiency') as mock_calc:
                mock_calc.return_value = {(10, 10): 0.8}

                target_state = goal.get_target_state(char_state, game_data)

                assert isinstance(target_state, GOAPTargetState)

    def test_get_target_state_optimal_monster_selection(self):
        """Test get_target_state with optimal monster selection."""
        goal = CombatGoal()
        char_state = create_test_character()
        game_data = create_test_game_data()

        mock_monster = Mock()
        mock_location = Mock()
        mock_location.x = 10
        mock_location.y = 15

        with patch.object(goal.level_targeting, 'find_optimal_monsters') as mock_find:
            mock_find.return_value = [(mock_monster, mock_location, 0.8)]

            target_state = goal.get_target_state(char_state, game_data)

            assert isinstance(target_state, GOAPTargetState)

    def test_get_target_state_no_monsters(self):
        """Test get_target_state with no available monsters."""
        goal = CombatGoal()
        char_state = create_test_character()
        game_data = create_test_game_data()

        with patch.object(goal.level_targeting, 'find_optimal_monsters') as mock_find:
            mock_find.return_value = []

            with pytest.raises((ValueError, Exception)):
                target_state = goal.get_target_state(char_state, game_data)

    def test_get_progression_value_below_target_level(self):
        """Test get_progression_value for character below level 5."""
        goal = CombatGoal()
        char_state = create_test_character()
        char_state.level = 3

        progression = goal.get_progression_value(char_state)

        assert isinstance(progression, (int, float))
        assert progression > 0.1  # Should have decent progression value

    def test_get_progression_value_at_target_level(self):
        """Test get_progression_value for character at level 5."""
        goal = CombatGoal()
        char_state = create_test_character()
        char_state.level = 5

        progression = goal.get_progression_value(char_state)

        assert isinstance(progression, (int, float))
        assert progression == 0.1  # Minimal progression value at target

    def test_estimate_error_risk_high_hp(self):
        """Test estimate_error_risk with high HP."""
        goal = CombatGoal()
        char_state = create_test_character()
        char_state.hp = 95
        char_state.max_hp = 100

        risk = goal.estimate_error_risk(char_state)

        assert isinstance(risk, (int, float))
        assert 0 <= risk <= 1

    def test_estimate_error_risk_low_hp(self):
        """Test estimate_error_risk with low HP."""
        goal = CombatGoal()
        char_state = create_test_character()
        char_state.hp = 20
        char_state.max_hp = 100

        risk = goal.estimate_error_risk(char_state)

        assert isinstance(risk, (int, float))
        assert risk > 0.4  # Should have higher risk with low HP

    def test_generate_sub_goal_requests_low_hp(self):
        """Test generate_sub_goal_requests with low HP."""
        goal = CombatGoal()
        char_state = create_test_character()
        char_state.hp = 30  # Below threshold
        char_state.max_hp = 100
        game_data = create_test_game_data()

        sub_goals = goal.generate_sub_goal_requests(char_state, game_data)

        assert isinstance(sub_goals, list)
        assert len(sub_goals) > 0
        assert any(sub_goal.goal_type == "reach_hp_threshold" for sub_goal in sub_goals)

    def test_generate_sub_goal_requests_not_at_monster_location(self):
        """Test generate_sub_goal_requests when not at monster location."""
        goal = CombatGoal()
        char_state = create_test_character()
        char_state.at_monster_location = False
        game_data = create_test_game_data()

        mock_monster = Mock()
        mock_monster.name = "Test Monster"
        mock_location = Mock()
        mock_location.x = 10
        mock_location.y = 10

        with patch.object(goal.level_targeting, 'find_optimal_monsters') as mock_find:
            mock_find.return_value = [(mock_monster, mock_location, 0.8)]

            sub_goals = goal.generate_sub_goal_requests(char_state, game_data)

            assert isinstance(sub_goals, list)
            # May contain movement sub-goal

    def test_generate_sub_goal_requests_good_conditions(self):
        """Test generate_sub_goal_requests with good conditions."""
        goal = CombatGoal()
        char_state = create_test_character()
        char_state.hp = 80  # Good HP
        char_state.at_monster_location = True
        game_data = create_test_game_data()

        sub_goals = goal.generate_sub_goal_requests(char_state, game_data)

        assert isinstance(sub_goals, list)
        # Should have minimal sub-goals with good conditions

    def test_calculate_combat_feasibility_components(self):
        """Test that combat feasibility considers all components."""
        goal = CombatGoal()
        char_state = create_test_character()
        game_data = create_test_game_data()

        with patch.object(goal.level_targeting, 'find_optimal_monsters') as mock_find:
            mock_find.return_value = [("monster", "location", 0.8)]

            feasibility = goal._calculate_combat_feasibility(char_state, game_data)

            assert isinstance(feasibility, (int, float))
            assert 0 <= feasibility <= 1

    def test_validates_game_data(self):
        """Test that methods validate game data."""
        goal = CombatGoal()
        char_state = create_test_character()
        empty_game_data = GameData()  # Empty data should fail validation

        with pytest.raises(ValueError):
            goal.calculate_weight(char_state, empty_game_data)

        with pytest.raises(ValueError):
            goal.is_feasible(char_state, empty_game_data)
