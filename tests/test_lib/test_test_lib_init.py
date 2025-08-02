"""
Test module for tests/test_lib/__init__.py

Validates that the test package initialization provides all expected utilities
and functions correctly.
"""

import importlib
import os
import tempfile
from unittest.mock import patch

import tests.test_lib
from tests.test_lib import (
    TestFixtures,
    __all__,
    check_lib_coverage,
    get_test_modules,
    run_all_tests,
    validate_imports,
)


class TestGetTestModules:
    """Test cases for get_test_modules function."""

    def test_returns_list_of_test_modules(self):
        """Test that get_test_modules returns a list of test module names."""
        modules = get_test_modules()

        assert isinstance(modules, list)
        assert len(modules) > 0

        # Should include known test modules
        expected_modules = [
            "test_goap",
            "test_goap_data",
            "test_yaml_data",
            "test_log",
            "test_httpstatus",
            "test_request_throttle",
            "test_throttled_transport",
            "test_init"
        ]

        for module in expected_modules:
            assert module in modules

    def test_excludes_non_test_files(self):
        """Test that only test_*.py files are included."""
        modules = get_test_modules()

        # Should not include __init__.py or other non-test files
        assert "__init__" not in modules

        # All modules should start with "test_"
        for module in modules:
            assert module.startswith("test_")

    def test_returns_stems_without_extension(self):
        """Test that module names don't include .py extension."""
        modules = get_test_modules()

        for module in modules:
            assert not module.endswith(".py")


class TestRunAllTests:
    """Test cases for run_all_tests function."""

    @patch('pytest.main')
    def test_basic_invocation(self, mock_pytest_main):
        """Test basic test runner invocation."""
        mock_pytest_main.return_value = 0

        result = run_all_tests(verbose=False, coverage=False)

        assert result == 0
        mock_pytest_main.assert_called_once()

        # Check that it called pytest with the test directory
        args = mock_pytest_main.call_args[0][0]
        assert len(args) >= 1
        assert "test_lib" in str(args[0])

    @patch('pytest.main')
    def test_verbose_mode(self, mock_pytest_main):
        """Test verbose mode adds -v flag."""
        mock_pytest_main.return_value = 0

        run_all_tests(verbose=True, coverage=False)

        args = mock_pytest_main.call_args[0][0]
        assert "-v" in args

    @patch('pytest.main')
    def test_coverage_mode(self, mock_pytest_main):
        """Test coverage mode adds coverage flags."""
        mock_pytest_main.return_value = 0

        run_all_tests(verbose=False, coverage=True)

        args = mock_pytest_main.call_args[0][0]
        assert "--cov=src.lib" in args
        assert "--cov-report=term-missing" in args

    @patch('pytest.main')
    def test_combined_flags(self, mock_pytest_main):
        """Test combining verbose and coverage flags."""
        mock_pytest_main.return_value = 0

        run_all_tests(verbose=True, coverage=True)

        args = mock_pytest_main.call_args[0][0]
        assert "-v" in args
        assert "--cov=src.lib" in args
        assert "--cov-report=term-missing" in args

    @patch('pytest.main')
    def test_returns_pytest_exit_code(self, mock_pytest_main):
        """Test that the function returns pytest's exit code."""
        mock_pytest_main.return_value = 2

        result = run_all_tests()

        assert result == 2


class TestValidateImports:
    """Test cases for validate_imports function."""

    def test_successful_validation(self):
        """Test validation when all imports succeed."""
        success, errors = validate_imports()

        # Should succeed since test modules should be importable
        assert success is True
        assert errors == []

    def test_validate_imports_handles_errors(self):
        """Test that validate_imports properly handles and reports errors."""
        # This test verifies the error handling structure exists
        # Real error scenarios would require non-existent modules

        # Test that the function returns the expected tuple structure
        success, errors = validate_imports()
        assert isinstance(success, bool)
        assert isinstance(errors, list)

        # For existing modules, should succeed
        assert success is True
        assert errors == []

    def test_validate_imports_import_error_handling(self):
        """Test that validate_imports handles ImportError exceptions."""
        # Temporarily replace get_test_modules to return a non-existent module
        original_get_test_modules = tests.test_lib.get_test_modules
        tests.test_lib.get_test_modules = lambda: ["nonexistent_test_module"]

        try:
            success, errors = validate_imports()
            assert success is False
            assert len(errors) >= 1
            assert any("Failed to import nonexistent_test_module" in error for error in errors)
        finally:
            # Restore original function
            tests.test_lib.get_test_modules = original_get_test_modules

    def test_validate_imports_general_exception_handling(self):
        """Test that validate_imports handles general exceptions."""
        # Save originals
        original_get_test_modules = tests.test_lib.get_test_modules
        original_import_module = importlib.import_module

        # Set up test scenario
        tests.test_lib.get_test_modules = lambda: ["error_test_module"]

        def mock_import_module(name):
            if "error_test_module" in name:
                raise ValueError("Simulated error")
            return original_import_module(name)

        importlib.import_module = mock_import_module

        try:
            success, errors = validate_imports()
            assert success is False
            assert len(errors) >= 1
            assert any("Error importing error_test_module" in error for error in errors)
        finally:
            # Restore originals
            tests.test_lib.get_test_modules = original_get_test_modules
            importlib.import_module = original_import_module


class TestCheckLibCoverage:
    """Test cases for check_lib_coverage function."""

    def test_returns_coverage_dict(self):
        """Test that check_lib_coverage returns a dictionary."""
        coverage = check_lib_coverage()

        assert isinstance(coverage, dict)
        assert len(coverage) > 0

    def test_includes_expected_lib_modules(self):
        """Test that coverage includes expected lib modules."""
        coverage = check_lib_coverage()

        expected_modules = [
            "goap",
            "goap_data",
            "yaml_data",
            "log",
            "httpstatus",
            "request_throttle",
            "throttled_transport"
        ]

        for module in expected_modules:
            assert module in coverage

    def test_coverage_values_are_boolean(self):
        """Test that all coverage values are boolean."""
        coverage = check_lib_coverage()

        for module, has_test in coverage.items():
            assert isinstance(has_test, bool)

    def test_well_tested_modules_show_true(self):
        """Test that modules with tests show True coverage."""
        coverage = check_lib_coverage()

        # These modules should have corresponding test files
        well_tested = ["goap", "yaml_data", "log", "httpstatus"]

        for module in well_tested:
            if module in coverage:
                assert coverage[module] is True


class TestTestFixtures:
    """Test cases for TestFixtures utility class."""

    def test_get_temp_yaml_path(self):
        """Test that get_temp_yaml_path returns a valid path."""
        path = TestFixtures.get_temp_yaml_path()

        assert isinstance(path, str)
        assert path.endswith(".yaml")
        assert not os.path.exists(path)  # Should be a non-existent temp path

    def test_cleanup_temp_files_existing_file(self):
        """Test cleanup of existing temporary files."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".yaml") as f:
            temp_path = f.name

        # Verify file exists
        assert os.path.exists(temp_path)

        # Clean it up
        TestFixtures.cleanup_temp_files(temp_path)

        # Verify file is gone
        assert not os.path.exists(temp_path)

    def test_cleanup_temp_files_nonexistent_file(self):
        """Test cleanup handles non-existent files gracefully."""
        fake_path = "/tmp/this_file_does_not_exist.yaml"

        # Should not raise an exception
        TestFixtures.cleanup_temp_files(fake_path)

    def test_cleanup_multiple_files(self):
        """Test cleanup of multiple files at once."""
        # Create multiple temporary files
        temp_paths = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{i}.yaml") as f:
                temp_paths.append(f.name)

        # Verify all files exist
        for path in temp_paths:
            assert os.path.exists(path)

        # Clean them all up
        TestFixtures.cleanup_temp_files(*temp_paths)

        # Verify all files are gone
        for path in temp_paths:
            assert not os.path.exists(path)

    @patch('os.path.exists')
    @patch('os.unlink')
    def test_cleanup_handles_os_error(self, mock_unlink, mock_exists):
        """Test that cleanup handles OS errors gracefully."""
        mock_exists.return_value = True
        mock_unlink.side_effect = OSError("Permission denied")

        # Should not raise an exception
        TestFixtures.cleanup_temp_files("some_file.yaml")


class TestModuleStructure:
    """Test the overall structure and exports of the test_lib package."""

    def test_all_exports_available(self):
        """Test that all expected exports are available in __all__."""
        expected_exports = [
            "get_test_modules",
            "run_all_tests",
            "validate_imports",
            "check_lib_coverage",
            "TestFixtures"
        ]

        for export in expected_exports:
            assert export in __all__

    def test_can_import_all_exports(self):
        """Test that all exports can be imported successfully."""
        # Basic smoke test - make sure nothing is None
        assert get_test_modules is not None
        assert run_all_tests is not None
        assert validate_imports is not None
        assert check_lib_coverage is not None
        assert TestFixtures is not None

    def test_module_docstring_exists(self):
        """Test that the module has a comprehensive docstring."""
        assert tests.test_lib.__doc__ is not None
        assert len(tests.test_lib.__doc__.strip()) > 100
        assert "ArtifactsMMO AI Player Library" in tests.test_lib.__doc__
