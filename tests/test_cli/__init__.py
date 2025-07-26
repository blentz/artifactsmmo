"""
CLI interface tests

Tests for command-line interface including character management commands,
AI player control, diagnostic commands, and argument parsing.

This package provides specialized test utilities, mock factories, and
assertion helpers for comprehensive testing of CLI functionality.
"""

import argparse
import sys
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.cli import CLIManager


class CLIMockFactory:
    """Factory for creating CLI-specific mock objects"""

    @staticmethod
    def create_cli_manager_mock() -> Mock:
        """Create a mock CLIManager object"""
        cli_manager = Mock(spec=CLIManager)
        cli_manager.log_manager = Mock()
        cli_manager.api_client = None
        cli_manager.diagnostic_commands = Mock()
        cli_manager.running_players = {}
        cli_manager.logger = Mock()
        
        # Mock all CLI manager methods
        cli_manager.create_parser = Mock(return_value=CLIMockFactory.create_argument_parser_mock())
        cli_manager.setup_logging = Mock()
        cli_manager.handle_create_character = AsyncMock()
        cli_manager.handle_delete_character = AsyncMock()
        cli_manager.handle_list_characters = AsyncMock()
        cli_manager.handle_run_character = AsyncMock()
        cli_manager.handle_stop_character = AsyncMock()
        cli_manager.handle_character_status = AsyncMock()
        cli_manager.handle_diagnose_state = AsyncMock()
        cli_manager.handle_diagnose_actions = AsyncMock()
        cli_manager.handle_diagnose_plan = AsyncMock()
        cli_manager.handle_test_planning = AsyncMock()
        
        return cli_manager

    @staticmethod
    def create_argument_parser_mock() -> Mock:
        """Create a mock ArgumentParser object"""
        parser = Mock(spec=argparse.ArgumentParser)
        parser.prog = "artifactsmmo-ai-player"
        parser.description = "ArtifactsMMO AI Player CLI"
        parser.parse_args = Mock(return_value=CLIMockFactory.create_parsed_args_mock())
        parser.format_help = Mock(return_value="CLI Help Text")
        parser.print_help = Mock()
        parser.add_argument = Mock()
        parser.add_subparsers = Mock(return_value=Mock())
        return parser

    @staticmethod
    def create_parsed_args_mock(
        command: str = "list-characters",
        **kwargs
    ) -> Mock:
        """Create a mock parsed arguments object"""
        args = Mock()
        args.command = command
        args.log_level = kwargs.get('log_level', 'INFO')
        args.token_file = kwargs.get('token_file', 'TOKEN')
        
        # Character management args
        args.name = kwargs.get('name', 'test_character')
        args.skin = kwargs.get('skin', 'men1')
        args.detailed = kwargs.get('detailed', False)
        args.confirm = kwargs.get('confirm', False)
        
        # AI player control args
        args.goal = kwargs.get('goal', None)
        args.max_runtime = kwargs.get('max_runtime', None)
        args.save_interval = kwargs.get('save_interval', 300)
        args.force = kwargs.get('force', False)
        args.monitor = kwargs.get('monitor', False)
        
        # Diagnostic args
        args.validate_enum = kwargs.get('validate_enum', False)
        args.character = kwargs.get('character', 'test_character')
        args.show_costs = kwargs.get('show_costs', False)
        args.list_all = kwargs.get('list_all', False)
        args.show_preconditions = kwargs.get('show_preconditions', False)
        args.verbose = kwargs.get('verbose', False)
        args.show_steps = kwargs.get('show_steps', False)
        args.mock_state_file = kwargs.get('mock_state_file', None)
        args.start_level = kwargs.get('start_level', 1)
        args.goal_level = kwargs.get('goal_level', 5)
        args.dry_run = kwargs.get('dry_run', False)
        args.filter = kwargs.get('filter', None)
        
        return args

    @staticmethod
    def create_api_client_mock() -> AsyncMock:
        """Create a mock API client object"""
        client = AsyncMock()
        
        # Character management methods
        client.create_character = AsyncMock(return_value=CLIMockFactory.create_character_mock())
        client.delete_character = AsyncMock(return_value=True)
        client.get_characters = AsyncMock(return_value=[CLIMockFactory.create_character_mock()])
        
        return client

    @staticmethod
    def create_character_mock(
        name: str = "test_character",
        level: int = 1,
        x: int = 0,
        y: int = 0,
        **kwargs
    ) -> Mock:
        """Create a mock character object"""
        character = Mock()
        character.name = name
        character.level = level
        character.x = x
        character.y = y
        character.skin = kwargs.get('skin', 'men1')
        character.hp = kwargs.get('hp', 100)
        character.max_hp = kwargs.get('max_hp', 100)
        character.gold = kwargs.get('gold', level * 100)
        character.xp = kwargs.get('xp', level * 250)
        return character

    @staticmethod
    def create_ai_player_mock(character_name: str = "test_character") -> AsyncMock:
        """Create a mock AI Player object"""
        ai_player = AsyncMock()
        ai_player.character_name = character_name
        ai_player.start = AsyncMock()
        ai_player.stop = AsyncMock()
        ai_player.set_goal = Mock()
        ai_player.get_status = Mock(return_value="idle")
        ai_player._running = False
        ai_player._stop_requested = False
        return ai_player

    @staticmethod
    def create_diagnostic_commands_mock() -> Mock:
        """Create a mock diagnostic commands object"""
        diagnostic = Mock()
        diagnostic.diagnose_state = Mock(return_value={'state': 'valid'})
        diagnostic.diagnose_actions = Mock(return_value=[{'action': 'move'}])
        diagnostic.diagnose_plan = Mock(return_value={'plan': 'found'})
        diagnostic.test_planning = Mock(return_value={'tests': 'passed'})
        diagnostic.format_state_output = Mock(return_value="Formatted state output")
        diagnostic.format_action_output = Mock(return_value="Formatted action output")
        diagnostic.format_planning_output = Mock(return_value="Formatted planning output")
        return diagnostic


class CLITestAssertions:
    """Assertion helpers specific to CLI testing"""

    @staticmethod
    def assert_command_parsed(
        args: Mock,
        expected_command: str,
        expected_args: Dict[str, Any] | None = None
    ):
        """Assert that command was parsed correctly"""
        assert args.command == expected_command, (
            f"Expected command '{expected_command}', got '{args.command}'"
        )
        
        if expected_args:
            for arg_name, expected_value in expected_args.items():
                actual_value = getattr(args, arg_name, None)
                assert actual_value == expected_value, (
                    f"Argument '{arg_name}': expected {expected_value}, got {actual_value}"
                )

    @staticmethod
    def assert_character_command_args(
        args: Mock,
        character_name: str | None = None,
        skin: str | None = None
    ):
        """Assert character command arguments are correct"""
        if character_name:
            assert args.name == character_name, (
                f"Expected character name '{character_name}', got '{args.name}'"
            )
        if skin:
            assert args.skin == skin, (
                f"Expected skin '{skin}', got '{args.skin}'"
            )

    @staticmethod
    def assert_ai_player_command_args(
        args: Mock,
        character_name: str | None = None,
        goal: str | None = None,
        max_runtime: int | None = None
    ):
        """Assert AI player command arguments are correct"""
        if character_name:
            assert args.name == character_name
        if goal is not None:
            assert args.goal == goal
        if max_runtime is not None:
            assert args.max_runtime == max_runtime

    @staticmethod
    def assert_diagnostic_command_args(
        args: Mock,
        character_name: str | None = None,
        verbose: bool | None = None,
        dry_run: bool | None = None
    ):
        """Assert diagnostic command arguments are correct"""
        if character_name:
            assert hasattr(args, 'name') and args.name == character_name
        if verbose is not None:
            assert args.verbose == verbose
        if dry_run is not None:
            assert args.dry_run == dry_run

    @staticmethod
    def assert_cli_output_contains(
        print_mock: Mock,
        expected_text: str,
        case_sensitive: bool = True
    ):
        """Assert CLI output contains expected text"""
        print_calls = [str(call) for call in print_mock.call_args_list]
        output_text = " ".join(print_calls)
        
        if not case_sensitive:
            output_text = output_text.lower()
            expected_text = expected_text.lower()
            
        assert expected_text in output_text, (
            f"Expected text '{expected_text}' not found in CLI output"
        )

    @staticmethod
    def assert_error_message_printed(
        print_mock: Mock,
        error_keyword: str = "Error"
    ):
        """Assert that an error message was printed"""
        print_calls = [str(call) for call in print_mock.call_args_list]
        error_found = any(error_keyword in call for call in print_calls)
        assert error_found, f"No error message containing '{error_keyword}' was printed"

    @staticmethod
    def assert_success_message_printed(
        print_mock: Mock,
        success_keyword: str = "Success"
    ):
        """Assert that a success message was printed"""
        print_calls = [str(call) for call in print_mock.call_args_list]
        success_found = any(success_keyword in call for call in print_calls)
        assert success_found, f"No success message containing '{success_keyword}' was printed"


class CLITestHelpers:
    """Helper functions for CLI testing scenarios"""

    @staticmethod
    def create_character_creation_scenario(
        character_name: str = "new_character",
        skin: str = "men1",
        should_succeed: bool = True
    ) -> Dict[str, Any]:
        """Create a character creation test scenario"""
        return {
            'args': CLIMockFactory.create_parsed_args_mock(
                command='create-character',
                name=character_name,
                skin=skin
            ),
            'expected_success': should_succeed,
            'character_data': CLIMockFactory.create_character_mock(
                name=character_name,
                skin=skin
            )
        }

    @staticmethod
    def create_ai_player_scenario(
        character_name: str = "ai_character",
        goal: str | None = None,
        max_runtime: int | None = None,
        should_succeed: bool = True
    ) -> Dict[str, Any]:
        """Create an AI player test scenario"""
        return {
            'args': CLIMockFactory.create_parsed_args_mock(
                command='run-character',
                name=character_name,
                goal=goal,
                max_runtime=max_runtime
            ),
            'ai_player': CLIMockFactory.create_ai_player_mock(character_name),
            'expected_success': should_succeed
        }

    @staticmethod
    def create_diagnostic_scenario(
        diagnostic_type: str = "diagnose-state",
        character_name: str = "diagnostic_character",
        options: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Create a diagnostic command test scenario"""
        args_dict = {
            'command': diagnostic_type,
            'name': character_name,
            **(options or {})
        }
        
        return {
            'args': CLIMockFactory.create_parsed_args_mock(**args_dict),
            'diagnostic_commands': CLIMockFactory.create_diagnostic_commands_mock(),
            'expected_diagnostic_type': diagnostic_type
        }

    @staticmethod
    async def simulate_cli_command_execution(
        cli_manager: Mock,
        command: str,
        args: Mock,
        mock_dependencies: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Simulate executing a CLI command and return results"""
        if mock_dependencies:
            for attr_name, mock_obj in mock_dependencies.items():
                setattr(cli_manager, attr_name, mock_obj)

        # Route to appropriate handler
        if command == 'create-character':
            await cli_manager.handle_create_character(args)
        elif command == 'delete-character':
            await cli_manager.handle_delete_character(args)
        elif command == 'list-characters':
            await cli_manager.handle_list_characters(args)
        elif command == 'run-character':
            await cli_manager.handle_run_character(args)
        elif command == 'stop-character':
            await cli_manager.handle_stop_character(args)
        elif command == 'status-character':
            await cli_manager.handle_character_status(args)
        elif command == 'diagnose-state':
            await cli_manager.handle_diagnose_state(args)
        elif command == 'diagnose-actions':
            await cli_manager.handle_diagnose_actions(args)
        elif command == 'diagnose-plan':
            await cli_manager.handle_diagnose_plan(args)
        elif command == 'test-planning':
            await cli_manager.handle_test_planning(args)

        return {
            'command_executed': command,
            'args_used': args,
            'cli_manager_state': cli_manager
        }

    @staticmethod
    def create_argument_parsing_test_cases() -> List[Dict[str, Any]]:
        """Create test cases for argument parsing validation"""
        return [
            {
                'name': 'create_character_valid',
                'args': ['create-character', 'test_char', 'men1'],
                'expected_command': 'create-character',
                'expected_valid': True
            },
            {
                'name': 'run_character_with_goal',
                'args': ['run-character', 'ai_char', '--goal', 'level_up'],
                'expected_command': 'run-character',
                'expected_valid': True
            },
            {
                'name': 'diagnose_state_verbose',
                'args': ['diagnose-state', 'debug_char', '--verbose'],
                'expected_command': 'diagnose-state',
                'expected_valid': True
            },
            {
                'name': 'invalid_command',
                'args': ['invalid-command'],
                'expected_command': None,
                'expected_valid': False
            },
            {
                'name': 'missing_character_name',
                'args': ['create-character'],
                'expected_command': 'create-character',
                'expected_valid': False
            }
        ]

    @staticmethod
    def validate_character_name(name: str) -> bool:
        """Validate character name according to game rules"""
        if len(name) < 3 or len(name) > 12:
            return False
        return name.replace('_', '').isalnum()

    @staticmethod
    def create_error_scenarios() -> List[Dict[str, Any]]:
        """Create test scenarios for error handling"""
        return [
            {
                'name': 'api_client_creation_error',
                'error_type': Exception,
                'error_message': 'API client creation failed',
                'expected_error_text': 'Error'
            },
            {
                'name': 'character_not_found',
                'error_type': ValueError,
                'error_message': 'Character not found',
                'expected_error_text': 'not found'
            },
            {
                'name': 'invalid_character_name',
                'error_type': ValueError,
                'error_message': 'Invalid character name',
                'expected_error_text': 'Invalid'
            },
            {
                'name': 'ai_player_start_error',
                'error_type': RuntimeError,
                'error_message': 'AI player failed to start',
                'expected_error_text': 'failed'
            }
        ]


# Common fixtures for CLI tests
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


# Test configuration specific to CLI
CLI_TEST_TIMEOUT = 10.0
ASYNC_CLI_TEST_TIMEOUT = 5.0
CLI_COMMAND_TIMEOUT = 3.0
