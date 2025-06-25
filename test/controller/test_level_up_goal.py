"""
Unit tests for level_up_goal functionality in AIPlayerController.
"""

import unittest
from unittest.mock import Mock, patch
import tempfile
import os

from src.controller.ai_player_controller import AIPlayerController
from src.game.character.state import CharacterState


class TestLevelUpGoal(unittest.TestCase):
    """Test cases for level_up goal functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.controller = AIPlayerController(client=self.mock_client)
        
        # Create mock character state
        self.mock_character = Mock()
        self.mock_character.name = "test_character"
        self.mock_character.data = {
            'level': 1,
            'xp': 50,
            'max_xp': 150,
            'hp': 80,
            'max_hp': 100,
            'x': 0,
            'y': 0
        }
        
        self.controller.set_character_state(self.mock_character)
        
    def test_level_up_goal_target_level_calculation(self):
        """Test that level_up_goal correctly calculates target level."""
        
        def mock_achieve_goal_side_effect(goal_state, config_file=None, max_iterations=3):
            # Simulate successful leveling by updating character state level
            if 'monsters_available' in goal_state:
                # This is a hunting cycle, update the character level
                new_level = self.controller.character_state.data.get('level', 1) + 1
                self.controller.character_state.data['level'] = new_level
                self.controller.character_state.data['xp'] = self.controller.character_state.data.get('max_xp', 150)
            return True
        
        # Test with no target level specified (should be current + 1)
        with patch.object(self.controller, 'achieve_goal_with_goap', side_effect=mock_achieve_goal_side_effect):
            success = self.controller.level_up_goal()
            self.assertTrue(success)
            
        # Reset character state for next test
        self.controller.character_state.data['level'] = 1
        self.controller.character_state.data['xp'] = 0
            
        # Test with specific target level
        with patch.object(self.controller, 'achieve_goal_with_goap', side_effect=mock_achieve_goal_side_effect):
            success = self.controller.level_up_goal(target_level=3)
            self.assertTrue(success)
            
    def test_level_up_goal_without_client(self):
        """Test level_up_goal fails gracefully without client."""
        controller = AIPlayerController()  # No client
        result = controller.level_up_goal()
        self.assertFalse(result)
        
    def test_level_up_goal_without_character_state(self):
        """Test level_up_goal fails gracefully without character state."""
        controller = AIPlayerController(client=self.mock_client)
        result = controller.level_up_goal()
        self.assertFalse(result)
        
    def test_level_up_goal_state_creation(self):
        """Test that level_up_goal creates correct goal state."""
        def mock_achieve_goal_state_check(goal_state, config_file=None, max_iterations=3):
            # Simulate successful leveling by updating character state level
            if 'monsters_available' in goal_state:
                # This is a hunting cycle, update the character level to reach target
                target_level = 2  # From test parameter
                self.controller.character_state.data['level'] = target_level
                self.controller.character_state.data['xp'] = self.controller.character_state.data.get('max_xp', 150)
            return True
            
        with patch.object(self.controller, 'achieve_goal_with_goap', side_effect=mock_achieve_goal_state_check) as mock_achieve:
            result = self.controller.level_up_goal(target_level=2)
            
            # Verify the goal was successful
            self.assertTrue(result)
            # Verify achieve_goal_with_goap was called (at least once for hunting cycles)
            mock_achieve.assert_called()
            # Verify final character level reached target
            self.assertEqual(self.controller.character_state.data.get('level'), 2)
            
    def test_level_up_goal_with_config_file(self):
        """Test level_up_goal with custom config file."""
        # Create temporary config file
        config_data = """
actions:
  test_action:
    conditions:
      test_condition: true
    reactions:
      test_result: true
    weight: 1.0

goal_templates:
  level_up:
    strategy:
      hunt_radius: 25
      xp_target: 200
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            tmp_file.write(config_data)
            tmp_file.flush()
            
            try:
                def mock_achieve_goal_with_config(goal_state, config_file=None, max_iterations=3):
                    # Simulate successful leveling by updating character state level
                    if 'monsters_available' in goal_state:
                        # This is a hunting cycle, update the character level
                        new_level = self.controller.character_state.data.get('level', 1) + 1
                        self.controller.character_state.data['level'] = new_level
                        self.controller.character_state.data['xp'] = self.controller.character_state.data.get('max_xp', 150)
                    return True
                    
                with patch.object(self.controller, 'achieve_goal_with_goap', side_effect=mock_achieve_goal_with_config):
                    success = self.controller.level_up_goal(config_file=tmp_file.name)
                    self.assertTrue(success)
                    
            finally:
                os.unlink(tmp_file.name)
                
    def test_level_up_goal_progress_tracking(self):
        """Test that level_up_goal properly tracks and reports progress."""
        # Mock character state with different final values
        def mock_achieve_goal(goal_state, config_file=None, max_iterations=50):
            # Simulate gaining XP and level
            self.mock_character.data['xp'] = 150
            self.mock_character.data['level'] = 2
            self.mock_character.data['hp'] = 90
            return True
            
        with patch.object(self.controller, 'achieve_goal_with_goap', side_effect=mock_achieve_goal):
            success = self.controller.level_up_goal(target_level=2)
            self.assertTrue(success)
            
    def test_level_up_goal_world_state_reset(self):
        """Test that level_up_goal resets hunting status appropriately."""
        # Set up world state
        self.controller.world_state.data = {'has_hunted_monsters': True}
        
        with patch.object(self.controller, 'achieve_goal_with_goap', return_value=True):
            self.controller.level_up_goal()
            
            # Verify hunting status was reset
            self.assertFalse(self.controller.world_state.data.get('has_hunted_monsters', True))


if __name__ == '__main__':
    unittest.main()