"""Unit tests for Characters class."""

import json
import unittest
from unittest.mock import Mock, patch

from artifactsmmo_api_client.errors import UnexpectedStatus
from src.game.characters import Characters


class TestCharacters(unittest.TestCase):
    """Test cases for Characters class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.mock_account = Mock()
        self.mock_account.name = "test_account"

    @patch('src.game.characters.account_sync')
    @patch('src.game.characters.CharacterState')
    def test_characters_initialization(self, mock_character_state, mock_account_sync):
        """Test Characters initialization and sync."""
        # Mock API response
        mock_char1 = Mock()
        mock_char1.name = "char1"
        mock_char1.to_dict.return_value = {"name": "char1", "level": 1}
        
        mock_char2 = Mock()
        mock_char2.name = "char2"
        mock_char2.to_dict.return_value = {"name": "char2", "level": 5}
        
        mock_response = Mock()
        mock_response.data = [mock_char1, mock_char2]
        mock_account_sync.return_value = mock_response
        
        # Mock CharacterState creation
        mock_char_state1 = Mock()
        mock_char_state2 = Mock()
        mock_character_state.side_effect = [mock_char_state1, mock_char_state2]
        
        characters = Characters(self.mock_account, self.mock_client)
        
        # Verify API was called
        mock_account_sync.assert_called_once_with(account="test_account", client=self.mock_client)
        
        # Verify CharacterState objects were created
        self.assertEqual(mock_character_state.call_count, 2)
        mock_character_state.assert_any_call(name="char1", data={"name": "char1", "level": 1})
        mock_character_state.assert_any_call(name="char2", data={"name": "char2", "level": 5})
        
        # Verify characters list
        self.assertEqual(len(characters._characters), 2)
        self.assertEqual(characters._characters[0], mock_char_state1)
        self.assertEqual(characters._characters[1], mock_char_state2)

    @patch('src.game.characters.account_sync')
    @patch('src.game.characters.CharacterState')
    def test_characters_repr_behavior(self, mock_character_state, mock_account_sync):
        """Test Characters __repr__ method behavior."""
        mock_response = Mock()
        mock_response.data = []
        mock_account_sync.return_value = mock_response
        
        characters = Characters(self.mock_account, self.mock_client)
        
        # Note: The implementation returns a list from __repr__ which is unusual
        # but we test the actual behavior as implemented
        self.assertIs(characters.__repr__(), characters._characters)

    @patch('src.game.characters.account_sync')
    @patch('src.game.characters.CharacterState')
    def test_characters_str(self, mock_character_state, mock_account_sync):
        """Test Characters string conversion."""
        mock_response = Mock()
        mock_response.data = []
        mock_account_sync.return_value = mock_response
        
        characters = Characters(self.mock_account, self.mock_client)
        
        # __str__ should return string of _characters list
        self.assertEqual(str(characters), str(characters._characters))

    @patch('src.game.characters.account_sync')
    @patch('src.game.characters.CharacterState')
    def test_characters_indexing(self, mock_character_state, mock_account_sync):
        """Test Characters indexing operations."""
        # Setup mock data
        mock_char = Mock()
        mock_char.name = "char1"
        mock_char.to_dict.return_value = {"name": "char1"}
        
        mock_response = Mock()
        mock_response.data = [mock_char]
        mock_account_sync.return_value = mock_response
        
        mock_char_state = Mock()
        mock_character_state.return_value = mock_char_state
        
        characters = Characters(self.mock_account, self.mock_client)
        
        # Test indexing
        self.assertEqual(characters[0], mock_char_state)
        
        # Test length
        self.assertEqual(len(characters), 1)
        
        # Test contains
        self.assertTrue(mock_char_state in characters)
        self.assertFalse("non_existent" in characters)

    @patch('src.game.characters.account_sync')
    @patch('src.game.characters.CharacterState')
    def test_characters_iteration(self, mock_character_state, mock_account_sync):
        """Test Characters iteration."""
        # Setup mock data
        mock_char1 = Mock()
        mock_char1.name = "char1"
        mock_char1.to_dict.return_value = {"name": "char1"}
        
        mock_char2 = Mock()
        mock_char2.name = "char2"
        mock_char2.to_dict.return_value = {"name": "char2"}
        
        mock_response = Mock()
        mock_response.data = [mock_char1, mock_char2]
        mock_account_sync.return_value = mock_response
        
        mock_char_state1 = Mock()
        mock_char_state2 = Mock()
        mock_character_state.side_effect = [mock_char_state1, mock_char_state2]
        
        characters = Characters(self.mock_account, self.mock_client)
        
        # Test iteration
        char_list = list(characters)
        self.assertEqual(len(char_list), 2)
        self.assertEqual(char_list[0], mock_char_state1)
        self.assertEqual(char_list[1], mock_char_state2)

    @patch('src.game.characters.account_sync')
    @patch('src.game.characters.CharacterState')
    @patch('src.game.characters.create_character')
    def test_create_character_success(self, mock_create, mock_character_state, mock_account_sync):
        """Test successful character creation."""
        # Setup initial sync
        mock_response = Mock()
        mock_response.data = []
        mock_account_sync.return_value = mock_response
        
        # Setup character creation response
        mock_create_response = Mock()
        mock_create.return_value = mock_create_response
        
        characters = Characters(self.mock_account, self.mock_client)
        
        # Reset mock to track second sync call
        mock_account_sync.reset_mock()
        mock_response.data = []  # Empty after creation for simplicity
        
        result = characters.create("new_character")
        
        # Verify create_character was called
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        self.assertEqual(call_args.kwargs['client'], self.mock_client)
        
        # Check the schema
        schema = call_args.kwargs['body']
        self.assertEqual(schema.name, "new_character")
        
        # Verify sync was called again
        mock_account_sync.assert_called_once()
        
        # Verify response is returned
        self.assertEqual(result, mock_create_response)

    @patch('src.game.characters.account_sync')
    @patch('src.game.characters.CharacterState')
    @patch('src.game.characters.create_character')
    @patch('src.game.characters.logging')
    def test_create_character_error(self, mock_logging, mock_create, mock_character_state, mock_account_sync):
        """Test character creation with API error."""
        # Setup initial sync
        mock_response = Mock()
        mock_response.data = []
        mock_account_sync.return_value = mock_response
        
        # Setup character creation to raise UnexpectedStatus
        error_content = json.dumps({"error": {"message": "Character name already exists"}}).encode()
        mock_create.side_effect = UnexpectedStatus(status_code=422, content=error_content)
        
        characters = Characters(self.mock_account, self.mock_client)
        
        result = characters.create("existing_character")
        
        # Verify error was logged
        mock_logging.error.assert_called_once()
        error_call = mock_logging.error.call_args[0][0]
        self.assertIn("Character name already exists", error_call)
        self.assertIn("422", error_call)
        
        # Verify None is returned on error
        self.assertIsNone(result)

    @patch('src.game.characters.account_sync')
    @patch('src.game.characters.CharacterState')
    @patch('src.game.characters.logging')
    def test_sync_logging(self, mock_logging, mock_character_state, mock_account_sync):
        """Test that sync operation logs character information."""
        # Setup mock data
        mock_char = Mock()
        mock_char.name = "test_char"
        mock_char.to_dict.return_value = {"name": "test_char"}
        
        mock_response = Mock()
        mock_response.data = [mock_char]
        mock_account_sync.return_value = mock_response
        
        mock_char_state = Mock()
        mock_character_state.return_value = mock_char_state
        
        Characters(self.mock_account, self.mock_client)
        
        # Verify debug logging was called
        mock_logging.debug.assert_called_once()
        debug_call = mock_logging.debug.call_args[0][0]
        self.assertIn("test_account", debug_call)
        self.assertIn("characters:", debug_call)

    @patch('src.game.characters.account_sync')
    @patch('src.game.characters.CharacterState')
    def test_empty_characters_list(self, mock_character_state, mock_account_sync):
        """Test Characters with empty character list."""
        mock_response = Mock()
        mock_response.data = []
        mock_account_sync.return_value = mock_response
        
        characters = Characters(self.mock_account, self.mock_client)
        
        # Should handle empty list gracefully
        self.assertEqual(len(characters), 0)
        self.assertEqual(list(characters), [])
        self.assertFalse("anything" in characters)

    @patch('src.game.characters.account_sync')
    @patch('src.game.characters.CharacterState')
    def test_class_attributes(self, mock_character_state, mock_account_sync):
        """Test Characters class attributes."""
        mock_response = Mock()
        mock_response.data = []
        mock_account_sync.return_value = mock_response
        
        # Check initial class attributes
        self.assertEqual(Characters._characters, [])
        self.assertIsNone(Characters._account)
        
        characters = Characters(self.mock_account, self.mock_client)
        
        # Instance should have its own attributes
        self.assertIsInstance(characters._characters, list)
        self.assertEqual(characters._account, self.mock_account)
        
        # Class attributes should remain unchanged
        self.assertEqual(Characters._characters, [])
        self.assertIsNone(Characters._account)
    
    @patch('src.game.characters.account_sync')
    @patch('src.game.characters.CharacterState')
    @patch('src.game.characters.delete_character')
    def test_delete_character_success(self, mock_delete, mock_character_state, mock_account_sync):
        """Test successful character deletion."""
        # Setup initial sync
        mock_response = Mock()
        mock_response.data = []
        mock_account_sync.return_value = mock_response
        
        # Setup character deletion response
        mock_delete_response = Mock()
        mock_delete.return_value = mock_delete_response
        
        characters = Characters(self.mock_account, self.mock_client)
        
        # Reset mock to track second sync call
        mock_account_sync.reset_mock()
        
        result = characters.delete("char_to_delete")
        
        # Verify delete_character was called
        mock_delete.assert_called_once()
        call_args = mock_delete.call_args
        self.assertEqual(call_args.kwargs['client'], self.mock_client)
        
        # Check the schema
        schema = call_args.kwargs['body']
        self.assertEqual(schema.name, "char_to_delete")
        
        # Verify sync was called again
        mock_account_sync.assert_called_once()
        
        # Verify response is returned
        self.assertEqual(result, mock_delete_response)
    
    @patch('src.game.characters.account_sync')
    @patch('src.game.characters.CharacterState')
    @patch('src.game.characters.delete_character')
    @patch('src.game.characters.logging')
    def test_delete_character_error(self, mock_logging, mock_delete, mock_character_state, mock_account_sync):
        """Test character deletion with API error."""
        # Setup initial sync
        mock_response = Mock()
        mock_response.data = []
        mock_account_sync.return_value = mock_response
        
        # Setup character deletion to raise UnexpectedStatus
        error_content = json.dumps({"error": {"message": "Character not found"}}).encode()
        mock_delete.side_effect = UnexpectedStatus(status_code=404, content=error_content)
        
        characters = Characters(self.mock_account, self.mock_client)
        
        result = characters.delete("non_existent_char")
        
        # Verify error was logged
        mock_logging.error.assert_called_once()
        error_call = mock_logging.error.call_args[0][0]
        self.assertIn("Character not found", error_call)
        self.assertIn("404", error_call)
        
        # Verify None is returned on error
        self.assertIsNone(result)
    
    @patch('src.game.characters.account_sync')
    @patch('src.game.characters.CharacterState')
    @patch('src.game.characters.delete_character')
    @patch('src.game.characters.logging')
    def test_delete_character_with_debug_logging(self, mock_logging, mock_delete, mock_character_state, mock_account_sync):
        """Test character deletion with debug logging."""
        # Setup initial sync
        mock_response = Mock()
        mock_response.data = []
        mock_account_sync.return_value = mock_response
        
        # Setup successful deletion
        mock_delete_response = Mock()
        mock_delete.return_value = mock_delete_response
        
        characters = Characters(self.mock_account, self.mock_client)
        
        result = characters.delete("char_with_debug")
        
        # Verify debug logging was called
        mock_logging.debug.assert_any_call(f"delete character response: {mock_delete_response}")
        
        self.assertEqual(result, mock_delete_response)
    
    @patch('src.game.characters.account_sync')
    @patch('src.game.characters.CharacterState')
    @patch('src.game.characters.get_character')
    def test_get_character_from_list(self, mock_get_char, mock_character_state, mock_account_sync):
        """Test getting a character that exists in the list."""
        # Setup character in list
        mock_char = Mock()
        mock_char.name = "existing_char"
        mock_char.to_dict.return_value = {"name": "existing_char"}
        
        mock_response = Mock()
        mock_response.data = [mock_char]
        mock_account_sync.return_value = mock_response
        
        mock_char_state = Mock()
        mock_char_state.name = "existing_char"
        mock_character_state.return_value = mock_char_state
        
        characters = Characters(self.mock_account, self.mock_client)
        
        # Test getting character from list
        result = characters.get("existing_char")
        
        # Should return from list without API call
        self.assertEqual(result, mock_char_state)
        mock_get_char.assert_not_called()
    
    @patch('src.game.characters.account_sync')
    @patch('src.game.characters.CharacterState')
    @patch('src.game.characters.get_character')
    @patch('src.game.characters.logging')
    def test_get_character_from_api(self, mock_logging, mock_get_char, mock_character_state, mock_account_sync):
        """Test getting a character that's not in the list (fallback to API)."""
        # Setup empty character list
        mock_response = Mock()
        mock_response.data = []
        mock_account_sync.return_value = mock_response
        
        # Setup API response
        mock_api_response = Mock()
        mock_get_char.return_value = mock_api_response
        
        characters = Characters(self.mock_account, self.mock_client)
        
        # Test getting character not in list
        result = characters.get("new_char")
        
        # Should call API
        mock_get_char.assert_called_once_with("new_char", client=self.mock_client)
        self.assertEqual(result, mock_api_response)
        
        # Verify debug logging
        mock_logging.debug.assert_called_with(f"get character response: {mock_api_response}")
    
    @patch('src.game.characters.account_sync')
    @patch('src.game.characters.CharacterState')
    @patch('src.game.characters.get_character')
    @patch('src.game.characters.logging')
    def test_get_character_with_debug_logging(self, mock_logging, mock_get_char, mock_character_state, mock_account_sync):
        """Test get method debug logging when character is found in list."""
        # Setup character in list
        mock_char = Mock()
        mock_char.name = "test_char"
        mock_char.to_dict.return_value = {"name": "test_char"}
        
        mock_response = Mock()
        mock_response.data = [mock_char]
        mock_account_sync.return_value = mock_response
        
        mock_char_state = Mock()
        mock_char_state.name = "test_char"
        mock_character_state.return_value = mock_char_state
        
        characters = Characters(self.mock_account, self.mock_client)
        
        # Clear previous debug calls
        mock_logging.debug.reset_mock()
        
        # Test getting character from list
        result = characters.get("test_char")
        
        # Verify debug logging for character in loop
        mock_logging.debug.assert_called_once()
        debug_call = mock_logging.debug.call_args[0][0]
        self.assertIn("character:", debug_call)
    
    @patch('src.game.characters.account_sync')
    @patch('src.game.characters.CharacterState')
    @patch('src.game.characters.get_character')
    def test_get_character_none_name(self, mock_get_char, mock_character_state, mock_account_sync):
        """Test get method with character that has None name."""
        # Setup character with None name
        mock_char = Mock()
        mock_char.name = "valid_char"
        mock_char.to_dict.return_value = {"name": "valid_char"}
        
        mock_char_none = Mock()
        mock_char_none.name = None
        mock_char_none.to_dict.return_value = {"name": None}
        
        mock_response = Mock()
        mock_response.data = [mock_char_none, mock_char]
        mock_account_sync.return_value = mock_response
        
        mock_char_state_none = Mock()
        mock_char_state_none.name = None
        
        mock_char_state_valid = Mock()
        mock_char_state_valid.name = "valid_char"
        
        mock_character_state.side_effect = [mock_char_state_none, mock_char_state_valid]
        
        # Setup API response
        mock_api_response = Mock()
        mock_get_char.return_value = mock_api_response
        
        characters = Characters(self.mock_account, self.mock_client)
        
        # Test getting any character - should skip None and return valid one
        result = characters.get("any_name")
        
        # Should return the valid character
        self.assertEqual(result, mock_char_state_valid)
        mock_get_char.assert_not_called()
    
    @patch('src.game.characters.account_sync')
    @patch('src.game.characters.CharacterState')
    @patch('src.game.characters.get_character')
    def test_get_character_empty_character(self, mock_get_char, mock_character_state, mock_account_sync):
        """Test get method with empty/None character in list."""
        # Setup list with None character
        mock_char = Mock()
        mock_char.name = "valid_char"
        mock_char.to_dict.return_value = {"name": "valid_char"}
        
        mock_response = Mock()
        mock_response.data = [mock_char]
        mock_account_sync.return_value = mock_response
        
        # Make CharacterState return None for first character
        mock_char_state = Mock()
        mock_char_state.name = "valid_char"
        mock_character_state.return_value = None
        
        characters = Characters(self.mock_account, self.mock_client)
        characters._characters = [None, mock_char_state]  # Manually set with None
        
        # Setup API response
        mock_api_response = Mock()
        mock_get_char.return_value = mock_api_response
        
        # Test getting character - should skip None and return valid one
        result = characters.get("any_name")
        
        # Should return the valid character from list
        self.assertEqual(result, mock_char_state)
        mock_get_char.assert_not_called()


if __name__ == '__main__':
    unittest.main()