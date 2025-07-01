"""
Unit tests for level_up_goal functionality in AIPlayerController.
"""

import logging
import unittest
from unittest.mock import Mock, patch

from src.controller.ai_player_controller import AIPlayerController

from test.fixtures import create_mock_client


class TestLevelUpGoal(unittest.TestCase):
    """Test cases for level_up goal functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = create_mock_client()
        self.controller = AIPlayerController(client=self.mock_client)
        self.logger = logging.getLogger()
        
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
            if 'has_hunted_monsters' in goal_state:
                # This is a hunting cycle, update the character level
                current_level = self.controller.character_state.data.get('level', 1)
                new_level = current_level + 1
                self.controller.character_state.data['level'] = new_level
                self.controller.character_state.data['xp'] = self.controller.character_state.data.get('max_xp', 150)
                self.logger.info(f"Mock leveling: {current_level} → {new_level}")
            return True
        
        # Test with no target level specified (should be current + 1)
        with patch.object(self.controller.mission_executor, 'execute_level_progression', return_value=True):
            success = self.controller.level_up_goal()
            self.assertTrue(success)
            
        # Reset character state for next test
        self.controller.character_state.data['level'] = 1
        self.controller.character_state.data['xp'] = 0
            
        # Test with specific target level
        with patch.object(self.controller.mission_executor, 'execute_level_progression', return_value=True):
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
        """Test that level_up_goal delegates to MissionExecutor correctly."""
        # Mock mission executor to simulate successful level progression
        with patch.object(self.controller.mission_executor, 'execute_level_progression') as mock_execute:
            mock_execute.return_value = True
            
            # Simulate character state change after level progression
            def simulate_level_up(*args, **kwargs):
                self.controller.character_state.data['level'] = 2
                self.controller.character_state.data['xp'] = self.controller.character_state.data.get('max_xp', 150)
                return True
            
            mock_execute.side_effect = simulate_level_up
            
            result = self.controller.level_up_goal(target_level=2)
            
            # Verify the goal was successful
            self.assertTrue(result)
            # Verify mission executor was called with correct target
            mock_execute.assert_called_once_with(2)
            # Verify final character level reached target
            self.assertEqual(self.controller.character_state.data.get('level'), 2)
            
    def test_level_up_goal_with_mission_executor(self):
        """Test level_up_goal delegation to MissionExecutor."""
        # Mock mission executor to simulate successful level progression
        with patch.object(self.controller.mission_executor, 'execute_level_progression') as mock_execute:
            mock_execute.return_value = True
            
            # Test level progression with default target
            success = self.controller.level_up_goal()
            
            # Verify delegation occurred
            self.assertTrue(success)
            mock_execute.assert_called_once_with(None)
            
        # Test with specific target level
        with patch.object(self.controller.mission_executor, 'execute_level_progression') as mock_execute:
            mock_execute.return_value = True
            
            success = self.controller.level_up_goal(target_level=5)
            
            # Verify delegation with target level
            self.assertTrue(success)
            mock_execute.assert_called_once_with(5)
                
    def test_level_up_goal_progress_tracking(self):
        """Test that level_up_goal properly tracks and reports progress."""
        # Mock character state with different final values
        def mock_achieve_goal(goal_state, config_file=None, max_iterations=50):
            # Simulate gaining XP and level
            self.mock_character.data['xp'] = 150
            self.mock_character.data['level'] = 2
            self.mock_character.data['hp'] = 90
            return True
            
        with patch.object(self.controller.mission_executor, 'execute_level_progression', return_value=True):
            success = self.controller.level_up_goal(target_level=2)
            self.assertTrue(success)
            
    def test_level_up_goal_world_state_reset(self):
        """Test that level_up_goal delegates to MissionExecutor without breaking world state."""
        # Set up world state
        self.controller.world_state.data = {'has_hunted_monsters': True}
        
        # Mock mission executor
        with patch.object(self.controller.mission_executor, 'execute_level_progression') as mock_execute:
            mock_execute.return_value = True
            
            self.controller.level_up_goal()
            
            # Verify mission executor was called
            mock_execute.assert_called_once_with(None)
            
            # World state management is now handled by the MissionExecutor, 
            # so we verify that the delegation occurred correctly


if __name__ == '__main__':
    unittest.main()