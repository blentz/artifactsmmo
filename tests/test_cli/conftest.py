"""
CLI test configuration and fixtures

This module provides pytest configuration and fixtures specifically
for CLI testing modules.
"""

import pytest

from tests.test_cli import (
    CLIMockFactory,
    CLITestAssertions,
    CLITestHelpers,
)


# CLI-specific fixtures
@pytest.fixture
def cli_mock_factory():
    """Provide CLIMockFactory for tests"""
    return CLIMockFactory


@pytest.fixture
def cli_assertions():
    """Provide CLITestAssertions for tests"""
    return CLITestAssertions


@pytest.fixture
def cli_helpers():
    """Provide CLITestHelpers for tests"""
    return CLITestHelpers


@pytest.fixture
def mock_cli_manager():
    """Provide a mock CLI manager for testing"""
    return CLIMockFactory.create_cli_manager_mock()


@pytest.fixture
def mock_argument_parser():
    """Provide a mock argument parser for testing"""
    return CLIMockFactory.create_argument_parser_mock()


@pytest.fixture
def mock_api_client():
    """Provide a mock API client for testing"""
    return CLIMockFactory.create_api_client_mock()


@pytest.fixture
def mock_character():
    """Provide a mock character for testing"""
    return CLIMockFactory.create_character_mock()


@pytest.fixture
def mock_ai_player():
    """Provide a mock AI player for testing"""
    return CLIMockFactory.create_ai_player_mock()


@pytest.fixture
def mock_diagnostic_commands():
    """Provide a mock diagnostic commands object for testing"""
    return CLIMockFactory.create_diagnostic_commands_mock()


@pytest.fixture
def sample_parsed_args():
    """Provide sample parsed arguments for testing"""
    return CLIMockFactory.create_parsed_args_mock()


@pytest.fixture
def character_creation_scenario():
    """Provide a character creation test scenario"""
    return CLITestHelpers.create_character_creation_scenario()


@pytest.fixture
def ai_player_scenario():
    """Provide an AI player test scenario"""
    return CLITestHelpers.create_ai_player_scenario()


@pytest.fixture
def diagnostic_scenario():
    """Provide a diagnostic test scenario"""
    return CLITestHelpers.create_diagnostic_scenario()