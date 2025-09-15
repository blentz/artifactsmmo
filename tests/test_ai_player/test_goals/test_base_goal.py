"""
Tests for BaseGoal abstract base class

This module tests the BaseGoal interface that all specialized goal types implement
for weighted goal selection and strategic planning.
"""

import inspect
from unittest.mock import Mock

import pytest

from src.ai_player.goals.base_goal import BaseGoal
from src.ai_player.state.character_game_state import CharacterGameState
from src.ai_player.state.game_state import GameState
from src.game_data.game_data import GameData
from src.ai_player.types.goap_models import GOAPTargetState
from src.game_data.models import GameItem, GameMap, GameMonster, GameNPC, GameResource


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


class ConcreteGoal(BaseGoal):
    """Concrete implementation of BaseGoal for testing."""

    def calculate_weight(self, character_state, game_data):
        return 5.0

    def is_feasible(self, character_state, game_data):
        return True

    def get_target_state(self, character_state, game_data):
        return GOAPTargetState(
            target_states={GameState.CHARACTER_LEVEL: 10},
            priority=5
        )

    def get_progression_value(self, character_state):
        return 0.8

    def estimate_error_risk(self, character_state):
        return 0.2

    def generate_sub_goal_requests(self, character_state, game_data):
        return []


class TestBaseGoal:
    """Test BaseGoal abstract interface and common functionality."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that BaseGoal cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseGoal()

    def test_concrete_implementation_works(self):
        """Test that concrete implementation of BaseGoal works."""
        goal = ConcreteGoal()
        char_state = create_test_character()
        game_data = create_test_game_data()

        # All abstract methods should work
        assert goal.calculate_weight(char_state, game_data) == 5.0
        assert goal.is_feasible(char_state, game_data) is True
        target_state = goal.get_target_state(char_state, game_data)
        assert isinstance(target_state, GOAPTargetState)
        assert target_state.priority == 5
        assert goal.get_progression_value(char_state) == 0.8
        assert goal.estimate_error_risk(char_state) == 0.2
        assert goal.generate_sub_goal_requests(char_state, game_data) == []

    def test_validate_game_data_success(self):
        """Test validate_game_data with valid data."""
        goal = ConcreteGoal()
        game_data = create_test_game_data()

        # Should not raise exception
        goal.validate_game_data(game_data)

    def test_validate_game_data_with_empty_data(self):
        """Test validate_game_data with empty GameData."""
        goal = ConcreteGoal()
        empty_game_data = GameData()  # Empty data should fail validation

        with pytest.raises(ValueError, match="Monster data is required but not cached"):
            goal.validate_game_data(empty_game_data)

    def test_validate_game_data_empty_monsters(self):
        """Test validate_game_data with empty monsters."""
        goal = ConcreteGoal()
        game_data = GameData()  # Empty data

        with pytest.raises(ValueError, match="Monster data is required but not cached"):
            goal.validate_game_data(game_data)

    def test_validate_game_data_calls_game_data_validation(self):
        """Test that validate_game_data calls GameData's own validation."""
        goal = ConcreteGoal()
        mock_game_data = Mock(spec=GameData)
        mock_game_data.validate_required_data = Mock()

        goal.validate_game_data(mock_game_data)

        mock_game_data.validate_required_data.assert_called_once()

    def test_abstract_methods_defined(self):
        """Test that all required abstract methods are defined."""
        # Get all abstract methods from BaseGoal
        abstract_methods = BaseGoal.__abstractmethods__

        expected_methods = {
            'calculate_weight',
            'is_feasible',
            'get_target_state',
            'get_progression_value',
            'estimate_error_risk',
            'generate_sub_goal_requests'
        }

        assert abstract_methods == expected_methods

    def test_docstrings_present(self):
        """Test that abstract methods have proper docstrings."""
        # Check that abstract methods have documentation
        assert BaseGoal.calculate_weight.__doc__ is not None
        assert BaseGoal.is_feasible.__doc__ is not None
        assert BaseGoal.get_target_state.__doc__ is not None
        assert BaseGoal.get_progression_value.__doc__ is not None
        assert BaseGoal.estimate_error_risk.__doc__ is not None
        assert BaseGoal.generate_sub_goal_requests.__doc__ is not None

    def test_method_signatures(self):
        """Test that abstract methods have correct signatures."""
        # This ensures the interface is properly defined
        # Check calculate_weight signature
        sig = inspect.signature(BaseGoal.calculate_weight)
        params = list(sig.parameters.keys())
        assert params == ['self', 'character_state', 'game_data']

        # Check is_feasible signature
        sig = inspect.signature(BaseGoal.is_feasible)
        params = list(sig.parameters.keys())
        assert params == ['self', 'character_state', 'game_data']

        # Check get_target_state signature
        sig = inspect.signature(BaseGoal.get_target_state)
        params = list(sig.parameters.keys())
        assert params == ['self', 'character_state', 'game_data']

        # Check get_progression_value signature
        sig = inspect.signature(BaseGoal.get_progression_value)
        params = list(sig.parameters.keys())
        assert params == ['self', 'character_state', 'game_data']

        # Check estimate_error_risk signature
        sig = inspect.signature(BaseGoal.estimate_error_risk)
        params = list(sig.parameters.keys())
        assert params == ['self', 'character_state']

        # Check generate_sub_goal_requests signature
        sig = inspect.signature(BaseGoal.generate_sub_goal_requests)
        params = list(sig.parameters.keys())
        assert params == ['self', 'character_state', 'game_data']
