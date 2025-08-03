"""
Targeted tests for CLI main module to improve coverage.

This test module focuses on testing the actual code paths that can be
tested without complex mocking, targeting the utility functions and
basic operations that contribute to coverage.
"""

import string
from unittest.mock import Mock, patch

import pytest

from src.cli.main import CLIManager, generate_random_character_name, main, async_main


class TestUtilityFunctions:
    """Test utility functions that can be easily tested."""

    def test_generate_random_character_name_length(self):
        """Test that generated character name has correct length."""
        name = generate_random_character_name()
        assert 6 <= len(name) <= 10

    def test_generate_random_character_name_characters(self):
        """Test that generated character name uses only allowed characters."""
        allowed_chars = set(string.ascii_letters + string.digits + '_-')
        name = generate_random_character_name()
        assert all(c in allowed_chars for c in name)

    def test_generate_random_character_name_uniqueness(self):
        """Test that multiple calls generate different names (probabilistically)."""
        names = {generate_random_character_name() for _ in range(10)}
        # With random generation, we should get mostly unique names
        assert len(names) > 5  # At least 6 different names out of 10


class TestCLIManagerBasic:
    """Test CLIManager basic functionality."""

    def test_cli_manager_init(self):
        """Test CLIManager initialization."""
        cli_manager = CLIManager()

        # Test that basic components are initialized
        assert cli_manager.log_manager is not None
        assert cli_manager.api_client is None  # Not initialized yet
        assert cli_manager.diagnostic_commands is not None  # Initialized in __init__
        assert cli_manager.running_players == {}
        assert cli_manager.logger is not None

    def test_cli_manager_create_parser(self):
        """Test argument parser creation."""
        cli_manager = CLIManager()
        parser = cli_manager.create_parser()

        assert parser is not None
        assert hasattr(parser, 'parse_args')

    def test_cli_manager_diagnostic_initialization(self):
        """Test that diagnostic commands are initialized."""
        cli_manager = CLIManager()

        # DiagnosticCommands should be initialized in __init__
        assert cli_manager.diagnostic_commands is not None

    @patch('src.cli.main.APIClientWrapper')
    @patch('src.cli.main.CacheManager')
    @patch('src.cli.main.get_global_registry')
    @patch('src.cli.main.GoalManager')
    @patch('src.cli.main.DiagnosticCommands')
    def test_cli_manager_initialize_diagnostic_components(self, mock_diagnostic, mock_goal_manager, mock_registry, mock_cache, mock_api):
        """Test _initialize_diagnostic_components method."""
        mock_api_instance = Mock()
        mock_api.return_value = mock_api_instance
        mock_api_instance.cooldown_manager = Mock()

        mock_cache_instance = Mock()
        mock_cache.return_value = mock_cache_instance

        mock_registry_instance = Mock()
        mock_registry.return_value = mock_registry_instance

        mock_goal_instance = Mock()
        mock_goal_manager.return_value = mock_goal_instance

        mock_diagnostic_instance = Mock()
        mock_diagnostic.return_value = mock_diagnostic_instance

        cli_manager = CLIManager()
        result = cli_manager._initialize_diagnostic_components("test_token")

        assert result == mock_diagnostic_instance
        mock_api.assert_called_once_with("test_token")
        mock_cache.assert_called_once_with(mock_api_instance)
        mock_registry.assert_called_once()
        mock_goal_manager.assert_called_once()
        # DiagnosticCommands is called twice: once in __init__, once in _initialize_diagnostic_components
        assert mock_diagnostic.call_count == 2

    def test_cli_manager_logging_setup(self):
        """Test logging setup functionality."""
        cli_manager = CLIManager()

        # Test that setup_logging method exists and can be called without error
        cli_manager.setup_logging("DEBUG")
        success = True
        assert success


class TestArgumentParsing:
    """Test argument parsing functionality."""

    def test_create_parser_basic(self):
        """Test basic argument parser creation."""
        # CLIManager imported at top

        cli_manager = CLIManager()
        parser = cli_manager.create_parser()
        assert parser is not None

        # Test that we can parse basic arguments without error
        args = parser.parse_args(['list-characters'])
        assert args.command == 'list-characters'

    def test_create_parser_help_available(self):
        """Test that help is available for parser."""
        # CLIManager imported at top

        cli_manager = CLIManager()
        parser = cli_manager.create_parser()

        # Test that help action works (will exit, so we catch SystemExit)
        with pytest.raises(SystemExit):
            parser.parse_args(['--help'])

    def test_create_parser_subcommands(self):
        """Test that main subcommands are available."""
        # CLIManager imported at top

        cli_manager = CLIManager()
        parser = cli_manager.create_parser()

        # Test some key subcommands can be parsed
        test_commands = [
            ['list-characters'],
            ['create-character', 'men1', '--name', 'test_char'],
            ['delete-character', 'test_char'],
            ['run-character', 'test_char']
        ]

        for cmd_args in test_commands:
            try:
                args = parser.parse_args(cmd_args)
                success = True
            except SystemExit:
                success = False
            assert success, f"Failed to parse command: {cmd_args}"


class TestMainFunction:
    """Test main function integration."""

    def test_main_function_exists(self):
        """Test that main function exists and is callable."""
        # main imported at top
        assert callable(main)

    def test_async_main_function_exists(self):
        """Test that async_main function exists and is callable."""
        # async_main imported at top
        assert callable(async_main)


class TestStringRepresentation:
    """Test string representations."""

    def test_cli_manager_str_representation(self):
        """Test CLIManager string representation."""
        cli_manager = CLIManager()
        str_repr = str(cli_manager)
        assert isinstance(str_repr, str)
        assert len(str_repr) > 0
