"""
Unit tests for goal manager cooldown state calculation fix.

This test validates the fix for the bug where expired cooldowns were incorrectly 
detected as active due to stale legacy cooldown field values.
"""

import unittest
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

from src.controller.goal_manager import GOAPGoalManager


class TestGoalManagerCooldownFix(unittest.TestCase):
    """Test goal manager cooldown state calculation fixes."""
    
    def setUp(self):
        """Set up test environment with mocked configuration."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a mock configuration file to avoid loading from disk
        with patch('src.lib.yaml_data.YamlData') as mock_yaml_data:
            mock_yaml_data.return_value.data = {
                'goal_templates': {},
                'goal_selection_rules': {},
                'state_calculation_rules': {},
                'thresholds': {},
                'content_classification': {}
            }
            self.goal_manager = GOAPGoalManager()
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_expired_cooldown_with_legacy_field_returns_false(self):
        """Test that expired cooldowns return False even when legacy cooldown field is set."""
        # Set up character data with expired cooldown but legacy field still set
        past_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        char_data = {
            'cooldown': 24,  # Legacy field still shows cooldown seconds
            'cooldown_expiration': past_time.isoformat(),  # But expiration time is in the past
            'hp': 100,
            'max_hp': 100,
            'level': 1,
            'xp': 88,
            'max_xp': 150,
            'x': 0,
            'y': 0
        }
        
        # Create mock character state
        mock_character_state = Mock()
        mock_character_state.data = char_data
        
        # Calculate world state
        world_state = self.goal_manager.calculate_world_state(mock_character_state)
        
        # Should not be on cooldown since expiration time has passed
        self.assertFalse(world_state.get('is_on_cooldown', True), 
                        "Expired cooldown should return False even with legacy cooldown field set")
    
    def test_active_cooldown_with_future_expiration_returns_true(self):
        """Test that active cooldowns return True when expiration is in the future."""
        # Set up character data with future cooldown expiration
        future_time = datetime.now(timezone.utc) + timedelta(seconds=10)
        char_data = {
            'cooldown': 10,
            'cooldown_expiration': future_time.isoformat(),
            'hp': 100,
            'max_hp': 100,
            'level': 1,
            'xp': 88,
            'max_xp': 150,
            'x': 0,
            'y': 0
        }
        
        # Create mock character state
        mock_character_state = Mock()
        mock_character_state.data = char_data
        
        # Calculate world state
        world_state = self.goal_manager.calculate_world_state(mock_character_state)
        
        # Should be on cooldown since expiration time is in the future
        self.assertTrue(world_state.get('is_on_cooldown', False),
                       "Active cooldown should return True when expiration is in the future")
    
    def test_no_expiration_time_uses_legacy_field(self):
        """Test that legacy cooldown field is used when no expiration time is available."""
        # Set up character data with no expiration time
        char_data = {
            'cooldown': 5,  # Only legacy field available
            'cooldown_expiration': None,
            'hp': 100,
            'max_hp': 100,
            'level': 1,
            'xp': 88,
            'max_xp': 150,
            'x': 0,
            'y': 0
        }
        
        # Create mock character state
        mock_character_state = Mock()
        mock_character_state.data = char_data
        
        # Calculate world state
        world_state = self.goal_manager.calculate_world_state(mock_character_state)
        
        # Should be on cooldown based on legacy field
        self.assertTrue(world_state.get('is_on_cooldown', False),
                       "Should use legacy cooldown field when no expiration time available")
    
    def test_no_cooldown_data_returns_false(self):
        """Test that no cooldown data returns False."""
        # Set up character data with no cooldown information
        char_data = {
            'cooldown': 0,
            'cooldown_expiration': None,
            'hp': 100,
            'max_hp': 100,
            'level': 1,
            'xp': 88,
            'max_xp': 150,
            'x': 0,
            'y': 0
        }
        
        # Create mock character state
        mock_character_state = Mock()
        mock_character_state.data = char_data
        
        # Calculate world state
        world_state = self.goal_manager.calculate_world_state(mock_character_state)
        
        # Should not be on cooldown
        self.assertFalse(world_state.get('is_on_cooldown', True),
                        "No cooldown data should return False")
    
    def test_direct_cooldown_check_method(self):
        """Test the _check_cooldown_status method directly."""
        # Test case 1: Expired cooldown with legacy field
        past_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        char_data_expired = {
            'cooldown': 24,
            'cooldown_expiration': past_time.isoformat()
        }
        self.assertFalse(self.goal_manager._check_cooldown_status(char_data_expired),
                        "Expired cooldown should return False")
        
        # Test case 2: Active cooldown
        future_time = datetime.now(timezone.utc) + timedelta(seconds=10)
        char_data_active = {
            'cooldown': 10,
            'cooldown_expiration': future_time.isoformat()
        }
        self.assertTrue(self.goal_manager._check_cooldown_status(char_data_active),
                       "Active cooldown should return True")
        
        # Test case 3: No expiration time, use legacy
        char_data_legacy = {
            'cooldown': 5,
            'cooldown_expiration': None
        }
        self.assertTrue(self.goal_manager._check_cooldown_status(char_data_legacy),
                       "Legacy cooldown should be used when no expiration available")
        
        # Test case 4: No cooldown
        char_data_none = {
            'cooldown': 0,
            'cooldown_expiration': None
        }
        self.assertFalse(self.goal_manager._check_cooldown_status(char_data_none),
                        "No cooldown should return False")
    
    def test_ai_player_controller_cooldown_check(self):
        """Test the AI player controller's _is_character_on_cooldown method."""
        from src.controller.ai_player_controller import AIPlayerController
        from unittest.mock import Mock
        
        # Create controller with mocked dependencies
        with patch('src.controller.ai_player_controller.StateManagerMixin.initialize_state_management'):
            with patch('src.controller.ai_player_controller.StateManagerMixin.create_managed_state'):
                controller = AIPlayerController(client=Mock())
        
        # Test case 1: Expired cooldown with legacy field
        past_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        mock_character_state = Mock()
        mock_character_state.data = {
            'cooldown': 24,
            'cooldown_expiration': past_time.isoformat()
        }
        controller.character_state = mock_character_state
        
        self.assertFalse(controller._is_character_on_cooldown(),
                        "AI controller: Expired cooldown should return False")
        
        # Test case 2: Active cooldown
        future_time = datetime.now(timezone.utc) + timedelta(seconds=10)
        mock_character_state.data = {
            'cooldown': 10,
            'cooldown_expiration': future_time.isoformat()
        }
        
        self.assertTrue(controller._is_character_on_cooldown(),
                       "AI controller: Active cooldown should return True")
        
        # Test case 3: No expiration time, use legacy
        mock_character_state.data = {
            'cooldown': 5,
            'cooldown_expiration': None
        }
        
        self.assertTrue(controller._is_character_on_cooldown(),
                       "AI controller: Legacy cooldown should be used when no expiration available")
        
        # Test case 4: No cooldown
        mock_character_state.data = {
            'cooldown': 0,
            'cooldown_expiration': None
        }
        
        self.assertFalse(controller._is_character_on_cooldown(),
                        "AI controller: No cooldown should return False")


if __name__ == '__main__':
    unittest.main()