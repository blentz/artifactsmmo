"""
Targeted tests for CLI main module to improve coverage.

This test module focuses on testing the actual code paths that can be
tested without complex mocking, targeting the utility functions and
basic operations that contribute to coverage.
"""

import pytest
import string
from unittest.mock import AsyncMock, Mock, patch

from src.cli.main import generate_random_character_name, CLIManager


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
        assert cli_manager.cache_manager is None
        assert cli_manager.action_registry is None
        assert cli_manager.goal_manager is None
        assert cli_manager.state_manager is None
        assert cli_manager.ai_player is None
        assert cli_manager.diagnostic_commands is None

    @patch('src.cli.main.APIClientWrapper')
    def test_cli_manager_setup_api_client(self, mock_api_wrapper):
        """Test API client setup."""
        mock_api_instance = Mock()
        mock_api_wrapper.return_value = mock_api_instance
        
        cli_manager = CLIManager()
        cli_manager.setup_api_client()
        
        assert cli_manager.api_client == mock_api_instance
        mock_api_wrapper.assert_called_once()

    @patch('src.cli.main.CacheManager')
    def test_cli_manager_setup_cache_manager(self, mock_cache_manager):
        """Test cache manager setup."""
        mock_cache_instance = Mock()
        mock_cache_manager.return_value = mock_cache_instance
        
        cli_manager = CLIManager()
        cli_manager.api_client = Mock()  # Required for cache manager
        cli_manager.setup_cache_manager()
        
        assert cli_manager.cache_manager == mock_cache_instance
        mock_cache_manager.assert_called_once_with(cli_manager.api_client)

    def test_cli_manager_setup_action_registry(self):
        """Test action registry setup."""
        cli_manager = CLIManager()
        
        with patch('src.cli.main.get_global_registry') as mock_get_registry:
            mock_registry = Mock()
            mock_get_registry.return_value = mock_registry
            
            cli_manager.setup_action_registry()
            
            assert cli_manager.action_registry == mock_registry
            mock_get_registry.assert_called_once()

    @patch('src.cli.main.GoalManager')
    def test_cli_manager_setup_goal_manager(self, mock_goal_manager):
        """Test goal manager setup."""
        mock_goal_instance = Mock()
        mock_goal_manager.return_value = mock_goal_instance
        
        cli_manager = CLIManager()
        cli_manager.action_registry = Mock()
        cli_manager.api_client = Mock()
        cli_manager.cache_manager = Mock()
        
        cli_manager.setup_goal_manager()
        
        assert cli_manager.goal_manager == mock_goal_instance
        mock_goal_manager.assert_called_once()

    @patch('src.cli.main.StateManager')
    def test_cli_manager_setup_state_manager(self, mock_state_manager):
        """Test state manager setup."""
        mock_state_instance = Mock()
        mock_state_manager.return_value = mock_state_instance
        
        cli_manager = CLIManager()
        cli_manager.api_client = Mock()
        
        cli_manager.setup_state_manager()
        
        assert cli_manager.state_manager == mock_state_instance
        mock_state_manager.assert_called_once_with(cli_manager.api_client)

    def test_cli_manager_setup_diagnostic_commands(self):
        """Test diagnostic commands setup."""
        cli_manager = CLIManager()
        cli_manager.action_registry = Mock()
        cli_manager.goal_manager = Mock()
        cli_manager.api_client = Mock()
        
        with patch('src.cli.main.DiagnosticCommands') as mock_diagnostic_commands:
            mock_diagnostic_instance = Mock()
            mock_diagnostic_commands.return_value = mock_diagnostic_instance
            
            cli_manager.setup_diagnostic_commands()
            
            assert cli_manager.diagnostic_commands == mock_diagnostic_instance
            mock_diagnostic_commands.assert_called_once()

    @patch('src.cli.main.AIPlayer')
    def test_cli_manager_setup_ai_player(self, mock_ai_player):
        """Test AI player setup."""
        mock_ai_instance = Mock()
        mock_ai_player.return_value = mock_ai_instance
        
        cli_manager = CLIManager()
        cli_manager.api_client = Mock()
        cli_manager.goal_manager = Mock()
        cli_manager.state_manager = Mock()
        
        # Mock ActionExecutor
        with patch('src.cli.main.ActionExecutor') as mock_action_executor:
            mock_executor_instance = Mock()
            mock_action_executor.return_value = mock_executor_instance
            
            cli_manager.setup_ai_player()
            
            assert cli_manager.ai_player == mock_ai_instance
            mock_ai_player.assert_called_once()

    def test_cli_manager_setup_logging(self):
        """Test logging setup."""
        cli_manager = CLIManager()
        
        # Test that we can call setup_logging without error
        try:
            cli_manager.setup_logging()
            success = True
        except Exception:
            success = False
        
        assert success

    def test_cli_manager_has_required_components_false(self):
        """Test component requirements check when missing."""
        cli_manager = CLIManager()
        
        required_components = ['api_client', 'action_registry']
        result = cli_manager.has_required_components(required_components)
        
        assert result is False

    def test_cli_manager_has_required_components_true(self):
        """Test component requirements check when present."""
        cli_manager = CLIManager()
        cli_manager.api_client = Mock()
        cli_manager.action_registry = Mock()
        
        required_components = ['api_client', 'action_registry']
        result = cli_manager.has_required_components(required_components)
        
        assert result is True


class TestArgumentParsing:
    """Test argument parsing functionality."""

    def test_create_parser_basic(self):
        """Test basic argument parser creation."""
        from src.cli.main import create_parser
        
        parser = create_parser()
        assert parser is not None
        
        # Test that we can parse basic arguments without error
        args = parser.parse_args(['list'])
        assert args.command == 'list'

    def test_create_parser_help_available(self):
        """Test that help is available for parser."""
        from src.cli.main import create_parser
        
        parser = create_parser()
        
        # Test that help action works (will exit, so we catch SystemExit)
        with pytest.raises(SystemExit):
            parser.parse_args(['--help'])

    def test_create_parser_subcommands(self):
        """Test that main subcommands are available."""
        from src.cli.main import create_parser
        
        parser = create_parser()
        
        # Test some key subcommands can be parsed
        test_commands = [
            ['list'],
            ['create', 'test_char'],
            ['delete', 'test_char'],
            ['start', 'test_char']
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

    @patch('src.cli.main.asyncio.run')
    @patch('src.cli.main.create_parser')
    def test_main_function_basic(self, mock_create_parser, mock_asyncio_run):
        """Test main function basic execution."""
        # Mock parser
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.command = 'list'
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        
        # Import and test main
        from src.cli.main import main
        
        with patch('sys.argv', ['main.py', 'list']):
            main()
            
        mock_create_parser.assert_called_once()
        mock_asyncio_run.assert_called_once()

    def test_main_function_exists(self):
        """Test that main function exists and is callable."""
        from src.cli.main import main
        assert callable(main)


class TestStringRepresentation:
    """Test string representations."""

    def test_cli_manager_str_representation(self):
        """Test CLIManager string representation."""
        cli_manager = CLIManager()
        str_repr = str(cli_manager)
        assert isinstance(str_repr, str)
        assert len(str_repr) > 0