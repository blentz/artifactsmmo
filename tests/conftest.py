"""
Common test configuration and fixtures

This module provides pytest configuration and fixtures that are available
to all test modules in the test suite.
"""

import pytest

from tests import MockFactory, TestAssertions, TestHelpers


# Common fixtures that can be used across all test modules
@pytest.fixture
def mock_factory():
    """Provide MockFactory instance for tests"""
    return MockFactory


@pytest.fixture
def test_assertions():
    """Provide TestAssertions instance for tests"""
    return TestAssertions


@pytest.fixture
def test_helpers():
    """Provide TestHelpers instance for tests"""
    return TestHelpers


@pytest.fixture
def sample_character():
    """Provide a sample character mock for testing"""
    return MockFactory.create_character_mock()


@pytest.fixture
def sample_api_response():
    """Provide a sample API response mock for testing"""
    return MockFactory.create_api_response_mock()
