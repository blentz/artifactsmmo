"""
Test location state invalidation to prevent stale workshop states
"""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.controller.ai_player_controller import AIPlayerController
from src.controller.world.state import WorldState
from src.game.character.state import CharacterState


class TestLocationStateInvalidation(unittest.TestCase):
    """Test that location-based states are properly invalidated"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary directory for test data
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.temp_dir, 'config')
        os.makedirs(self.config_dir)
        
        # Create test location states config
        self.location_config_path = os.path.join(self.config_dir, 'location_states.yaml')
        with open(self.location_config_path, 'w') as f:
            f.write("""location_based_states:
  - at_correct_workshop
  - at_target_location
  - at_resource_location
  - at_workshop
  - monster_present
  - resource_found
""")
        
        # Patch the DATA_PREFIX and CONFIG_PREFIX to use temp directory
        self.data_prefix_patcher = patch('src.controller.world.state.DATA_PREFIX', self.temp_dir)
        self.data_prefix_patcher.start()
        
        self.config_prefix_patcher = patch('src.controller.ai_player_controller.CONFIG_PREFIX', self.config_dir)
        self.config_prefix_patcher.start()
        
        # Create controller instance
        self.controller = AIPlayerController()
        
        # Create mock world state with stale location data
        self.controller.world_state = WorldState('test_world')
        self.controller.world_state.data = {
            'at_correct_workshop': True,
            'at_target_location': True,
            'at_resource_location': True,
            'at_workshop': True,
            'monster_present': True,
            'resource_found': True,
            'best_weapon_selected': True,
            'other_state': True  # Non-location state should not be invalidated
        }
        
    def tearDown(self):
        """Clean up after tests"""
        self.data_prefix_patcher.stop()
        self.config_prefix_patcher.stop()
        
    def test_location_states_invalidated_on_character_set(self):
        """Test that location states are invalidated when character is set"""
        # Create mock character state
        mock_char_state = Mock(spec=CharacterState)
        
        # Set character state (should trigger invalidation)
        self.controller.set_character_state(mock_char_state)
        
        # Verify location states were invalidated
        self.assertFalse(self.controller.world_state.data.get('at_correct_workshop'))
        self.assertFalse(self.controller.world_state.data.get('at_target_location'))
        self.assertFalse(self.controller.world_state.data.get('at_resource_location'))
        self.assertFalse(self.controller.world_state.data.get('at_workshop'))
        self.assertFalse(self.controller.world_state.data.get('monster_present'))
        self.assertFalse(self.controller.world_state.data.get('resource_found'))
        
        # Verify non-location states were preserved
        self.assertTrue(self.controller.world_state.data.get('best_weapon_selected'))
        self.assertTrue(self.controller.world_state.data.get('other_state'))
        
    def test_invalidation_handles_missing_world_state(self):
        """Test that invalidation handles missing world state gracefully"""
        # Remove world state
        self.controller.world_state = None
        
        # This should not raise an exception
        mock_char_state = Mock(spec=CharacterState)
        self.controller.set_character_state(mock_char_state)
        
        # Verify character state was still set
        self.assertEqual(self.controller.character_state, mock_char_state)
        
    def test_invalidation_handles_missing_data_attribute(self):
        """Test that invalidation handles world state without data attribute"""
        # Create world state without data attribute
        self.controller.world_state = Mock()
        del self.controller.world_state.data
        
        # This should not raise an exception
        mock_char_state = Mock(spec=CharacterState)
        self.controller.set_character_state(mock_char_state)
        
        # Verify character state was still set
        self.assertEqual(self.controller.character_state, mock_char_state)
        
    def test_invalidation_saves_world_state(self):
        """Test that world state is saved after invalidation"""
        # Mock the save method
        self.controller.world_state.save = Mock()
        
        # Set character state
        mock_char_state = Mock(spec=CharacterState)
        self.controller.set_character_state(mock_char_state)
        
        # Verify save was called
        self.controller.world_state.save.assert_called_once()
        
    def test_partial_location_states_invalidated(self):
        """Test invalidation when only some location states are present"""
        # Set only some location states
        self.controller.world_state.data = {
            'at_correct_workshop': True,
            'at_target_location': True,
            'best_weapon_selected': True,
            'craft_plan_available': True
        }
        
        # Set character state
        mock_char_state = Mock(spec=CharacterState)
        self.controller.set_character_state(mock_char_state)
        
        # Verify only existing location states were invalidated
        self.assertFalse(self.controller.world_state.data.get('at_correct_workshop'))
        self.assertFalse(self.controller.world_state.data.get('at_target_location'))
        
        # Verify non-location states were preserved
        self.assertTrue(self.controller.world_state.data.get('best_weapon_selected'))
        self.assertTrue(self.controller.world_state.data.get('craft_plan_available'))


if __name__ == '__main__':
    unittest.main()