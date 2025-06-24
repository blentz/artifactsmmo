import os
import tempfile
import unittest
from unittest.mock import patch, mock_open

from src.lib.yaml_data import YamlData

class TestYamlData(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.filename = os.path.join(self.test_dir.name, "test.yaml")
        # Create an empty file to simulate file existence
        with open(self.filename, 'w') as f:
            pass

    def tearDown(self):
        self.test_dir.cleanup()

    @patch('src.lib.yaml_data.safe_load')
    @patch('builtins.open', new_callable=mock_open, read_data='test: data')
    @patch('os.path.exists')
    def test_init_with_existing_file(self, mock_exists, mock_file, mock_safe_load):
        # Mock file as existing and YAML content
        mock_exists.return_value = True
        mock_content = {'test': 'data'}
        mock_safe_load.return_value = mock_content

        # Create YamlData instance
        yaml_data = YamlData(filename=self.filename)

        # Check if data is loaded correctly
        self.assertEqual(yaml_data.data, mock_content)
        self.assertEqual(yaml_data.filename, self.filename)

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('src.lib.yaml_data.safe_dump')
    def test_init_with_nonexistent_file(self, mock_safe_dump, mock_file, mock_exists):
        # Mock file as not existing
        mock_exists.return_value = False

        # Create YamlData instance
        yaml_data = YamlData(filename=self.filename)

        # Check if empty data is created
        self.assertEqual(yaml_data.data, {})
        self.assertEqual(yaml_data.filename, self.filename)
        # Verify that save was called to create the file
        mock_safe_dump.assert_called_once()

    @patch('src.lib.yaml_data.safe_load')
    @patch('builtins.open', new_callable=mock_open, read_data='test: data')
    @patch('os.path.exists')
    def test_load(self, mock_exists, mock_file, mock_safe_load):
        # Mock file as existing and YAML content
        mock_exists.return_value = True
        mock_content = {'test': 'data'}
        mock_safe_load.return_value = mock_content

        # Create YamlData instance and load data
        yaml_data = YamlData(filename=self.filename)
        loaded_data = yaml_data.load()

        # Check if data is loaded correctly
        self.assertEqual(loaded_data, mock_content)

    @patch('src.lib.yaml_data.safe_dump')
    @patch('builtins.open', new_callable=mock_open)
    def test_save(self, mock_file, mock_safe_dump):
        # Create YamlData instance with initial data
        yaml_data = YamlData(filename=self.filename)
        yaml_data.data = {'existing': 'data'}

        # Save new data
        yaml_data.save(new_key='new_value')

        # Check if save was called with correct arguments
        expected_data = {'data': {'existing': 'data'}, 'new_key': 'new_value'}
        mock_safe_dump.assert_called_once()
        call_args = mock_safe_dump.call_args[0][0]
        self.assertEqual(call_args, expected_data)

if __name__ == '__main__':
    unittest.main()
