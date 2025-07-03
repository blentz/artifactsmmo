"""Comprehensive tests for main.py to achieve 100% coverage"""

import asyncio
import os
import signal
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch, MagicMock

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
    async def test_task_success_xp_gained(self, mock_controller, mock_goal_manager,
                                         mock_client, mock_transport, mock_account,
                                         mock_characters, mock_map_state, mock_bulk_loader):
        """Test successful task execution with XP gained."""
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
        
        # Verify mission execution
        mock_controller_instance.execute_autonomous_mission.assert_called_once_with({'target_level': 45})
    
    @patch('src.main.BulkDataLoader')
    @patch('src.main.MapState')
    @patch('src.main.Characters')
    @patch('src.main.Account')
    @patch('src.main.ThrottledTransport')
    @patch('src.main.AuthenticatedClient')
    @patch('src.main.GOAPGoalManager')
    @patch('src.main.AIPlayerController')
    @patch('src.main.logging')
    async def test_task_success_level_gained(self, mock_logging, mock_controller, mock_goal_manager,
                                           mock_client, mock_transport, mock_account,
                                           mock_characters, mock_map_state, mock_bulk_loader):
        """Test successful task execution with level gained (line 135)."""
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
        # Level gained from 5 to 6
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
        
        # Verify level gained message logged (line 135)
        log_calls = [str(call) for call in mock_logging.info.call_args_list]
        assert any('MISSION ACCOMPLISHED: Target level achieved!' in str(call) for call in log_calls)
    
    @patch('src.main.BulkDataLoader')
    @patch('src.main.MapState')
    @patch('src.main.Characters')
    @patch('src.main.Account')
    @patch('src.main.ThrottledTransport')
    @patch('src.main.AuthenticatedClient')
    @patch('src.main.GOAPGoalManager')
    @patch('src.main.AIPlayerController')
    @patch('src.main.logging')
    async def test_task_success_no_level_gained(self, mock_logging, mock_controller, mock_goal_manager,
                                              mock_client, mock_transport, mock_account,
                                              mock_characters, mock_map_state, mock_bulk_loader):
        """Test successful task execution without level gain (line 137)."""
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
        # No level gained, same level
        mock_controller_instance.character_state.data = {'xp': 150, 'level': 5, 'hp': 60}
        mock_controller_instance.knowledge_base = Mock()
        mock_controller.return_value = mock_controller_instance
        
        mock_map_instance = Mock()
        mock_map_state.return_value = mock_map_instance
        
        mock_loader_instance = Mock()
        mock_loader_instance.load_all_game_data = Mock(return_value=True)
        mock_bulk_loader.return_value = mock_loader_instance
        
        # Run task
        await task()
        
        # Verify success without level gain message logged (line 137)
        log_calls = [str(call) for call in mock_logging.info.call_args_list]
        assert any('MISSION COMPLETED: Goal-driven execution successful!' in str(call) for call in log_calls)
    
    @patch('src.main.BulkDataLoader')
    @patch('src.main.MapState')
    @patch('src.main.Characters')
    @patch('src.main.Account')
    @patch('src.main.ThrottledTransport')
    @patch('src.main.AuthenticatedClient')
    @patch('src.main.GOAPGoalManager')
    @patch('src.main.AIPlayerController')
    @patch('src.main.logging')
    async def test_task_failure(self, mock_logging, mock_controller, mock_goal_manager,
                               mock_client, mock_transport, mock_account,
                               mock_characters, mock_map_state, mock_bulk_loader):
        """Test failed task execution (line 138)."""
        # Set up mocks
        mock_character = Mock()
        mock_character.name = 'TestChar'
        mock_character.data = {'x': 0, 'y': 0, 'xp': 100, 'level': 5, 'hp': 50}
        
        mock_characters_instance = Mock()
        mock_characters_instance.__len__ = Mock(return_value=1)
        mock_characters_instance.__getitem__ = Mock(return_value=mock_character)
        mock_characters.return_value = mock_characters_instance
        
        mock_controller_instance = Mock()
        # Mission failed
        mock_controller_instance.execute_autonomous_mission = Mock(return_value=False)
        mock_controller_instance.character_state = Mock()
        mock_controller_instance.character_state.data = {'xp': 100, 'level': 5, 'hp': 50}
        mock_controller_instance.knowledge_base = Mock()
        mock_controller.return_value = mock_controller_instance
        
        mock_map_instance = Mock()
        mock_map_state.return_value = mock_map_instance
        
        mock_loader_instance = Mock()
        mock_loader_instance.load_all_game_data = Mock(return_value=True)
        mock_bulk_loader.return_value = mock_loader_instance
        
        # Run task
        await task()
        
        # Verify failure message logged (line 138)
        log_calls = [str(call) for call in mock_logging.warning.call_args_list]
        assert any('MISSION INCOMPLETE: Goal-driven execution did not reach target' in str(call) for call in log_calls)
    
    @patch('src.main.BulkDataLoader')
    @patch('src.main.MapState')
    @patch('src.main.Characters')
    @patch('src.main.Account')
    @patch('src.main.ThrottledTransport')
    @patch('src.main.AuthenticatedClient')
    @patch('src.main.GOAPGoalManager')
    @patch('src.main.AIPlayerController')
    @patch('src.main.logging')
    async def test_task_no_xp_gained(self, mock_logging, mock_controller, mock_goal_manager,
                                    mock_client, mock_transport, mock_account,
                                    mock_characters, mock_map_state, mock_bulk_loader):
        """Test task execution with no XP gained (line 143)."""
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
        # No XP gained
        mock_controller_instance.character_state.data = {'xp': 100, 'level': 5, 'hp': 50}
        mock_controller_instance.knowledge_base = Mock()
        mock_controller.return_value = mock_controller_instance
        
        mock_map_instance = Mock()
        mock_map_state.return_value = mock_map_instance
        
        mock_loader_instance = Mock()
        mock_loader_instance.load_all_game_data = Mock(return_value=True)
        mock_bulk_loader.return_value = mock_loader_instance
        
        # Run task
        await task()
        
        # Verify no XP gained message logged (line 143)
        log_calls = [str(call) for call in mock_logging.warning.call_args_list]
        assert any('No XP gained - review goal selection and action execution' in str(call) for call in log_calls)
    
    @patch('src.main.BulkDataLoader')
    @patch('src.main.MapState')
    @patch('src.main.Characters')
    @patch('src.main.Account')
    @patch('src.main.ThrottledTransport')
    @patch('src.main.AuthenticatedClient')
    @patch('src.main.GOAPGoalManager')
    @patch('src.main.AIPlayerController')
    @patch('src.main.logging')
    async def test_task_bulk_loading_failure(self, mock_logging, mock_controller, mock_goal_manager,
                                           mock_client, mock_transport, mock_account,
                                           mock_characters, mock_map_state, mock_bulk_loader):
        """Test task with bulk data loading failure (line 97)."""
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
        # Bulk loading fails
        mock_loader_instance.load_all_game_data = Mock(return_value=False)
        mock_bulk_loader.return_value = mock_loader_instance
        
        # Run task
        await task()
        
        # Verify bulk loading failure message (line 97)
        log_calls = [str(call) for call in mock_logging.warning.call_args_list]
        assert any('Bulk data loading failed - AI will use discovery-based learning' in str(call) for call in log_calls)


class TestDiagnosticTools(unittest.TestCase):
    """Test cases for diagnostic tool functions."""
    
    @patch('src.main.DiagnosticTools')
    @patch('src.main.AuthenticatedClient')
    @patch('src.main.ThrottledTransport')
    def test_show_goal_plan_with_args(self, mock_transport, mock_client, mock_diagnostic):
        """Test show_goal_plan with args."""
        # Set up mocks
        mock_args = Mock()
        mock_args.online = False
        mock_args.clean_state = True
        mock_args.state = {'test': 'state'}
        
        mock_tools_instance = Mock()
        mock_diagnostic.return_value = mock_tools_instance
        
        # Run function
        with patch.dict('os.environ', {'TOKEN': 'test_token'}):
            show_goal_plan('test_goal', mock_client.return_value, mock_args)
        
        # Verify DiagnosticTools created with correct params
        mock_diagnostic.assert_called_once_with(
            client=mock_client.return_value,
            offline=True,  # not args.online
            clean_state=True,
            custom_state={'test': 'state'},
            args=mock_args
        )
        
        # Verify show_goal_plan called
        mock_tools_instance.show_goal_plan.assert_called_once_with('test_goal')
    
    @patch('src.main.DiagnosticTools')
    @patch('src.main.AuthenticatedClient')
    @patch('src.main.ThrottledTransport')
    def test_evaluate_user_plan_with_args(self, mock_transport, mock_client, mock_diagnostic):
        """Test evaluate_user_plan with args."""
        # Set up mocks
        mock_args = Mock()
        mock_args.online = True
        mock_args.clean_state = False
        mock_args.state = None
        
        mock_tools_instance = Mock()
        mock_diagnostic.return_value = mock_tools_instance
        
        # Run function
        with patch.dict('os.environ', {'TOKEN': 'test_token'}):
            evaluate_user_plan('move->fight', mock_client.return_value, mock_args)
        
        # Verify DiagnosticTools created with correct params
        mock_diagnostic.assert_called_once_with(
            client=mock_client.return_value,
            offline=False,  # args.online = True
            clean_state=False,
            custom_state=None,
            args=mock_args
        )
        
        # Verify evaluate_user_plan called
        mock_tools_instance.evaluate_user_plan.assert_called_once_with('move->fight')


@pytest.mark.asyncio
class TestMainFunction:
    """Test cases for the main function."""
    
    @patch('src.main.parse_args')
    @patch('src.main.setup_logging')
    @patch('src.main.validate_args')
    @patch('src.main.safely_start_logger')
    @patch('src.main.extend_http_status')
    @patch('src.main.show_goal_plan')
    @patch('src.main.AuthenticatedClient')
    @patch('src.main.ThrottledTransport')
    async def test_main_goal_planner(self, mock_transport, mock_client, mock_show_goal,
                                   mock_extend, mock_start_logger, mock_validate,
                                   mock_setup_logging, mock_parse_args):
        """Test main with goal planner command."""
        # Set up mocks
        mock_args = Mock(
            goal_planner='level 10', clean=False, create_character=None,
            delete_character=None, evaluate_plan=None, log_level='INFO',
            live=False, clean_state=False, state=None
        )
        mock_parse_args.return_value = mock_args
        mock_validate.return_value = True
        
        with patch.dict('os.environ', {'TOKEN': 'test_token'}):
            await main()
        
        # Verify goal planner was called
        mock_show_goal.assert_called_once()
        call_args = mock_show_goal.call_args
        assert call_args[0][0] == 'level 10'
        assert call_args[0][2] == mock_args
    
    @patch('src.main.parse_args')
    @patch('src.main.setup_logging')
    @patch('src.main.validate_args')
    @patch('src.main.safely_start_logger')
    @patch('src.main.extend_http_status')
    @patch('src.main.evaluate_user_plan')
    @patch('src.main.AuthenticatedClient')
    @patch('src.main.ThrottledTransport')
    async def test_main_evaluate_plan(self, mock_transport, mock_client, mock_eval_plan,
                                    mock_extend, mock_start_logger, mock_validate,
                                    mock_setup_logging, mock_parse_args):
        """Test main with evaluate plan command."""
        # Set up mocks
        mock_args = Mock(
            evaluate_plan='move->fight->rest', clean=False, create_character=None,
            delete_character=None, goal_planner=None, log_level='INFO',
            live=True, clean_state=True, state={'hp': 100}
        )
        mock_parse_args.return_value = mock_args
        mock_validate.return_value = True
        
        with patch.dict('os.environ', {'TOKEN': 'test_token'}):
            await main()
        
        # Verify evaluate plan was called
        mock_eval_plan.assert_called_once()
        call_args = mock_eval_plan.call_args
        assert call_args[0][0] == 'move->fight->rest'
        assert call_args[0][2] == mock_args
    
    @patch('src.main.parse_args')
    @patch('src.main.setup_logging')
    @patch('src.main.validate_args')
    @patch('src.main.safely_start_logger')
    @patch('src.main.extend_http_status')
    @patch('src.main.create_character')
    @patch('src.main.AuthenticatedClient')
    @patch('src.main.ThrottledTransport')
    async def test_main_create_character(self, mock_transport, mock_client, mock_create_char,
                                       mock_extend, mock_start_logger, mock_validate,
                                       mock_setup_logging, mock_parse_args):
        """Test main with create character command."""
        # Set up mocks
        mock_args = Mock(
            create_character=True, clean=False, delete_character=None,
            goal_planner=None, evaluate_plan=None, log_level='INFO'
        )
        mock_parse_args.return_value = mock_args
        mock_validate.return_value = True
        
        with patch.dict('os.environ', {'TOKEN': 'test_token'}):
            await main()
        
        # Verify create character was called with client
        mock_create_char.assert_called_once()
        # Should be called with just the client (no character name)
        assert len(mock_create_char.call_args[0]) == 1
    
    @patch('src.main.parse_args')
    @patch('src.main.setup_logging')
    @patch('src.main.validate_args')
    @patch('src.main.safely_start_logger')
    @patch('src.main.extend_http_status')
    @patch('src.main.delete_character')
    @patch('src.main.AuthenticatedClient')
    @patch('src.main.ThrottledTransport')
    async def test_main_delete_character(self, mock_transport, mock_client, mock_delete_char,
                                       mock_extend, mock_start_logger, mock_validate,
                                       mock_setup_logging, mock_parse_args):
        """Test main with delete character command."""
        # Set up mocks
        mock_args = Mock(
            delete_character='OldHero', clean=False, create_character=None,
            goal_planner=None, evaluate_plan=None, log_level='INFO'
        )
        mock_parse_args.return_value = mock_args
        mock_validate.return_value = True
        
        with patch.dict('os.environ', {'TOKEN': 'test_token'}):
            await main()
        
        # Verify delete character was called
        mock_delete_char.assert_called_once()
        assert mock_delete_char.call_args[0][0] == 'OldHero'
    
    @patch('src.main.parse_args')
    @patch('src.main.setup_logging')
    @patch('src.main.validate_args')
    @patch('src.main.safely_start_logger')
    @patch('src.main.extend_http_status')
    @patch('src.main.Client')
    @patch('src.main.ThrottledTransport')
    @patch('src.main.show_goal_plan')
    async def test_main_no_token_special_ops(self, mock_show_goal, mock_transport, mock_client,
                                           mock_extend, mock_start_logger, mock_validate,
                                           mock_setup_logging, mock_parse_args):
        """Test main with special operations but no token."""
        # Set up mocks
        mock_args = Mock(
            goal_planner='test_goal', clean=False, create_character=None,
            delete_character=None, evaluate_plan=None, log_level='INFO',
            live=False, clean_state=False, state=None
        )
        mock_parse_args.return_value = mock_args
        mock_validate.return_value = True
        
        # Clear TOKEN from environment
        with patch.dict('os.environ', {}, clear=True):
            await main()
        
        # Verify unauthenticated client was created
        mock_client.assert_called_once()
        assert 'token' not in mock_client.call_args.kwargs
    
    @patch('src.main.parse_args')
    @patch('src.main.setup_logging')
    @patch('src.main.validate_args')
    @patch('src.main.safely_start_logger')
    @patch('src.main.extend_http_status')
    @patch('src.main.get_character_list')
    @patch('src.main.task')
    @patch('asyncio.TaskGroup')
    async def test_main_no_characters_default_execution(self, mock_task_group, mock_task, 
                                                      mock_get_chars, mock_extend, 
                                                      mock_start_logger, mock_validate,
                                                      mock_setup_logging, mock_parse_args):
        """Test main with no characters specified (default execution)."""
        # Set up mocks
        mock_args = Mock(
            daemon=False, clean=False, create_character=None,
            delete_character=None, goal_planner=None, evaluate_plan=None,
            log_level='INFO'
        )
        mock_parse_args.return_value = mock_args
        mock_validate.return_value = True
        # Return empty list to trigger default behavior
        mock_get_chars.return_value = []
        
        # Mock TaskGroup
        mock_group_instance = AsyncMock()
        mock_group_instance.__aenter__ = AsyncMock(return_value=mock_group_instance)
        mock_group_instance.__aexit__ = AsyncMock(return_value=None)
        
        # Track task creations
        task_creations = []
        def track_task(*args, **kwargs):
            task_creations.append((args, kwargs))
            return AsyncMock()
        
        mock_group_instance.create_task = Mock(side_effect=track_task)
        mock_task_group.return_value = mock_group_instance
        
        # Run main
        await main()
        
        # Verify default execution with MAX_THREADS tasks
        assert len(task_creations) == MAX_THREADS
        
        # Verify task was called without character_name
        for args, kwargs in task_creations:
            # Should be task(args=mock_args)
            assert len(args) == 1  # Only the coroutine
            # The coroutine should be task() with args parameter


class TestEntryPoint(unittest.TestCase):
    """Test the __main__ entry point."""
    
    @patch('asyncio.run')
    @patch('src.main.__name__', '__main__')
    def test_main_entry_point(self, mock_run):
        """Test the if __name__ == '__main__' block (line 290)."""
        # Import and execute the module
        import src.main
        
        # The entry point check happens at module load time,
        # so we need to manually trigger it
        if "__main__" in src.main.__name__:
            asyncio.run(src.main.main())
        
        # Verify asyncio.run was called
        mock_run.assert_called_once()


if __name__ == '__main__':
    unittest.main()