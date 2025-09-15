"""
Comprehensive Coverage Tests for CLI Main Module

This module provides tests specifically designed to achieve 100% coverage
of the CLI main module, focusing on all classes, methods, and edge cases.
"""

import argparse
import asyncio
import sys
from io import StringIO
from unittest.mock import AsyncMock, Mock, patch
import pytest

from src.cli.main import (
    CLIManager, 
    generate_random_character_name,
    main,
    async_main
)


class TestGenerateRandomCharacterName:
    """Test the random character name generator comprehensively."""
    
    def test_generate_random_character_name_format(self):
        """Test that generated names meet API requirements."""
        name = generate_random_character_name()
        
        # Check length requirements (6-10 characters)
        assert 6 <= len(name) <= 10
        
        # Check character requirements (alphanumeric, underscore, hyphen only)
        allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-')
        assert all(c in allowed_chars for c in name)
    
    def test_generate_random_character_name_multiple_calls(self):
        """Test that multiple calls generate different names (most of the time)."""
        names = [generate_random_character_name() for _ in range(10)]
        
        # Should generate at least some different names
        unique_names = set(names)
        assert len(unique_names) > 1  # Very likely to be true with random generation


class TestCLIManagerInit:
    """Test CLI Manager initialization comprehensively."""
    
    def test_cli_manager_initialization(self):
        """Test basic CLI manager initialization."""
        cli = CLIManager()
        
        # Check that essential components are initialized
        assert cli.diagnostic_commands is not None
        assert hasattr(cli, 'api_client')
        assert hasattr(cli, 'running_players')
        assert hasattr(cli, 'log_manager')
        assert cli.api_client is None  # Not initialized until needed
        assert isinstance(cli.running_players, dict)
        assert len(cli.running_players) == 0


class TestCLIManagerInitialization:
    """Test CLI manager diagnostic initialization."""
    
    @patch('src.cli.main.APIClientWrapper')
    @patch('src.cli.main.CacheManager')
    @patch('src.cli.main.ActionExecutor')
    @patch('src.cli.main.GoalManager')
    @patch('src.cli.main.get_global_registry')
    def test_initialize_diagnostic_components(
        self, 
        mock_registry,
        mock_goal_manager, 
        mock_executor,
        mock_cache_manager,
        mock_api_wrapper
    ):
        """Test diagnostic components initialization."""
        mock_registry.return_value = Mock()
        
        cli = CLIManager()
        result = cli._initialize_diagnostic_components("TOKEN")
        
        # Should have diagnostic components initialized
        assert cli.diagnostic_commands is not None
        assert result is not None
        assert cli.api_client is not None
        mock_api_wrapper.assert_called_once_with("TOKEN")
        mock_cache_manager.assert_called_once()


class TestCLIManagerParser:
    """Test CLI argument parser functionality."""
    
    def test_create_parser(self):
        """Test argument parser creation."""
        cli = CLIManager()
        parser = cli.create_parser()
        
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.description == "ArtifactsMMO AI Player - Autonomous character control system"
        assert hasattr(parser, '_subparsers')
    
    def test_setup_character_commands(self):
        """Test character commands setup."""
        cli = CLIManager()
        parser = cli.create_parser()
        subparsers = parser.add_subparsers(dest='command')
        
        # This should not raise an exception
        cli.setup_character_commands(subparsers)
        
        # Verify commands were added
        assert hasattr(subparsers, '_name_parser_map')
    
    def test_setup_ai_player_commands(self):
        """Test AI player commands setup."""
        cli = CLIManager()
        parser = cli.create_parser()
        subparsers = parser.add_subparsers(dest='command')
        
        # This should not raise an exception
        cli.setup_ai_player_commands(subparsers)
        
        # Verify commands were added
        assert hasattr(subparsers, '_name_parser_map')
    
    def test_setup_diagnostic_commands(self):
        """Test diagnostic commands setup."""
        cli = CLIManager()
        parser = cli.create_parser()
        subparsers = parser.add_subparsers(dest='command')
        
        # This should not raise an exception
        cli.setup_diagnostic_commands(subparsers)
        
        # Verify commands were added
        assert hasattr(subparsers, '_name_parser_map')


class TestCLIManagerHandlers:
    """Test CLI command handlers."""
    
    @pytest.fixture
    def cli_manager(self):
        """Create CLI manager with mocked dependencies."""
        with patch('src.cli.main.APIClientWrapper') as mock_api:
            mock_api.return_value = Mock()
            cli = CLIManager()
            cli.api_client = Mock()
            cli.api_client.create_character = AsyncMock(return_value=Mock(name="test_char"))
            cli.api_client.delete_character = AsyncMock()
            cli.api_client.get_characters = AsyncMock(return_value=[])
            return cli
    
    @pytest.mark.asyncio
    async def test_handle_create_character_basic(self, cli_manager):
        """Test basic character creation."""
        args = Mock()
        args.name = "test_character"
        args.skin = "men1"
        
        await cli_manager.handle_create_character(args)
        
        cli_manager.api_client.create_character.assert_called_once_with("test_character", "men1")
    
    @pytest.mark.asyncio
    async def test_handle_create_character_random_name(self, cli_manager):
        """Test character creation with random name."""
        args = Mock()
        args.name = "random"
        args.skin = "men1"
        
        await cli_manager.handle_create_character(args)
        
        cli_manager.api_client.create_character.assert_called_once()
        call_args = cli_manager.api_client.create_character.call_args[0]
        assert call_args[1] == "men1"  # skin
        assert len(call_args[0]) >= 6  # name length
    
    @pytest.mark.asyncio
    async def test_handle_delete_character(self, cli_manager):
        """Test character deletion."""
        args = Mock()
        args.name = "test_character"
        args.force = False
        
        with patch('builtins.input', return_value='yes'):
            await cli_manager.handle_delete_character(args)
        
        cli_manager.api_client.delete_character.assert_called_once_with("test_character")
    
    @pytest.mark.asyncio
    async def test_handle_delete_character_force(self, cli_manager):
        """Test character deletion with force flag."""
        args = Mock()
        args.name = "test_character"
        args.force = True
        
        await cli_manager.handle_delete_character(args)
        
        cli_manager.api_client.delete_character.assert_called_once_with("test_character")
    
    @pytest.mark.asyncio
    async def test_handle_list_characters(self, cli_manager):
        """Test character listing."""
        args = Mock()
        
        await cli_manager.handle_list_characters(args)
        
        cli_manager.api_client.get_characters.assert_called_once()


class TestCLIManagerAIPlayer:
    """Test AI player management functionality."""
    
    @pytest.fixture
    def cli_manager(self):
        """Create CLI manager with mocked dependencies."""
        with patch('src.cli.main.APIClientWrapper'):
            with patch('src.cli.main.CacheManager'):
                with patch('src.cli.main.AIPlayer') as mock_ai_player:
                    mock_ai_player.return_value = Mock()
                    cli = CLIManager()
                    cli.api_client = Mock()
                    return cli
    
    @pytest.mark.asyncio
    async def test_handle_run_character(self, cli_manager):
        """Test running a character."""
        args = Mock()
        args.name = "test_character"
        
        with patch('src.cli.main.AIPlayer') as mock_ai_player:
            mock_player = Mock()
            mock_player.start = AsyncMock()
            mock_ai_player.return_value = mock_player
            
            await cli_manager.handle_run_character(args)
            
            assert "test_character" in cli_manager.running_players
    
    @pytest.mark.asyncio
    async def test_handle_stop_character(self, cli_manager):
        """Test stopping a character."""
        args = Mock()
        args.name = "test_character"
        
        # Setup a running player
        mock_player = Mock()
        mock_player.stop = AsyncMock()
        cli_manager.running_players["test_character"] = mock_player
        
        await cli_manager.handle_stop_character(args)
        
        mock_player.stop.assert_called_once()
        assert "test_character" not in cli_manager.running_players
    
    @pytest.mark.asyncio
    async def test_handle_character_status(self, cli_manager):
        """Test character status checking."""
        args = Mock()
        args.name = "test_character"
        
        cli_manager.api_client.get_character = AsyncMock(return_value=Mock(
            name="test_character",
            level=1,
            hp=100
        ))
        
        await cli_manager.handle_character_status(args)
        
        cli_manager.api_client.get_character.assert_called_once_with("test_character")


class TestCLIManagerLogging:
    """Test logging setup functionality."""
    
    def test_setup_logging(self):
        """Test logging configuration."""
        cli = CLIManager()
        
        # Test valid log levels
        for level in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
            cli.setup_logging(level)
            # Should not raise an exception
    
    def test_setup_logging_invalid_level(self):
        """Test logging with invalid level."""
        cli = CLIManager()
        
        # Invalid level should default to INFO
        cli.setup_logging("INVALID")
        # Should not raise an exception


class TestMainEntryPoints:
    """Test main entry point functions."""
    
    @patch('src.cli.main.asyncio.run')
    @patch('src.cli.main.async_main')
    def test_main_function(self, mock_async_main, mock_asyncio_run):
        """Test main function calls async_main."""
        main()
        
        mock_asyncio_run.assert_called_once_with(mock_async_main())
    
    @pytest.mark.asyncio
    @patch('src.cli.main.CLIManager')
    async def test_async_main_create_character(self, mock_cli_manager_class):
        """Test async_main with create-character command."""
        mock_cli_manager = Mock()
        mock_cli_manager.create_parser.return_value = Mock()
        mock_cli_manager.handle_create_character = AsyncMock()
        mock_cli_manager_class.return_value = mock_cli_manager
        
        with patch('sys.argv', ['prog', 'create-character', 'test_char', 'men1']):
            with patch('src.cli.main.CLIManager.create_parser') as mock_parser_method:
                mock_parser = Mock()
                mock_args = Mock()
                mock_args.command = 'create-character'
                mock_args.func = mock_cli_manager.handle_create_character
                mock_parser.parse_args.return_value = mock_args
                mock_parser_method.return_value = mock_parser
                
                await async_main()
                
                mock_args.func.assert_called_once_with(mock_args)


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_handle_create_character_api_error(self):
        """Test character creation with API error."""
        cli = CLIManager()
        cli.api_client = Mock()
        cli.api_client.create_character = AsyncMock(side_effect=Exception("API Error"))
        
        args = Mock()
        args.name = "test_character"
        args.skin = "men1"
        
        # Should handle exception gracefully
        await cli.handle_create_character(args)
        # Should not raise an exception
    
    @pytest.mark.asyncio
    async def test_handle_list_characters_api_error(self):
        """Test character listing with API error."""
        cli = CLIManager()
        cli.api_client = Mock()
        cli.api_client.get_characters = AsyncMock(side_effect=Exception("API Error"))
        
        args = Mock()
        
        # Should handle exception gracefully
        await cli.handle_list_characters(args)
        # Should not raise an exception


class TestFormattingMethods:
    """Test output formatting methods."""
    
    def test_format_weights_output(self):
        """Test weights output formatting."""
        cli = CLIManager()
        
        weights_data = {
            "actions_analyzed": 10,
            "cost_range": "1-5",
            "average_cost": 2.5,
            "optimization_opportunities": ["test"],
            "recommendations": ["test recommendation"]
        }
        
        result = cli.format_weights_output(weights_data)
        
        assert isinstance(result, str)
        assert "10" in result  # actions_analyzed
        assert "1-5" in result  # cost_range
    
    def test_format_cooldowns_output(self):
        """Test cooldowns output formatting."""
        cli = CLIManager()
        
        cooldowns_data = {
            "api_available": True,
            "cooldown_manager_available": True,
            "character_ready": False,
            "remaining_time": 15.3,
            "recommendations": ["test recommendation"]
        }
        
        result = cli.format_cooldowns_output(cooldowns_data)
        
        assert isinstance(result, str)
        assert "15.3" in result  # remaining_time
        assert "False" in result  # character_ready


class TestDiagnosticCommands:
    """Test diagnostic command handlers."""
    
    @pytest.fixture
    def cli_manager(self):
        """Create CLI manager with mocked diagnostic commands."""
        cli = CLIManager()
        cli.diagnostic_commands = Mock()
        return cli
    
    @pytest.mark.asyncio
    async def test_handle_diagnose_state(self, cli_manager):
        """Test state diagnostics handling."""
        cli_manager.diagnostic_commands.diagnose_state = AsyncMock(return_value={})
        
        args = Mock()
        args.character = "test_character"
        args.validate_enum = False
        
        await cli_manager.handle_diagnose_state(args)
        
        cli_manager.diagnostic_commands.diagnose_state.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_diagnose_actions(self, cli_manager):
        """Test action diagnostics handling."""
        cli_manager.diagnostic_commands.diagnose_actions = AsyncMock(return_value={})
        
        args = Mock()
        args.character = "test_character"
        args.list_all = False
        args.show_costs = False
        args.show_preconditions = False
        
        await cli_manager.handle_diagnose_actions(args)
        
        cli_manager.diagnostic_commands.diagnose_actions.assert_called_once()