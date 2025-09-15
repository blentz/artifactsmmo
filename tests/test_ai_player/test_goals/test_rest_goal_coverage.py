"""
Comprehensive tests for RestGoal to achieve 100% code coverage.

This module focuses on testing all code paths, edge cases, and error conditions
in the RestGoal implementation to ensure complete test coverage.
"""

import pytest
from unittest.mock import Mock

from src.ai_player.goals.rest_goal import RestGoal
from src.ai_player.state.character_game_state import CharacterGameState
from src.ai_player.state.game_state import GameState
from src.game_data.game_data import GameData
from src.ai_player.types.goap_models import GOAPTargetState
from src.game_data.models import GameItem, GameMap, GameMonster, GameNPC, GameResource


def create_test_character(hp: int = 80, max_hp: int = 100, **kwargs):
    """Create a test character with customizable HP values."""
    defaults = {
        "name": "test_character",
        "level": 3,
        "xp": 1000,
        "hp": hp,
        "max_hp": max_hp,
        "x": 5,
        "y": 5,
        "gold": 500,
        "mining_level": 2,
        "mining_xp": 100,
        "woodcutting_level": 1,
        "woodcutting_xp": 50,
        "fishing_level": 1,
        "fishing_xp": 0,
        "weaponcrafting_level": 1,
        "weaponcrafting_xp": 0,
        "gearcrafting_level": 1,
        "gearcrafting_xp": 0,
        "jewelrycrafting_level": 1,
        "jewelrycrafting_xp": 0,
        "cooking_level": 1,
        "cooking_xp": 0,
        "alchemy_level": 1,
        "alchemy_xp": 0,
        "cooldown": 0,
        "weapon_slot": "basic_sword",
        "rune_slot": "",
        "shield_slot": "",
        "helmet_slot": "",
        "body_armor_slot": "",
        "leg_armor_slot": "",
        "boots_slot": "",
        "ring1_slot": "",
        "ring2_slot": "",
        "amulet_slot": "",
        "artifact1_slot": "",
        "at_monster_location": False
    }
    defaults.update(kwargs)
    return CharacterGameState(**defaults)


def create_test_game_data():
    """Create test game data with mock objects."""
    mock_monster = Mock(spec=GameMonster)
    mock_item = Mock(spec=GameItem)
    mock_resource = Mock(spec=GameResource)
    mock_map = Mock(spec=GameMap)
    mock_npc = Mock(spec=GameNPC)

    return GameData(
        monsters=[mock_monster],
        items=[mock_item],
        resources=[mock_resource],
        maps=[mock_map],
        npcs=[mock_npc]
    )


class TestRestGoal:
    """Comprehensive tests for RestGoal class."""

    def test_init_default_values(self):
        """Test RestGoal initialization with default values."""
        goal = RestGoal()
        assert goal.min_hp_percentage == 0.8

    def test_init_custom_values(self):
        """Test RestGoal initialization with custom values."""
        goal = RestGoal(min_hp_percentage=0.9)
        assert goal.min_hp_percentage == 0.9

    def test_init_value_clamping(self):
        """Test that initialization clamps values to valid range."""
        # Test lower bound
        goal = RestGoal(min_hp_percentage=-0.5)
        assert goal.min_hp_percentage == 0.0

        # Test upper bound
        goal = RestGoal(min_hp_percentage=1.5)
        assert goal.min_hp_percentage == 1.0

    def test_calculate_weight_zero_max_hp(self):
        """Test calculate_weight with zero max HP."""
        goal = RestGoal()
        # Create a mock character to bypass Pydantic validation
        character = Mock()
        character.hp = 0
        character.max_hp = 0
        game_data = create_test_game_data()
        
        weight = goal.calculate_weight(character, game_data)
        assert weight == 0.0

    def test_calculate_weight_no_rest_needed(self):
        """Test calculate_weight when no rest is needed."""
        goal = RestGoal(min_hp_percentage=0.8)
        character = create_test_character(hp=85, max_hp=100)  # 85% HP
        game_data = create_test_game_data()
        
        weight = goal.calculate_weight(character, game_data)
        assert weight == 0.0

    def test_calculate_weight_critical_hp(self):
        """Test calculate_weight with critical HP (< 30%)."""
        goal = RestGoal()
        character = create_test_character(hp=25, max_hp=100)  # 25% HP
        game_data = create_test_game_data()
        
        weight = goal.calculate_weight(character, game_data)
        assert weight == 10.0

    def test_calculate_weight_high_priority_hp(self):
        """Test calculate_weight with high priority HP (30-50%)."""
        goal = RestGoal()
        character = create_test_character(hp=40, max_hp=100)  # 40% HP
        game_data = create_test_game_data()
        
        weight = goal.calculate_weight(character, game_data)
        assert weight == 8.0

    def test_calculate_weight_moderate_priority_hp(self):
        """Test calculate_weight with moderate priority HP (>50%)."""
        goal = RestGoal(min_hp_percentage=0.8)
        character = create_test_character(hp=60, max_hp=100)  # 60% HP
        game_data = create_test_game_data()
        
        weight = goal.calculate_weight(character, game_data)
        # hp_deficit = 0.8 - 0.6 = 0.2
        # weight = 5.0 + 0.2 * 3.0 = 5.6
        assert abs(weight - 5.6) < 0.1

    def test_is_feasible_zero_max_hp(self):
        """Test is_feasible with zero max HP."""
        goal = RestGoal()
        character = Mock()
        character.hp = 0
        character.max_hp = 0
        game_data = create_test_game_data()
        
        feasible = goal.is_feasible(character, game_data)
        assert feasible is False

    def test_is_feasible_already_at_target(self):
        """Test is_feasible when already at or above target HP."""
        goal = RestGoal(min_hp_percentage=0.8)
        character = create_test_character(hp=85, max_hp=100)  # 85% HP
        game_data = create_test_game_data()
        
        feasible = goal.is_feasible(character, game_data)
        assert feasible is False

    def test_is_feasible_already_at_max_hp(self):
        """Test is_feasible when already at max HP."""
        goal = RestGoal()
        character = create_test_character(hp=100, max_hp=100)  # 100% HP
        game_data = create_test_game_data()
        
        feasible = goal.is_feasible(character, game_data)
        assert feasible is False

    def test_is_feasible_valid_scenario(self):
        """Test is_feasible with valid rest scenario."""
        goal = RestGoal(min_hp_percentage=0.8)
        character = create_test_character(hp=60, max_hp=100)  # 60% HP
        game_data = create_test_game_data()
        
        feasible = goal.is_feasible(character, game_data)
        assert feasible is True

    def test_get_target_state_basic(self):
        """Test get_target_state returns correct GOAP target state."""
        goal = RestGoal(min_hp_percentage=0.8)
        character = create_test_character(hp=60, max_hp=100)
        game_data = create_test_game_data()
        
        target_state = goal.get_target_state(character, game_data)
        
        assert isinstance(target_state, GOAPTargetState)
        assert target_state.target_states[GameState.HP_CURRENT] == 80  # 100 * 0.8
        assert target_state.target_states[GameState.COOLDOWN_READY] is True
        assert target_state.priority == 8
        assert target_state.timeout_seconds == 300

    def test_is_completed_zero_max_hp(self):
        """Test is_completed with zero max HP edge case."""
        goal = RestGoal()
        character = Mock()
        character.hp = 0
        character.max_hp = 0
        game_data = create_test_game_data()
        
        completed = goal.is_completed(character, game_data)
        assert completed is True

    def test_is_completed_target_reached(self):
        """Test is_completed when target HP is reached."""
        goal = RestGoal(min_hp_percentage=0.8)
        character = create_test_character(hp=85, max_hp=100)  # 85% HP
        game_data = create_test_game_data()
        
        completed = goal.is_completed(character, game_data)
        assert completed is True

    def test_is_completed_target_not_reached(self):
        """Test is_completed when target HP is not reached."""
        goal = RestGoal(min_hp_percentage=0.8)
        character = create_test_character(hp=60, max_hp=100)  # 60% HP
        game_data = create_test_game_data()
        
        completed = goal.is_completed(character, game_data)
        assert completed is False

    def test_get_progression_value_zero_max_hp(self):
        """Test get_progression_value with zero max HP."""
        goal = RestGoal()
        character = Mock()
        character.hp = 0
        character.max_hp = 0
        game_data = create_test_game_data()
        
        progression = goal.get_progression_value(character, game_data)
        assert progression == 1.0

    def test_get_progression_value_completed(self):
        """Test get_progression_value when goal is completed."""
        goal = RestGoal(min_hp_percentage=0.8)
        character = create_test_character(hp=85, max_hp=100)  # 85% HP
        game_data = create_test_game_data()
        
        progression = goal.get_progression_value(character, game_data)
        assert progression == 1.0

    def test_get_progression_value_partial_progress(self):
        """Test get_progression_value with partial progress."""
        goal = RestGoal(min_hp_percentage=0.8)
        character = create_test_character(hp=40, max_hp=100)  # 40% HP
        game_data = create_test_game_data()
        
        progression = goal.get_progression_value(character, game_data)
        # progress = 0.4 / 0.8 = 0.5
        assert progression == 0.5

    def test_str_representation(self):
        """Test string representation of RestGoal."""
        goal = RestGoal(min_hp_percentage=0.75)
        str_repr = str(goal)
        assert str_repr == "RestGoal(min_hp_percentage=75.0%)"

    def test_repr_representation(self):
        """Test detailed string representation of RestGoal."""
        goal = RestGoal(min_hp_percentage=0.75)
        repr_str = repr(goal)
        assert repr_str == "RestGoal(min_hp_percentage=0.75)"

    def test_estimate_error_risk_zero_max_hp(self):
        """Test estimate_error_risk with zero max HP."""
        goal = RestGoal()
        character = Mock()
        character.hp = 0
        character.max_hp = 0
        
        risk = goal.estimate_error_risk(character)
        assert risk == 0.0

    def test_estimate_error_risk_extremely_low_hp(self):
        """Test estimate_error_risk with extremely low HP (<10%)."""
        goal = RestGoal()
        character = create_test_character(hp=5, max_hp=100)  # 5% HP
        
        risk = goal.estimate_error_risk(character)
        assert risk == 0.3

    def test_estimate_error_risk_low_hp(self):
        """Test estimate_error_risk with low HP (10-20%)."""
        goal = RestGoal()
        character = create_test_character(hp=15, max_hp=100)  # 15% HP
        
        risk = goal.estimate_error_risk(character)
        assert risk == 0.1

    def test_estimate_error_risk_normal_hp(self):
        """Test estimate_error_risk with normal HP (>20%)."""
        goal = RestGoal()
        character = create_test_character(hp=50, max_hp=100)  # 50% HP
        
        risk = goal.estimate_error_risk(character)
        assert risk == 0.0

    def test_generate_sub_goal_requests(self):
        """Test generate_sub_goal_requests returns empty list."""
        goal = RestGoal()
        character = create_test_character()
        game_data = create_test_game_data()
        
        sub_goals = goal.generate_sub_goal_requests(character, game_data)
        assert sub_goals == []

    @pytest.mark.parametrize("hp,max_hp,min_percentage,expected_weight", [
        (20, 100, 0.8, 10.0),  # Critical HP
        (40, 100, 0.8, 8.0),   # High priority HP
        (60, 100, 0.8, 5.6),   # Moderate priority HP: 5.0 + (0.8-0.6)*3.0 = 5.6
        (80, 100, 0.8, 0.0),   # No rest needed
        (0, 100, 0.8, 10.0),   # Zero HP (critical)
        (100, 100, 0.8, 0.0),  # Full HP
    ])
    def test_calculate_weight_various_scenarios(self, hp, max_hp, min_percentage, expected_weight):
        """Test calculate_weight with various HP scenarios."""
        goal = RestGoal(min_hp_percentage=min_percentage)
        character = create_test_character(hp=hp, max_hp=max_hp)
        game_data = create_test_game_data()
        
        weight = goal.calculate_weight(character, game_data)
        assert abs(weight - expected_weight) < 0.1  # Allow small floating point differences

    @pytest.mark.parametrize("hp,max_hp,min_percentage,expected_feasible", [
        (60, 100, 0.8, True),   # Below target, feasible
        (80, 100, 0.8, False),  # At target, not feasible
        (90, 100, 0.8, False),  # Above target, not feasible
        (100, 100, 0.8, False), # At max HP, not feasible
        (1, 1, 0.8, False),     # Need to use valid max_hp for Pydantic
    ])
    def test_is_feasible_various_scenarios(self, hp, max_hp, min_percentage, expected_feasible):
        """Test is_feasible with various HP scenarios."""
        goal = RestGoal(min_hp_percentage=min_percentage)
        character = create_test_character(hp=hp, max_hp=max_hp)
        game_data = create_test_game_data()
        
        feasible = goal.is_feasible(character, game_data)
        assert feasible == expected_feasible