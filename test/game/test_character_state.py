"""Test module for CharacterState."""

import unittest
from unittest.mock import patch, Mock
import tempfile
import os
from src.game.character.state import CharacterState


class TestCharacterState(unittest.TestCase):
    """Test cases for CharacterState."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_name = "test_character"
        self.test_data = {'level': 10, 'hp': 100, 'x': 5, 'y': 3}

    @patch('src.game.character.state.DATA_PREFIX', '/tmp/test_data')
    @patch('src.game.character.state.YamlData.__init__')
    @patch('src.game.character.state.YamlData.save')
    def test_character_state_initialization_default_name(self, mock_save, mock_yaml_init):
        """Test CharacterState initialization with default name."""
        mock_yaml_init.return_value = None
        
        state = CharacterState(self.test_data)
        
        # Check that YamlData.__init__ was called with the correct filename parameter
        args, kwargs = mock_yaml_init.call_args
        self.assertEqual(kwargs['filename'], "/tmp/test_data/character.yaml")
        self.assertEqual(state.name, "character")
        self.assertEqual(state.data, self.test_data)
        mock_save.assert_called_once()

    @patch('src.game.character.state.DATA_PREFIX', '/tmp/test_data')
    @patch('src.game.character.state.YamlData.__init__')
    @patch('src.game.character.state.YamlData.save')
    def test_character_state_initialization_custom_name(self, mock_save, mock_yaml_init):
        """Test CharacterState initialization with custom name."""
        mock_yaml_init.return_value = None
        
        state = CharacterState(self.test_data, name=self.test_name)
        
        # Check that YamlData.__init__ was called with the correct filename parameter
        args, kwargs = mock_yaml_init.call_args
        self.assertEqual(kwargs['filename'], f"/tmp/test_data/{self.test_name}.yaml")
        self.assertEqual(state.name, self.test_name)
        self.assertEqual(state.data, self.test_data)
        mock_save.assert_called_once()

    @patch('src.game.character.state.DATA_PREFIX', '/tmp/test_data')
    @patch('src.game.character.state.YamlData.__init__')
    @patch('src.game.character.state.YamlData.save')
    def test_character_state_repr(self, mock_save, mock_yaml_init):
        """Test CharacterState string representation."""
        mock_yaml_init.return_value = None
        
        state = CharacterState(self.test_data, name=self.test_name)
        
        expected = f"CharacterState({self.test_name}): {self.test_data}"
        self.assertEqual(repr(state), expected)

    @patch('src.game.character.state.DATA_PREFIX', '/tmp/test_data')
    @patch('src.game.character.state.YamlData.__init__')
    @patch('src.game.character.state.YamlData.save')
    def test_character_state_class_attributes(self, mock_save, mock_yaml_init):
        """Test CharacterState class attributes."""
        mock_yaml_init.return_value = None
        
        # Test that class attributes exist
        self.assertIsNone(CharacterState.name)
        self.assertEqual(CharacterState.data, {})
        
        # Test that instance attributes are set correctly
        state = CharacterState(self.test_data, name=self.test_name)
        self.assertEqual(state.name, self.test_name)
        self.assertEqual(state.data, self.test_data)

    @patch('src.game.character.state.DATA_PREFIX', '/tmp/test_data')
    @patch('src.game.character.state.YamlData.__init__')
    @patch('src.game.character.state.YamlData.save')
    def test_character_state_empty_data(self, mock_save, mock_yaml_init):
        """Test CharacterState with empty data."""
        mock_yaml_init.return_value = None
        empty_data = {}
        
        state = CharacterState(empty_data, name="empty_character")
        
        self.assertEqual(state.name, "empty_character")
        self.assertEqual(state.data, empty_data)
        mock_save.assert_called_once()


if __name__ == '__main__':
    unittest.main()