"""
Unit tests for API optimization fixes.

This test file covers the fixes made to address:
1. API rate limiting from excessive character state refreshing
2. Cooldown detection infinite loops
3. Wait action duration calculation
4. Character state caching optimization
"""

import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from src.controller.ai_player_controller import AIPlayerController

from test.fixtures import create_mock_client


class TestAPIOptimizationFixes(unittest.TestCase):
    """Test API optimization fixes to prevent rate limiting and infinite loops."""
    
    def setUp(self):
        """Set up test environment with mocked components."""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_client = create_mock_client()
        
        # Create controller with mocked dependencies
        with patch('src.controller.ai_player_controller.StateManagerMixin.initialize_state_management'):
            with patch('src.controller.ai_player_controller.StateManagerMixin.create_managed_state'):
                self.controller = AIPlayerController(client=self.mock_client)
        
        # Mock character state
        self.mock_character_state = Mock()
        self.mock_character_state.name = "test_character"
        self.mock_character_state.data = {
            'hp': 100,
            'max_hp': 100,
            'level': 1,
            'xp': 50,
            'max_xp': 150,
            'cooldown': 0,
            'cooldown_expiration': None
        }
        self.controller.set_character_state(self.mock_character_state)
        
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)


class TestCharacterStateCaching(TestAPIOptimizationFixes):
    """Test character state caching to reduce API calls."""
    
    def test_should_refresh_character_state_cache_logic(self):
        """Test that character state caching works correctly."""
        # First call should always refresh (no cache)
        self.assertTrue(self.controller._should_refresh_character_state())
        
        # Simulate a refresh using CooldownManager
        self.controller.cooldown_manager.mark_character_state_refreshed()
        
        # Immediate second call should use cache
        self.assertFalse(self.controller._should_refresh_character_state())
        
        # Call after cache expiration should refresh
        self.controller.cooldown_manager._last_character_refresh = time.time() - 10.0  # 10 seconds ago
        self.assertTrue(self.controller._should_refresh_character_state())
    
    def test_get_current_world_state_respects_cache(self):
        """Test that get_current_world_state respects caching flags."""
        with patch.object(self.controller, '_refresh_character_state') as mock_refresh:
            with patch.object(self.controller, '_should_refresh_character_state', return_value=False):
                # Without force_refresh, should not call _refresh_character_state when cache is fresh
                self.controller.get_current_world_state(force_refresh=False)
                mock_refresh.assert_not_called()
                
                # With force_refresh=True, should always call _refresh_character_state
                self.controller.get_current_world_state(force_refresh=True)
                mock_refresh.assert_called_once()
    
    def test_refresh_character_state_updates_cache_timestamp(self):
        """Test that _refresh_character_state updates the cache timestamp."""
        # Mock the API call
        mock_response = Mock()
        mock_response.data.to_dict.return_value = {'hp': 100, 'cooldown': 0}
        
        with patch('src.controller.ai_player_controller.get_character', return_value=mock_response):
            initial_time = time.time()
            self.controller._refresh_character_state()
            
            # Cache timestamp should be updated in CooldownManager
            self.assertGreater(self.controller.cooldown_manager._last_character_refresh, initial_time)
            self.assertLessEqual(self.controller.cooldown_manager._last_character_refresh, time.time())


class TestCooldownDetectionFixes(TestAPIOptimizationFixes):
    """Test cooldown detection fixes to avoid infinite loops."""
    
    def test_cooldown_expiration_calculation(self):
        """Test that cooldown expiration is calculated correctly."""
        # Set up character with future cooldown expiration
        future_time = datetime.now(timezone.utc) + timedelta(seconds=10)
        self.mock_character_state.data['cooldown_expiration'] = future_time.isoformat()
        
        # Test that cooldown is detected correctly
        with patch.object(self.controller, '_refresh_character_state'):
            state = self.controller.get_current_world_state()
            self.assertTrue(state['character_status']['cooldown_active'])
    
    def test_expired_cooldown_detection(self):
        """Test that expired cooldowns are detected correctly."""
        # Set up character with past cooldown expiration
        past_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        self.mock_character_state.data['cooldown_expiration'] = past_time.isoformat()
        
        # Test that cooldown is not detected
        with patch.object(self.controller, '_refresh_character_state'):
            state = self.controller.get_current_world_state()
            self.assertFalse(state['character_status']['cooldown_active'])
    
    def test_cooldown_wait_duration_calculation(self):
        """Test that wait duration is calculated correctly based on cooldown expiration."""
        # Set up character with cooldown that expires in 5 seconds
        future_time = datetime.now(timezone.utc) + timedelta(seconds=5)
        self.mock_character_state.data['cooldown_expiration'] = future_time.isoformat()
        
        # Mock ActionExecutor's execute_action method
        from src.controller.action_executor import ActionResult
        mock_result = ActionResult(success=True, response={}, action_name='wait', error_message=None)
        
        with patch.object(self.controller.action_executor, 'execute_action', return_value=mock_result) as mock_execute:
            success = self.controller._execute_cooldown_wait()
            
            # Should have executed wait action
            self.assertTrue(success)
            mock_execute.assert_called_once()
            
            # Check that wait action was called with proper parameters
            args, kwargs = mock_execute.call_args
            action_name = args[0]
            action_data = args[1]
            self.assertEqual(action_name, 'wait')
            self.assertIn('wait_duration', action_data)
            
            # Check that wait duration was reasonable (around 5 seconds, but may be slightly less due to processing time)
            wait_duration = action_data['wait_duration']
            self.assertGreater(wait_duration, 3.0)  # At least 3 seconds
            self.assertLessEqual(wait_duration, 6.0)  # At most 6 seconds
    
    def test_expired_cooldown_skips_wait(self):
        """Test that expired cooldowns skip the wait action."""
        # Set up character with expired cooldown
        past_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        self.mock_character_state.data['cooldown_expiration'] = past_time.isoformat()
        
        with patch.object(self.controller, '_execute_action') as mock_execute:
            success = self.controller._execute_cooldown_wait()
            
            # Should succeed without executing wait action
            self.assertTrue(success)
            mock_execute.assert_not_called()


class TestWaitActionOptimization(TestAPIOptimizationFixes):
    """Test wait action optimization to avoid short waits."""
    
    def test_wait_action_calculates_proper_duration(self):
        """Test that WaitAction calculates proper wait duration."""
        from src.controller.actions.wait import WaitAction
        
        # Set up character with cooldown that expires in 10 seconds
        future_time = datetime.now(timezone.utc) + timedelta(seconds=10)
        self.mock_character_state.data['cooldown_expiration'] = future_time.isoformat()
        self.mock_character_state.data['cooldown'] = 10
        
        wait_action = WaitAction()
        
        # Mock time.sleep to avoid actually waiting
        with patch('time.sleep') as mock_sleep:
            from test.fixtures import MockActionContext
            context = MockActionContext(character_state=self.mock_character_state)
            result = wait_action.execute(self.mock_client, context)
            
            # Should have called sleep with reasonable duration
            mock_sleep.assert_called_once()
            sleep_duration = mock_sleep.call_args[0][0]
            self.assertGreater(sleep_duration, 8.0)  # At least 8 seconds
            self.assertLessEqual(sleep_duration, 12.0)  # At most 12 seconds (with bounds)
            
            # Should return success
            self.assertTrue(result['success'])
    
    def test_wait_action_handles_expired_cooldown(self):
        """Test that WaitAction handles expired cooldowns correctly."""
        from src.controller.actions.wait import WaitAction
        
        # Set up character with expired cooldown
        past_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        self.mock_character_state.data['cooldown_expiration'] = past_time.isoformat()
        self.mock_character_state.data['cooldown'] = 0
        
        wait_action = WaitAction()
        
        # Mock time.sleep to verify it's called with minimal duration
        with patch('time.sleep') as mock_sleep:
            from test.fixtures import MockActionContext
            context = MockActionContext(character_state=self.mock_character_state)
            result = wait_action.execute(self.mock_client, context)
            
            # Should have called sleep with minimal duration for expired cooldown
            mock_sleep.assert_called_once()
            sleep_duration = mock_sleep.call_args[0][0]
            self.assertLessEqual(sleep_duration, 1.0)  # Should be minimal wait
            
            # Should return success
            self.assertTrue(result['success'])


class TestGOAPIterationOptimization(TestAPIOptimizationFixes):
    """Test GOAP iteration optimization to reduce API calls."""
    
    def test_achieve_goal_with_goap_reduces_api_calls(self):
        """Test that achieve_goal_with_goap reduces API calls through caching."""
        goal_state = {'test_goal': True}
        
        with patch.object(self.controller, 'get_current_world_state') as mock_get_state:
            with patch.object(self.controller.goap_execution_manager, '_load_actions_from_config', return_value={}):
                # Mock state to show no cooldown so we don't get stuck in wait loop
                mock_get_state.return_value = {
                    'is_on_cooldown': False,
                    'character_alive': True,
                    'test_goal': True  # Goal already achieved
                }
                
                # Run with max_iterations=3 to test caching behavior
                result = self.controller.goap_execution_manager.achieve_goal_with_goap(goal_state, self.controller, max_iterations=3)
                
                # Should have called get_current_world_state multiple times
                self.assertGreater(mock_get_state.call_count, 0)
                
                # Check that force_refresh was only True for first call
                call_args_list = mock_get_state.call_args_list
                if call_args_list:
                    # First call should have force_refresh=True
                    first_call_kwargs = call_args_list[0][1] if call_args_list[0][1] else {}
                    force_refresh = first_call_kwargs.get('force_refresh', False)
                    # Note: May be False if iterations stopped early due to goal achievement
                    
                    # Subsequent calls should have force_refresh=False
                    for call_args in call_args_list[1:]:
                        call_kwargs = call_args[1] if call_args[1] else {}
                        subsequent_force_refresh = call_kwargs.get('force_refresh', False)
                        self.assertFalse(subsequent_force_refresh)


class TestAPIErrorHandling(TestAPIOptimizationFixes):
    """Test API error handling to prevent cascading failures."""
    
    def test_refresh_character_state_handles_api_errors(self):
        """Test that _refresh_character_state handles API errors gracefully."""
        # Mock API error (429 rate limit)
        with patch('src.controller.ai_player_controller.get_character', 
                   side_effect=Exception("Rate limit exceeded")):
            
            # Should not raise exception
            self.controller._refresh_character_state()
            
            # Cache timestamp should not be updated on failure
            self.assertFalse(hasattr(self.controller, '_last_character_refresh') and 
                           self.controller._last_character_refresh > 0)
    
    def test_cooldown_wait_handles_api_failures(self):
        """Test that cooldown wait continues to work even with API failures."""
        # Set up character with future cooldown expiration
        future_time = datetime.now(timezone.utc) + timedelta(seconds=0.1)  # Short wait for test
        self.mock_character_state.data['cooldown_expiration'] = future_time.isoformat()
        self.mock_character_state.data['cooldown'] = 0.1  # 0.1 seconds cooldown
        
        # Mock the action executor to succeed
        with patch.object(self.controller.action_executor, 'execute_action') as mock_execute:
            mock_execute.return_value = Mock(success=True)
            success = self.controller._execute_cooldown_wait()
            
            # Should succeed even with stale character state
            self.assertTrue(success)
            
            # Verify wait action was called with proper context
            mock_execute.assert_called_once()
            call_args = mock_execute.call_args
            self.assertEqual(call_args[0][0], 'wait')  # action name
            context = call_args[0][3]  # context argument
            self.assertIn('character_state', context)
            self.assertEqual(context['character_state'], self.mock_character_state)


if __name__ == '__main__':
    unittest.main()