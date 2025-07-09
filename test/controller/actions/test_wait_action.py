""" Tests for WaitAction class """

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.wait import WaitAction
from test.test_base import UnifiedContextTestBase


class TestWaitAction(UnifiedContextTestBase):
    """ Test cases for WaitAction """

    def setUp(self):
        """ Set up test fixtures """
        super().setUp()
        self.wait_action = WaitAction()
        self.mock_client = Mock()
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up mock objects
        self.wait_action = None
        self.mock_client = None
        
        # Clear any patches that might be active
        patch.stopall()
        
        # Base class handles context cleanup
        super().tearDown()

    def test_init(self):
        """ Test WaitAction initialization """
        action = WaitAction()
        self.assertEqual(action.conditions['character_status']['cooldown_active'], True)
        self.assertEqual(action.reactions['character_status']['cooldown_active'], False)
        self.assertEqual(action.weight, 1)

    def test_init_no_params(self):
        """ Test WaitAction initialization with no parameters """
        action = WaitAction()
        # No wait_duration attribute since it uses ActionContext now
        self.assertIsInstance(action, WaitAction)

    @patch('time.sleep')
    def test_execute_default_wait(self, mock_sleep):
        """ Test execute with default wait duration """
        self.context.wait_duration = 1.0
        result = self.wait_action.execute(self.mock_client, self.context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertIn('Waited 1.0 seconds', result.message)
        mock_sleep.assert_called_once_with(1.0)  # Uses provided wait_duration

    @patch('time.sleep')
    def test_execute_with_character_state_no_cooldown(self, mock_sleep):
        """ Test execute with character state but no active cooldown """
        mock_character_state = Mock()
        mock_character_state.data = {
            'cooldown': 0,
            'cooldown_expiration': None
        }
        
        # With default wait_duration (not setting wait_duration to test default)
        self.context.character_state = mock_character_state
        # Don't set wait_duration to test the default behavior
        result = self.wait_action.execute(self.mock_client, self.context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        mock_sleep.assert_called_once_with(1.0)  # Uses default wait_duration

    @patch('time.sleep')
    def test_execute_with_active_cooldown(self, mock_sleep):
        """ Test execute with GOAP-provided wait duration """
        mock_character_state = Mock()
        mock_character_state.data = {
            'cooldown': 6,
            'cooldown_expiration': '2023-01-01T12:00:06+00:00'
        }
        
        # GOAP provides the calculated wait duration
        self.context.character_state = mock_character_state
        self.context.wait_duration = 5.5
        result = self.wait_action.execute(self.mock_client, self.context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertIn('Waited 5.5 seconds', result.message)
        mock_sleep.assert_called_once_with(5.5)

    @patch('time.sleep')
    def test_execute_with_expired_cooldown(self, mock_sleep):
        """ Test execute with zero wait duration (cooldown already expired) """
        mock_character_state = Mock()
        mock_character_state.data = {
            'cooldown': 0,
            'cooldown_expiration': None
        }
        
        # GOAP would provide 0.1 for expired/no cooldown (minimum wait)
        self.context.character_state = mock_character_state
        self.context.wait_duration = 0.1
        result = self.wait_action.execute(self.mock_client, self.context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        mock_sleep.assert_called_once_with(0.1)  # Minimum wait

    @patch('time.sleep')
    def test_execute_with_cooldown_seconds_only(self, mock_sleep):
        """ Test execute with GOAP-provided wait duration """
        mock_character_state = Mock()
        mock_character_state.data = {
            'cooldown': 3,
            'cooldown_expiration': None
        }
        
        # GOAP provides wait duration
        self.context.character_state = mock_character_state
        self.context.wait_duration = 3.0
        result = self.wait_action.execute(self.mock_client, self.context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        mock_sleep.assert_called_once_with(3.0)

    @patch('time.sleep')
    def test_execute_with_large_cooldown_clamped(self, mock_sleep):
        """ Test execute with large cooldown gets clamped to maximum """
        mock_character_state = Mock()
        mock_character_state.data = {
            'cooldown': 120,  # 2 minutes
            'cooldown_expiration': None
        }
        
        # GOAP would already clamp this, but wait action also clamps for safety
        self.context.character_state = mock_character_state
        self.context.wait_duration = 120.0
        result = self.wait_action.execute(self.mock_client, self.context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        mock_sleep.assert_called_once_with(60.0)  # Clamped to 60 seconds max

    @patch('time.sleep')
    def test_execute_with_string_cooldown_expiration(self, mock_sleep):
        """ Test execute with GOAP-calculated wait duration from string expiration """
        mock_character_state = Mock()
        mock_character_state.data = {
            'cooldown': 3,
            'cooldown_expiration': '2023-01-01T12:00:02.500000+00:00'
        }
        
        # GOAP calculates and provides the wait duration
        self.context.character_state = mock_character_state
        self.context.wait_duration = 2.5
        result = self.wait_action.execute(self.mock_client, self.context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        mock_sleep.assert_called_once_with(2.5)

    @patch('time.sleep')
    def test_execute_with_parse_error_fallback(self, mock_sleep):
        """ Test execute with GOAP fallback duration when parsing fails """
        mock_character_state = Mock()
        mock_character_state.data = {
            'cooldown': 4,
            'cooldown_expiration': 'invalid-date-format'
        }
        
        # GOAP would handle parse errors and provide a fallback duration
        self.context.character_state = mock_character_state
        self.context.wait_duration = 4.0
        result = self.wait_action.execute(self.mock_client, self.context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        mock_sleep.assert_called_once_with(4.0)

    @patch('time.sleep')
    def test_execute_exception_handling(self, mock_sleep):
        """ Test execute handles exceptions gracefully """
        mock_sleep.side_effect = Exception("Sleep interrupted")
        
        self.context.wait_duration = 1.0
        result = self.wait_action.execute(self.mock_client, self.context)
        
        self.assertIsNotNone(result)
        self.assertFalse(result.success)
        self.assertIn('Wait failed', result.error)

    def test_execute_without_context(self):
        """ Test execute without context (uses default) """
        self.context.wait_duration = 1.0
        result = self.wait_action.execute(self.mock_client, self.context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.success)

    def test_repr(self):
        """ Test string representation """
        action = WaitAction()
        self.assertEqual(str(action), "WaitAction()")


if __name__ == '__main__':
    unittest.main()