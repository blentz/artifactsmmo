"""
Tests for Combat Action Factory Implementation

This module tests the CombatActionFactory for creating CombatAction instances
with proper monster targeting for combat operations within the GOAP system.
"""

from unittest.mock import Mock

from src.ai_player.actions.combat_action import CombatAction
from src.ai_player.actions.combat_action_factory import CombatActionFactory
from src.ai_player.state.character_game_state import CharacterGameState


class TestCombatActionFactory:
    """Test CombatActionFactory class"""

    def setup_method(self):
        """Setup test fixtures"""
        self.factory = CombatActionFactory()
        self.mock_character_state = Mock(spec=CharacterGameState)

    def test_get_action_type(self):
        """Test get_action_type returns CombatAction"""
        action_type = self.factory.get_action_type()
        assert action_type == CombatAction

    def test_create_instances_no_monsters(self):
        """Test creating instances when no monsters are available"""
        game_data = Mock()
        game_data.monsters = None

        instances = self.factory.create_instances(game_data, self.mock_character_state)

        # Should create a generic combat action
        assert len(instances) == 1
        assert isinstance(instances[0], CombatAction)
        assert instances[0].target_monster is None

    def test_create_instances_empty_monsters(self):
        """Test creating instances when monsters list is empty"""
        game_data = Mock()
        game_data.monsters = []

        instances = self.factory.create_instances(game_data, self.mock_character_state)

        # Should create only a generic combat action
        assert len(instances) == 1
        assert isinstance(instances[0], CombatAction)
        assert instances[0].target_monster is None

    def test_create_instances_with_monsters(self):
        """Test creating instances when monsters are available"""
        mock_monster1 = Mock()
        mock_monster1.code = "chicken"
        mock_monster2 = Mock()
        mock_monster2.code = "cow"

        game_data = Mock()
        game_data.monsters = [mock_monster1, mock_monster2]

        instances = self.factory.create_instances(game_data, self.mock_character_state)

        # Should create generic action plus specific monster actions
        assert len(instances) == 3
        assert all(isinstance(action, CombatAction) for action in instances)

        # First should be generic
        assert instances[0].target_monster is None

        # Rest should be monster-specific
        target_monsters = [instances[1].target_monster, instances[2].target_monster]
        assert "chicken" in target_monsters
        assert "cow" in target_monsters

    def test_create_instances_monsters_without_code(self):
        """Test creating instances when monsters don't have code attribute"""
        mock_monster = Mock()
        del mock_monster.code  # Remove code attribute

        game_data = Mock()
        game_data.monsters = [mock_monster]

        instances = self.factory.create_instances(game_data, self.mock_character_state)

        # Should create only generic action (monster without code is skipped)
        assert len(instances) == 1
        assert isinstance(instances[0], CombatAction)
        assert instances[0].target_monster is None

    def test_create_instances_no_monsters_attribute(self):
        """Test creating instances when game_data has no monsters attribute"""
        game_data = Mock()
        if hasattr(game_data, 'monsters'):
            delattr(game_data, 'monsters')

        instances = self.factory.create_instances(game_data, self.mock_character_state)

        # Should create only generic action
        assert len(instances) == 1
        assert isinstance(instances[0], CombatAction)
        assert instances[0].target_monster is None

    def test_create_instances_mixed_monsters(self):
        """Test creating instances with mix of valid and invalid monsters"""
        mock_monster_valid = Mock()
        mock_monster_valid.code = "chicken"

        mock_monster_invalid = Mock()
        del mock_monster_invalid.code  # No code attribute

        game_data = Mock()
        game_data.monsters = [mock_monster_valid, mock_monster_invalid]

        instances = self.factory.create_instances(game_data, self.mock_character_state)

        # Should create generic action plus one valid monster action
        assert len(instances) == 2
        assert instances[0].target_monster is None
        assert instances[1].target_monster == "chicken"
