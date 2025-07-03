"""Comprehensive unit tests for main.py"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Ensure src is in the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.main import (
    MAX_THREADS,
    clean_data_files,
    create_character,
    delete_character,
    evaluate_user_plan,
    handle_shutdown,
    main,
    show_goal_plan,
    task,
)


@pytest.mark.asyncio
class TestMainTask:
    """Test cases for the task coroutine."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.token_patcher = patch.dict('os.environ', {'TOKEN': 'test_token'})
        self.token_patcher.start()
        
    def teardown_method(self):
        """Clean up patches."""
        self.token_patcher.stop()
    
    @patch('src.main.BulkDataLoader')
    @patch('src.main.MapState')
    @patch('src.main.Characters')
    @patch('src.main.Account')
    @patch('src.main.ThrottledTransport')
    @patch('src.main.AuthenticatedClient')
    @patch('src.main.GOAPGoalManager')
    @patch('src.main.AIPlayerController')
    async def test_task_success_authenticated(self, mock_controller, mock_goal_manager,
                                            mock_client, mock_transport, mock_account,
                                            mock_characters, mock_map_state, mock_bulk_loader):
        """Test successful task execution with authenticated client."""
        # Set up mocks
        mock_character = Mock()
        mock_character.name = 'TestChar'
        mock_character.data = {'x': 0, 'y': 0, 'xp': 100, 'level': 5, 'hp': 50}
        
        mock_characters_instance = Mock()
        mock_characters_instance.__len__ = Mock(return_value=1)
        mock_characters_instance.__getitem__ = Mock(return_value=mock_character)
        mock_characters.return_value = mock_characters_instance
        
        mock_controller_instance = Mock()
        mock_controller_instance.execute_autonomous_mission = Mock(return_value=True)
        mock_controller_instance.character_state = Mock()
        mock_controller_instance.character_state.data = {'xp': 200, 'level': 6, 'hp': 60}
        mock_controller_instance.knowledge_base = Mock()
        mock_controller.return_value = mock_controller_instance
        
        mock_map_instance = Mock()
        mock_map_state.return_value = mock_map_instance
        
        mock_loader_instance = Mock()
        mock_loader_instance.load_all_game_data = Mock(return_value=True)
        mock_bulk_loader.return_value = mock_loader_instance
        
        # Run task
        await task()
        
        # Verify client creation with authentication
        mock_client.assert_called_once()
        assert 'token' in mock_client.call_args.kwargs
        assert mock_client.call_args.kwargs['token'] == 'test_token'
        
        # Verify controller setup
        mock_controller.assert_called_once()
        mock_controller_instance.set_character_state.assert_called_once_with(mock_character)
        mock_controller_instance.set_map_state.assert_called_once_with(mock_map_instance)
        
        # Verify bulk data loading
        mock_loader_instance.load_all_game_data.assert_called_once()
        
        # Verify mission execution
        mock_controller_instance.execute_autonomous_mission.assert_called_once_with({'target_level': 45})
    
    @patch('src.main.AIPlayerController')
    @patch('src.main.GOAPGoalManager')
    @patch('src.main.Client')
    @patch('src.main.ThrottledTransport')
    @patch('src.main.Account')
    @patch('src.main.Characters')
    async def test_task_no_token(self, mock_characters, mock_account, mock_transport,
                                mock_client, mock_goal_manager, mock_controller):
        """Test task execution without authentication token."""
        # Clear TOKEN from environment
        with patch.dict('os.environ', {}, clear=True):
            # Set up minimal mocks to prevent errors
            mock_characters.return_value = []
            
            # Run task
            await task()
            
            # Verify unauthenticated client creation
            mock_client.assert_called_once()
            assert 'token' not in mock_client.call_args.kwargs
    
    @patch('src.main.logging')
    @patch('src.main.Account')
    async def test_task_api_maintenance_error(self, mock_account, mock_logging):
        """Test handling of API maintenance (502) error."""
        # Make Account raise 502 error
        mock_account.side_effect = Exception("502 Bad Gateway")
        
        with patch.dict('os.environ', {'TOKEN': 'test_token'}):
            with patch('src.main.AuthenticatedClient'):
                with patch('src.main.ThrottledTransport'):
                    await task()
        
        # Verify maintenance error handling
        error_calls = [call for call in mock_logging.error.call_args_list 
                      if '502' in str(call) or 'maintenance' in str(call)]
        assert len(error_calls) >= 1
    
    @patch('src.main.Account')
    async def test_task_other_api_error(self, mock_account):
        """Test handling of non-maintenance API errors."""
        # Make Account raise non-502 error
        mock_account.side_effect = Exception("Connection failed")
        
        with patch.dict('os.environ', {'TOKEN': 'test_token'}):
            with patch('src.main.AuthenticatedClient'):
                with patch('src.main.ThrottledTransport'):
                    with pytest.raises(Exception) as cm:
                        await task()
                    assert "Connection failed" in str(cm.value)
    
    @patch('src.main.logging')
    @patch('src.main.Characters')
    @patch('src.main.Account')
    async def test_task_no_characters(self, mock_account, mock_characters, mock_logging):
        """Test handling when no characters exist."""
        # Set up empty characters list
        mock_characters.return_value = []
        
        with patch.dict('os.environ', {'TOKEN': 'test_token'}):
            with patch('src.main.AuthenticatedClient'):
                with patch('src.main.ThrottledTransport'):
                    await task()
        
        # Verify error logging
        error_calls = [call for call in mock_logging.error.call_args_list 
                      if 'No characters found' in str(call)]
        assert len(error_calls) >= 1


class TestDataFileOperations(unittest.TestCase):
    """Test cases for data file operations."""
    
    def setUp(self):
        """Create temporary directory for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir_patcher = patch('src.main.DATA_DIR', Path(self.temp_dir))
        self.data_dir_patcher.start()
        
    def tearDown(self):
        """Clean up temporary directory."""
        self.data_dir_patcher.stop()
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @patch('src.main.logging')
    def test_clean_data_files_existing(self, mock_logging):
        """Test cleaning existing data files."""
        # Create test files
        test_files = ["world.yaml", "map.yaml", "knowledge.yaml"]
        for filename in test_files:
            file_path = Path(self.temp_dir) / filename
            file_path.write_text("test data")
        
        # Run clean
        clean_data_files()
        
        # Verify files are deleted
        for filename in test_files:
            file_path = Path(self.temp_dir) / filename
            assert not file_path.exists()
        
        # Verify logging
        assert mock_logging.info.called
    
    def test_clean_data_files_missing(self):
        """Test cleaning when files don't exist."""
        # Run clean (no files exist)
        clean_data_files()  # Should not raise any errors


class TestGoalPlanning(unittest.TestCase):
    """Test cases for GOAP planning functionality."""
    
    @patch('src.main.DiagnosticTools')
    def test_show_goal_plan_template(self, mock_diagnostic_tools):
        """Test showing plan for a goal template."""
        # Set up mocks
        mock_tools_instance = Mock()
        mock_diagnostic_tools.return_value = mock_tools_instance
        
        # Create mock args
        mock_args = Mock(live=False, clean_state=False, state=None)
        
        # Run function
        show_goal_plan('test_goal', Mock(), mock_args)
        
        # Verify DiagnosticTools was created
        mock_diagnostic_tools.assert_called_once()
        
        # Verify show_goal_plan was called
        mock_tools_instance.show_goal_plan.assert_called_once_with('test_goal')
    
    @patch('src.main.DiagnosticTools')
    def test_show_goal_plan_level(self, mock_diagnostic_tools):
        """Test showing plan for level goal."""
        # Set up mocks
        mock_tools_instance = Mock()
        mock_diagnostic_tools.return_value = mock_tools_instance
        
        # Create mock args
        mock_args = Mock(live=False, clean_state=False, state=None)
        
        # Run function with level goal
        show_goal_plan('level 10', Mock(), mock_args)
        
        # Verify DiagnosticTools was created with correct params
        mock_diagnostic_tools.assert_called_once()
        
        # Verify show_goal_plan was called on the instance
        mock_tools_instance.show_goal_plan.assert_called_once_with('level 10')
    
    @patch('src.main.DiagnosticTools')
    def test_show_goal_plan_no_plan_found(self, mock_diagnostic_tools):
        """Test when no plan can be found."""
        # Set up mocks
        mock_tools_instance = Mock()
        mock_diagnostic_tools.return_value = mock_tools_instance
        
        # Create mock args
        mock_args = Mock(live=False, clean_state=False, state=None)
        
        # Run function
        show_goal_plan('impossible_goal', Mock(), mock_args)
        
        # Verify show_goal_plan was called
        mock_tools_instance.show_goal_plan.assert_called_once_with('impossible_goal')


class TestPlanEvaluation(unittest.TestCase):
    """Test cases for plan evaluation functionality."""
    
    @patch('src.main.DiagnosticTools')
    def test_evaluate_user_plan_valid(self, mock_diagnostic_tools):
        """Test evaluating a valid user plan."""
        # Set up mocks
        mock_tools_instance = Mock()
        mock_diagnostic_tools.return_value = mock_tools_instance
        
        # Create mock args
        mock_args = Mock(live=False, clean_state=False, state=None)
        
        # Evaluate plan
        evaluate_user_plan('move->fight', Mock(), mock_args)
        
        # Verify DiagnosticTools was created
        mock_diagnostic_tools.assert_called_once()
        
        # Verify evaluate_user_plan was called
        mock_tools_instance.evaluate_user_plan.assert_called_once_with('move->fight')
    
    @patch('src.main.DiagnosticTools')
    def test_evaluate_user_plan_unknown_action(self, mock_diagnostic_tools):
        """Test evaluating plan with unknown action."""
        # Set up mocks
        mock_tools_instance = Mock()
        mock_diagnostic_tools.return_value = mock_tools_instance
        
        # Create mock args
        mock_args = Mock(live=False, clean_state=False, state=None)
        
        # Evaluate plan with unknown action
        evaluate_user_plan('move->unknown_action', Mock(), mock_args)
        
        # Verify DiagnosticTools was created
        mock_diagnostic_tools.assert_called_once()
        
        # Verify evaluate_user_plan was called
        mock_tools_instance.evaluate_user_plan.assert_called_once_with('move->unknown_action')
    
    @patch('src.main.DiagnosticTools')
    def test_evaluate_user_plan_conditions_not_met(self, mock_diagnostic_tools):
        """Test evaluating plan where conditions aren't met."""
        # Set up mocks
        mock_tools_instance = Mock()
        mock_diagnostic_tools.return_value = mock_tools_instance
        
        # Create mock args
        mock_args = Mock(live=False, clean_state=False, state=None)
        
        # Evaluate plan
        evaluate_user_plan('fight', Mock(), mock_args)
        
        # Verify DiagnosticTools was created
        mock_diagnostic_tools.assert_called_once()
        
        # Verify evaluate_user_plan was called
        mock_tools_instance.evaluate_user_plan.assert_called_once_with('fight')


class TestCharacterManagement(unittest.TestCase):
    """Test cases for character management functions."""
    
    @patch('src.main.create_character_sync')
    @patch('src.main.generate_random_character_name')
    def test_create_character(self, mock_generate_name, mock_api_call):
        """Test character creation with new implementation."""
        # Setup
        mock_client = Mock(spec=Mock)  # Use mock for AuthenticatedClient check
        mock_client.__class__.__name__ = 'AuthenticatedClient'
        mock_generate_name.return_value = "TestChar"
        mock_api_call.return_value = Mock()
        
        # Execute
        result = create_character(mock_client)
        
        # Verify it works with authenticated client
        assert result is True
        mock_api_call.assert_called_once()
    
    @patch('src.main.delete_character_sync')
    def test_delete_character(self, mock_api_call):
        """Test character deletion with new implementation."""
        # Setup
        mock_client = Mock(spec=Mock)  # Use mock for AuthenticatedClient check
        mock_client.__class__.__name__ = 'AuthenticatedClient'
        mock_api_call.return_value = Mock()
        
        # Execute
        result = delete_character('TestChar', mock_client)
        
        # Verify it works with authenticated client
        assert result is True
        mock_api_call.assert_called_once()


class TestSignalHandling(unittest.TestCase):
    """Test cases for signal handling."""
    
    @patch('sys.exit')
    @patch('src.main.logging')
    def test_handle_shutdown(self, mock_logging, mock_exit):
        """Test shutdown signal handling."""
        handle_shutdown(None, None)
        
        # Verify logging
        mock_logging.info.assert_called_with("Shutdown signal received, cleaning up...")
        
        # Verify exit
        mock_exit.assert_called_once_with(0)


@pytest.mark.asyncio
class TestMainFunction:
    """Test cases for the main function."""
    
    @patch('src.main.parse_args')
    @patch('src.main.setup_logging')
    @patch('src.main.validate_args')
    @patch('src.main.safely_start_logger')
    @patch('src.main.extend_http_status')
    @patch('src.main.task')
    @patch('asyncio.TaskGroup')
    async def test_main_normal_execution(self, mock_task_group, mock_task, mock_extend,
                                       mock_start_logger, mock_validate, mock_setup_logging,
                                       mock_parse_args):
        """Test normal main execution flow."""
        # Set up mocks
        mock_args = Mock(
            daemon=False, clean=False, create_character=None,
            delete_character=None, goal_planner=None, evaluate_plan=None,
            log_level='INFO', character=None, characters=None, parallel=None
        )
        mock_parse_args.return_value = mock_args
        mock_validate.return_value = True
        
        # Mock TaskGroup
        mock_group_instance = AsyncMock()
        mock_group_instance.__aenter__ = AsyncMock(return_value=mock_group_instance)
        mock_group_instance.__aexit__ = AsyncMock(return_value=None)
        mock_group_instance.create_task = AsyncMock()
        mock_task_group.return_value = mock_group_instance
        
        # Run main
        await main()
        
        # Verify setup
        mock_parse_args.assert_called_once()
        mock_setup_logging.assert_called_once_with('INFO')
        mock_validate.assert_called_once_with(mock_args)
        mock_extend.assert_called_once()
        
        # Verify task creation
        assert mock_group_instance.create_task.call_count == MAX_THREADS
    
    @patch('src.main.parse_args')
    @patch('src.main.setup_logging')
    @patch('src.main.validate_args')
    @patch('src.main.safely_start_logger')
    @patch('src.main.extend_http_status')
    @patch('src.main.clean_data_files')
    async def test_main_clean_command(self, mock_clean, mock_extend, mock_start_logger,
                                    mock_validate, mock_setup_logging, mock_parse_args):
        """Test main with --clean command."""
        # Set up mocks for clean command
        mock_args = Mock(
            clean=True, create_character=None, delete_character=None,
            goal_planner=None, evaluate_plan=None, log_level='INFO'
        )
        mock_parse_args.return_value = mock_args
        mock_validate.return_value = True
        
        with patch.dict('os.environ', {'TOKEN': 'test_token'}):
            await main()
        
        # Verify clean was called
        mock_clean.assert_called_once()
    
    @patch('src.main.parse_args')
    @patch('src.main.setup_logging')
    @patch('src.main.validate_args')
    async def test_main_invalid_args(self, mock_validate, mock_setup_logging, mock_parse_args):
        """Test main with invalid arguments."""
        # Set up mocks
        mock_args = Mock(log_level='INFO')
        mock_parse_args.return_value = mock_args
        mock_validate.return_value = False
        
        with patch('sys.exit') as mock_exit:
            await main()
            mock_exit.assert_called_once_with(1)
    
    @patch('src.main.parse_args')
    @patch('src.main.setup_logging')
    @patch('src.main.validate_args')
    @patch('src.main.safely_start_logger')
    @patch('src.main.extend_http_status')
    @patch('src.main.signal.signal')
    @patch('src.main.task')
    @patch('asyncio.TaskGroup')
    async def test_main_daemon_mode(self, mock_task_group, mock_task, mock_signal,
                                   mock_extend, mock_start_logger, mock_validate,
                                   mock_setup_logging, mock_parse_args):
        """Test main in daemon mode."""
        # Set up mocks
        mock_args = Mock(
            daemon=True, clean=False, create_character=None,
            delete_character=None, goal_planner=None, evaluate_plan=None,
            log_level='INFO', character=None, characters=None, parallel=None
        )
        mock_parse_args.return_value = mock_args
        mock_validate.return_value = True
        
        # Mock TaskGroup
        mock_group_instance = AsyncMock()
        mock_group_instance.__aenter__ = AsyncMock(return_value=mock_group_instance)
        mock_group_instance.__aexit__ = AsyncMock(return_value=None)
        mock_group_instance.create_task = AsyncMock()
        mock_task_group.return_value = mock_group_instance
        
        # Run main
        await main()
        
        # Verify signal handlers were set
        assert mock_signal.call_count == 2  # SIGTERM and SIGINT
    
    @patch('src.main.parse_args')
    @patch('src.main.setup_logging')
    @patch('src.main.validate_args')
    @patch('src.main.safely_start_logger')
    @patch('src.main.extend_http_status')
    @patch('src.main.get_character_list')
    @patch('src.main.task')
    @patch('asyncio.TaskGroup')
    async def test_main_multiple_characters(self, mock_task_group, mock_task, mock_get_chars,
                                          mock_extend, mock_start_logger, mock_validate,
                                          mock_setup_logging, mock_parse_args):
        """Test main with multiple characters."""
        # Set up mocks
        mock_args = Mock(
            daemon=False, clean=False, create_character=None,
            delete_character=None, goal_planner=None, evaluate_plan=None,
            log_level='INFO'
        )
        mock_parse_args.return_value = mock_args
        mock_validate.return_value = True
        mock_get_chars.return_value = ['Char1', 'Char2', 'Char3']
        
        # Mock TaskGroup
        mock_group_instance = AsyncMock()
        mock_group_instance.__aenter__ = AsyncMock(return_value=mock_group_instance)
        mock_group_instance.__aexit__ = AsyncMock(return_value=None)
        mock_group_instance.create_task = AsyncMock()
        mock_task_group.return_value = mock_group_instance
        
        # Run main
        await main()
        
        # Verify tasks created for each character
        assert mock_group_instance.create_task.call_count == 3
        
        # Verify task was called with correct character names
        expected_calls = [
            (('Char1',), {'args': mock_args}),
            (('Char2',), {'args': mock_args}),
            (('Char3',), {'args': mock_args})
        ]
        
        # Get the actual calls to task()
        task_calls = mock_task.call_args_list
        assert len(task_calls) == 3
        
        # Extract character names from task calls
        actual_char_names = [call[1]['character_name'] for call in task_calls]
        assert set(actual_char_names) == {'Char1', 'Char2', 'Char3'}


if __name__ == '__main__':
    unittest.main()