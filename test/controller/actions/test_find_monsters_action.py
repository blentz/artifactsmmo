"""Test module for architecture-compliant FindMonstersAction."""

import unittest
from unittest.mock import Mock, patch, MagicMock

from src.controller.actions.find_monsters import FindMonstersAction
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from test.fixtures import MockActionContext, create_mock_client


class TestFindMonstersAction(unittest.TestCase):
    """Test cases for architecture-compliant FindMonstersAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.action = FindMonstersAction()
        self.mock_client = create_mock_client()
        
    def test_action_initialization(self):
        """Test FindMonstersAction initialization."""
        action = FindMonstersAction()
        self.assertIsNotNone(action.logger)
        
    def test_repr(self):
        """Test string representation."""
        self.assertEqual(str(self.action), "FindMonstersAction(architecture_compliant=True)")

    def test_execute_no_character_position(self):
        """Test execute when character position is not available in context."""
        context = ActionContext()
        context.character_name = "test_character"
        # Not setting CHARACTER_X, CHARACTER_Y, CHARACTER_LEVEL
        mock_knowledge_base = Mock()
        context.knowledge_base = mock_knowledge_base
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        # The action can fail at different points without character position
        self.assertIsNotNone(result.error)
        
    @patch('artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync')
    def test_execute_character_already_at_monster_location(self, mock_get_character):
        """Test execute when character is already at monster location."""
        # Mock character response
        mock_char_response = Mock()
        mock_char_response.data.x = 10
        mock_char_response.data.y = 20
        mock_char_response.data.level = 5
        mock_get_character.return_value = mock_char_response
        
        # Create context with character position/level and monster data
        context = ActionContext()
        context.character_name = "test_character"
        context.set(StateParameters.CHARACTER_X, 10)
        context.set(StateParameters.CHARACTER_Y, 20)
        context.set(StateParameters.CHARACTER_LEVEL, 5)
        
        # Mock knowledge base with monster at character location
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            "monsters": {
                "chicken": {"level": 3}
            }
        }
        mock_knowledge_base.find_monsters_in_map.return_value = [
            {
                'x': 10,
                'y': 20,
                'monster_code': "chicken",
                'distance': 0.0
            }
        ]
        context.knowledge_base = mock_knowledge_base
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertIn("Found chicken at current location", result.message)
        
    @patch('artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync')
    def test_execute_requests_movement_subgoal(self, mock_get_character):
        """Test execute when character needs to move to monster location."""
        # Mock character response
        mock_char_response = Mock()
        mock_char_response.data.x = 5
        mock_char_response.data.y = 5
        mock_char_response.data.level = 5
        mock_get_character.return_value = mock_char_response
        
        # Create context with character position
        context = ActionContext()
        context.character_name = "test_character"
        context.set(StateParameters.CHARACTER_X, 5)
        context.set(StateParameters.CHARACTER_Y, 5)
        context.set(StateParameters.CHARACTER_LEVEL, 5)
        
        # Mock knowledge base with monster at different location
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            "monsters": {
                "chicken": {"level": 3}
            }
        }
        mock_knowledge_base.find_monsters_in_map.return_value = [
            {
                'x': 10,
                'y': 20,
                'monster_code': "chicken",
                'distance': 10.0
            }
        ]
        context.knowledge_base = mock_knowledge_base
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertIn("Need to move to monster location", result.message)
        self.assertIsNotNone(result.subgoal_request)
        self.assertEqual(result.subgoal_request["goal_name"], "move_to_location")
        self.assertEqual(result.subgoal_request["parameters"], {})  # Parameters set in UnifiedStateContext
        
        # Check that coordinates were set in UnifiedStateContext
        from src.lib.unified_state_context import get_unified_context
        unified_context = get_unified_context()
        self.assertEqual(unified_context.get(StateParameters.TARGET_X), 10)
        self.assertEqual(unified_context.get(StateParameters.TARGET_Y), 20)
        
    @patch('artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync')
    def test_execute_continuation_from_movement(self, mock_get_character):
        """Test execute when continuing from movement subgoal."""
        # Mock character response at target location
        mock_char_response = Mock()
        mock_char_response.data.x = 10
        mock_char_response.data.y = 20
        mock_char_response.data.level = 5
        mock_get_character.return_value = mock_char_response
        
        # Create context with target coordinates (continuation)
        context = ActionContext()
        context.character_name = "test_character"
        context.target_x = 10
        context.target_y = 20
        context.target_monster_code = 'chicken'
        context.set(StateParameters.CHARACTER_X, 10)
        context.set(StateParameters.CHARACTER_Y, 20)
        context.set(StateParameters.CHARACTER_LEVEL, 5)
        
        # Mock knowledge base with monster at target location
        mock_knowledge_base = Mock()
        mock_knowledge_base.find_monsters_in_map.return_value = [
            {
                'x': 10,
                'y': 20,
                'monster_code': "chicken",
                'distance': 5.0
            }
        ]
        context.knowledge_base = mock_knowledge_base
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertIn("Found chicken at current location", result.message)
        
    @patch('artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync')
    def test_execute_no_monsters_in_knowledge_base(self, mock_get_character):
        """Test execute when no monsters found in knowledge base."""
        # Mock character response
        mock_char_response = Mock()
        mock_char_response.data.x = 5
        mock_char_response.data.y = 5
        mock_char_response.data.level = 5
        mock_get_character.return_value = mock_char_response
        
        # Create context with character position
        context = ActionContext()
        context.character_name = "test_character"
        context.set(StateParameters.CHARACTER_X, 5)
        context.set(StateParameters.CHARACTER_Y, 5)
        context.set(StateParameters.CHARACTER_LEVEL, 5)
        
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {"monsters": {}}
        mock_knowledge_base.find_monsters_in_map.return_value = []
        context.knowledge_base = mock_knowledge_base
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertIn("No suitable monsters found in knowledge base", result.error)
        
        
    def test_player_finds_optimal_monster_location_no_knowledge_base(self):
        """Test _player_finds_optimal_monster_location with no knowledge base."""
        context = ActionContext()
        
        result = self.action._player_finds_optimal_monster_location(5, 5, 5, context)
        
        self.assertIsNone(result)
        
    def test_player_finds_optimal_monster_location_no_map_data(self):
        """Test _player_finds_optimal_monster_location with no map data."""
        context = ActionContext()
        context.knowledge_base = Mock()
        context.knowledge_base.data = {"monsters": {}}
        context.knowledge_base.find_monsters_in_map.return_value = []
        
        result = self.action._player_finds_optimal_monster_location(5, 5, 5, context)
        
        self.assertIsNone(result)
        
    def test_player_finds_optimal_monster_location_success(self):
        """Test _player_finds_optimal_monster_location successful monster finding."""
        context = ActionContext()
        
        # Mock knowledge base
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            "monsters": {
                "chicken": {"level": 3},
                "wolf": {"level": 8}  # Too high level
            }
        }
        mock_knowledge_base.find_monsters_in_map.return_value = [
            {
                'x': 10,
                'y': 10,
                'monster_code': "chicken",
                'distance': 7.07  # Distance from (5,5) to (10,10)
            }
        ]
        context.knowledge_base = mock_knowledge_base
        
        result = self.action._player_finds_optimal_monster_location(5, 5, 5, context)
        
        self.assertIsNotNone(result)
        self.assertEqual(result, (10, 10, "chicken"))
        
    def test_character_finds_monsters_at_location_no_monster(self):
        """Test _character_finds_monsters_at_location when no monster at location."""
        context = ActionContext()
        mock_knowledge_base = Mock()
        mock_knowledge_base.find_monsters_in_map.return_value = []
        context.knowledge_base = mock_knowledge_base
        
        result = self.action._character_finds_monsters_at_location(10, 10, 5, context)
        
        self.assertFalse(result.success)
        self.assertIn("No monsters found at current location", result.error)
        
    def test_character_finds_monsters_at_location_success(self):
        """Test _character_finds_monsters_at_location successful finding."""
        context = ActionContext()
        mock_knowledge_base = Mock()
        mock_knowledge_base.find_monsters_in_map.return_value = [
            {
                'x': 10,
                'y': 10,
                'monster_code': "chicken",
                'distance': 0.0
            }
        ]
        context.knowledge_base = mock_knowledge_base
        
        result = self.action._character_finds_monsters_at_location(10, 10, 5, context)
        
        self.assertTrue(result.success)
        self.assertIn("Found chicken at current location", result.message)
        
    @patch('artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync')
    def test_execute_exception_handling(self, mock_get_character):
        """Test execute with exception handling."""
        mock_get_character.side_effect = Exception("Unexpected error")
        context = ActionContext()
        context.character_name = "test_character"
        mock_knowledge_base = Mock()
        context.knowledge_base = mock_knowledge_base
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        # The action can fail at different points, so just check that it fails
        self.assertIsNotNone(result.error)


if __name__ == '__main__':
    unittest.main()