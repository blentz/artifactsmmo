""" Tests for yaml_data module """

import os
import tempfile
from unittest.mock import patch

import pytest

from src.lib.yaml_data import YamlData


class TestYamlData:
    """Test cases for YamlData class"""

    def test_init_with_default_filename(self) -> None:
        """Test initialization with default filename"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('os.getcwd', return_value=temp_dir):
                yaml_data = YamlData()
                assert yaml_data.filename == "data.yaml"
                assert yaml_data.data == {}
                assert yaml_data._log is not None

    def test_init_with_custom_filename(self) -> None:
        """Test initialization with custom filename"""
        custom_filename = "custom.yaml"
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('os.getcwd', return_value=temp_dir):
                yaml_data = YamlData(custom_filename)
                assert yaml_data.filename == custom_filename
                assert yaml_data.data == {}

    def test_repr(self) -> None:
        """Test string representation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('os.getcwd', return_value=temp_dir):
                yaml_data = YamlData("test.yaml")
                expected = "YamlData(test.yaml): {}"
                assert repr(yaml_data) == expected

    def test_iter(self) -> None:
        """Test iteration over YamlData"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('os.getcwd', return_value=temp_dir):
                yaml_data = YamlData("test.yaml")
                yaml_data.data = {"key": "value"}

                for key, value in yaml_data:
                    assert key == "data"
                    assert value == {"key": "value"}

    def test_getitem(self) -> None:
        """Test dictionary-style access"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('os.getcwd', return_value=temp_dir):
                yaml_data = YamlData("test.yaml")
                yaml_data.data = {"key": "value", "number": 42}

                assert yaml_data["key"] == "value"
                assert yaml_data["number"] == 42

    def test_getitem_key_error(self) -> None:
        """Test KeyError when accessing non-existent key"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('os.getcwd', return_value=temp_dir):
                yaml_data = YamlData("test.yaml")
                yaml_data.data = {"key": "value"}

                with pytest.raises(KeyError):
                    _ = yaml_data["nonexistent"]

    def test_getitem_data_none(self) -> None:
        """Test TypeError when data is None"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('os.getcwd', return_value=temp_dir):
                yaml_data = YamlData("test.yaml")
                yaml_data.data = None

                with pytest.raises(TypeError):
                    _ = yaml_data["any_key"]

    def test_load_yaml_file_not_exists(self) -> None:
        """Test loading when file doesn't exist - should create empty file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            filename = os.path.join(temp_dir, "test.yaml")
            yaml_data = YamlData.__new__(YamlData)
            yaml_data.filename = filename  # Set filename before calling _load_yaml

            # Mock logger
            with patch('logging.getLogger') as mock_logger:
                yaml_data._log = mock_logger.return_value

                result = yaml_data._load_yaml(filename)
                assert result == {}
                assert os.path.exists(filename)

    def test_load_yaml_file_exists_with_data(self) -> None:
        """Test loading existing file with data"""
        test_data = {"test": "data", "number": 123}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            import yaml
            yaml.safe_dump(test_data, f)
            temp_filename = f.name

        try:
            yaml_data = YamlData.__new__(YamlData)
            with patch('logging.getLogger') as mock_logger:
                yaml_data._log = mock_logger.return_value

                result = yaml_data._load_yaml(temp_filename)
                assert result == test_data
        finally:
            os.unlink(temp_filename)

    def test_load_yaml_file_exists_empty(self) -> None:
        """Test loading existing but empty file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("")  # Empty file
            temp_filename = f.name

        try:
            yaml_data = YamlData.__new__(YamlData)
            with patch('logging.getLogger') as mock_logger:
                yaml_data._log = mock_logger.return_value

                result = yaml_data._load_yaml(temp_filename)
                assert result == {}
        finally:
            os.unlink(temp_filename)

    def test_load_yaml_file_exists_null_content(self) -> None:
        """Test loading file with null YAML content"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("null")  # YAML null
            temp_filename = f.name

        try:
            yaml_data = YamlData.__new__(YamlData)
            with patch('logging.getLogger') as mock_logger:
                yaml_data._log = mock_logger.return_value

                result = yaml_data._load_yaml(temp_filename)
                assert result == {}
        finally:
            os.unlink(temp_filename)

    def test_save_yaml(self) -> None:
        """Test saving YAML data to file"""
        test_data = {"test": "data", "number": 123}

        with tempfile.TemporaryDirectory() as temp_dir:
            filename = os.path.join(temp_dir, "test.yaml")
            yaml_data = YamlData.__new__(YamlData)
            yaml_data.filename = filename

            with patch('logging.getLogger') as mock_logger:
                yaml_data._log = mock_logger.return_value

                yaml_data._save_yaml(test_data)

                # Verify file was created and contains correct data
                assert os.path.exists(filename)
                import yaml
                with open(filename) as f:
                    loaded_data = yaml.safe_load(f)
                assert loaded_data == test_data

    def test_load_public_interface(self) -> None:
        """Test public load method"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('os.getcwd', return_value=temp_dir):
                yaml_data = YamlData("test.yaml")

                # Should call _load_yaml internally
                with patch.object(yaml_data, '_load_yaml') as mock_load:
                    mock_load.return_value = {"loaded": "data"}

                    result = yaml_data.load()
                    mock_load.assert_called_once_with("test.yaml")
                    assert result == {"loaded": "data"}

    def test_save_public_interface_with_empty_data(self) -> None:
        """Test public save method when data is empty"""
        with tempfile.TemporaryDirectory() as temp_dir:
            filename = os.path.join(temp_dir, "test.yaml")
            yaml_data = YamlData.__new__(YamlData)
            yaml_data.filename = filename
            yaml_data.data = None

            with patch('logging.getLogger') as mock_logger:
                yaml_data._log = mock_logger.return_value

                with patch.object(yaml_data, '_save_yaml') as mock_save:
                    yaml_data.save(extra="value")
                    mock_save.assert_called_once_with({"data": None, "extra": "value"})

    def test_save_public_interface_with_existing_data_no_data_key(self) -> None:
        """Test public save method when data exists but has no 'data' key"""
        with tempfile.TemporaryDirectory() as temp_dir:
            filename = os.path.join(temp_dir, "test.yaml")
            yaml_data = YamlData.__new__(YamlData)
            yaml_data.filename = filename
            yaml_data.data = {"existing": "value"}

            with patch('logging.getLogger') as mock_logger:
                yaml_data._log = mock_logger.return_value

                with patch.object(yaml_data, '_save_yaml') as mock_save:
                    yaml_data.save(extra="value")
                    mock_save.assert_called_once_with({"data": {"existing": "value"}, "extra": "value"})

    def test_save_public_interface_with_existing_data_with_data_key(self) -> None:
        """Test public save method when data exists and has 'data' key"""
        with tempfile.TemporaryDirectory() as temp_dir:
            filename = os.path.join(temp_dir, "test.yaml")
            yaml_data = YamlData.__new__(YamlData)
            yaml_data.filename = filename
            yaml_data.data = {"data": "existing", "other": "value"}

            with patch('logging.getLogger') as mock_logger:
                yaml_data._log = mock_logger.return_value

                with patch.object(yaml_data, '_save_yaml') as mock_save:
                    yaml_data.save(extra="value")
                    mock_save.assert_called_once_with({"data": "existing", "other": "value", "extra": "value"})

    def test_full_workflow_integration(self) -> None:
        """Test complete workflow: create, save, load"""
        with tempfile.TemporaryDirectory() as temp_dir:
            filename = os.path.join(temp_dir, "workflow.yaml")

            # Create and populate YamlData
            yaml_data1 = YamlData.__new__(YamlData)
            yaml_data1.filename = filename
            yaml_data1.data = {"initial": "data"}

            with patch('logging.getLogger') as mock_logger:
                yaml_data1._log = mock_logger.return_value

                # Save data
                yaml_data1.save(extra="added")

                # Create new instance and load
                yaml_data2 = YamlData.__new__(YamlData)
                yaml_data2.filename = filename
                yaml_data2._log = mock_logger.return_value

                loaded_data = yaml_data2._load_yaml(filename)

                # Verify data was saved and loaded correctly
                expected = {"data": {"initial": "data"}, "extra": "added"}
                assert loaded_data == expected

    def test_yaml_file_permissions_error(self) -> None:
        """Test handling of permission errors when creating/writing files"""
        with tempfile.TemporaryDirectory() as temp_dir:
            filename = os.path.join(temp_dir, "test.yaml")
            yaml_data = YamlData.__new__(YamlData)
            yaml_data.filename = filename

            with patch('logging.getLogger') as mock_logger:
                yaml_data._log = mock_logger.return_value

                # Mock open to raise PermissionError
                with patch('builtins.open', side_effect=PermissionError("Permission denied")):
                    with pytest.raises(PermissionError):
                        yaml_data._save_yaml({"test": "data"})

    def test_yaml_invalid_content(self) -> None:
        """Test handling of invalid YAML content"""
        # Create file with invalid YAML
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [unclosed")
            temp_filename = f.name

        try:
            yaml_data = YamlData.__new__(YamlData)
            with patch('logging.getLogger') as mock_logger:
                yaml_data._log = mock_logger.return_value

                # Should raise YAMLError due to invalid content
                with pytest.raises(Exception):  # yaml.YAMLError or similar
                    yaml_data._load_yaml(temp_filename)
        finally:
            os.unlink(temp_filename)

    def test_init_creates_file_and_loads_data(self) -> None:
        """Test that __init__ properly creates file and loads data"""
        with tempfile.TemporaryDirectory() as temp_dir:
            filename = os.path.join(temp_dir, "init_test.yaml")

            # Change to temp directory
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)

                # File doesn't exist initially
                assert not os.path.exists(filename)

                # Create YamlData instance
                yaml_data = YamlData("init_test.yaml")

                # File should be created and data loaded
                assert os.path.exists(filename)
                assert yaml_data.data == {}
                assert yaml_data.filename == "init_test.yaml"
            finally:
                os.chdir(original_cwd)

    def test_debug_logging_calls(self) -> None:
        """Test that debug logging is called appropriately"""
        with tempfile.TemporaryDirectory() as temp_dir:
            filename = os.path.join(temp_dir, "debug_test.yaml")

            with patch('logging.getLogger') as mock_get_logger:
                mock_logger = mock_get_logger.return_value

                # Test file creation logging
                yaml_data = YamlData.__new__(YamlData)
                yaml_data._log = mock_logger
                yaml_data.filename = filename

                yaml_data._load_yaml(filename)

                # Should log file creation
                mock_logger.debug.assert_any_call(f"YamlData({filename}): file not found. creating...")

                # Test file loading logging
                # Create a file with content first
                test_data = {"test": "data"}
                import yaml
                with open(filename, 'w') as f:
                    yaml.safe_dump(test_data, f)

                mock_logger.debug.reset_mock()
                yaml_data._load_yaml(filename)

                # Should log file loading
                mock_logger.debug.assert_any_call(f"YamlData({filename}): file found. loading...")
