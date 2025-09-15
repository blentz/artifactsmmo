"""
Common test configuration and fixtures

This module provides pytest configuration and fixtures that are available
to all test modules in the test suite.
"""

import pytest

from tests import MockFactory, TestAssertions, TestHelpers
from src.ai_player.state.character_game_state import CharacterGameState


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


@pytest.fixture
def valid_character_state():
    """Create a valid CharacterGameState for testing."""
    return CharacterGameState(
        name="test_character",
        level=10,
        xp=1000,
        gold=500,
        hp=100,
        max_hp=100,
        x=5,
        y=5,
        mining_level=5,
        mining_xp=100,
        woodcutting_level=5,
        woodcutting_xp=100,
        fishing_level=5,
        fishing_xp=100,
        weaponcrafting_level=5,
        weaponcrafting_xp=100,
        gearcrafting_level=5,
        gearcrafting_xp=100,
        jewelrycrafting_level=5,
        jewelrycrafting_xp=100,
        cooking_level=5,
        cooking_xp=100,
        alchemy_level=5,
        alchemy_xp=100,
        cooldown=0
    )


@pytest.fixture
def low_level_character_state():
    """Create a low-level CharacterGameState for testing."""
    return CharacterGameState(
        name="low_level_character",
        level=1,
        xp=0,
        gold=100,
        hp=50,
        max_hp=50,
        x=0,
        y=0,
        mining_level=1,
        mining_xp=0,
        woodcutting_level=1,
        woodcutting_xp=0,
        fishing_level=1,
        fishing_xp=0,
        weaponcrafting_level=1,
        weaponcrafting_xp=0,
        gearcrafting_level=1,
        gearcrafting_xp=0,
        jewelrycrafting_level=1,
        jewelrycrafting_xp=0,
        cooking_level=1,
        cooking_xp=0,
        alchemy_level=1,
        alchemy_xp=0,
        cooldown=0
    )
