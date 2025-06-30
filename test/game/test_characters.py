"""Unit tests for Characters class."""

import unittest
import json
from unittest.mock import Mock, patch, MagicMock
from src.game.characters import Characters
from artifactsmmo_api_client.errors import UnexpectedStatus


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


if __name__ == '__main__':
    unittest.main()