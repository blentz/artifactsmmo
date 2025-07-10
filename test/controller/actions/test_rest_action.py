"""Unit tests for RestAction class."""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.rest import RestAction
from src.lib.state_parameters import StateParameters
from test.fixtures import create_mock_client
from test.test_base import UnifiedContextTestBase


class TestRestAction(UnifiedContextTestBase):
    """Test cases for RestAction class."""

    def setUp(self) -> None:
        """Set up test fixtures before each test method."""
        super().setUp()
        self.char_name = "test_character"
        self.rest_action = RestAction()
        self.context.set(StateParameters.CHARACTER_NAME, self.char_name)

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
        result = self.rest_action.execute(mock_client, self.context)
        
        # Verify API was called correctly
        mock_rest_api.assert_called_once_with(name=self.char_name, client=mock_client)
        
        # Verify response format
        self.assertTrue(result.success)
        self.assertEqual(result.data['current_hp'], 80)
        self.assertEqual(result.data['max_hp'], 100)
        self.assertEqual(result.data['hp_percentage'], 80.0)

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
        self.context.set(StateParameters.CHARACTER_PREVIOUS_HP, 60)
        result = self.rest_action.execute(mock_client, self.context)
        
        # Verify HP recovery was calculated
        self.assertEqual(result.data['hp_recovered'], 20)  # 80 - 60

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
        result = self.rest_action.execute(mock_client, self.context)
        
        # Verify response shows low HP
        self.assertEqual(result.data['hp_percentage'], 25.0)

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
        result = self.rest_action.execute(mock_client, self.context)
        
        # Should still return success with default values
        self.assertTrue(result.success)
        self.assertEqual(result.data['current_hp'], 0)
        self.assertEqual(result.data['max_hp'], 0)
        self.assertEqual(result.data['hp_percentage'], 0)

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
        result = self.rest_action.execute(mock_client, self.context)
        
        # Should still return success with default values
        self.assertTrue(result.success)
        self.assertEqual(result.data['current_hp'], 0)
        self.assertEqual(result.data['max_hp'], 0)

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
        result = self.rest_action.execute(mock_client, self.context)
        
        # Should handle division by zero gracefully
        self.assertEqual(result.data['hp_percentage'], 0)

    def test_rest_action_execute_no_client(self):
        """Test executing rest action without client."""
        result = self.rest_action.execute(None, self.context)
        
        # Should return error
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    @patch('src.controller.actions.rest.rest_character_api')
    def test_rest_action_execute_api_error_cooldown(self, mock_rest_api):
        """Test executing rest action when character is in cooldown."""
        # Setup API to raise cooldown error
        mock_rest_api.side_effect = Exception("Character is in cooldown")
        
        # Setup mock client
        mock_client = create_mock_client()
        
        # Execute action
        result = self.rest_action.execute(mock_client, self.context)
        
        # Should return error with cooldown flag
        self.assertFalse(result.success)
        self.assertIn('Character is in cooldown', result.error)
        self.assertTrue(result.data.get('is_cooldown', False))

    @patch('src.controller.actions.rest.rest_character_api')
    def test_rest_action_execute_api_error_not_found(self, mock_rest_api):
        """Test executing rest action when character not found."""
        # Setup API to raise not found error
        mock_rest_api.side_effect = Exception("Character not found")
        
        # Setup mock client
        mock_client = create_mock_client()
        
        # Execute action
        result = self.rest_action.execute(mock_client, self.context)
        
        # Should return appropriate error
        self.assertFalse(result.success)
        self.assertIn('Character not found', result.error)

    @patch('src.controller.actions.rest.rest_character_api')
    def test_rest_action_execute_api_error_generic(self, mock_rest_api):
        """Test executing rest action with generic API error."""
        # Setup API to raise generic error
        mock_rest_api.side_effect = Exception("Network error")
        
        # Setup mock client
        mock_client = create_mock_client()
        
        # Execute action
        result = self.rest_action.execute(mock_client, self.context)
        
        # Should return error with original message
        self.assertFalse(result.success)
        self.assertIn('Network error', result.error)

    def test_rest_action_validate_no_character_name(self):
        """Test validation fails when character name is empty."""
        action = RestAction()
        self.context.character_name = ""
        mock_client = create_mock_client()
        result = action.execute(mock_client, self.context)
        self.assertFalse(result.success)

    def test_rest_action_class_attributes(self):
        """Test RestAction class has expected GOAP attributes."""
        # RestAction GOAP parameters are now defined in actions.yaml, not as class attributes
        # Test that the class can be instantiated successfully
        action = RestAction()
        self.assertIsInstance(action, RestAction)
        
        # Test that it inherits from expected base classes
        from src.controller.actions.base.character import CharacterActionBase
        self.assertIsInstance(action, CharacterActionBase)


if __name__ == '__main__':
    unittest.main()