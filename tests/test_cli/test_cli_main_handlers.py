"""
Handler Coverage Tests for CLI Main Module

This module contains tests specifically designed to achieve coverage
for all CLI handler functions that were at 0% coverage.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from src.cli.main import CLIManager


class TestCLIHandlers:
    """Test CLI command handlers with minimal mocking."""
    
    @pytest.fixture
    def cli_manager(self):
        """Create a CLI manager for testing."""
        return CLIManager()
    
    @pytest.mark.asyncio
    async def test_handle_create_character_basic(self, cli_manager):
        """Test basic character creation handler."""
        args = Mock()
        args.name = 'test_character'
        args.force = False
        
        with patch.object(cli_manager, '_initialize_diagnostic_components'):
            with patch('src.cli.main.APIClientWrapper') as mock_client_class:
                mock_client = Mock()
                mock_client.create_character = AsyncMock(return_value=Mock(name='test_character'))
                mock_client_class.return_value = mock_client
                
                await cli_manager.handle_create_character(args)
                mock_client.create_character.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_create_character_random_name(self, cli_manager):
        """Test character creation with random name generation."""
        args = Mock()
        args.name = None
        args.force = False
        
        with patch.object(cli_manager, '_initialize_diagnostic_components'):
            with patch('src.cli.main.APIClientWrapper') as mock_client_class:
                mock_client = Mock()
                mock_client.create_character = AsyncMock(return_value=Mock(name='random_name'))
                mock_client_class.return_value = mock_client
                
                await cli_manager.handle_create_character(args)
                mock_client.create_character.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_create_character_with_error(self, cli_manager):
        """Test character creation error handling."""
        args = Mock()
        args.name = 'test_character'
        args.force = False
        
        with patch.object(cli_manager, '_initialize_diagnostic_components'):
            with patch('src.cli.main.APIClientWrapper') as mock_client_class:
                mock_client = Mock()
                mock_client.create_character = AsyncMock(side_effect=Exception("Creation failed"))
                mock_client_class.return_value = mock_client
                
                with patch('builtins.print') as mock_print:
                    await cli_manager.handle_create_character(args)
                    mock_print.assert_called()
    
    @pytest.mark.asyncio
    async def test_handle_delete_character(self, cli_manager):
        """Test character deletion handler."""
        args = Mock()
        args.name = 'test_character'
        args.force = False
        
        with patch.object(cli_manager, '_initialize_diagnostic_components'):
            with patch('src.cli.main.APIClientWrapper') as mock_client_class:
                mock_client = Mock()
                mock_client.delete_character = AsyncMock(return_value=Mock())
                mock_client_class.return_value = mock_client
                
                with patch('builtins.input', return_value='y'):
                    await cli_manager.handle_delete_character(args)
                    mock_client.delete_character.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_delete_character_force(self, cli_manager):
        """Test character deletion with force flag."""
        args = Mock()
        args.name = 'test_character'
        args.force = True
        
        with patch.object(cli_manager, '_initialize_diagnostic_components'):
            with patch('src.cli.main.APIClientWrapper') as mock_client_class:
                mock_client = Mock()
                mock_client.delete_character = AsyncMock(return_value=Mock())
                mock_client_class.return_value = mock_client
                
                await cli_manager.handle_delete_character(args)
                mock_client.delete_character.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_list_characters(self, cli_manager):
        """Test character listing handler."""
        args = Mock()
        
        mock_characters = [
            Mock(name='char1', level=5, hp=100, max_hp=100),
            Mock(name='char2', level=3, hp=80, max_hp=90)
        ]
        
        with patch.object(cli_manager, '_initialize_diagnostic_components'):
            with patch('src.cli.main.APIClientWrapper') as mock_client_class:
                mock_client = Mock()
                mock_client.get_all_characters = AsyncMock(return_value=mock_characters)
                mock_client_class.return_value = mock_client
                
                with patch('builtins.print') as mock_print:
                    await cli_manager.handle_list_characters(args)
                    mock_print.assert_called()
    
    @pytest.mark.asyncio
    async def test_handle_load_data(self, cli_manager):
        """Test data loading handler."""
        args = Mock()
        args.force_refresh = False
        
        with patch.object(cli_manager, '_initialize_diagnostic_components'):
            with patch('src.cli.main.CacheManager') as mock_cache_class:
                mock_cache = Mock()
                mock_cache.get_game_data = AsyncMock(return_value=Mock())
                mock_cache_class.return_value = mock_cache
                
                with patch('builtins.print') as mock_print:
                    await cli_manager.handle_load_data(args)
                    mock_print.assert_called()
    
    @pytest.mark.asyncio
    async def test_handle_run_character(self, cli_manager):
        """Test character running handler."""
        args = Mock()
        args.character = 'test_character'
        args.duration = None
        args.max_actions = None
        args.dry_run = False
        
        with patch.object(cli_manager, '_initialize_diagnostic_components'):
            with patch('src.cli.main.StateManager') as mock_state_manager:
                with patch('src.cli.main.AIPlayer') as mock_ai_player:
                    mock_ai_instance = Mock()
                    mock_ai_instance.run = AsyncMock()
                    mock_ai_player.return_value = mock_ai_instance
                    
                    await cli_manager.handle_run_character(args)
                    mock_ai_player.assert_called()
    
    @pytest.mark.asyncio
    async def test_handle_stop_character(self, cli_manager):
        """Test character stopping handler."""
        args = Mock()
        args.character = 'test_character'
        
        # Add a running player to the manager
        mock_player = Mock()
        mock_player.stop = AsyncMock()
        cli_manager.running_players['test_character'] = mock_player
        
        with patch('builtins.print') as mock_print:
            await cli_manager.handle_stop_character(args)
            mock_player.stop.assert_called_once()
            mock_print.assert_called()
    
    @pytest.mark.asyncio
    async def test_handle_character_status(self, cli_manager):
        """Test character status handler."""
        args = Mock()
        args.character = 'test_character'
        
        mock_character = Mock()
        mock_character.name = 'test_character'
        mock_character.level = 5
        mock_character.hp = 80
        mock_character.max_hp = 100
        mock_character.x = 10
        mock_character.y = 15
        
        with patch.object(cli_manager, '_initialize_diagnostic_components'):
            with patch('src.cli.main.APIClientWrapper') as mock_client_class:
                mock_client = Mock()
                mock_client.get_character = AsyncMock(return_value=mock_character)
                mock_client_class.return_value = mock_client
                
                with patch('builtins.print') as mock_print:
                    await cli_manager.handle_character_status(args)
                    mock_client.get_character.assert_called_once()
                    mock_print.assert_called()


class TestDiagnosticHandlers:
    """Test diagnostic command handlers."""
    
    @pytest.fixture
    def cli_manager(self):
        """Create a CLI manager for testing."""
        cli = CLIManager()
        # Mock the diagnostic components
        cli.diagnostic_commands = Mock()
        return cli
    
    @pytest.mark.asyncio
    async def test_handle_diagnose_state(self, cli_manager):
        """Test state diagnosis handler."""
        args = Mock()
        args.character = 'test_character'
        args.validate_enum = False
        
        mock_result = {"summary": {"total_states": 10}, "recommendations": ["test"]}
        cli_manager.diagnostic_commands.diagnose_state = AsyncMock(return_value=mock_result)
        
        with patch('builtins.print') as mock_print:
            await cli_manager.handle_diagnose_state(args)
            cli_manager.diagnostic_commands.diagnose_state.assert_called_once()
            mock_print.assert_called()
    
    @pytest.mark.asyncio
    async def test_handle_diagnose_actions(self, cli_manager):
        """Test actions diagnosis handler."""
        args = Mock()
        args.character = 'test_character'
        args.show_costs = False
        args.list_all = False
        args.show_preconditions = False
        
        mock_result = {"summary": {"total_actions": 5}, "recommendations": ["test"]}
        cli_manager.diagnostic_commands.diagnose_actions = AsyncMock(return_value=mock_result)
        
        with patch('builtins.print') as mock_print:
            await cli_manager.handle_diagnose_actions(args)
            cli_manager.diagnostic_commands.diagnose_actions.assert_called_once()
            mock_print.assert_called()
    
    @pytest.mark.asyncio
    async def test_handle_diagnose_plan(self, cli_manager):
        """Test plan diagnosis handler."""
        args = Mock()
        args.character = 'test_character'
        args.goal = 'test_goal'
        args.verbose = False
        args.show_steps = False
        
        mock_result = {"planning_successful": True, "total_cost": 10}
        cli_manager.diagnostic_commands.diagnose_plan = AsyncMock(return_value=mock_result)
        
        with patch('builtins.print') as mock_print:
            await cli_manager.handle_diagnose_plan(args)
            cli_manager.diagnostic_commands.diagnose_plan.assert_called_once()
            mock_print.assert_called()
    
    @pytest.mark.asyncio
    async def test_handle_test_planning(self, cli_manager):
        """Test planning test handler."""
        args = Mock()
        args.character = 'test_character'
        args.goal = 'test_goal'
        
        mock_result = {"scenarios_tested": []}
        cli_manager.diagnostic_commands.test_planning = AsyncMock(return_value=mock_result)
        
        with patch('builtins.print') as mock_print:
            await cli_manager.handle_test_planning(args)
            cli_manager.diagnostic_commands.test_planning.assert_called_once()
            mock_print.assert_called()
    
    @pytest.mark.asyncio
    async def test_handle_diagnose_weights(self, cli_manager):
        """Test weights diagnosis handler."""
        args = Mock()
        args.character = 'test_character'
        
        mock_result = {"summary": {"total_actions": 5}, "recommendations": ["test"]}
        cli_manager.diagnostic_commands.diagnose_actions = AsyncMock(return_value=mock_result)
        
        with patch('builtins.print') as mock_print:
            await cli_manager.handle_diagnose_weights(args)
            cli_manager.diagnostic_commands.diagnose_actions.assert_called_once()
            mock_print.assert_called()
    
    @pytest.mark.asyncio
    async def test_handle_diagnose_cooldowns(self, cli_manager):
        """Test cooldowns diagnosis handler."""
        args = Mock()
        args.character = 'test_character'
        args.monitor = False
        
        mock_result = {"character_name": "test_character", "recommendations": ["test"]}
        cli_manager.diagnostic_commands.diagnose_cooldowns = AsyncMock(return_value=mock_result)
        
        with patch('builtins.print') as mock_print:
            await cli_manager.handle_diagnose_cooldowns(args)
            cli_manager.diagnostic_commands.diagnose_cooldowns.assert_called_once()
            mock_print.assert_called()


class TestInitializeDiagnosticComponents:
    """Test diagnostic components initialization."""
    
    def test_initialize_diagnostic_components(self):
        """Test _initialize_diagnostic_components method."""
        cli = CLIManager()
        
        with patch('src.cli.main.APIClientWrapper') as mock_api_wrapper:
            with patch('src.cli.main.CacheManager') as mock_cache_manager:
                with patch('src.cli.main.get_global_registry') as mock_registry:
                    with patch('src.cli.main.GoalManager') as mock_goal_manager:
                        with patch('src.cli.main.DiagnosticCommands') as mock_diagnostic_commands:
                            
                            result = cli._initialize_diagnostic_components("test_token.txt")
                            
                            # Should create all components
                            mock_api_wrapper.assert_called_once_with("test_token.txt")
                            mock_cache_manager.assert_called_once()
                            mock_registry.assert_called_once()
                            mock_goal_manager.assert_called_once()
                            mock_diagnostic_commands.assert_called_once()
                            
                            assert result is not None