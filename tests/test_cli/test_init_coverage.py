"""
Tests for CLI __init__.py module coverage

This module specifically tests the utility functions and classes
defined in the CLI test __init__.py module to ensure 100% coverage.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from tests.test_cli import (
    CLIMockFactory,
    CLITestAssertions,
    CLITestHelpers,
    CLI_TEST_TIMEOUT,
    ASYNC_CLI_TEST_TIMEOUT,
    CLI_COMMAND_TIMEOUT
)


class TestCLIMockFactory:
    """Test CLIMockFactory functionality"""

    def test_create_cli_manager_mock(self):
        """Test CLI manager mock creation"""
        cli_manager = CLIMockFactory.create_cli_manager_mock()
        
        assert cli_manager is not None
        assert hasattr(cli_manager, 'log_manager')
        assert hasattr(cli_manager, 'api_client')
        assert hasattr(cli_manager, 'diagnostic_commands')
        assert hasattr(cli_manager, 'running_players')
        assert hasattr(cli_manager, 'logger')
        assert hasattr(cli_manager, 'create_parser')
        assert hasattr(cli_manager, 'setup_logging')
        assert hasattr(cli_manager, 'handle_create_character')
        assert hasattr(cli_manager, 'handle_delete_character')
        assert hasattr(cli_manager, 'handle_list_characters')
        assert hasattr(cli_manager, 'handle_run_character')
        assert hasattr(cli_manager, 'handle_stop_character')
        assert hasattr(cli_manager, 'handle_character_status')
        assert hasattr(cli_manager, 'handle_diagnose_state')
        assert hasattr(cli_manager, 'handle_diagnose_actions')
        assert hasattr(cli_manager, 'handle_diagnose_plan')
        assert hasattr(cli_manager, 'handle_test_planning')

    def test_create_argument_parser_mock(self):
        """Test argument parser mock creation"""
        parser = CLIMockFactory.create_argument_parser_mock()
        
        assert parser is not None
        assert parser.prog == "artifactsmmo-ai-player"
        assert parser.description == "ArtifactsMMO AI Player CLI"
        assert hasattr(parser, 'parse_args')
        assert hasattr(parser, 'format_help')
        assert hasattr(parser, 'print_help')
        assert hasattr(parser, 'add_argument')
        assert hasattr(parser, 'add_subparsers')

    def test_create_parsed_args_mock_defaults(self):
        """Test parsed arguments mock with defaults"""
        args = CLIMockFactory.create_parsed_args_mock()
        
        assert args.command == "list-characters"
        assert args.log_level == 'INFO'
        assert args.token_file == 'TOKEN'
        assert args.name == 'test_character'
        assert args.skin == 'men1'
        assert args.detailed is False
        assert args.confirm is False

    def test_create_parsed_args_mock_custom(self):
        """Test parsed arguments mock with custom values"""
        args = CLIMockFactory.create_parsed_args_mock(
            command="create-character",
            name="custom_char",
            skin="women1",
            detailed=True,
            log_level="DEBUG"
        )
        
        assert args.command == "create-character"
        assert args.name == "custom_char"
        assert args.skin == "women1"
        assert args.detailed is True
        assert args.log_level == "DEBUG"

    def test_create_api_client_mock(self):
        """Test API client mock creation"""
        client = CLIMockFactory.create_api_client_mock()
        
        assert client is not None
        assert hasattr(client, 'create_character')
        assert hasattr(client, 'delete_character')
        assert hasattr(client, 'get_characters')

    def test_create_character_mock_defaults(self):
        """Test character mock with defaults"""
        character = CLIMockFactory.create_character_mock()
        
        assert character.name == "test_character"
        assert character.level == 1
        assert character.x == 0
        assert character.y == 0
        assert character.skin == 'men1'
        assert character.hp == 100
        assert character.max_hp == 100
        assert character.gold == 100  # level * 100
        assert character.xp == 250   # level * 250

    def test_create_character_mock_custom(self):
        """Test character mock with custom values"""
        character = CLIMockFactory.create_character_mock(
            name="custom_char",
            level=5,
            x=10,
            y=20,
            hp=80,
            max_hp=120,
            gold=500,
            xp=1000
        )
        
        assert character.name == "custom_char"
        assert character.level == 5
        assert character.x == 10
        assert character.y == 20
        assert character.hp == 80
        assert character.max_hp == 120
        assert character.gold == 500
        assert character.xp == 1000

    def test_create_ai_player_mock(self):
        """Test AI player mock creation"""
        ai_player = CLIMockFactory.create_ai_player_mock("test_char")
        
        assert ai_player.character_name == "test_char"
        assert hasattr(ai_player, 'start')
        assert hasattr(ai_player, 'stop')
        assert hasattr(ai_player, 'set_goal')
        assert hasattr(ai_player, 'get_status')
        assert ai_player._running is False
        assert ai_player._stop_requested is False

    def test_create_diagnostic_commands_mock(self):
        """Test diagnostic commands mock creation"""
        diagnostic = CLIMockFactory.create_diagnostic_commands_mock()
        
        assert hasattr(diagnostic, 'diagnose_state')
        assert hasattr(diagnostic, 'diagnose_actions')
        assert hasattr(diagnostic, 'diagnose_plan')
        assert hasattr(diagnostic, 'test_planning')
        assert hasattr(diagnostic, 'format_state_output')
        assert hasattr(diagnostic, 'format_action_output')
        assert hasattr(diagnostic, 'format_planning_output')
        
        # Test return values
        assert diagnostic.diagnose_state() == {'state': 'valid'}
        assert diagnostic.diagnose_actions() == [{'action': 'move'}]
        assert diagnostic.diagnose_plan() == {'plan': 'found'}
        assert diagnostic.test_planning() == {'tests': 'passed'}


class TestCLITestAssertions:
    """Test CLITestAssertions functionality"""

    def test_assert_command_parsed_success(self):
        """Test successful command parsing assertion"""
        args = Mock()
        args.command = "test-command"
        args.name = "test_name"
        
        # Should not raise exception
        CLITestAssertions.assert_command_parsed(
            args, 
            "test-command", 
            {"name": "test_name"}
        )

    def test_assert_command_parsed_failure(self):
        """Test failed command parsing assertion"""
        args = Mock()
        args.command = "wrong-command"
        
        with pytest.raises(AssertionError, match="Expected command"):
            CLITestAssertions.assert_command_parsed(args, "test-command")

    def test_assert_character_command_args_success(self):
        """Test successful character command args assertion"""
        args = Mock()
        args.name = "test_char"
        args.skin = "men1"
        
        # Should not raise exception
        CLITestAssertions.assert_character_command_args(
            args, 
            character_name="test_char", 
            skin="men1"
        )

    def test_assert_character_command_args_failure(self):
        """Test failed character command args assertion"""
        args = Mock()
        args.name = "wrong_char"
        
        with pytest.raises(AssertionError, match="Expected character name"):
            CLITestAssertions.assert_character_command_args(
                args, 
                character_name="test_char"
            )

    def test_assert_ai_player_command_args(self):
        """Test AI player command args assertion"""
        args = Mock()
        args.name = "ai_char"
        args.goal = "level_up"
        args.max_runtime = 60
        
        # Should not raise exception
        CLITestAssertions.assert_ai_player_command_args(
            args,
            character_name="ai_char",
            goal="level_up",
            max_runtime=60
        )

    def test_assert_diagnostic_command_args(self):
        """Test diagnostic command args assertion"""
        args = Mock()
        args.name = "debug_char"
        args.verbose = True
        args.dry_run = False
        
        # Should not raise exception
        CLITestAssertions.assert_diagnostic_command_args(
            args,
            character_name="debug_char",
            verbose=True,
            dry_run=False
        )

    def test_assert_cli_output_contains_success(self):
        """Test successful CLI output assertion"""
        print_mock = Mock()
        print_mock.call_args_list = [
            Mock(__str__=lambda x: "Test output message"),
            Mock(__str__=lambda x: "Another message")
        ]
        
        # Should not raise exception
        CLITestAssertions.assert_cli_output_contains(
            print_mock, 
            "Test output"
        )

    def test_assert_cli_output_contains_case_insensitive(self):
        """Test CLI output assertion case insensitive"""
        print_mock = Mock()
        print_mock.call_args_list = [
            Mock(__str__=lambda x: "TEST OUTPUT MESSAGE")
        ]
        
        # Should not raise exception
        CLITestAssertions.assert_cli_output_contains(
            print_mock, 
            "test output",
            case_sensitive=False
        )

    def test_assert_cli_output_contains_failure(self):
        """Test failed CLI output assertion"""
        print_mock = Mock()
        print_mock.call_args_list = [
            Mock(__str__=lambda x: "Different message")
        ]
        
        with pytest.raises(AssertionError, match="Expected text.*not found"):
            CLITestAssertions.assert_cli_output_contains(
                print_mock, 
                "Missing text"
            )

    def test_assert_error_message_printed_success(self):
        """Test successful error message assertion"""
        print_mock = Mock()
        print_mock.call_args_list = [
            Mock(__str__=lambda x: "Error: Something went wrong")
        ]
        
        # Should not raise exception
        CLITestAssertions.assert_error_message_printed(print_mock)

    def test_assert_error_message_printed_failure(self):
        """Test failed error message assertion"""
        print_mock = Mock()
        print_mock.call_args_list = [
            Mock(__str__=lambda x: "Success: Everything is fine")
        ]
        
        with pytest.raises(AssertionError, match="No error message"):
            CLITestAssertions.assert_error_message_printed(print_mock)

    def test_assert_success_message_printed_success(self):
        """Test successful success message assertion"""
        print_mock = Mock()
        print_mock.call_args_list = [
            Mock(__str__=lambda x: "Success: Operation completed")
        ]
        
        # Should not raise exception
        CLITestAssertions.assert_success_message_printed(print_mock)

    def test_assert_success_message_printed_failure(self):
        """Test failed success message assertion"""
        print_mock = Mock()
        print_mock.call_args_list = [
            Mock(__str__=lambda x: "Error: Something failed")
        ]
        
        with pytest.raises(AssertionError, match="No success message"):
            CLITestAssertions.assert_success_message_printed(print_mock)


class TestCLITestHelpers:
    """Test CLITestHelpers functionality"""

    def test_create_character_creation_scenario_defaults(self):
        """Test character creation scenario with defaults"""
        scenario = CLITestHelpers.create_character_creation_scenario()
        
        assert 'args' in scenario
        assert 'expected_success' in scenario
        assert 'character_data' in scenario
        assert scenario['expected_success'] is True
        assert scenario['args'].command == 'create-character'
        assert scenario['args'].name == 'new_character'
        assert scenario['args'].skin == 'men1'

    def test_create_character_creation_scenario_custom(self):
        """Test character creation scenario with custom values"""
        scenario = CLITestHelpers.create_character_creation_scenario(
            character_name="custom_char",
            skin="women1",
            should_succeed=False
        )
        
        assert scenario['expected_success'] is False
        assert scenario['args'].name == 'custom_char'
        assert scenario['args'].skin == 'women1'

    def test_create_ai_player_scenario_defaults(self):
        """Test AI player scenario with defaults"""
        scenario = CLITestHelpers.create_ai_player_scenario()
        
        assert 'args' in scenario
        assert 'ai_player' in scenario
        assert 'expected_success' in scenario
        assert scenario['expected_success'] is True
        assert scenario['args'].command == 'run-character'
        assert scenario['args'].name == 'ai_character'

    def test_create_ai_player_scenario_custom(self):
        """Test AI player scenario with custom values"""
        scenario = CLITestHelpers.create_ai_player_scenario(
            character_name="custom_ai",
            goal="level_up",
            max_runtime=120,
            should_succeed=False
        )
        
        assert scenario['expected_success'] is False
        assert scenario['args'].name == 'custom_ai'
        assert scenario['args'].goal == 'level_up'
        assert scenario['args'].max_runtime == 120

    def test_create_diagnostic_scenario_defaults(self):
        """Test diagnostic scenario with defaults"""
        scenario = CLITestHelpers.create_diagnostic_scenario()
        
        assert 'args' in scenario
        assert 'diagnostic_commands' in scenario
        assert 'expected_diagnostic_type' in scenario
        assert scenario['expected_diagnostic_type'] == 'diagnose-state'
        assert scenario['args'].command == 'diagnose-state'
        assert scenario['args'].name == 'diagnostic_character'

    def test_create_diagnostic_scenario_custom(self):
        """Test diagnostic scenario with custom values"""
        scenario = CLITestHelpers.create_diagnostic_scenario(
            diagnostic_type="diagnose-actions",
            character_name="debug_char",
            options={"verbose": True, "show_costs": True}
        )
        
        assert scenario['expected_diagnostic_type'] == 'diagnose-actions'
        assert scenario['args'].command == 'diagnose-actions'
        assert scenario['args'].name == 'debug_char'
        assert scenario['args'].verbose is True
        assert scenario['args'].show_costs is True

    @pytest.mark.asyncio
    async def test_simulate_cli_command_execution_create_character(self):
        """Test CLI command execution simulation for create character"""
        cli_manager = Mock()
        cli_manager.handle_create_character = AsyncMock()
        
        args = Mock()
        args.command = 'create-character'
        
        result = await CLITestHelpers.simulate_cli_command_execution(
            cli_manager, 'create-character', args
        )
        
        assert result['command_executed'] == 'create-character'
        assert result['args_used'] == args
        assert result['cli_manager_state'] == cli_manager
        cli_manager.handle_create_character.assert_called_once_with(args)

    @pytest.mark.asyncio
    async def test_simulate_cli_command_execution_with_dependencies(self):
        """Test CLI command execution with mock dependencies"""
        cli_manager = Mock()
        cli_manager.handle_list_characters = AsyncMock()
        
        args = Mock()
        mock_api_client = Mock()
        
        result = await CLITestHelpers.simulate_cli_command_execution(
            cli_manager, 'list-characters', args, 
            {'api_client': mock_api_client}
        )
        
        assert cli_manager.api_client == mock_api_client
        cli_manager.handle_list_characters.assert_called_once_with(args)

    @pytest.mark.asyncio
    async def test_simulate_cli_command_execution_all_commands(self):
        """Test CLI command execution for all supported commands"""
        commands_to_test = [
            'create-character', 'delete-character', 'list-characters',
            'run-character', 'stop-character', 'status-character',
            'diagnose-state', 'diagnose-actions', 'diagnose-plan', 'test-planning'
        ]
        
        for command in commands_to_test:
            cli_manager = Mock()
            # Set up all the handler methods
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
            
            args = Mock()
            
            result = await CLITestHelpers.simulate_cli_command_execution(
                cli_manager, command, args
            )
            
            assert result['command_executed'] == command
            assert result['args_used'] == args
            assert result['cli_manager_state'] == cli_manager

    def test_create_argument_parsing_test_cases(self):
        """Test argument parsing test cases creation"""
        test_cases = CLITestHelpers.create_argument_parsing_test_cases()
        
        assert isinstance(test_cases, list)
        assert len(test_cases) > 0
        
        # Check first test case structure
        first_case = test_cases[0]
        assert 'name' in first_case
        assert 'args' in first_case
        assert 'expected_command' in first_case
        assert 'expected_valid' in first_case

    def test_validate_character_name_valid(self):
        """Test character name validation for valid names"""
        assert CLITestHelpers.validate_character_name("test_char") is True
        assert CLITestHelpers.validate_character_name("abc123") is True
        assert CLITestHelpers.validate_character_name("TestChar123") is True

    def test_validate_character_name_invalid(self):
        """Test character name validation for invalid names"""
        assert CLITestHelpers.validate_character_name("ab") is False  # too short
        assert CLITestHelpers.validate_character_name("very_long_character_name") is False  # too long
        assert CLITestHelpers.validate_character_name("char@name") is False  # invalid chars

    def test_create_error_scenarios(self):
        """Test error scenarios creation"""
        error_scenarios = CLITestHelpers.create_error_scenarios()
        
        assert isinstance(error_scenarios, list)
        assert len(error_scenarios) > 0
        
        # Check first error scenario structure
        first_scenario = error_scenarios[0]
        assert 'name' in first_scenario
        assert 'error_type' in first_scenario
        assert 'error_message' in first_scenario
        assert 'expected_error_text' in first_scenario


class TestCLIFixtures:
    """Test CLI fixtures functionality"""

    def test_cli_mock_factory_fixture(self, cli_mock_factory):
        """Test CLI mock factory fixture"""
        assert cli_mock_factory == CLIMockFactory

    def test_cli_assertions_fixture(self, cli_assertions):
        """Test CLI assertions fixture"""
        assert cli_assertions == CLITestAssertions

    def test_cli_helpers_fixture(self, cli_helpers):
        """Test CLI helpers fixture"""
        assert cli_helpers == CLITestHelpers

    def test_mock_cli_manager_fixture(self, mock_cli_manager):
        """Test mock CLI manager fixture"""
        assert mock_cli_manager is not None
        assert hasattr(mock_cli_manager, 'log_manager')

    def test_mock_argument_parser_fixture(self, mock_argument_parser):
        """Test mock argument parser fixture"""
        assert mock_argument_parser is not None
        assert mock_argument_parser.prog == "artifactsmmo-ai-player"

    def test_mock_api_client_fixture(self, mock_api_client):
        """Test mock API client fixture"""
        assert mock_api_client is not None
        assert hasattr(mock_api_client, 'create_character')

    def test_mock_character_fixture(self, mock_character):
        """Test mock character fixture"""
        assert mock_character is not None
        assert mock_character.name == "test_character"

    def test_mock_ai_player_fixture(self, mock_ai_player):
        """Test mock AI player fixture"""
        assert mock_ai_player is not None
        assert mock_ai_player.character_name == "test_character"

    def test_mock_diagnostic_commands_fixture(self, mock_diagnostic_commands):
        """Test mock diagnostic commands fixture"""
        assert mock_diagnostic_commands is not None
        assert hasattr(mock_diagnostic_commands, 'diagnose_state')

    def test_sample_parsed_args_fixture(self, sample_parsed_args):
        """Test sample parsed args fixture"""
        assert sample_parsed_args is not None
        assert sample_parsed_args.command == "list-characters"

    def test_character_creation_scenario_fixture(self, character_creation_scenario):
        """Test character creation scenario fixture"""
        assert character_creation_scenario is not None
        assert 'args' in character_creation_scenario
        assert 'expected_success' in character_creation_scenario

    def test_ai_player_scenario_fixture(self, ai_player_scenario):
        """Test AI player scenario fixture"""
        assert ai_player_scenario is not None
        assert 'args' in ai_player_scenario
        assert 'ai_player' in ai_player_scenario

    def test_diagnostic_scenario_fixture(self, diagnostic_scenario):
        """Test diagnostic scenario fixture"""
        assert diagnostic_scenario is not None
        assert 'args' in diagnostic_scenario
        assert 'diagnostic_commands' in diagnostic_scenario

    def test_fixture_functions_direct(self):
        """Test fixture functions directly to ensure 100% coverage"""
        from tests.test_cli import (
            cli_mock_factory, cli_assertions, cli_helpers, mock_cli_manager,
            mock_argument_parser, mock_api_client, mock_character, mock_ai_player,
            mock_diagnostic_commands, sample_parsed_args, character_creation_scenario,
            ai_player_scenario, diagnostic_scenario
        )
        
        # Test each fixture function exists and is callable
        assert callable(cli_mock_factory)
        assert callable(cli_assertions)
        assert callable(cli_helpers)
        assert callable(mock_cli_manager)
        assert callable(mock_argument_parser)
        assert callable(mock_api_client)
        assert callable(mock_character)
        assert callable(mock_ai_player)
        assert callable(mock_diagnostic_commands)
        assert callable(sample_parsed_args)
        assert callable(character_creation_scenario)
        assert callable(ai_player_scenario)
        assert callable(diagnostic_scenario)


class TestCLIConfiguration:
    """Test CLI configuration constants"""

    def test_timeout_constants(self):
        """Test CLI timeout constants"""
        assert CLI_TEST_TIMEOUT == 10.0
        assert ASYNC_CLI_TEST_TIMEOUT == 5.0
        assert CLI_COMMAND_TIMEOUT == 3.0


class TestCLIIntegrationScenarios:
    """Test integrated CLI scenarios using the utilities"""

    @pytest.mark.asyncio
    async def test_complete_character_workflow(self, cli_helpers, cli_assertions):
        """Test complete character management workflow"""
        # Create character creation scenario
        creation_scenario = cli_helpers.create_character_creation_scenario(
            character_name="workflow_char",
            skin="men1"
        )
        
        # Validate scenario
        cli_assertions.assert_command_parsed(
            creation_scenario['args'],
            'create-character',
            {'name': 'workflow_char', 'skin': 'men1'}
        )
        
        assert creation_scenario['expected_success'] is True

    @pytest.mark.asyncio
    async def test_ai_player_workflow(self, cli_helpers, cli_assertions):
        """Test AI player management workflow"""
        # Create AI player scenario
        ai_scenario = cli_helpers.create_ai_player_scenario(
            character_name="ai_workflow_char",
            goal="level_up",
            max_runtime=60
        )
        
        # Validate scenario
        cli_assertions.assert_ai_player_command_args(
            ai_scenario['args'],
            character_name="ai_workflow_char",
            goal="level_up",
            max_runtime=60
        )
        
        assert ai_scenario['expected_success'] is True

    @pytest.mark.asyncio
    async def test_diagnostic_workflow(self, cli_helpers, cli_assertions):
        """Test diagnostic command workflow"""
        # Create diagnostic scenario
        diag_scenario = cli_helpers.create_diagnostic_scenario(
            diagnostic_type="diagnose-plan",
            character_name="diag_char",
            options={"verbose": True, "show_steps": True}
        )
        
        # Validate scenario
        cli_assertions.assert_diagnostic_command_args(
            diag_scenario['args'],
            character_name="diag_char",
            verbose=True
        )
        
        assert diag_scenario['expected_diagnostic_type'] == "diagnose-plan"

    def test_error_handling_scenarios(self, cli_helpers):
        """Test error handling scenarios"""
        error_scenarios = cli_helpers.create_error_scenarios()
        
        # Test each error scenario has required fields
        for scenario in error_scenarios:
            assert 'name' in scenario
            assert 'error_type' in scenario
            assert 'error_message' in scenario
            assert 'expected_error_text' in scenario
            
            # Verify error types are exception classes
            assert issubclass(scenario['error_type'], BaseException)

    def test_argument_parsing_test_cases(self, cli_helpers):
        """Test argument parsing test case generation"""
        test_cases = cli_helpers.create_argument_parsing_test_cases()
        
        # Verify structure of each test case
        for case in test_cases:
            assert 'name' in case
            assert 'args' in case
            assert 'expected_command' in case
            assert 'expected_valid' in case
            
            # Verify args is a list
            assert isinstance(case['args'], list)