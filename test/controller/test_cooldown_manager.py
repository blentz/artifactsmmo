"""Comprehensive unit tests for CooldownManager"""

import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from src.controller.cooldown_manager import CooldownManager


class TestCooldownManager(unittest.TestCase):
    """Test cases for CooldownManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary config file
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "test_config.yaml"
        
        # Create test configuration
        test_config = """
thresholds:
  max_cooldown_wait: 30
  character_refresh_cache_duration: 10.0
"""
        self.config_file.write_text(test_config)
        
        # Create manager with test config
        self.manager = CooldownManager(str(self.config_file))
        
        # Create mock character state
        self.mock_character_state = Mock()
        self.mock_character_state.data = {}
        
    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_initialization_with_config_file(self):
        """Test manager initialization with custom config file."""
        manager = CooldownManager(str(self.config_file))
        
        # Verify configuration was loaded
        self.assertEqual(manager.max_cooldown_wait, 30)
        self.assertEqual(manager.character_refresh_cache_duration, 10.0)
    
    @patch('src.controller.cooldown_manager.YamlData')
    def test_initialization_with_default_config(self, mock_yaml_data):
        """Test manager initialization with default config path."""
        mock_yaml_data.return_value.data = {}
        
        manager = CooldownManager()
        
        # Should use default config path
        expected_path = f"{self.manager.config_data.data.get('CONFIG_PREFIX', 'config')}/goal_templates.yaml"
        mock_yaml_data.assert_called_once()
    
    def test_load_configuration_success(self):
        """Test successful configuration loading."""
        # Configuration should be loaded in setUp
        self.assertEqual(self.manager.max_cooldown_wait, 30)
        self.assertEqual(self.manager.character_refresh_cache_duration, 10.0)
    
    def test_load_configuration_missing_thresholds(self):
        """Test configuration loading with missing thresholds."""
        # Create config without thresholds
        config_file = Path(self.temp_dir) / "minimal_config.yaml"
        config_file.write_text("other_config: value")
        
        manager = CooldownManager(str(config_file))
        
        # Should use defaults
        self.assertEqual(manager.max_cooldown_wait, 65)
        self.assertEqual(manager.character_refresh_cache_duration, 5.0)
    
    def test_load_configuration_exception(self):
        """Test configuration loading with exception during _load_configuration."""
        # Create a manager that will fail during _load_configuration
        with patch('src.controller.cooldown_manager.logging') as mock_logging:
            # Mock config_data.data.get to raise exception
            with patch.object(self.manager.config_data, 'data', new_callable=Mock) as mock_data:
                mock_data.get.side_effect = Exception("Config access failed")
                
                # Call _load_configuration directly to test exception handling
                self.manager._load_configuration()
                
                # Should use defaults after exception
                self.assertEqual(self.manager.max_cooldown_wait, 65)
                self.assertEqual(self.manager.character_refresh_cache_duration, 5.0)
    
    def test_is_character_on_cooldown_no_character_state(self):
        """Test cooldown check with no character state."""
        result = self.manager.is_character_on_cooldown(None)
        self.assertFalse(result)
    
    def test_is_character_on_cooldown_no_cooldown_data(self):
        """Test cooldown check with no cooldown data."""
        self.mock_character_state.data = {}
        
        result = self.manager.is_character_on_cooldown(self.mock_character_state)
        self.assertFalse(result)
    
    def test_is_character_on_cooldown_expiration_future(self):
        """Test cooldown check with future expiration time."""
        # Set expiration 10 seconds in the future
        future_time = datetime.now(timezone.utc) + timedelta(seconds=10)
        expiration_str = future_time.isoformat()
        
        self.mock_character_state.data = {'cooldown_expiration': expiration_str}
        
        result = self.manager.is_character_on_cooldown(self.mock_character_state)
        self.assertTrue(result)
    
    def test_is_character_on_cooldown_expiration_past(self):
        """Test cooldown check with past expiration time."""
        # Set expiration 10 seconds in the past
        past_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        expiration_str = past_time.isoformat()
        
        self.mock_character_state.data = {'cooldown_expiration': expiration_str}
        
        result = self.manager.is_character_on_cooldown(self.mock_character_state)
        self.assertFalse(result)
    
    def test_is_character_on_cooldown_expiration_near_zero(self):
        """Test cooldown check with expiration very near."""
        # Set expiration 0.5 seconds in future
        future_time = datetime.now(timezone.utc) + timedelta(seconds=0.5)
        expiration_str = future_time.isoformat()
        
        self.mock_character_state.data = {'cooldown_expiration': expiration_str}
        
        result = self.manager.is_character_on_cooldown(self.mock_character_state)
        self.assertTrue(result)  # Should be True because expiration is in the future
    
    def test_is_character_on_cooldown_exception_handling(self):
        """Test cooldown check with exception during processing."""
        # Set invalid expiration format
        self.mock_character_state.data = {'cooldown_expiration': 'invalid-format'}
        
        with patch('src.controller.cooldown_manager.logging') as mock_logging:
            result = self.manager.is_character_on_cooldown(self.mock_character_state)
            self.assertFalse(result)
    
    def test_calculate_wait_duration_no_character_state(self):
        """Test wait duration calculation with no character state."""
        result = self.manager.calculate_wait_duration(None)
        self.assertEqual(result, 0.0)
    
    def test_calculate_wait_duration_no_cooldown(self):
        """Test wait duration calculation with no cooldown data."""
        self.mock_character_state.data = {}
        
        result = self.manager.calculate_wait_duration(self.mock_character_state)
        self.assertEqual(result, 0.0)  # No cooldown data means no wait
    
    def test_calculate_wait_duration_future_expiration(self):
        """Test wait duration calculation with future expiration."""
        # Set expiration 5 seconds in the future
        future_time = datetime.now(timezone.utc) + timedelta(seconds=5)
        expiration_str = future_time.isoformat()
        
        self.mock_character_state.data = {'cooldown_expiration': expiration_str}
        
        result = self.manager.calculate_wait_duration(self.mock_character_state)
        # Should be close to 5.0, but allow for small timing differences
        self.assertGreater(result, 4.0)
        self.assertLess(result, 6.0)
    
    def test_calculate_wait_duration_past_expiration(self):
        """Test wait duration calculation with past expiration."""
        # Set expiration 5 seconds in the past
        past_time = datetime.now(timezone.utc) - timedelta(seconds=5)
        expiration_str = past_time.isoformat()
        
        self.mock_character_state.data = {'cooldown_expiration': expiration_str}
        
        result = self.manager.calculate_wait_duration(self.mock_character_state)
        self.assertEqual(result, 0.0)  # No wait needed
    
    def test_calculate_wait_duration_exceeds_max(self):
        """Test wait duration calculation when it exceeds maximum."""
        # Set expiration 60 seconds in the future (exceeds max of 30)
        future_time = datetime.now(timezone.utc) + timedelta(seconds=60)
        expiration_str = future_time.isoformat()
        
        self.mock_character_state.data = {'cooldown_expiration': expiration_str}
        
        result = self.manager.calculate_wait_duration(self.mock_character_state)
        self.assertEqual(result, 30.0)  # Should be capped at max_cooldown_wait
    
    def test_calculate_wait_duration_below_min(self):
        """Test wait duration calculation when it's very short."""
        # Set expiration 0.1 seconds in the future
        future_time = datetime.now(timezone.utc) + timedelta(seconds=0.1)
        expiration_str = future_time.isoformat()
        
        self.mock_character_state.data = {'cooldown_expiration': expiration_str}
        
        result = self.manager.calculate_wait_duration(self.mock_character_state)
        # Should return actual remaining time, not enforce minimum
        self.assertAlmostEqual(result, 0.1, places=1)
    
    def test_calculate_wait_duration_exception_handling(self):
        """Test wait duration calculation with exception."""
        # Set invalid expiration format
        self.mock_character_state.data = {
            'cooldown_expiration': 'invalid-format',
            'cooldown': 10
        }
        
        with patch('src.controller.cooldown_manager.logging') as mock_logging:
            result = self.manager.calculate_wait_duration(self.mock_character_state)
            # Should return 0.0 on error
            self.assertEqual(result, 0.0)
    
    def test_calculate_wait_duration_outer_exception(self):
        """Test wait duration calculation with outer exception."""
        # Make character_state.data raise an exception
        mock_state = Mock()
        mock_state.data = Mock(side_effect=Exception("Data access failed"))
        
        with patch('src.controller.cooldown_manager.logging') as mock_logging:
            result = self.manager.calculate_wait_duration(mock_state)
            self.assertEqual(result, 0.0)  # Should return 0.0 on error
    
    def test_should_refresh_character_state_initial(self):
        """Test should refresh character state on first call."""
        # Should return True initially
        result = self.manager.should_refresh_character_state()
        self.assertTrue(result)
    
    def test_should_refresh_character_state_after_mark(self):
        """Test should refresh character state after marking as refreshed."""
        # Mark as refreshed
        self.manager.mark_character_state_refreshed()
        
        # Should return False immediately after
        result = self.manager.should_refresh_character_state()
        self.assertFalse(result)
    
    def test_should_refresh_character_state_after_timeout(self):
        """Test should refresh character state after cache timeout."""
        # Mark as refreshed
        self.manager.mark_character_state_refreshed()
        
        # Mock time to simulate cache duration passed
        with patch('time.time') as mock_time:
            # Simulate 15 seconds passed (> 10 second cache duration)
            mock_time.return_value = self.manager._last_character_refresh + 15
            
            result = self.manager.should_refresh_character_state()
            self.assertTrue(result)
    
    def test_mark_character_state_refreshed(self):
        """Test marking character state as refreshed."""
        # Get initial time
        initial_time = self.manager._last_character_refresh
        
        # Sleep briefly to ensure time difference
        time.sleep(0.01)
        
        # Mark as refreshed
        self.manager.mark_character_state_refreshed()
        
        # Should have updated timestamp
        self.assertGreater(self.manager._last_character_refresh, initial_time)
    
    def test_handle_cooldown_with_wait_success(self):
        """Test successful cooldown handling with wait."""
        # Set up character state with cooldown
        future_time = datetime.now(timezone.utc) + timedelta(seconds=2)
        expiration_str = future_time.isoformat()
        self.mock_character_state.data = {'cooldown_expiration': expiration_str}
        
        # Mock action executor
        mock_action_executor = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_action_executor.execute_action.return_value = mock_result
        
        # Mock controller
        mock_controller = Mock()
        
        result = self.manager.handle_cooldown_with_wait(
            self.mock_character_state, mock_action_executor, mock_controller
        )
        
        self.assertTrue(result)
        mock_action_executor.execute_action.assert_called_once()
        
        # Verify call arguments
        call_args = mock_action_executor.execute_action.call_args
        self.assertEqual(call_args[0][0], 'wait')  # action name
        self.assertIn('wait_duration', call_args[0][1])  # action data
        self.assertIn('controller', call_args[0][3])  # context
    
    def test_handle_cooldown_with_wait_no_wait_needed(self):
        """Test cooldown handling when no wait is needed."""
        # Set up character state with expired cooldown
        past_time = datetime.now(timezone.utc) - timedelta(seconds=5)
        expiration_str = past_time.isoformat()
        self.mock_character_state.data = {'cooldown_expiration': expiration_str}
        
        mock_action_executor = Mock()
        
        result = self.manager.handle_cooldown_with_wait(
            self.mock_character_state, mock_action_executor
        )
        
        self.assertTrue(result)
        # Should not call action executor
        mock_action_executor.execute_action.assert_not_called()
    
    def test_handle_cooldown_with_wait_action_fails(self):
        """Test cooldown handling when wait action fails."""
        # Set up character state with cooldown
        future_time = datetime.now(timezone.utc) + timedelta(seconds=2)
        expiration_str = future_time.isoformat()
        self.mock_character_state.data = {'cooldown_expiration': expiration_str}
        
        # Mock action executor with failing result
        mock_action_executor = Mock()
        mock_result = Mock()
        mock_result.success = False
        mock_result.error_message = "Wait action failed"
        mock_action_executor.execute_action.return_value = mock_result
        
        result = self.manager.handle_cooldown_with_wait(
            self.mock_character_state, mock_action_executor
        )
        
        self.assertFalse(result)
    
    def test_handle_cooldown_with_wait_no_controller(self):
        """Test cooldown handling without controller reference."""
        # Set up character state with cooldown
        future_time = datetime.now(timezone.utc) + timedelta(seconds=1)
        expiration_str = future_time.isoformat()
        self.mock_character_state.data = {'cooldown_expiration': expiration_str}
        
        # Mock action executor
        mock_action_executor = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_action_executor.execute_action.return_value = mock_result
        
        result = self.manager.handle_cooldown_with_wait(
            self.mock_character_state, mock_action_executor
        )
        
        self.assertTrue(result)
        
        # Verify context doesn't include controller
        call_args = mock_action_executor.execute_action.call_args
        context = call_args[0][3]
        self.assertNotIn('controller', context)
    
    def test_handle_cooldown_with_wait_exception(self):
        """Test cooldown handling with exception during wait action."""
        # Set up character state with actual cooldown
        future_time = datetime.now(timezone.utc) + timedelta(seconds=5)
        expiration_str = future_time.isoformat()
        self.mock_character_state.data = {'cooldown_expiration': expiration_str}
        
        # Mock action executor that raises exception
        mock_action_executor = Mock()
        mock_action_executor.execute_action.side_effect = Exception("Action execution failed")
        
        with patch('src.controller.cooldown_manager.logging') as mock_logging:
            result = self.manager.handle_cooldown_with_wait(
                self.mock_character_state, mock_action_executor
            )
            
            self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()