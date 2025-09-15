"""
Comprehensive tests for MovementGoal to achieve 100% code coverage.

This module focuses on testing all code paths, edge cases, and error conditions
in the MovementGoal implementation to ensure complete test coverage.
"""

import pytest
from unittest.mock import Mock

from src.ai_player.goals.movement_goal import MovementGoal
from src.ai_player.state.character_game_state import CharacterGameState
from src.ai_player.state.game_state import GameState
from src.game_data.game_data import GameData
from src.ai_player.types.goap_models import GOAPTargetState
from src.game_data.models import GameItem, GameMap, GameMonster, GameNPC, GameResource


def create_test_character(x: int = 5, y: int = 5, **kwargs):
    """Create a test character with customizable position."""
    defaults = {
        "name": "test_character",
        "level": 3,
        "xp": 1000,
        "hp": 80,
        "max_hp": 100,
        "x": x,
        "y": y,
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


class TestMovementGoal:
    """Comprehensive tests for MovementGoal class."""

    def test_init_basic(self):
        """Test MovementGoal initialization with basic values."""
        goal = MovementGoal(target_x=10, target_y=15)
        assert goal.target_x == 10
        assert goal.target_y == 15

    def test_init_negative_coordinates(self):
        """Test MovementGoal initialization with negative coordinates."""
        goal = MovementGoal(target_x=-5, target_y=-10)
        assert goal.target_x == -5
        assert goal.target_y == -10

    def test_init_zero_coordinates(self):
        """Test MovementGoal initialization with zero coordinates."""
        goal = MovementGoal(target_x=0, target_y=0)
        assert goal.target_x == 0
        assert goal.target_y == 0

    def test_calculate_weight_same_location(self):
        """Test calculate_weight when at same location as target."""
        goal = MovementGoal(target_x=5, target_y=5)
        character = create_test_character(x=5, y=5)
        game_data = create_test_game_data()
        
        weight = goal.calculate_weight(character, game_data)
        # Distance = 0, distance_factor = 0.0
        # Weight = 5.0 + 0.0 * 2.0 = 5.0
        assert weight == 5.0

    def test_calculate_weight_close_distance(self):
        """Test calculate_weight with close distance."""
        goal = MovementGoal(target_x=8, target_y=7)
        character = create_test_character(x=5, y=5)
        game_data = create_test_game_data()
        
        weight = goal.calculate_weight(character, game_data)
        # Distance = |5-8| + |5-7| = 3 + 2 = 5
        # distance_factor = min(1.0, 5/10.0) = 0.5
        # Weight = 5.0 + 0.5 * 2.0 = 6.0
        assert weight == 6.0

    def test_calculate_weight_far_distance(self):
        """Test calculate_weight with far distance (capped at max)."""
        goal = MovementGoal(target_x=20, target_y=20)
        character = create_test_character(x=5, y=5)
        game_data = create_test_game_data()
        
        weight = goal.calculate_weight(character, game_data)
        # Distance = |5-20| + |5-20| = 15 + 15 = 30
        # distance_factor = min(1.0, 30/10.0) = 1.0 (capped)
        # Weight = 5.0 + 1.0 * 2.0 = 7.0
        assert weight == 7.0

    def test_is_feasible_already_at_target(self):
        """Test is_feasible when already at target location."""
        goal = MovementGoal(target_x=5, target_y=5)
        character = create_test_character(x=5, y=5)
        game_data = create_test_game_data()
        
        feasible = goal.is_feasible(character, game_data)
        assert feasible is False

    def test_is_feasible_not_at_target(self):
        """Test is_feasible when not at target location."""
        goal = MovementGoal(target_x=10, target_y=10)
        character = create_test_character(x=5, y=5)
        game_data = create_test_game_data()
        
        feasible = goal.is_feasible(character, game_data)
        assert feasible is True

    def test_is_feasible_partial_match_x(self):
        """Test is_feasible when only X coordinate matches."""
        goal = MovementGoal(target_x=5, target_y=10)
        character = create_test_character(x=5, y=5)
        game_data = create_test_game_data()
        
        feasible = goal.is_feasible(character, game_data)
        assert feasible is True

    def test_is_feasible_partial_match_y(self):
        """Test is_feasible when only Y coordinate matches."""
        goal = MovementGoal(target_x=10, target_y=5)
        character = create_test_character(x=5, y=5)
        game_data = create_test_game_data()
        
        feasible = goal.is_feasible(character, game_data)
        assert feasible is True

    def test_get_target_state_basic(self):
        """Test get_target_state returns correct GOAP target state."""
        goal = MovementGoal(target_x=10, target_y=15)
        character = create_test_character(x=5, y=5)
        game_data = create_test_game_data()
        
        target_state = goal.get_target_state(character, game_data)
        
        assert isinstance(target_state, GOAPTargetState)
        assert target_state.target_states[GameState.CURRENT_X] == 10
        assert target_state.target_states[GameState.CURRENT_Y] == 15
        assert target_state.priority == 5
        assert target_state.timeout_seconds == 60

    def test_get_target_state_negative_coordinates(self):
        """Test get_target_state with negative coordinates."""
        goal = MovementGoal(target_x=-3, target_y=-7)
        character = create_test_character(x=5, y=5)
        game_data = create_test_game_data()
        
        target_state = goal.get_target_state(character, game_data)
        
        assert target_state.target_states[GameState.CURRENT_X] == -3
        assert target_state.target_states[GameState.CURRENT_Y] == -7

    def test_get_progression_value_always_zero(self):
        """Test get_progression_value always returns 0.0."""
        goal = MovementGoal(target_x=10, target_y=10)
        character = create_test_character(x=5, y=5)
        
        progression = goal.get_progression_value(character)
        assert progression == 0.0

    def test_estimate_error_risk_constant(self):
        """Test estimate_error_risk returns constant low risk."""
        goal = MovementGoal(target_x=10, target_y=10)
        character = create_test_character(x=5, y=5)
        
        risk = goal.estimate_error_risk(character)
        assert risk == 0.1

    def test_generate_sub_goal_requests_empty(self):
        """Test generate_sub_goal_requests returns empty list."""
        goal = MovementGoal(target_x=10, target_y=10)
        character = create_test_character(x=5, y=5)
        game_data = create_test_game_data()
        
        sub_goals = goal.generate_sub_goal_requests(character, game_data)
        assert sub_goals == []

    @pytest.mark.parametrize("char_x,char_y,target_x,target_y,expected_distance,expected_weight", [
        (0, 0, 0, 0, 0, 5.0),       # Same position
        (0, 0, 1, 1, 2, 5.4),       # Distance 2
        (0, 0, 5, 5, 10, 7.0),      # Distance 10 (at threshold)
        (0, 0, 10, 10, 20, 7.0),    # Distance 20 (capped)
        (-5, -5, 5, 5, 20, 7.0),    # Negative to positive
        (5, 5, -5, -5, 20, 7.0),    # Positive to negative
    ])
    def test_calculate_weight_various_distances(self, char_x, char_y, target_x, target_y, expected_distance, expected_weight):
        """Test calculate_weight with various distance scenarios."""
        goal = MovementGoal(target_x=target_x, target_y=target_y)
        character = create_test_character(x=char_x, y=char_y)
        game_data = create_test_game_data()
        
        weight = goal.calculate_weight(character, game_data)
        assert abs(weight - expected_weight) < 0.1  # Allow small floating point differences

    @pytest.mark.parametrize("char_x,char_y,target_x,target_y,expected_feasible", [
        (5, 5, 5, 5, False),   # Exact match - not feasible
        (5, 5, 5, 6, True),    # Y different - feasible
        (5, 5, 6, 5, True),    # X different - feasible
        (5, 5, 6, 6, True),    # Both different - feasible
        (0, 0, 0, 0, False),   # Origin match - not feasible
        (-1, -1, -1, -1, False), # Negative match - not feasible
    ])
    def test_is_feasible_various_positions(self, char_x, char_y, target_x, target_y, expected_feasible):
        """Test is_feasible with various position combinations."""
        goal = MovementGoal(target_x=target_x, target_y=target_y)
        character = create_test_character(x=char_x, y=char_y)
        game_data = create_test_game_data()
        
        feasible = goal.is_feasible(character, game_data)
        assert feasible == expected_feasible