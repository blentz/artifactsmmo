"""
Pytest configuration and fixtures for AI Player tests

This module provides pytest fixtures specific to the AI Player test suite,
making them available to all test files in the test_ai_player package.
"""

import pytest

from tests.test_ai_player import (
    AIPlayerMockFactory,
    AIPlayerTestAssertions,
    AIPlayerTestHelpers,
)


# Import all fixtures from the package __init__.py
@pytest.fixture
def ai_player_mock_factory():
    """Provide AIPlayerMockFactory for tests"""
    return AIPlayerMockFactory


@pytest.fixture
def ai_player_assertions():
    """Provide AIPlayerTestAssertions for tests"""
    return AIPlayerTestAssertions


@pytest.fixture
def ai_player_helpers():
    """Provide AIPlayerTestHelpers for tests"""
    return AIPlayerTestHelpers


@pytest.fixture
def sample_game_state():
    """Provide a sample game state for testing"""
    return AIPlayerMockFactory.create_game_state_mock()


@pytest.fixture
def sample_action():
    """Provide a sample action for testing"""
    return AIPlayerMockFactory.create_base_action_mock()


@pytest.fixture
def sample_goal():
    """Provide a sample goal for testing"""
    return AIPlayerMockFactory.create_goal_mock()


@pytest.fixture
def sample_ai_player():
    """Provide a sample AI player for testing"""
    return AIPlayerMockFactory.create_ai_player_mock()
