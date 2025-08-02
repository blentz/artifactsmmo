"""
Test suite for ArtifactsMMO AI Player

This test suite provides comprehensive testing for the AI player application,
including unit tests, integration tests, and fixtures for test-driven development.
"""

import asyncio
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
import yaml

# Test configuration
TEST_TIMEOUT = 30.0
ASYNCIO_MODE = "auto"


def configure_test_environment():
    """Configure test environment settings and paths"""
    # Add src directory to Python path for imports
    src_path = Path(__file__).parent.parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


# Common test utilities
class MockFactory:
    """Factory for creating common mock objects used across tests"""

    @staticmethod
    def create_character_mock(
        name: str = "test_character",
        level: int = 10,
        hp: int = 100,
        x: int = 0,
        y: int = 0,
        **kwargs
    ) -> Mock:
        """Create a mock character object with common attributes"""
        character = Mock()
        character.name = name
        character.level = level
        character.hp = hp
        character.max_hp = kwargs.get('max_hp', 100)
        character.x = x
        character.y = y
        character.xp = kwargs.get('xp', level * 250)
        character.gold = kwargs.get('gold', level * 100)
        character.cooldown = kwargs.get('cooldown', 0)
        character.cooldown_expiration = kwargs.get('cooldown_expiration', None)

        # Add additional attributes from kwargs
        for key, value in kwargs.items():
            if key not in ['max_hp', 'xp', 'gold', 'cooldown', 'cooldown_expiration']:
                setattr(character, key, value)

        return character

    @staticmethod
    def create_api_response_mock(
        status_code: int = 200,
        data: Any = None,
        **kwargs
    ) -> Mock:
        """Create a mock API response object"""
        response = Mock()
        response.status_code = status_code
        response.data = data or Mock()

        # Add additional attributes from kwargs
        for key, value in kwargs.items():
            setattr(response, key, value)

        return response

    @staticmethod
    def create_async_mock_with_return(return_value: Any = None) -> AsyncMock:
        """Create an AsyncMock with a specified return value"""
        async_mock = AsyncMock()
        async_mock.return_value = return_value
        return async_mock

    @staticmethod
    def create_cooldown_mock(
        total_seconds: int = 0,
        remaining_seconds: int = 0,
        expiration: datetime | None = None
    ) -> Mock:
        """Create a mock cooldown object"""
        cooldown = Mock()
        cooldown.total_seconds = total_seconds
        cooldown.remaining_seconds = remaining_seconds
        cooldown.expiration = expiration or (datetime.now() + timedelta(seconds=remaining_seconds))
        cooldown.is_active = remaining_seconds > 0
        return cooldown


class TestAssertions:
    """Common assertion helpers for tests"""

    @staticmethod
    def assert_mock_called_with_timeout(
        mock_obj: Mock,
        timeout: float = 1.0,
        call_count: int = 1
    ):
        """Assert that a mock was called within a timeout period"""
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            if mock_obj.call_count >= call_count:
                return
            time.sleep(0.01)

        pytest.fail(f"Mock was not called {call_count} times within {timeout} seconds")

    @staticmethod
    def assert_character_attributes(
        character: Mock,
        expected_attributes: dict[str, Any]
    ):
        """Assert that a character mock has expected attributes"""
        for attr_name, expected_value in expected_attributes.items():
            actual_value = getattr(character, attr_name, None)
            assert actual_value == expected_value, (
                f"Character attribute '{attr_name}' expected {expected_value}, "
                f"got {actual_value}"
            )

    @staticmethod
    def assert_api_response_structure(
        response: Mock,
        expected_status: int = 200,
        expected_data_attrs: list[str] | None = None
    ):
        """Assert that an API response has expected structure"""
        assert hasattr(response, 'status_code'), "Response missing status_code"
        assert response.status_code == expected_status, (
            f"Expected status {expected_status}, got {response.status_code}"
        )

        if expected_data_attrs:
            assert hasattr(response, 'data'), "Response missing data attribute"
            for attr in expected_data_attrs:
                assert hasattr(response.data, attr), (
                    f"Response data missing expected attribute: {attr}"
                )


class TestHelpers:
    """Helper functions for common test operations"""

    @staticmethod
    def create_test_directory_structure(temp_dir: Path) -> dict[str, Path]:
        """Create a temporary directory structure for tests"""
        directories = {
            'config': temp_dir / 'config',
            'data': temp_dir / 'data',
            'logs': temp_dir / 'logs',
            'cache': temp_dir / 'cache'
        }

        for directory in directories.values():
            directory.mkdir(parents=True, exist_ok=True)

        return directories

    @staticmethod
    def create_test_config_file(
        config_dir: Path,
        config_data: dict[str, Any],
        filename: str = "test_config.yaml"
    ) -> Path:
        """Create a test configuration file"""

        config_file = config_dir / filename
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        return config_file

    @staticmethod
    async def wait_for_condition(
        condition_func,
        timeout: float = 5.0,
        check_interval: float = 0.1
    ) -> bool:
        """Wait for a condition to become true within a timeout"""
        start_time = datetime.now()

        while (datetime.now() - start_time).total_seconds() < timeout:
            if condition_func():
                return True
            await asyncio.sleep(check_interval)

        return False

    @staticmethod
    def generate_test_data_sequence(
        base_data: dict[str, Any],
        modifications: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Generate a sequence of test data by applying modifications"""
        sequence = []

        for modification in modifications:
            data = base_data.copy()
            data.update(modification)
            sequence.append(data)

        return sequence


# Test configuration setup
def pytest_configure(config):
    """Configure pytest with custom settings"""
    configure_test_environment()


# Initialize test environment
configure_test_environment()
