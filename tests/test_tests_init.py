"""
Tests for tests/__init__.py module

This module validates all functionality provided by the tests package __init__.py,
including MockFactory, TestAssertions, TestHelpers, fixtures, and configuration.
"""

import asyncio
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
import yaml
from _pytest.outcomes import Failed

from tests import (
    ASYNCIO_MODE,
    TEST_TIMEOUT,
    MockFactory,
    TestAssertions,
    TestHelpers,
    configure_test_environment,
)


class TestConfiguration:
    """Test configuration constants and environment setup"""

    def test_test_timeout_constant(self):
        """Test that TEST_TIMEOUT constant is properly defined"""
        assert TEST_TIMEOUT == 30.0
        assert isinstance(TEST_TIMEOUT, float)

    def test_asyncio_mode_constant(self):
        """Test that ASYNCIO_MODE constant is properly defined"""
        assert ASYNCIO_MODE == "auto"
        assert isinstance(ASYNCIO_MODE, str)

    def test_configure_test_environment_adds_src_path(self):
        """Test that configure_test_environment adds src to Python path"""
        # Save original path
        original_path = sys.path.copy()

        try:
            # Remove src path if it exists
            src_path = str(Path(__file__).parent.parent / "src")
            if src_path in sys.path:
                sys.path.remove(src_path)

            # Call configure function
            configure_test_environment()

            # Verify src path was added
            assert src_path in sys.path
            # Verify it was added at the beginning (index 0)
            assert sys.path[0] == src_path

        finally:
            # Restore original path
            sys.path[:] = original_path

    def test_configure_test_environment_idempotent(self):
        """Test that configure_test_environment can be called multiple times safely"""
        # Save original path
        original_path = sys.path.copy()

        try:
            # Call multiple times
            configure_test_environment()
            path_after_first = sys.path.copy()

            configure_test_environment()
            path_after_second = sys.path.copy()

            # Paths should be identical (no duplicates)
            assert path_after_first == path_after_second

        finally:
            # Restore original path
            sys.path[:] = original_path

    def test_pytest_configure_calls_configure_test_environment(self):
        """Test that pytest_configure calls configure_test_environment"""
        from tests import pytest_configure

        # Mock pytest config object
        mock_config = Mock()

        # Save original path
        original_path = sys.path.copy()

        try:
            # Remove src path if it exists
            src_path = str(Path(__file__).parent.parent / "src")
            if src_path in sys.path:
                sys.path.remove(src_path)

            # Call pytest_configure
            pytest_configure(mock_config)

            # Verify src path was added
            assert src_path in sys.path

        finally:
            # Restore original path
            sys.path[:] = original_path


class TestMockFactory:
    """Test MockFactory utility class methods"""

    def test_create_character_mock_default_attributes(self):
        """Test that create_character_mock creates mock with default attributes"""
        character = MockFactory.create_character_mock()

        assert character.name == "test_character"
        assert character.level == 10
        assert character.hp == 100
        assert character.max_hp == 100
        assert character.x == 0
        assert character.y == 0
        assert character.xp == 2500  # level * 250
        assert character.gold == 1000  # level * 100
        assert character.cooldown == 0
        assert character.cooldown_expiration is None

    def test_create_character_mock_custom_attributes(self):
        """Test that create_character_mock accepts custom attributes"""
        character = MockFactory.create_character_mock(
            name="custom_char",
            level=5,
            hp=75,
            x=10,
            y=20,
            max_hp=150,
            xp=1000,
            gold=500,
            cooldown=30,
            cooldown_expiration="2024-01-01T12:00:00"
        )

        assert character.name == "custom_char"
        assert character.level == 5
        assert character.hp == 75
        assert character.max_hp == 150
        assert character.x == 10
        assert character.y == 20
        assert character.xp == 1000
        assert character.gold == 500
        assert character.cooldown == 30
        assert character.cooldown_expiration == "2024-01-01T12:00:00"

    def test_create_character_mock_kwargs_attributes(self):
        """Test that create_character_mock adds additional kwargs as attributes"""
        character = MockFactory.create_character_mock(
            custom_attr1="value1",
            custom_attr2=42,
            custom_attr3=True
        )

        assert character.custom_attr1 == "value1"
        assert character.custom_attr2 == 42
        assert character.custom_attr3 is True

    def test_create_api_response_mock_default_attributes(self):
        """Test that create_api_response_mock creates mock with default attributes"""
        response = MockFactory.create_api_response_mock()

        assert response.status_code == 200
        assert response.data is not None
        assert isinstance(response.data, Mock)

    def test_create_api_response_mock_custom_attributes(self):
        """Test that create_api_response_mock accepts custom attributes"""
        custom_data = Mock()
        custom_data.result = "success"

        response = MockFactory.create_api_response_mock(
            status_code=201,
            data=custom_data,
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 201
        assert response.data == custom_data
        assert response.data.result == "success"
        assert response.headers == {"Content-Type": "application/json"}

    def test_create_async_mock_with_return_default(self):
        """Test that create_async_mock_with_return creates AsyncMock with None return"""
        async_mock = MockFactory.create_async_mock_with_return()

        assert isinstance(async_mock, AsyncMock)
        assert async_mock.return_value is None

    def test_create_async_mock_with_return_custom_value(self):
        """Test that create_async_mock_with_return creates AsyncMock with custom return"""
        return_value = {"result": "success"}
        async_mock = MockFactory.create_async_mock_with_return(return_value)

        assert isinstance(async_mock, AsyncMock)
        assert async_mock.return_value == return_value

    def test_create_cooldown_mock_default_attributes(self):
        """Test that create_cooldown_mock creates mock with default attributes"""
        cooldown = MockFactory.create_cooldown_mock()

        assert cooldown.total_seconds == 0
        assert cooldown.remaining_seconds == 0
        assert cooldown.is_active is False
        assert isinstance(cooldown.expiration, datetime)

    def test_create_cooldown_mock_custom_attributes(self):
        """Test that create_cooldown_mock accepts custom attributes"""
        expiration_time = datetime.now() + timedelta(seconds=60)
        cooldown = MockFactory.create_cooldown_mock(
            total_seconds=60,
            remaining_seconds=30,
            expiration=expiration_time
        )

        assert cooldown.total_seconds == 60
        assert cooldown.remaining_seconds == 30
        assert cooldown.expiration == expiration_time
        assert cooldown.is_active is True

    def test_create_cooldown_mock_auto_expiration(self):
        """Test that create_cooldown_mock automatically calculates expiration"""
        cooldown = MockFactory.create_cooldown_mock(remaining_seconds=45)

        # Expiration should be approximately 45 seconds from now
        now = datetime.now()
        time_diff = (cooldown.expiration - now).total_seconds()
        assert 44 <= time_diff <= 46  # Allow for small timing differences


class TestTestAssertions:
    """Test TestAssertions utility class methods"""

    def test_assert_character_attributes_success(self):
        """Test that assert_character_attributes passes with matching attributes"""
        character = Mock()
        character.name = "test"
        character.level = 5
        character.hp = 80

        expected_attributes = {
            "name": "test",
            "level": 5,
            "hp": 80
        }

        # Should not raise an exception
        TestAssertions.assert_character_attributes(character, expected_attributes)

    def test_assert_character_attributes_failure(self):
        """Test that assert_character_attributes fails with mismatched attributes"""
        character = Mock()
        character.name = "test"
        character.level = 5
        character.hp = 80

        expected_attributes = {
            "name": "test",
            "level": 10,  # Different value
            "hp": 80
        }

        with pytest.raises(AssertionError) as exc_info:
            TestAssertions.assert_character_attributes(character, expected_attributes)

        assert "Character attribute 'level' expected 10, got 5" in str(exc_info.value)

    def test_assert_character_attributes_missing_attribute(self):
        """Test that assert_character_attributes handles missing attributes"""
        character = Mock(spec=['name'])  # Mock with limited spec
        character.name = "test"
        # Missing 'level' attribute

        expected_attributes = {
            "name": "test",
            "level": 5
        }

        with pytest.raises(AssertionError) as exc_info:
            TestAssertions.assert_character_attributes(character, expected_attributes)

        assert "Character attribute 'level' expected 5, got" in str(exc_info.value)

    def test_assert_api_response_structure_success(self):
        """Test that assert_api_response_structure passes with valid structure"""
        response = Mock()
        response.status_code = 200
        response.data = Mock()
        response.data.result = "success"
        response.data.timestamp = "2024-01-01T12:00:00"

        # Should not raise an exception
        TestAssertions.assert_api_response_structure(
            response,
            expected_status=200,
            expected_data_attrs=["result", "timestamp"]
        )

    def test_assert_api_response_structure_wrong_status(self):
        """Test that assert_api_response_structure fails with wrong status"""
        response = Mock()
        response.status_code = 404

        with pytest.raises(AssertionError) as exc_info:
            TestAssertions.assert_api_response_structure(response, expected_status=200)

        assert "Expected status 200, got 404" in str(exc_info.value)

    def test_assert_api_response_structure_missing_status_code(self):
        """Test that assert_api_response_structure fails with missing status_code"""
        response = Mock(spec=[])  # Mock with no attributes

        with pytest.raises(AssertionError) as exc_info:
            TestAssertions.assert_api_response_structure(response)

        assert "Response missing status_code" in str(exc_info.value)

    def test_assert_api_response_structure_missing_data(self):
        """Test that assert_api_response_structure fails with missing data"""
        response = Mock(spec=['status_code'])  # Mock with limited spec
        response.status_code = 200
        # Missing 'data' attribute

        with pytest.raises(AssertionError) as exc_info:
            TestAssertions.assert_api_response_structure(
                response,
                expected_data_attrs=["result"]
            )

        assert "Response missing data attribute" in str(exc_info.value)

    def test_assert_api_response_structure_missing_data_attribute(self):
        """Test that assert_api_response_structure fails with missing data attribute"""
        response = Mock()
        response.status_code = 200
        response.data = Mock(spec=['result'])  # Mock with limited spec
        response.data.result = "success"
        # Missing 'timestamp' attribute on data

        with pytest.raises(AssertionError) as exc_info:
            TestAssertions.assert_api_response_structure(
                response,
                expected_data_attrs=["result", "timestamp"]
            )

        assert "Response data missing expected attribute: timestamp" in str(exc_info.value)

    def test_assert_mock_called_with_timeout_success(self):
        """Test that assert_mock_called_with_timeout succeeds when mock is called"""
        mock_obj = Mock()

        # Call the mock
        mock_obj()

        # Should not raise an exception
        TestAssertions.assert_mock_called_with_timeout(mock_obj, timeout=0.1, call_count=1)

    def test_assert_mock_called_with_timeout_failure(self):
        """Test that assert_mock_called_with_timeout fails when mock is not called enough"""
        mock_obj = Mock()

        # Don't call the mock, but expect 1 call
        with pytest.raises(Failed) as exc_info:
            TestAssertions.assert_mock_called_with_timeout(mock_obj, timeout=0.1, call_count=1)

        assert "Mock was not called 1 times within 0.1 seconds" in str(exc_info.value)

    def test_assert_mock_called_with_timeout_multiple_calls(self):
        """Test that assert_mock_called_with_timeout works with multiple calls"""
        mock_obj = Mock()

        # Call the mock 3 times
        mock_obj()
        mock_obj()
        mock_obj()

        # Should not raise an exception
        TestAssertions.assert_mock_called_with_timeout(mock_obj, timeout=0.1, call_count=3)


class TestTestHelpers:
    """Test TestHelpers utility class methods"""

    def test_create_test_directory_structure(self):
        """Test that create_test_directory_structure creates expected directories"""
        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)

            directories = TestHelpers.create_test_directory_structure(temp_dir)

            # Check that all expected directories are returned
            expected_dirs = ['config', 'data', 'logs', 'cache']
            assert set(directories.keys()) == set(expected_dirs)

            # Check that all directories actually exist
            for dir_name, dir_path in directories.items():
                assert dir_path.exists()
                assert dir_path.is_dir()
                assert dir_path.parent == temp_dir
                assert dir_path.name == dir_name

    def test_create_test_config_file(self):
        """Test that create_test_config_file creates valid YAML config"""
        with tempfile.TemporaryDirectory() as temp_dir_str:
            config_dir = Path(temp_dir_str)

            config_data = {
                "api": {
                    "base_url": "https://api.example.com",
                    "timeout": 30
                },
                "character": {
                    "name": "test_character",
                    "auto_rest": True
                }
            }

            config_file = TestHelpers.create_test_config_file(
                config_dir,
                config_data,
                "custom_config.yaml"
            )

            # Check that file was created
            assert config_file.exists()
            assert config_file.name == "custom_config.yaml"
            assert config_file.parent == config_dir

            # Check that file contains expected data
            with open(config_file) as f:
                loaded_data = yaml.safe_load(f)

            assert loaded_data == config_data

    def test_create_test_config_file_default_filename(self):
        """Test that create_test_config_file uses default filename"""
        with tempfile.TemporaryDirectory() as temp_dir_str:
            config_dir = Path(temp_dir_str)

            config_data = {"test": "data"}

            config_file = TestHelpers.create_test_config_file(config_dir, config_data)

            assert config_file.name == "test_config.yaml"

    @pytest.mark.asyncio
    async def test_wait_for_condition_success(self):
        """Test that wait_for_condition returns True when condition becomes true"""
        condition_met = False

        def condition_func():
            return condition_met

        # Start the wait in a task
        wait_task = asyncio.create_task(
            TestHelpers.wait_for_condition(condition_func, timeout=2.0)
        )

        # Wait a bit then set condition to true
        await asyncio.sleep(0.2)
        condition_met = True

        # Wait should return True
        result = await wait_task
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_condition_timeout(self):
        """Test that wait_for_condition returns False on timeout"""
        def condition_func():
            return False  # Condition never met

        result = await TestHelpers.wait_for_condition(
            condition_func,
            timeout=0.5,
            check_interval=0.1
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_condition_immediate_success(self):
        """Test that wait_for_condition returns immediately if condition is already true"""
        def condition_func():
            return True

        start_time = datetime.now()
        result = await TestHelpers.wait_for_condition(condition_func, timeout=5.0)
        end_time = datetime.now()

        assert result is True
        # Should return very quickly (less than 0.1 seconds)
        assert (end_time - start_time).total_seconds() < 0.1

    def test_generate_test_data_sequence(self):
        """Test that generate_test_data_sequence creates expected sequence"""
        base_data = {
            "name": "test",
            "level": 1,
            "hp": 100
        }

        modifications = [
            {"level": 2, "hp": 110},
            {"level": 3, "hp": 120, "xp": 750},
            {"name": "advanced_test", "level": 4}
        ]

        sequence = TestHelpers.generate_test_data_sequence(base_data, modifications)

        assert len(sequence) == 3

        # Check first item
        assert sequence[0] == {"name": "test", "level": 2, "hp": 110}

        # Check second item
        assert sequence[1] == {"name": "test", "level": 3, "hp": 120, "xp": 750}

        # Check third item
        assert sequence[2] == {"name": "advanced_test", "level": 4, "hp": 100}

    def test_generate_test_data_sequence_empty_modifications(self):
        """Test that generate_test_data_sequence handles empty modifications"""
        base_data = {"test": "value"}
        modifications = []

        sequence = TestHelpers.generate_test_data_sequence(base_data, modifications)

        assert sequence == []


class TestFixtures:
    """Test common fixtures provided by tests/__init__.py"""

    def test_mock_factory_fixture(self, mock_factory):
        """Test that mock_factory fixture provides MockFactory class"""
        assert mock_factory is MockFactory

        # Test that it can create mocks
        character = mock_factory.create_character_mock()
        assert character.name == "test_character"

    def test_test_assertions_fixture(self, test_assertions):
        """Test that test_assertions fixture provides TestAssertions class"""
        assert test_assertions is TestAssertions

    def test_test_helpers_fixture(self, test_helpers):
        """Test that test_helpers fixture provides TestHelpers class"""
        assert test_helpers is TestHelpers

    def test_sample_character_fixture(self, sample_character):
        """Test that sample_character fixture provides character mock"""
        assert isinstance(sample_character, Mock)
        assert sample_character.name == "test_character"
        assert sample_character.level == 10

    def test_sample_api_response_fixture(self, sample_api_response):
        """Test that sample_api_response fixture provides API response mock"""
        assert isinstance(sample_api_response, Mock)
        assert sample_api_response.status_code == 200
        assert sample_api_response.data is not None


class TestIntegration:
    """Integration tests using multiple components together"""

    def test_mock_factory_and_assertions_integration(self):
        """Test using MockFactory with TestAssertions"""
        # Create character with MockFactory
        character = MockFactory.create_character_mock(
            name="integration_test",
            level=15,
            hp=150
        )

        # Use TestAssertions to validate
        expected_attrs = {
            "name": "integration_test",
            "level": 15,
            "hp": 150,
            "xp": 3750,  # level * 250
            "gold": 1500  # level * 100
        }

        TestAssertions.assert_character_attributes(character, expected_attrs)

    def test_helpers_and_assertions_integration(self, test_helpers, test_assertions):
        """Test using TestHelpers with TestAssertions"""
        # Generate test data sequence
        base_data = {"level": 1, "hp": 100}
        modifications = [
            {"level": 2, "hp": 110},
            {"level": 3, "hp": 120}
        ]

        sequence = test_helpers.generate_test_data_sequence(base_data, modifications)

        # Use assertions to validate sequence
        assert len(sequence) == 2
        assert sequence[0]["level"] == 2
        assert sequence[1]["level"] == 3

    @pytest.mark.asyncio
    async def test_async_mock_with_wait_condition(self):
        """Test using AsyncMock with wait_for_condition"""
        # Create async mock that will be called
        async_mock = MockFactory.create_async_mock_with_return("success")

        # Set up condition that checks if mock was called
        def condition_func():
            return async_mock.called

        # Call the mock after a delay
        async def call_mock_after_delay():
            await asyncio.sleep(0.2)
            await async_mock()

        # Start both tasks
        call_task = asyncio.create_task(call_mock_after_delay())
        wait_task = asyncio.create_task(
            TestHelpers.wait_for_condition(condition_func, timeout=1.0)
        )

        # Both should complete successfully
        call_result = await call_task
        wait_result = await wait_task

        assert wait_result is True
        assert async_mock.called
        assert async_mock.return_value == "success"
