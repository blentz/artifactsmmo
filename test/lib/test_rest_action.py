"""Unit tests for RestAction class."""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.rest import RestAction

from test.fixtures import create_mock_client


class TestRestAction(unittest.TestCase):
    """Test cases for RestAction class."""

    def setUp(self) -> None:
        """Set up test fixtures before each test method."""
        self.char_name = "test_character"
        self.rest_action = RestAction()

    def test_rest_action_initialization(self):
        """Test RestAction initialization."""
        action = RestAction()
        
        self.assertFalse(hasattr(action, 'character_name'))
        self.assertIsNotNone(action.logger)

    def test_rest_action_repr(self):
        """Test RestAction string representation."""
        action = RestAction()
        expected = "RestAction()"
        
        self.assertEqual(repr(action), expected)

    @patch('src.controller.actions.rest.rest_character_api')
    def test_rest_action_execute_success(self, mock_rest_api):
        """Test executing rest action successfully."""
        # Setup mock response
        mock_response = Mock()
        mock_char_data = Mock()
        mock_char_data.hp = 80
        mock_char_data.max_hp = 100
        mock_response.data = Mock()
        mock_response.data.character = mock_char_data
        mock_rest_api.return_value = mock_response
        
        # Setup mock client
        mock_client = create_mock_client()
        
        # Execute action
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name)
        result = self.rest_action.execute(mock_client, context)
        
        # Verify API was called correctly
        mock_rest_api.assert_called_once_with(name=self.char_name, client=mock_client)
        
        # Verify response format
        self.assertTrue(result['success'])
        self.assertEqual(result['action'], 'RestAction')
        self.assertEqual(result['current_hp'], 80)
        self.assertEqual(result['max_hp'], 100)
        self.assertEqual(result['hp_percentage'], 80.0)

    @patch('src.controller.actions.rest.rest_character_api')
    def test_rest_action_execute_with_hp_recovery(self, mock_rest_api):
        """Test executing rest action with HP recovery tracking."""
        # Setup mock response
        mock_response = Mock()
        mock_char_data = Mock()
        mock_char_data.hp = 80
        mock_char_data.max_hp = 100
        mock_response.data = Mock()
        mock_response.data.character = mock_char_data
        mock_rest_api.return_value = mock_response
        
        # Setup mock client
        mock_client = create_mock_client()
        
        # Execute action with previous HP info
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name, previous_hp=60)
        result = self.rest_action.execute(mock_client, context)
        
        # Verify HP recovery was calculated
        self.assertEqual(result['hp_recovered'], 20)  # 80 - 60

    @patch('src.controller.actions.rest.rest_character_api')
    def test_rest_action_execute_low_hp(self, mock_rest_api):
        """Test executing rest action when HP is low."""
        # Setup mock response with low HP
        mock_response = Mock()
        mock_char_data = Mock()
        mock_char_data.hp = 25  # 25% HP
        mock_char_data.max_hp = 100
        mock_response.data = Mock()
        mock_response.data.character = mock_char_data
        mock_rest_api.return_value = mock_response
        
        # Setup mock client
        mock_client = create_mock_client()
        
        # Execute action
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name)
        result = self.rest_action.execute(mock_client, context)
        
        # Verify response shows low HP
        self.assertEqual(result['hp_percentage'], 25.0)

    @patch('src.controller.actions.rest.rest_character_api')
    def test_rest_action_execute_no_response_data(self, mock_rest_api):
        """Test executing rest action when response has no data."""
        # Setup mock response without data
        mock_response = Mock()
        mock_response.data = None
        mock_rest_api.return_value = mock_response
        
        # Setup mock client
        mock_client = create_mock_client()
        
        # Execute action
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name)
        result = self.rest_action.execute(mock_client, context)
        
        # Should still return success with default values
        self.assertTrue(result['success'])
        self.assertEqual(result['current_hp'], 0)
        self.assertEqual(result['max_hp'], 0)
        self.assertEqual(result['hp_percentage'], 0)

    @patch('src.controller.actions.rest.rest_character_api')
    def test_rest_action_execute_no_character_data(self, mock_rest_api):
        """Test executing rest action when response has no character data."""
        # Setup mock response without character data
        mock_response = Mock()
        mock_response.data = Mock()
        mock_response.data.character = None
        mock_rest_api.return_value = mock_response
        
        # Setup mock client
        mock_client = create_mock_client()
        
        # Execute action
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name)
        result = self.rest_action.execute(mock_client, context)
        
        # Should still return success with default values
        self.assertTrue(result['success'])
        self.assertEqual(result['current_hp'], 0)
        self.assertEqual(result['max_hp'], 0)

    @patch('src.controller.actions.rest.rest_character_api')
    def test_rest_action_execute_zero_max_hp(self, mock_rest_api):
        """Test executing rest action when max HP is zero."""
        # Setup mock response with zero max HP
        mock_response = Mock()
        mock_char_data = Mock()
        mock_char_data.hp = 0
        mock_char_data.max_hp = 0
        mock_response.data = Mock()
        mock_response.data.character = mock_char_data
        mock_rest_api.return_value = mock_response
        
        # Setup mock client
        mock_client = create_mock_client()
        
        # Execute action
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name)
        result = self.rest_action.execute(mock_client, context)
        
        # Should handle division by zero gracefully
        self.assertEqual(result['hp_percentage'], 0)

    def test_rest_action_execute_no_client(self):
        """Test executing rest action without client."""
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name)
        result = self.rest_action.execute(None, context)
        
        # Should return error
        self.assertFalse(result['success'])
        self.assertIn('error', result)

    @patch('src.controller.actions.rest.rest_character_api')
    def test_rest_action_execute_api_error_cooldown(self, mock_rest_api):
        """Test executing rest action when character is in cooldown."""
        # Setup API to raise cooldown error
        mock_rest_api.side_effect = Exception("Character is in cooldown")
        
        # Setup mock client
        mock_client = create_mock_client()
        
        # Execute action
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name)
        result = self.rest_action.execute(mock_client, context)
        
        # Should return error with cooldown flag
        self.assertFalse(result['success'])
        self.assertIn('Character is in cooldown', result['error'])
        self.assertTrue(result.get('is_cooldown', False))

    @patch('src.controller.actions.rest.rest_character_api')
    def test_rest_action_execute_api_error_not_found(self, mock_rest_api):
        """Test executing rest action when character not found."""
        # Setup API to raise not found error
        mock_rest_api.side_effect = Exception("Character not found")
        
        # Setup mock client
        mock_client = create_mock_client()
        
        # Execute action
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name)
        result = self.rest_action.execute(mock_client, context)
        
        # Should return appropriate error
        self.assertFalse(result['success'])
        self.assertIn('Character not found', result['error'])

    @patch('src.controller.actions.rest.rest_character_api')
    def test_rest_action_execute_api_error_generic(self, mock_rest_api):
        """Test executing rest action with generic API error."""
        # Setup API to raise generic error
        mock_rest_api.side_effect = Exception("Network error")
        
        # Setup mock client
        mock_client = create_mock_client()
        
        # Execute action
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name=self.char_name)
        result = self.rest_action.execute(mock_client, context)
        
        # Should return error with original message
        self.assertFalse(result['success'])
        self.assertIn('Network error', result['error'])

    def test_rest_action_validate_no_character_name(self):
        """Test validation fails when character name is empty."""
        action = RestAction()
        from test.fixtures import MockActionContext, create_mock_client
        context = MockActionContext(character_name="")
        mock_client = create_mock_client()
        result = action.execute(mock_client, context)
        self.assertFalse(result['success'])

    def test_rest_action_class_attributes(self):
        """Test RestAction class has expected GOAP attributes."""
        # Check that GOAP attributes exist and have meaningful values
        self.assertIsInstance(RestAction.conditions, dict)
        self.assertIsInstance(RestAction.reactions, dict)
        self.assertIsInstance(RestAction.weight, (int, float))
        
        # Check specific GOAP conditions (consolidated state format)
        self.assertIn('character_status', RestAction.conditions)
        self.assertEqual(RestAction.conditions['character_status']['alive'], True)
        self.assertEqual(RestAction.conditions['character_status']['hp_percentage'], '<100')
        
        # Check specific GOAP reactions (consolidated state format)
        self.assertIn('character_status', RestAction.reactions)
        self.assertEqual(RestAction.reactions['character_status']['hp_percentage'], 100)
        self.assertEqual(RestAction.reactions['character_status']['safe'], True)
        
        # Check weight (consolidated format)
        self.assertEqual(RestAction.weight, 1)


if __name__ == '__main__':
    unittest.main()