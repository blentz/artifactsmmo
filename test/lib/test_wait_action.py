""" Tests for WaitAction class """

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from src.controller.actions.wait import WaitAction

from test.base_test import BaseTest
from test.fixtures import MockActionContext, create_mock_client


class TestWaitAction(BaseTest):
    """ Test cases for WaitAction """

    def setUp(self):
        """ Set up test fixtures """
        self.wait_action = WaitAction()
        self.mock_client = create_mock_client()
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up mock objects
        self.wait_action = None
        self.mock_client = None
        
        # Clear any patches that might be active
        patch.stopall()

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
        context = MockActionContext(wait_duration=1.0)
        result = self.wait_action.execute(self.mock_client, context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.get('success', False))
        self.assertIn('Waited 0.1 seconds', result.get('message', ''))
        mock_sleep.assert_called_once_with(0.1)  # Default character has no cooldown, so min wait

    @patch('time.sleep')
    def test_execute_with_character_state_no_cooldown(self, mock_sleep):
        """ Test execute with character state but no active cooldown """
        mock_character_state = Mock()
        mock_character_state.data = {
            'cooldown': 0,
            'cooldown_expiration': None
        }
        
        context = MockActionContext(character_state=mock_character_state)
        result = self.wait_action.execute(self.mock_client, context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.get('success', False))
        mock_sleep.assert_called_once_with(0.1)  # Minimum wait

    @patch('time.sleep')
    @patch('src.controller.actions.wait.datetime')
    def test_execute_with_active_cooldown(self, mock_datetime, mock_sleep):
        """ Test execute with active cooldown """
        # Set up current time and cooldown expiration
        current_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        cooldown_end = current_time + timedelta(seconds=5.5)
        
        mock_datetime.now.return_value = current_time
        mock_datetime.fromisoformat.return_value = cooldown_end
        
        mock_character_state = Mock()
        mock_character_state.data = {
            'cooldown': 6,
            'cooldown_expiration': cooldown_end.isoformat()
        }
        
        context = MockActionContext(character_state=mock_character_state)
        result = self.wait_action.execute(self.mock_client, context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.get('success', False))
        self.assertIn('Waited 5.5 seconds', result.get('message', ''))
        mock_sleep.assert_called_once_with(5.5)

    @patch('time.sleep')
    @patch('src.controller.actions.wait.datetime')
    def test_execute_with_expired_cooldown(self, mock_datetime, mock_sleep):
        """ Test execute with expired cooldown """
        # Set up current time after cooldown expiration
        current_time = datetime(2023, 1, 1, 12, 0, 10, tzinfo=timezone.utc)
        cooldown_end = current_time - timedelta(seconds=5)  # Expired 5 seconds ago
        
        mock_datetime.now.return_value = current_time
        mock_datetime.fromisoformat.return_value = cooldown_end
        
        mock_character_state = Mock()
        mock_character_state.data = {
            'cooldown': 6,
            'cooldown_expiration': cooldown_end.isoformat()
        }
        
        context = MockActionContext(character_state=mock_character_state)
        result = self.wait_action.execute(self.mock_client, context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.get('success', False))
        mock_sleep.assert_not_called()  # No sleep for expired cooldown

    @patch('time.sleep')
    def test_execute_with_cooldown_seconds_only(self, mock_sleep):
        """ Test execute with cooldown seconds but no expiration time """
        mock_character_state = Mock()
        mock_character_state.data = {
            'cooldown': 3,
            'cooldown_expiration': None
        }
        
        context = MockActionContext(character_state=mock_character_state)
        result = self.wait_action.execute(self.mock_client, context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.get('success', False))
        mock_sleep.assert_called_once_with(3.0)

    @patch('time.sleep')
    def test_execute_with_large_cooldown_clamped(self, mock_sleep):
        """ Test execute with large cooldown gets clamped to maximum """
        mock_character_state = Mock()
        mock_character_state.data = {
            'cooldown': 120,  # 2 minutes
            'cooldown_expiration': None
        }
        
        context = MockActionContext(character_state=mock_character_state)
        result = self.wait_action.execute(self.mock_client, context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.get('success', False))
        mock_sleep.assert_called_once_with(60.0)  # Clamped to 60 seconds max

    @patch('time.sleep')
    @patch('src.controller.actions.wait.datetime')
    def test_execute_with_string_cooldown_expiration(self, mock_datetime, mock_sleep):
        """ Test execute with string cooldown expiration """
        current_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        cooldown_end = current_time + timedelta(seconds=2.5)
        
        mock_datetime.now.return_value = current_time
        mock_datetime.fromisoformat.return_value = cooldown_end
        
        mock_character_state = Mock()
        mock_character_state.data = {
            'cooldown': 3,
            'cooldown_expiration': '2023-01-01T12:00:02.500000+00:00'
        }
        
        context = MockActionContext(character_state=mock_character_state)
        result = self.wait_action.execute(self.mock_client, context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.get('success', False))
        mock_sleep.assert_called_once_with(2.5)

    @patch('time.sleep')
    def test_execute_with_parse_error_fallback(self, mock_sleep):
        """ Test execute falls back to cooldown seconds when parsing fails """
        mock_character_state = Mock()
        mock_character_state.data = {
            'cooldown': 4,
            'cooldown_expiration': 'invalid-date-format'
        }
        
        context = MockActionContext(character_state=mock_character_state)
        result = self.wait_action.execute(self.mock_client, context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.get('success', False))
        mock_sleep.assert_called_once_with(4.0)

    @patch('time.sleep')
    def test_execute_exception_handling(self, mock_sleep):
        """ Test execute handles exceptions gracefully """
        mock_sleep.side_effect = Exception("Sleep interrupted")
        
        context = MockActionContext(wait_duration=1.0)
        result = self.wait_action.execute(self.mock_client, context)
        
        self.assertIsNotNone(result)
        self.assertFalse(result.get('success', True))
        self.assertIn('Wait failed', result.get('error', ''))

    def test_repr(self):
        """ Test string representation """
        action = WaitAction()
        self.assertEqual(str(action), "WaitAction()")


if __name__ == '__main__':
    unittest.main()