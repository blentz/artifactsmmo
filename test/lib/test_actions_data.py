"""Unit tests for ActionsData class."""

import os
import tempfile
import unittest
from unittest.mock import patch

from src.lib.actions_data import ActionsData


class TestActionsData(unittest.TestCase):
    """Test cases for ActionsData class."""

    def setUp(self) -> None:
        """Set up test fixtures before each test method."""
        self.test_actions_data = {
            'actions': {
                'move': {
                    'conditions': {'can_move': True},
                    'reactions': {'at_location': True},
                    'weight': 1.0
                },
                'attack': {
                    'conditions': {'can_attack': True},
                    'reactions': {'enemy_defeated': True},
                    'weight': 2.0
                }
            },
            'metadata': {
                'version': '1.0',
                'description': 'Test actions'
            }
        }

    def test_actions_data_initialization(self):
        """Test ActionsData initialization."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            import yaml
            yaml.safe_dump(self.test_actions_data, tmp_file)
            tmp_file.flush()
            
            try:
                actions_data = ActionsData(tmp_file.name)
                
                self.assertEqual(actions_data.filename, tmp_file.name)
                self.assertIsInstance(actions_data.data, dict)
            finally:
                os.unlink(tmp_file.name)

    def test_get_actions(self):
        """Test getting actions from ActionsData."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            import yaml
            yaml.safe_dump(self.test_actions_data, tmp_file)
            tmp_file.flush()
            
            try:
                actions_data = ActionsData(tmp_file.name)
                actions = actions_data.get_actions()
                
                self.assertEqual(len(actions), 2)
                self.assertIn('move', actions)
                self.assertIn('attack', actions)
                self.assertEqual(actions['move']['weight'], 1.0)
                self.assertEqual(actions['attack']['weight'], 2.0)
            finally:
                os.unlink(tmp_file.name)

    def test_get_metadata(self):
        """Test getting metadata from ActionsData."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            import yaml
            yaml.safe_dump(self.test_actions_data, tmp_file)
            tmp_file.flush()
            
            try:
                actions_data = ActionsData(tmp_file.name)
                metadata = actions_data.get_metadata()
                
                self.assertEqual(metadata['version'], '1.0')
                self.assertEqual(metadata['description'], 'Test actions')
            finally:
                os.unlink(tmp_file.name)

    def test_get_actions_empty_file(self):
        """Test getting actions from empty or malformed file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            import yaml
            yaml.safe_dump({}, tmp_file)  # Empty YAML file
            tmp_file.flush()
            
            try:
                actions_data = ActionsData(tmp_file.name)
                actions = actions_data.get_actions()
                
                self.assertEqual(actions, {})
            finally:
                os.unlink(tmp_file.name)

    def test_get_metadata_empty_file(self):
        """Test getting metadata from empty file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            import yaml
            yaml.safe_dump({}, tmp_file)  # Empty YAML file
            tmp_file.flush()
            
            try:
                actions_data = ActionsData(tmp_file.name)
                metadata = actions_data.get_metadata()
                
                self.assertEqual(metadata, {})
            finally:
                os.unlink(tmp_file.name)

    def test_actions_data_repr(self):
        """Test ActionsData string representation."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            import yaml
            yaml.safe_dump(self.test_actions_data, tmp_file)
            tmp_file.flush()
            
            try:
                actions_data = ActionsData(tmp_file.name)
                repr_str = repr(actions_data)
                
                self.assertIn('ActionsData', repr_str)
                self.assertIn('2 actions', repr_str)
                self.assertIn(tmp_file.name, repr_str)
            finally:
                os.unlink(tmp_file.name)

    def test_actions_data_default_filename(self):
        """Test ActionsData with default filename."""
        actions_data = ActionsData()
        
        self.assertEqual(actions_data.filename, "config/default_actions.yaml")

    @patch('src.lib.actions_data.YamlData._load_yaml')
    def test_actions_data_with_mocked_yaml(self, mock_load_yaml):
        """Test ActionsData with mocked YAML loading."""
        mock_load_yaml.return_value = self.test_actions_data
        
        actions_data = ActionsData("test_file.yaml")
        actions = actions_data.get_actions()
        metadata = actions_data.get_metadata()
        
        self.assertEqual(len(actions), 2)
        self.assertEqual(metadata['version'], '1.0')
        mock_load_yaml.assert_called_once_with("test_file.yaml")


if __name__ == '__main__':
    unittest.main()