"""Unit tests for CharacterActionBase class."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Optional

from artifactsmmo_api_client.client import AuthenticatedClient
from src.controller.actions.character_base import CharacterActionBase


class TestCharacterImplementation(CharacterActionBase):
    """Test implementation of CharacterActionBase."""
    
    def __init__(self, character_name: str, return_data: Dict = None):
        """Initialize with optional return data for testing."""
        super().__init__(character_name)
        self.return_data = return_data or {}
    
    def perform_action(self, client, **kwargs) -> Optional[Dict]:
        """Simple implementation for testing."""
        return self.get_success_response(
            test_action_executed=True,
            character_name=self.character_name,
            **self.return_data
        )


class TestCharacterActionBase(unittest.TestCase):
    """Test cases for CharacterActionBase class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.char_name = "test_character"
        self.action = TestCharacterImplementation(self.char_name)
        self.client = Mock(spec=AuthenticatedClient)
    
    def test_initialization(self):
        """Test CharacterActionBase initialization."""
        action = CharacterActionBase("test_char")
        self.assertEqual(action.character_name, "test_char")
        self.assertIsNotNone(action.logger)
    
    def test_repr(self):
        """Test string representation."""
        self.assertEqual(repr(self.action), "TestCharacterImplementation(test_character)")
    
    def test_validate_execution_context_success(self):
        """Test successful context validation."""
        result = self.action.validate_execution_context(self.client)
        self.assertTrue(result)
    
    def test_validate_execution_context_no_client(self):
        """Test context validation with no client."""
        result = self.action.validate_execution_context(None)
        self.assertFalse(result)
    
    def test_validate_execution_context_empty_character_name(self):
        """Test context validation with empty character name."""
        action = CharacterActionBase("")
        result = action.validate_execution_context(self.client)
        self.assertFalse(result)
    
    def test_validate_execution_context_none_character_name(self):
        """Test context validation with None character name."""
        # Manually set character_name to None to test edge case
        action = CharacterActionBase("test")
        action.character_name = None
        result = action.validate_execution_context(self.client)
        self.assertFalse(result)
    
    def test_character_data_mixin_available(self):
        """Test that CharacterDataMixin methods are available."""
        # These methods should be available through the mixin
        self.assertTrue(hasattr(self.action, 'get_character_data'))
        self.assertTrue(hasattr(self.action, 'get_character_location'))
        self.assertTrue(hasattr(self.action, 'get_character_inventory'))
    
    @patch('src.controller.actions.character_base.CharacterActionBase.get_character_data')
    def test_get_character_data_integration(self, mock_get_char_data):
        """Test that character data mixin integration works."""
        # Mock character data
        mock_char_data = {
            'name': self.char_name,
            'level': 5,
            'hp': 80,
            'max_hp': 100
        }
        mock_get_char_data.return_value = mock_char_data
        
        # Get character data
        char_data = self.action.get_character_data(self.client)
        
        # Verify the mixin method was called
        mock_get_char_data.assert_called_once_with(self.client)
        self.assertEqual(char_data, mock_char_data)
    
    @patch('src.controller.actions.character_base.CharacterActionBase.get_character_location')
    def test_get_character_location_integration(self, mock_get_location):
        """Test that character location mixin integration works."""
        # Mock location data
        mock_location = {'x': 10, 'y': 20}
        mock_get_location.return_value = mock_location
        
        # Get character location
        location = self.action.get_character_location(self.client)
        
        # Verify the mixin method was called
        mock_get_location.assert_called_once_with(self.client)
        self.assertEqual(location, mock_location)
    
    @patch('src.controller.actions.character_base.CharacterActionBase.get_character_inventory')
    def test_get_character_inventory_integration(self, mock_get_inventory):
        """Test that character inventory mixin integration works."""
        # Mock inventory data
        mock_inventory = [
            {'code': 'sword', 'quantity': 1},
            {'code': 'iron_ore', 'quantity': 5}
        ]
        mock_get_inventory.return_value = mock_inventory
        
        # Get character inventory
        inventory = self.action.get_character_inventory(self.client)
        
        # Verify the mixin method was called
        mock_get_inventory.assert_called_once_with(self.client)
        self.assertEqual(inventory, mock_inventory)
    
    def test_inheritance_chain(self):
        """Test that CharacterActionBase properly inherits from both base classes."""
        # Should inherit from ActionBase
        self.assertTrue(hasattr(self.action, 'get_success_response'))
        self.assertTrue(hasattr(self.action, 'get_error_response'))
        self.assertTrue(hasattr(self.action, 'log_execution_start'))
        self.assertTrue(hasattr(self.action, 'log_execution_result'))
        
        # Should inherit from CharacterDataMixin
        self.assertTrue(hasattr(self.action, 'get_character_data'))
        self.assertTrue(hasattr(self.action, 'get_character_location'))
        self.assertTrue(hasattr(self.action, 'get_character_inventory'))
    
    def test_validate_and_execute_success(self):
        """Test successful validate_and_execute flow."""
        # Create action with return data
        action = TestCharacterImplementation(self.char_name, {'extra_field': 'test_value'})
        
        # Execute action
        result = action.validate_and_execute(self.client)
        
        # Verify success response
        self.assertTrue(result['success'])
        self.assertTrue(result['test_action_executed'])
        self.assertEqual(result['character_name'], self.char_name)
        self.assertEqual(result['extra_field'], 'test_value')
    
    def test_validate_and_execute_no_client(self):
        """Test validate_and_execute with no client."""
        result = self.action.validate_and_execute(None)
        
        # Should return error
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])
    
    def test_validate_and_execute_empty_character_name(self):
        """Test validate_and_execute with empty character name."""
        action = TestCharacterImplementation("")
        result = action.validate_and_execute(self.client)
        
        # Should return error
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])
    
    def test_validate_and_execute_exception_handling(self):
        """Test validate_and_execute with exception in perform_action."""
        # Create action that raises exception
        class FailingAction(CharacterActionBase):
            def perform_action(self, client, **kwargs):
                raise ValueError("Test exception")
        
        action = FailingAction(self.char_name)
        result = action.validate_and_execute(self.client)
        
        # Should return error response
        self.assertFalse(result['success'])
        self.assertIn('FailingAction failed', result['error'])
        self.assertIn('Test exception', result['error'])
    
    def test_validate_and_execute_functionality(self):
        """Test that validate_and_execute method works properly."""
        # Execute action using validate_and_execute pattern
        result = self.action.validate_and_execute(self.client, param1='value1', param2='value2')
        
        # Verify it calls perform_action and returns expected result
        self.assertTrue(result['success'])
        self.assertTrue(result['test_action_executed'])
        self.assertEqual(result['character_name'], self.char_name)
    
    def test_action_base_methods_available(self):
        """Test that ActionBase methods are properly available."""
        # Test success response
        success_response = self.action.get_success_response(test_field='test_value')
        self.assertTrue(success_response['success'])
        self.assertEqual(success_response['action'], 'TestCharacterImplementation')
        self.assertEqual(success_response['test_field'], 'test_value')
        
        # Test error response
        error_response = self.action.get_error_response('Test error', extra_info='extra')
        self.assertFalse(error_response['success'])
        self.assertEqual(error_response['error'], 'Test error')
        self.assertEqual(error_response['extra_info'], 'extra')
    
    def test_validate_execution_context_with_kwargs(self):
        """Test context validation with additional kwargs."""
        result = self.action.validate_execution_context(
            self.client, 
            extra_param='value',
            another_param=123
        )
        self.assertTrue(result)
    
    def test_multiple_character_actions(self):
        """Test creating multiple character actions with different names."""
        action1 = CharacterActionBase("character1")
        action2 = CharacterActionBase("character2")
        
        self.assertEqual(action1.character_name, "character1")
        self.assertEqual(action2.character_name, "character2")
        self.assertNotEqual(action1.character_name, action2.character_name)


if __name__ == '__main__':
    unittest.main()