import os
import tempfile
import unittest
from unittest.mock import patch

from yaml_data import YamlData

class TestYamlData(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.filename = os.path.join(self.test_dir.name, "test.yaml")
        # Create an empty file to simulate file existence
        with open(self.filename, 'w') as f:
            pass

    def tearDown(self):
        self.test_dir.cleanup()

    @patch('yaml_data.safe_load')
    def test_init_with_existing_file(self, mock_safe_load):
        # Mock the YAML content
        mock_content = {'data': 'test data'}
        mock_safe_load.return_value = mock_content

        # Create YamlData instance
        yaml_data = YamlData(filename=self.filename)

        # Check if data is loaded correctly
        self.assertEqual(yaml_data.data, mock_content)
        self.assertEqual(yaml_data.filename, self.filename)

    @patch('yaml_data.os.path.exists')
    def test_init_with_nonexistent_file(self, mock_exists):
        # Mock file as not existing
        mock_exists.return_value = False

        # Create YamlData instance
        yaml_data = YamlData(filename=self.filename)

        # Check if empty data is created
        self.assertEqual(yaml_data.data, {})
        self.assertEqual(yaml_data.filename, self.filename)

    @patch('yaml_data.safe_load')
    def test_load(self, mock_safe_load):
        # Mock the YAML content
        mock_content = {'data': 'test data'}
        mock_safe_load.return_value = mock_content

        # Create YamlData instance and load data
        yaml_data = YamlData(filename=self.filename)
        loaded_data = yaml_data.load()

        # Check if data is loaded correctly
        self.assertEqual(loaded_data, mock_content)

    @patch('yaml_data.safe_dump')
    def test_save(self, mock_safe_dump):
        # Create YamlData instance with initial data
        yaml_data = YamlData(filename=self.filename)
        yaml_data.data = {'existing': 'data'}

        # Save new data
        yaml_data.save(new_key='new_value')

        # Check if save was called with correct arguments
        expected_data = {'existing': 'data', 'new_key': 'new_value'}
        mock_safe_dump.assert_called_once_with(expected_data, yaml_data._save_yaml.__self__)

if __name__ == '__main__':
    unittest.main()
