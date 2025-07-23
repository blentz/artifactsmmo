""" Tests for WaitAction class """

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.wait import WaitAction
from src.lib.state_parameters import StateParameters
from test.test_base import UnifiedContextTestBase


class TestWaitAction(UnifiedContextTestBase):
    """ Test cases for WaitAction """

    def setUp(self):
        """ Set up test fixtures """
        super().setUp()
        self.wait_action = WaitAction()
        self.mock_client = Mock()
        
        # Set up character name in context for API calls
        self.context.set(StateParameters.CHARACTER_NAME, "test_character")
    
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
        self.assertEqual(action.conditions['character_status.cooldown_active'], True)
        self.assertEqual(action.reactions['character_status.cooldown_active'], False)
        self.assertEqual(action.weight, 0.1)

    def test_init_no_params(self):
        """ Test WaitAction initialization with no parameters """
        action = WaitAction()
        # No wait_duration attribute since it uses ActionContext now
        self.assertIsInstance(action, WaitAction)

    @patch('src.controller.actions.wait.get_character_api')
    @patch('time.sleep')
    def test_execute_default_wait(self, mock_sleep, mock_get_character):
        """ Test execute gets cooldown from API """
        # Mock API response with cooldown
        mock_response = Mock()
        mock_response.data.cooldown = 3
        mock_get_character.return_value = mock_response
        
        result = self.wait_action.execute(self.mock_client, self.context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertIn('Waited 3.0 seconds', result.message)
        mock_sleep.assert_called_once_with(3.0)
        mock_get_character.assert_called_once_with(name="test_character", client=self.mock_client)

    @patch('src.controller.actions.wait.get_character_api')
    @patch('time.sleep')
    def test_execute_with_zero_cooldown_clamped_to_minimum(self, mock_sleep, mock_get_character):
        """ Test execute with zero cooldown gets clamped to minimum """
        # Mock API response with zero cooldown
        mock_response = Mock()
        mock_response.data.cooldown = 0
        mock_get_character.return_value = mock_response
        
        result = self.wait_action.execute(self.mock_client, self.context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertIn('Waited 0.1 seconds', result.message)  # Clamped to minimum
        mock_sleep.assert_called_once_with(0.1)  # Clamped to minimum 0.1

    @patch('src.controller.actions.wait.get_character_api')
    @patch('time.sleep')
    def test_execute_with_active_cooldown(self, mock_sleep, mock_get_character):
        """ Test execute with specific cooldown from API """
        # Mock API response with specific cooldown
        mock_response = Mock()
        mock_response.data.cooldown = 6
        mock_get_character.return_value = mock_response
        
        result = self.wait_action.execute(self.mock_client, self.context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertIn('Waited 6.0 seconds', result.message)
        mock_sleep.assert_called_once_with(6.0)

    @patch('src.controller.actions.wait.get_character_api')
    @patch('time.sleep')
    def test_execute_with_expired_cooldown(self, mock_sleep, mock_get_character):
        """ Test execute with zero cooldown gets clamped to minimum """
        # Mock API response with zero cooldown (expired)
        mock_response = Mock()
        mock_response.data.cooldown = 0
        mock_get_character.return_value = mock_response
        
        result = self.wait_action.execute(self.mock_client, self.context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertIn('Waited 0.1 seconds', result.message)  # Clamped to minimum
        mock_sleep.assert_called_once_with(0.1)  # Minimum wait

    @patch('src.controller.actions.wait.get_character_api')
    @patch('time.sleep')
    def test_execute_with_cooldown_seconds_only(self, mock_sleep, mock_get_character):
        """ Test execute with standard API cooldown """
        # Mock API response with standard cooldown
        mock_response = Mock()
        mock_response.data.cooldown = 3
        mock_get_character.return_value = mock_response
        
        result = self.wait_action.execute(self.mock_client, self.context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertIn('Waited 3.0 seconds', result.message)
        mock_sleep.assert_called_once_with(3.0)

    @patch('src.controller.actions.wait.get_character_api')
    @patch('time.sleep')
    def test_execute_with_large_cooldown_clamped(self, mock_sleep, mock_get_character):
        """ Test execute with large cooldown gets clamped to maximum """
        # Mock API response with large cooldown that should be clamped
        mock_response = Mock()
        mock_response.data.cooldown = 120
        mock_get_character.return_value = mock_response
        
        result = self.wait_action.execute(self.mock_client, self.context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertIn('Waited 60.0 seconds', result.message)  # Clamped to 60 max
        mock_sleep.assert_called_once_with(60.0)  # Clamped to 60 seconds max

    @patch('src.controller.actions.wait.get_character_api')
    @patch('time.sleep')
    def test_execute_with_moderate_cooldown(self, mock_sleep, mock_get_character):
        """ Test execute with moderate cooldown from API """
        # Mock API response with moderate cooldown
        mock_response = Mock()
        mock_response.data.cooldown = 15
        mock_get_character.return_value = mock_response
        
        result = self.wait_action.execute(self.mock_client, self.context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertIn('Waited 15.0 seconds', result.message)
        mock_sleep.assert_called_once_with(15.0)

    @patch('src.controller.actions.wait.get_character_api')
    @patch('time.sleep')
    def test_execute_with_api_fallback(self, mock_sleep, mock_get_character):
        """ Test execute with API providing fallback cooldown """
        # Mock API response with fallback cooldown
        mock_response = Mock()
        mock_response.data.cooldown = 4
        mock_get_character.return_value = mock_response
        
        result = self.wait_action.execute(self.mock_client, self.context)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertIn('Waited 4.0 seconds', result.message)
        mock_sleep.assert_called_once_with(4.0)

    @patch('src.controller.actions.wait.get_character_api')
    @patch('time.sleep')
    def test_execute_exception_handling(self, mock_sleep, mock_get_character):
        """ Test execute handles exceptions gracefully """
        # Mock API response with valid cooldown
        mock_response = Mock()
        mock_response.data.cooldown = 1
        mock_get_character.return_value = mock_response
        
        # Make sleep fail
        mock_sleep.side_effect = Exception("Sleep interrupted")
        
        result = self.wait_action.execute(self.mock_client, self.context)
        
        self.assertIsNotNone(result)
        self.assertFalse(result.success)
        self.assertIn('Wait failed', result.error)

    @patch('src.controller.actions.wait.get_character_api')
    def test_execute_with_context_uses_api(self, mock_get_character):
        """ Test execute with context uses API for cooldown """
        # Mock API response with default cooldown
        mock_response = Mock()
        mock_response.data.cooldown = 3
        mock_get_character.return_value = mock_response
        
        with patch('time.sleep') as mock_sleep:
            result = self.wait_action.execute(self.mock_client, self.context)
            
            self.assertIsNotNone(result)
            self.assertTrue(result.success)
            self.assertIn('Waited 3.0 seconds', result.message)
            mock_sleep.assert_called_once_with(3.0)

    def test_execute_without_character_name(self):
        """ Test execute fails gracefully when no character name provided """
        # Clear character name from context
        self.context.set(StateParameters.CHARACTER_NAME, None)
        
        result = self.wait_action.execute(self.mock_client, self.context)
        
        self.assertIsNotNone(result)
        self.assertFalse(result.success)
        self.assertIn('No character name available', result.error)

    @patch('src.controller.actions.wait.get_character_api')
    def test_execute_api_failure(self, mock_get_character):
        """ Test execute handles API failures gracefully """
        # Mock API to return None
        mock_get_character.return_value = None
        
        result = self.wait_action.execute(self.mock_client, self.context)
        
        self.assertIsNotNone(result)
        self.assertFalse(result.success)
        self.assertIn('Could not get character data from API', result.error)

    def test_repr(self):
        """ Test string representation """
        action = WaitAction()
        self.assertEqual(str(action), "WaitAction()")


if __name__ == '__main__':
    unittest.main()