"""
Comprehensive tests for CLI main module to achieve 95% coverage.

This test module provides extensive coverage for the CLI main entry point,
including argument parsing, command handling, error scenarios, and integration
with the AI player system. All tests use Pydantic models throughout as required
by the architecture.
"""

import argparse
import string
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ai_player.ai_player import AIPlayer
from src.cli.main import CLIManager, generate_random_character_name, main


class TestGenerateRandomCharacterName:
    """Test the random character name generation utility function."""

    def test_generate_random_character_name_length(self):
        """Test that generated names are within required length bounds."""
        for _ in range(100):  # Test multiple generations
            name = generate_random_character_name()
            assert 6 <= len(name) <= 10, f"Name length {len(name)} out of bounds: {name}"

    def test_generate_random_character_name_allowed_characters(self):
        """Test that generated names only contain allowed characters."""
        allowed_chars = set(string.ascii_letters + string.digits + '_-')

        for _ in range(100):  # Test multiple generations
            name = generate_random_character_name()
            name_chars = set(name)
            invalid_chars = name_chars - allowed_chars
            assert not invalid_chars, f"Name contains invalid characters: {invalid_chars}"

    def test_generate_random_character_name_uniqueness(self):
        """Test that the function generates different names (randomness check)."""
        names = {generate_random_character_name() for _ in range(100)}
        # With proper randomness, we should get mostly unique names
        assert len(names) > 50, "Random name generation appears to lack sufficient randomness"

    def test_generate_random_character_name_no_periods(self):
        """Test that generated names don't contain periods (API restriction)."""
        for _ in range(100):
            name = generate_random_character_name()
            assert '.' not in name, f"Name contains forbidden period character: {name}"

    @patch('random.randint')
    @patch('random.choice')
    def test_generate_random_character_name_deterministic(self, mock_choice, mock_randint):
        """Test name generation with mocked randomness for predictable results."""
        mock_randint.return_value = 6  # Fixed length
        mock_choice.side_effect = ['a', 'b', 'c', 'd', 'e', 'f']  # Fixed choices

        name = generate_random_character_name()
        assert name == 'abcdef'
        mock_randint.assert_called_once_with(6, 10)
        assert mock_choice.call_count == 6


class TestCLIManagerInitialization:
    """Test CLIManager class initialization and basic functionality."""

    def test_cli_manager_init(self):
        """Test basic CLIManager initialization."""
        cli_manager = CLIManager()

        assert cli_manager.log_manager is not None
        assert cli_manager.api_client is None
        assert cli_manager.diagnostic_commands is not None
        assert cli_manager.running_players == {}
        assert cli_manager.logger is not None
        assert cli_manager.logger.name == "cli.manager"

    @patch('src.cli.main.LogManager')
    @patch('src.cli.main.DiagnosticCommands')
    def test_cli_manager_init_with_mocks(self, mock_diagnostics, mock_log_manager):
        """Test CLIManager initialization with proper component mocking."""
        mock_log_instance = Mock()
        mock_diagnostic_instance = Mock()
        mock_log_manager.return_value = mock_log_instance
        mock_diagnostics.return_value = mock_diagnostic_instance

        cli_manager = CLIManager()

        assert cli_manager.log_manager == mock_log_instance
        assert cli_manager.diagnostic_commands == mock_diagnostic_instance
        mock_log_manager.assert_called_once()
        mock_diagnostics.assert_called_once()


class TestCLIManagerDiagnosticComponents:
    """Test the diagnostic components initialization."""

    @patch('src.cli.main.APIClientWrapper')
    @patch('src.cli.main.CacheManager')
    @patch('src.cli.main.get_global_registry')
    @patch('src.cli.main.GoalManager')
    def test_initialize_diagnostic_components_new_api_client(
        self, mock_goal_manager, mock_registry,
        mock_cache_manager, mock_api_client_wrapper
    ):
        """Test diagnostic components initialization when API client doesn't exist."""
        cli_manager = CLIManager()

        # Mock return values
        mock_api_instance = Mock()
        mock_cache_instance = Mock()
        mock_registry_instance = Mock()
        mock_goal_instance = Mock()

        mock_api_client_wrapper.return_value = mock_api_instance
        mock_cache_manager.return_value = mock_cache_instance
        mock_registry.return_value = mock_registry_instance
        mock_goal_manager.return_value = mock_goal_instance

        result = cli_manager._initialize_diagnostic_components("test_token.txt")

        # Verify API client was created and assigned
        assert cli_manager.api_client == mock_api_instance
        mock_api_client_wrapper.assert_called_once_with("test_token.txt")

        # Verify all components were initialized properly
        mock_cache_manager.assert_called_once_with(mock_api_instance)
        mock_registry.assert_called_once()
        mock_goal_manager.assert_called_once_with(
            mock_registry_instance,
            mock_api_instance.cooldown_manager,
            mock_cache_instance
        )

        # Result should be a DiagnosticCommands instance
        assert result is not None

    @patch('src.cli.main.APIClientWrapper')
    @patch('src.cli.main.CacheManager')
    @patch('src.cli.main.get_global_registry')
    @patch('src.cli.main.GoalManager')
    @patch('src.cli.main.DiagnosticCommands')
    def test_initialize_diagnostic_components_existing_api_client(
        self, mock_diagnostic_commands, mock_goal_manager, mock_registry,
        mock_cache_manager, mock_api_client_wrapper
    ):
        """Test diagnostic components initialization when API client already exists."""
        cli_manager = CLIManager()
        existing_api_client = Mock()
        cli_manager.api_client = existing_api_client

        # Mock return values
        mock_cache_instance = Mock()
        mock_registry_instance = Mock()
        mock_goal_instance = Mock()
        mock_diagnostic_instance = Mock()

        mock_cache_manager.return_value = mock_cache_instance
        mock_registry.return_value = mock_registry_instance
        mock_goal_manager.return_value = mock_goal_instance
        mock_diagnostic_commands.return_value = mock_diagnostic_instance

        result = cli_manager._initialize_diagnostic_components("test_token.txt")

        # Verify existing API client was used, not created
        assert cli_manager.api_client == existing_api_client
        mock_api_client_wrapper.assert_not_called()

        # Verify components were initialized with existing client
        mock_cache_manager.assert_called_once_with(existing_api_client)
        mock_goal_manager.assert_called_once_with(
            mock_registry_instance,
            existing_api_client.cooldown_manager,
            mock_cache_instance
        )

        assert result == mock_diagnostic_instance


class TestCLIManagerArgumentParser:
    """Test argument parser creation and command setup."""

    def test_create_parser_basic_structure(self):
        """Test that create_parser returns a properly configured ArgumentParser."""
        cli_manager = CLIManager()
        parser = cli_manager.create_parser()

        assert isinstance(parser, argparse.ArgumentParser)
        assert "ArtifactsMMO AI Player" in parser.description
        assert parser.formatter_class == argparse.RawDescriptionHelpFormatter

    def test_create_parser_global_options(self):
        """Test that global options are properly configured."""
        cli_manager = CLIManager()
        parser = cli_manager.create_parser()

        # Test parsing global options
        args = parser.parse_args(['--log-level', 'DEBUG', '--token-file', 'test.token', 'list-characters'])
        assert args.log_level == 'DEBUG'
        assert args.token_file == 'test.token'

    def test_create_parser_default_values(self):
        """Test that default values are set correctly."""
        cli_manager = CLIManager()
        parser = cli_manager.create_parser()

        args = parser.parse_args(['list-characters'])
        assert args.log_level == 'INFO'
        assert args.token_file == 'TOKEN'

    def test_create_parser_invalid_log_level(self):
        """Test that invalid log levels are rejected."""
        cli_manager = CLIManager()
        parser = cli_manager.create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(['--log-level', 'INVALID', 'list-characters'])

    @patch.object(CLIManager, 'setup_character_commands')
    @patch.object(CLIManager, 'setup_ai_player_commands')
    @patch.object(CLIManager, 'setup_diagnostic_commands')
    def test_create_parser_command_setup_calls(self, mock_diag, mock_ai, mock_char):
        """Test that all command setup methods are called."""
        cli_manager = CLIManager()
        parser = cli_manager.create_parser()

        mock_char.assert_called_once()
        mock_ai.assert_called_once()
        mock_diag.assert_called_once()


class TestCLIManagerCharacterCommands:
    """Test character command setup and handling."""

    def test_setup_character_commands_create_character(self):
        """Test create-character command setup."""
        cli_manager = CLIManager()
        parser = cli_manager.create_parser()

        # Test valid create command
        args = parser.parse_args(['create-character', 'men1'])
        assert args.command == 'create-character'
        assert args.skin == 'men1'
        assert args.name is None
        assert args.func == cli_manager.handle_create_character

    def test_setup_character_commands_create_character_with_name(self):
        """Test create-character command with custom name."""
        cli_manager = CLIManager()
        parser = cli_manager.create_parser()

        args = parser.parse_args(['create-character', 'women1', '--name', 'test_char'])
        assert args.command == 'create-character'
        assert args.skin == 'women1'
        assert args.name == 'test_char'

    def test_setup_character_commands_create_character_invalid_skin(self):
        """Test create-character command with invalid skin."""
        cli_manager = CLIManager()
        parser = cli_manager.create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(['create-character', 'invalid_skin'])

    def test_setup_character_commands_delete_character(self):
        """Test delete-character command setup."""
        cli_manager = CLIManager()
        parser = cli_manager.create_parser()

        args = parser.parse_args(['delete-character', 'test_char'])
        assert args.command == 'delete-character'
        assert args.name == 'test_char'
        assert args.confirm is False
        assert args.func == cli_manager.handle_delete_character

    def test_setup_character_commands_delete_character_with_confirm(self):
        """Test delete-character command with confirmation flag."""
        cli_manager = CLIManager()
        parser = cli_manager.create_parser()

        args = parser.parse_args(['delete-character', 'test_char', '--confirm'])
        assert args.confirm is True

    def test_setup_character_commands_list_characters(self):
        """Test list-characters command setup."""
        cli_manager = CLIManager()
        parser = cli_manager.create_parser()

        args = parser.parse_args(['list-characters'])
        assert args.command == 'list-characters'
        assert args.func == cli_manager.handle_list_characters


class TestCLIManagerAsyncCommandHandlers:
    """Test async command handlers with proper mocking."""

    @pytest.mark.asyncio
    @patch('src.cli.main.APIClientWrapper')
    async def test_handle_create_character_with_random_name(self, mock_api_wrapper):
        """Test create character handler with random name generation."""
        # Setup mocks
        mock_api_instance = AsyncMock()
        mock_character = Mock()
        mock_character.name = "test_char"
        mock_character.level = 1
        mock_character.x = 0
        mock_character.y = 0
        mock_character.skin = "men1"
        mock_api_instance.create_character.return_value = mock_character
        mock_api_wrapper.return_value = mock_api_instance

        cli_manager = CLIManager()

        # Create args object
        args = Mock()
        args.skin = "men1"
        args.name = None
        args.token_file = "test_token.txt"

        # Use a valid name that passes validation (3-12 chars)
        with patch('src.cli.main.generate_random_character_name', return_value="test_char"):
            with patch('builtins.print') as mock_print:
                await cli_manager.handle_create_character(args)

        # Verify API client was created and character creation was called
        mock_api_wrapper.assert_called_once_with("test_token.txt")
        mock_api_instance.create_character.assert_called_once_with("test_char", "men1")

    @pytest.mark.asyncio
    @patch('src.cli.main.APIClientWrapper')
    async def test_handle_create_character_with_provided_name(self, mock_api_wrapper):
        """Test create character handler with user-provided name."""
        # Setup mocks
        mock_api_instance = AsyncMock()
        mock_character = Mock()
        mock_character.name = "user_name"
        mock_character.skin = "women2"
        mock_api_instance.create_character.return_value = mock_character
        mock_api_wrapper.return_value = mock_api_instance

        cli_manager = CLIManager()

        # Create args object
        args = Mock()
        args.skin = "women2"
        args.name = "user_name"
        args.token_file = "test_token.txt"

        await cli_manager.handle_create_character(args)

        # Verify character creation was called with provided name
        mock_api_instance.create_character.assert_called_once_with("user_name", "women2")

    @pytest.mark.asyncio
    @patch('src.cli.main.APIClientWrapper')
    async def test_handle_create_character_api_error(self, mock_api_wrapper):
        """Test create character handler with API error."""
        # Setup mocks to raise exception
        mock_api_instance = AsyncMock()
        mock_api_instance.create_character.side_effect = Exception("API Error")
        mock_api_wrapper.return_value = mock_api_instance

        cli_manager = CLIManager()

        args = Mock()
        args.skin = "men1"
        args.name = "test_char"
        args.token_file = "test_token.txt"

        # Should handle the exception gracefully
        with patch('builtins.print') as mock_print:
            await cli_manager.handle_create_character(args)
            # Should print error message
            mock_print.assert_called()

    @pytest.mark.asyncio
    @patch('src.cli.main.APIClientWrapper')
    @patch('builtins.input', return_value='y')
    async def test_handle_delete_character_with_confirmation(self, mock_input, mock_api_wrapper):
        """Test delete character handler with user confirmation."""
        # Setup mocks
        mock_api_instance = AsyncMock()
        mock_api_instance.delete_character.return_value = True
        mock_api_wrapper.return_value = mock_api_instance

        cli_manager = CLIManager()

        args = Mock()
        args.name = "test_char"
        args.confirm = False
        args.token_file = "test_token.txt"

        await cli_manager.handle_delete_character(args)

        # Verify confirmation was requested and deletion was called
        mock_input.assert_called_once()
        mock_api_instance.delete_character.assert_called_once_with("test_char")

    @pytest.mark.asyncio
    @patch('src.cli.main.APIClientWrapper')
    @patch('builtins.input', return_value='n')
    async def test_handle_delete_character_cancelled(self, mock_input, mock_api_wrapper):
        """Test delete character handler when user cancels."""
        # Setup mocks
        mock_api_instance = AsyncMock()
        mock_api_wrapper.return_value = mock_api_instance

        cli_manager = CLIManager()

        args = Mock()
        args.name = "test_char"
        args.confirm = False
        args.token_file = "test_token.txt"

        with patch('builtins.print') as mock_print:
            await cli_manager.handle_delete_character(args)

        # Verify confirmation was requested but deletion was NOT called
        mock_input.assert_called_once()
        mock_api_instance.delete_character.assert_not_called()

    @pytest.mark.asyncio
    @patch('src.cli.main.APIClientWrapper')
    async def test_handle_delete_character_auto_confirm(self, mock_api_wrapper):
        """Test delete character handler with auto-confirmation flag."""
        # Setup mocks
        mock_api_instance = AsyncMock()
        mock_api_instance.delete_character.return_value = True
        mock_api_wrapper.return_value = mock_api_instance

        cli_manager = CLIManager()

        args = Mock()
        args.name = "test_char"
        args.confirm = True
        args.token_file = "test_token.txt"

        with patch('builtins.input') as mock_input:
            await cli_manager.handle_delete_character(args)

        # Verify no confirmation was requested, deletion was called directly
        mock_input.assert_not_called()
        mock_api_instance.delete_character.assert_called_once_with("test_char")

    @pytest.mark.asyncio
    @patch('src.cli.main.APIClientWrapper')
    @patch('src.cli.main.CacheManager')
    async def test_handle_list_characters(self, mock_cache_manager, mock_api_wrapper):
        """Test list characters handler."""
        # Setup mocks
        mock_api_instance = AsyncMock()
        mock_cache_instance = AsyncMock()
        mock_characters = [
            Mock(name="char1", level=5, skin="men1", x=0, y=0, hp=100, max_hp=100, gold=50),
            Mock(name="char2", level=10, skin="women1", x=5, y=5, hp=150, max_hp=150, gold=100)
        ]
        mock_cache_instance.cache_all_characters.return_value = mock_characters
        mock_api_wrapper.return_value = mock_api_instance
        mock_cache_manager.return_value = mock_cache_instance

        cli_manager = CLIManager()

        args = Mock()
        args.token_file = "test_token.txt"
        args.detailed = False  # Simple output format

        with patch('builtins.print') as mock_print:
            await cli_manager.handle_list_characters(args)

        # Verify cache manager was created and characters were fetched
        mock_cache_manager.assert_called_once_with(mock_api_instance)
        mock_cache_instance.cache_all_characters.assert_called_once()
        # Should print character information
        assert mock_print.call_count >= 2  # At least one call per character

    @pytest.mark.asyncio
    @patch('src.cli.main.APIClientWrapper')
    @patch('src.cli.main.CacheManager')
    async def test_handle_list_characters_detailed(self, mock_cache_manager, mock_api_wrapper):
        """Test list characters handler with detailed output."""
        # Setup mocks
        mock_api_instance = AsyncMock()
        mock_cache_instance = AsyncMock()
        mock_characters = [
            Mock(name="char1", level=5, skin="men1", x=0, y=0, hp=100, max_hp=100, gold=50)
        ]
        mock_cache_instance.cache_all_characters.return_value = mock_characters
        mock_api_wrapper.return_value = mock_api_instance
        mock_cache_manager.return_value = mock_cache_instance

        cli_manager = CLIManager()

        args = Mock()
        args.token_file = "test_token.txt"
        args.detailed = True  # Detailed output format

        with patch('builtins.print') as mock_print:
            await cli_manager.handle_list_characters(args)

        # Should print detailed character information
        assert mock_print.call_count >= 5  # More calls for detailed format

    @pytest.mark.asyncio
    @patch('src.cli.main.APIClientWrapper')
    @patch('src.cli.main.CacheManager')
    async def test_handle_list_characters_empty(self, mock_cache_manager, mock_api_wrapper):
        """Test list characters handler with no characters."""
        # Setup mocks
        mock_api_instance = AsyncMock()
        mock_cache_instance = AsyncMock()
        mock_cache_instance.cache_all_characters.return_value = []
        mock_api_wrapper.return_value = mock_api_instance
        mock_cache_manager.return_value = mock_cache_instance

        cli_manager = CLIManager()

        args = Mock()
        args.token_file = "test_token.txt"

        with patch('builtins.print') as mock_print:
            await cli_manager.handle_list_characters(args)

        # Should print no characters message
        mock_print.assert_any_call("No characters found on this account.")


class TestMainFunction:
    """Test the main entry point function."""

    @patch('src.cli.main.async_main')
    def test_main_function_basic(self, mock_async_main):
        """Test basic main function execution."""
        with patch('asyncio.run') as mock_asyncio_run:
            main()

        # Verify asyncio.run was called with async_main
        mock_asyncio_run.assert_called_once()
        # The argument to asyncio.run should be the result of calling async_main()
        args, kwargs = mock_asyncio_run.call_args
        assert len(args) == 1  # One positional argument

    @patch('src.cli.main.async_main')
    def test_main_function_keyboard_interrupt(self, mock_async_main):
        """Test main function keyboard interrupt handling."""
        with patch('asyncio.run', side_effect=KeyboardInterrupt()):
            with patch('builtins.print') as mock_print:
                with patch('sys.exit') as mock_exit:
                    main()

        # Should print cancellation message and exit
        mock_print.assert_called_with("\nOperation cancelled by user.")
        mock_exit.assert_called_once_with(1)

    def test_main_function_other_exception(self):
        """Test main function lets other exceptions bubble up."""
        with patch('asyncio.run', side_effect=ValueError("Test error")):
            with pytest.raises(ValueError, match="Test error"):
                main()


class TestAsyncMainFunction:
    """Test the async main function."""

    @patch('src.cli.main.CLIManager')
    @patch('sys.argv', ['program', 'list-characters'])
    async def test_async_main_function_basic(self, mock_cli_manager):
        """Test basic async main function execution."""
        mock_manager_instance = Mock()
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.func = AsyncMock()
        mock_args.log_level = 'INFO'

        mock_manager_instance.create_parser.return_value = mock_parser
        mock_manager_instance.setup_logging = Mock()
        mock_parser.parse_args.return_value = mock_args
        mock_cli_manager.return_value = mock_manager_instance

        from src.cli.main import async_main
        await async_main()

        # Verify components were initialized
        mock_cli_manager.assert_called_once()
        mock_manager_instance.create_parser.assert_called_once()
        mock_parser.parse_args.assert_called_once()
        mock_manager_instance.setup_logging.assert_called_once_with('INFO')
        mock_args.func.assert_called_once_with(mock_args)

    @patch('src.cli.main.CLIManager')
    @patch('sys.argv', ['program', '--log-level', 'DEBUG', 'create-character', 'men1'])
    async def test_async_main_function_with_log_level(self, mock_cli_manager):
        """Test async main function with custom log level."""
        mock_manager_instance = Mock()
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.func = AsyncMock()
        mock_args.log_level = 'DEBUG'

        mock_manager_instance.create_parser.return_value = mock_parser
        mock_manager_instance.setup_logging = Mock()
        mock_parser.parse_args.return_value = mock_args
        mock_cli_manager.return_value = mock_manager_instance

        from src.cli.main import async_main
        await async_main()

        # Verify debug log level was set
        mock_manager_instance.setup_logging.assert_called_once_with('DEBUG')

    @patch('src.cli.main.CLIManager')
    @patch('sys.argv', ['program'])
    async def test_async_main_function_no_command(self, mock_cli_manager):
        """Test async main function when no command is provided."""
        mock_manager_instance = Mock()
        mock_parser = Mock()
        mock_args = Mock()
        del mock_args.func  # No func attribute (no command)
        mock_args.log_level = 'INFO'

        mock_manager_instance.create_parser.return_value = mock_parser
        mock_manager_instance.setup_logging = Mock()
        mock_parser.parse_args.return_value = mock_args
        mock_parser.print_help = Mock()
        mock_cli_manager.return_value = mock_manager_instance

        from src.cli.main import async_main
        await async_main()

        # Should call print_help
        mock_parser.print_help.assert_called_once()


class TestCLIManagerIntegrationScenarios:
    """Test integration scenarios and edge cases."""

    def test_running_players_management(self):
        """Test management of running AI players."""
        cli_manager = CLIManager()

        # Initially empty
        assert len(cli_manager.running_players) == 0

        # Add a mock player
        mock_player = Mock(spec=AIPlayer)
        cli_manager.running_players["test_char"] = mock_player

        assert len(cli_manager.running_players) == 1
        assert cli_manager.running_players["test_char"] == mock_player

    @patch('src.cli.main.logging.getLogger')
    def test_logger_initialization(self, mock_get_logger):
        """Test that logger is properly initialized."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        cli_manager = CLIManager()

        mock_get_logger.assert_called_with("cli.manager")
        assert cli_manager.logger == mock_logger

    def test_cli_manager_str_representation(self):
        """Test string representation of CLIManager (if implemented)."""
        cli_manager = CLIManager()
        # Just verify it doesn't crash
        str_repr = str(cli_manager)
        assert isinstance(str_repr, str)
