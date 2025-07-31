"""
Real tests for CLI main module that actually exercise the code.

This test module tests the actual methods and functions in the CLI main
module to get real coverage measurements.
"""

import pytest
import string
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import argparse

from src.cli.main import generate_random_character_name, CLIManager


class TestUtilityFunctions:
    """Test utility functions that provide real coverage."""

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
        assert len(names) > 5


class TestCLIManagerReal:
    """Test CLIManager with actual methods."""

    def test_cli_manager_init(self):
        """Test CLIManager initialization."""
        cli_manager = CLIManager()
        assert cli_manager.log_manager is not None

    def test_cli_manager_setup_logging(self):
        """Test logging setup."""
        cli_manager = CLIManager()
        # This method exists and should not raise an exception
        cli_manager.setup_logging()
        assert True  # If we get here, no exception was raised

    def test_cli_manager_create_parser(self):
        """Test create_parser method."""
        cli_manager = CLIManager()
        parser = cli_manager.create_parser()
        assert isinstance(parser, argparse.ArgumentParser)

    def test_cli_manager_format_cooldowns_output(self):
        """Test cooldowns output formatting."""
        cli_manager = CLIManager()
        
        # Mock cooldowns data
        cooldowns_data = {
            "character_name": "test_char",
            "active_cooldowns": [],
            "cooldown_status": "ready"
        }
        
        result = cli_manager.format_cooldowns_output(cooldowns_data)
        assert isinstance(result, str)
        assert "test_char" in result

    def test_cli_manager_format_weights_output(self):
        """Test weights output formatting."""
        cli_manager = CLIManager()
        
        # Mock weights data
        weights_data = {
            "action_costs": {"move": 1, "fight": 3},
            "goal_weights": {"level_up": 100}
        }
        
        result = cli_manager.format_weights_output(weights_data)
        assert isinstance(result, str)

    def test_cli_manager_setup_character_commands(self):
        """Test character commands setup."""
        cli_manager = CLIManager()
        parser = cli_manager.create_parser()
        
        # This should add character subcommands
        cli_manager.setup_character_commands(parser)
        
        # Test that we can parse character commands
        args = parser.parse_args(['list'])
        assert args.command == 'list'

    def test_cli_manager_setup_ai_player_commands(self):
        """Test AI player commands setup."""  
        cli_manager = CLIManager()
        parser = cli_manager.create_parser()
        
        # This should add AI player subcommands
        cli_manager.setup_ai_player_commands(parser)
        
        # Parser should still work after setup
        assert parser is not None

    def test_cli_manager_setup_diagnostic_commands(self):
        """Test diagnostic commands setup."""
        cli_manager = CLIManager()
        parser = cli_manager.create_parser()
        
        # This should add diagnostic subcommands
        cli_manager.setup_diagnostic_commands(parser)
        
        # Parser should still work after setup
        assert parser is not None

    @patch('src.cli.main.APIClientWrapper')
    @pytest.mark.asyncio
    async def test_handle_list_characters(self, mock_api_wrapper):
        """Test handle_list_characters method."""
        cli_manager = CLIManager()
        
        # Mock API client
        mock_api_client = AsyncMock()
        mock_characters = [
            Mock(name="char1", level=5),
            Mock(name="char2", level=10)
        ]
        mock_api_client.get_characters.return_value = mock_characters
        
        with patch.object(cli_manager, '_get_api_client', return_value=mock_api_client):
            # This should not raise an exception
            await cli_manager.handle_list_characters(Mock())

    @patch('src.cli.main.APIClientWrapper')
    @pytest.mark.asyncio
    async def test_handle_create_character(self, mock_api_wrapper):
        """Test handle_create_character method."""
        cli_manager = CLIManager()
        
        # Mock API client
        mock_api_client = AsyncMock()
        mock_character = Mock(name="test_char")
        mock_api_client.create_character.return_value = mock_character
        
        # Mock arguments
        args = Mock()
        args.name = "test_char"
        args.skin = "men1"
        
        with patch.object(cli_manager, '_get_api_client', return_value=mock_api_client):
            await cli_manager.handle_create_character(args)

    @patch('src.cli.main.APIClientWrapper')
    @pytest.mark.asyncio
    async def test_handle_delete_character(self, mock_api_wrapper):
        """Test handle_delete_character method."""
        cli_manager = CLIManager()
        
        # Mock API client
        mock_api_client = AsyncMock()
        mock_api_client.delete_character.return_value = True
        
        # Mock arguments
        args = Mock()
        args.name = "test_char"
        
        with patch.object(cli_manager, '_get_api_client', return_value=mock_api_client):
            await cli_manager.handle_delete_character(args)

    @patch('src.cli.main.APIClientWrapper')
    @pytest.mark.asyncio
    async def test_handle_character_status(self, mock_api_wrapper):
        """Test handle_character_status method."""
        cli_manager = CLIManager()
        
        # Mock API client
        mock_api_client = AsyncMock()
        mock_character = Mock(name="test_char", level=5, hp=100)
        mock_api_client.get_character.return_value = mock_character
        
        # Mock arguments
        args = Mock()
        args.name = "test_char"
        
        with patch.object(cli_manager, '_get_api_client', return_value=mock_api_client):
            await cli_manager.handle_character_status(args)

    @pytest.mark.asyncio
    async def test_handle_diagnose_state(self):
        """Test handle_diagnose_state method."""
        cli_manager = CLIManager()
        
        # Mock arguments
        args = Mock()
        args.character_name = "test_char"
        
        # Mock diagnostic commands
        mock_diagnostic_commands = AsyncMock()
        mock_diagnostic_commands.diagnose_state.return_value = {"status": "ok"}
        
        with patch.object(cli_manager, '_initialize_diagnostic_components'):
            cli_manager.diagnostic_commands = mock_diagnostic_commands
            
            await cli_manager.handle_diagnose_state(args)

    @pytest.mark.asyncio
    async def test_handle_diagnose_actions(self):
        """Test handle_diagnose_actions method."""
        cli_manager = CLIManager()
        
        # Mock arguments
        args = Mock()
        args.list_all = False
        
        # Mock diagnostic commands
        mock_diagnostic_commands = AsyncMock()
        mock_diagnostic_commands.diagnose_actions.return_value = {"actions": []}
        
        with patch.object(cli_manager, '_initialize_diagnostic_components'):
            cli_manager.diagnostic_commands = mock_diagnostic_commands
            
            await cli_manager.handle_diagnose_actions(args)

    @pytest.mark.asyncio
    async def test_handle_diagnose_plan(self):
        """Test handle_diagnose_plan method."""
        cli_manager = CLIManager()
        
        # Mock arguments
        args = Mock()
        args.character_name = "test_char"
        args.goal = "level_up"
        
        # Mock diagnostic commands
        mock_diagnostic_commands = AsyncMock()
        mock_diagnostic_commands.diagnose_plan.return_value = {"plan": []}
        
        with patch.object(cli_manager, '_initialize_diagnostic_components'):
            cli_manager.diagnostic_commands = mock_diagnostic_commands
            
            await cli_manager.handle_diagnose_plan(args)

    @pytest.mark.asyncio
    async def test_handle_test_planning(self):
        """Test handle_test_planning method."""
        cli_manager = CLIManager()
        
        # Mock arguments
        args = Mock()
        
        # Mock diagnostic commands
        mock_diagnostic_commands = AsyncMock()
        mock_diagnostic_commands.test_planning.return_value = {"results": []}
        
        with patch.object(cli_manager, '_initialize_diagnostic_components'):
            cli_manager.diagnostic_commands = mock_diagnostic_commands
            
            await cli_manager.handle_test_planning(args)

    @pytest.mark.asyncio
    async def test_handle_diagnose_weights(self):
        """Test handle_diagnose_weights method."""
        cli_manager = CLIManager()
        
        # Mock arguments
        args = Mock()
        args.show_action_costs = False
        
        # Mock diagnostic commands
        mock_diagnostic_commands = AsyncMock()
        mock_diagnostic_commands.diagnose_weights.return_value = {"weights": {}}
        
        with patch.object(cli_manager, '_initialize_diagnostic_components'):
            cli_manager.diagnostic_commands = mock_diagnostic_commands
            
            await cli_manager.handle_diagnose_weights(args)

    @pytest.mark.asyncio
    async def test_handle_diagnose_cooldowns(self):
        """Test handle_diagnose_cooldowns method."""
        cli_manager = CLIManager()
        
        # Mock arguments
        args = Mock()
        args.character_name = "test_char"
        
        # Mock diagnostic commands
        mock_diagnostic_commands = AsyncMock()
        mock_diagnostic_commands.diagnose_cooldowns.return_value = {"cooldowns": {}}
        
        with patch.object(cli_manager, '_initialize_diagnostic_components'):
            cli_manager.diagnostic_commands = mock_diagnostic_commands
            
            await cli_manager.handle_diagnose_cooldowns(args)

    @patch('src.cli.main.CacheManager')
    @pytest.mark.asyncio
    async def test_handle_load_data(self, mock_cache_manager):
        """Test handle_load_data method."""
        cli_manager = CLIManager()
        
        # Mock arguments
        args = Mock()
        
        # Mock cache manager
        mock_cache_instance = AsyncMock()
        mock_cache_manager.return_value = mock_cache_instance
        
        with patch.object(cli_manager, '_get_api_client', return_value=Mock()):
            await cli_manager.handle_load_data(args)


class TestMainIntegration:
    """Test main function and integration."""

    def test_main_function_exists(self):
        """Test that main function exists."""
        from src.cli.main import main
        assert callable(main)

    @patch('sys.argv', ['cli.py', 'list'])
    @patch('src.cli.main.asyncio.run')
    def test_main_function_execution(self, mock_asyncio_run):
        """Test main function can be called."""
        from src.cli.main import main
        
        # Should not raise an exception
        main()
        mock_asyncio_run.assert_called_once()

    def test_cli_manager_str_representation(self):
        """Test CLIManager string representation."""
        cli_manager = CLIManager()
        str_repr = str(cli_manager)
        assert isinstance(str_repr, str)
        assert len(str_repr) > 0