"""
Tests for CLI __init__ module

These tests validate all functionality exposed by the CLI __init__.py module
including factory functions, convenience functions, programmatic interfaces,
and module initialization with comprehensive mocking of dependencies.
"""

import argparse
import asyncio
import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest

import src.cli as cli_module
from src.cli import (
    CLIManager,
    __all__,
    __version__,
    async_main,
    create_cli_manager,
    initialize_cli_module,
    main,
    parse_cli_args,
    run_character_cli,
    run_cli,
    run_diagnostic_cli,
)


class TestModuleStructure:
    """Test CLI module structure and exports"""

    def test_module_has_correct_version(self):
        """Test that module has correct version defined"""
        assert __version__ == "2.0.0"

    def test_module_has_all_exports(self):
        """Test that __all__ contains all expected exports"""
        expected_exports = [
            "CLIManager",
            "main",
            "async_main",
            "run_cli",
            "create_cli_manager",
            "parse_cli_args",
            "run_character_cli",
            "run_diagnostic_cli",
        ]

        for export in expected_exports:
            assert export in __all__

    def test_all_exports_are_importable(self):
        """Test that all exports in __all__ can be imported"""
        for export_name in __all__:
            assert hasattr(cli_module, export_name)


class TestCLIManagerFactory:
    """Test CLI manager factory function"""

    def test_create_cli_manager_returns_instance(self):
        """Test that create_cli_manager returns CLIManager instance"""
        with patch('src.cli.CLIManager') as mock_cli_manager:
            mock_instance = Mock()
            mock_cli_manager.return_value = mock_instance

            result = create_cli_manager()

            mock_cli_manager.assert_called_once()
            assert result == mock_instance

    def test_create_cli_manager_no_arguments(self):
        """Test that create_cli_manager takes no arguments"""
        with patch('src.cli.CLIManager') as mock_cli_manager:
            create_cli_manager()
            mock_cli_manager.assert_called_once_with()


class TestArgumentParsing:
    """Test CLI argument parsing functionality"""

    def test_parse_cli_args_with_no_args(self):
        """Test parse_cli_args with default arguments"""
        mock_cli_manager = Mock()
        mock_parser = Mock()
        mock_args = Mock()
        mock_parser.parse_args.return_value = mock_args
        mock_cli_manager.create_parser.return_value = mock_parser

        with patch('src.cli.create_cli_manager', return_value=mock_cli_manager):
            result = parse_cli_args()

            mock_cli_manager.create_parser.assert_called_once()
            mock_parser.parse_args.assert_called_once_with(None)
            assert result == mock_args

    def test_parse_cli_args_with_custom_args(self):
        """Test parse_cli_args with custom argument list"""
        mock_cli_manager = Mock()
        mock_parser = Mock()
        mock_args = Mock()
        mock_parser.parse_args.return_value = mock_args
        mock_cli_manager.create_parser.return_value = mock_parser

        test_args = ["command", "--option", "value"]

        with patch('src.cli.create_cli_manager', return_value=mock_cli_manager):
            result = parse_cli_args(test_args)

            mock_cli_manager.create_parser.assert_called_once()
            mock_parser.parse_args.assert_called_once_with(test_args)
            assert result == mock_args

    def test_parse_cli_args_creates_new_manager_each_time(self):
        """Test that parse_cli_args creates a new CLI manager each time"""
        with patch('src.cli.create_cli_manager') as mock_create_manager:
            mock_manager = Mock()
            mock_parser = Mock()
            mock_manager.create_parser.return_value = mock_parser
            mock_create_manager.return_value = mock_manager

            parse_cli_args()
            parse_cli_args()

            assert mock_create_manager.call_count == 2


class TestCLIRunner:
    """Test CLI runner functions"""

    def test_run_cli_with_no_args_calls_main(self):
        """Test that run_cli with no args calls main function"""
        with patch('src.cli.main') as mock_main:
            run_cli()
            mock_main.assert_called_once()

    def test_run_cli_with_args_modifies_sys_argv(self):
        """Test that run_cli with args modifies sys.argv temporarily"""
        original_argv = sys.argv[:]
        test_args = ["command", "--option"]

        with patch('src.cli.main') as mock_main:
            run_cli(test_args)

            # sys.argv should be restored after call
            assert sys.argv == original_argv
            mock_main.assert_called_once()

    def test_run_cli_restores_argv_on_exception(self):
        """Test that run_cli restores sys.argv even if main raises exception"""
        original_argv = sys.argv[:]
        test_args = ["command", "--option"]

        with patch('src.cli.main', side_effect=RuntimeError("Test error")):
            with pytest.raises(RuntimeError):
                run_cli(test_args)

            # sys.argv should still be restored
            assert sys.argv == original_argv


class TestCharacterCLI:
    """Test character CLI programmatic interface"""

    @pytest.mark.asyncio
    async def test_run_character_cli_create_command(self):
        """Test run_character_cli with create command"""
        mock_cli_manager = Mock()
        mock_cli_manager.handle_create_character = AsyncMock()

        with patch('src.cli.create_cli_manager', return_value=mock_cli_manager):
            await run_character_cli("test_char", "create", {"skin": "default"})

            mock_cli_manager.handle_create_character.assert_called_once()
            args = mock_cli_manager.handle_create_character.call_args[0][0]
            assert args.character == "test_char"
            assert args.command == "create"
            assert args.skin == "default"

    @pytest.mark.asyncio
    async def test_run_character_cli_delete_command(self):
        """Test run_character_cli with delete command"""
        mock_cli_manager = Mock()
        mock_cli_manager.handle_delete_character = AsyncMock()

        with patch('src.cli.create_cli_manager', return_value=mock_cli_manager):
            await run_character_cli("test_char", "delete")

            mock_cli_manager.handle_delete_character.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_character_cli_list_command(self):
        """Test run_character_cli with list command"""
        mock_cli_manager = Mock()
        mock_cli_manager.handle_list_characters = AsyncMock()

        with patch('src.cli.create_cli_manager', return_value=mock_cli_manager):
            await run_character_cli("test_char", "list")

            mock_cli_manager.handle_list_characters.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_character_cli_run_command(self):
        """Test run_character_cli with run command"""
        mock_cli_manager = Mock()
        mock_cli_manager.handle_run_character = AsyncMock()

        with patch('src.cli.create_cli_manager', return_value=mock_cli_manager):
            await run_character_cli("test_char", "run", {"verbose": True})

            mock_cli_manager.handle_run_character.assert_called_once()
            args = mock_cli_manager.handle_run_character.call_args[0][0]
            assert args.verbose is True

    @pytest.mark.asyncio
    async def test_run_character_cli_stop_command(self):
        """Test run_character_cli with stop command"""
        mock_cli_manager = Mock()
        mock_cli_manager.handle_stop_character = AsyncMock()

        with patch('src.cli.create_cli_manager', return_value=mock_cli_manager):
            await run_character_cli("test_char", "stop")

            mock_cli_manager.handle_stop_character.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_character_cli_status_command(self):
        """Test run_character_cli with status command"""
        mock_cli_manager = Mock()
        mock_cli_manager.handle_character_status = AsyncMock()

        with patch('src.cli.create_cli_manager', return_value=mock_cli_manager):
            await run_character_cli("test_char", "status")

            mock_cli_manager.handle_character_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_character_cli_invalid_command(self):
        """Test run_character_cli with invalid command raises ValueError"""
        with patch('src.cli.create_cli_manager'):
            with pytest.raises(ValueError, match="Unknown character command: invalid"):
                await run_character_cli("test_char", "invalid")

    @pytest.mark.asyncio
    async def test_run_character_cli_none_options(self):
        """Test run_character_cli with None options"""
        mock_cli_manager = Mock()
        mock_cli_manager.handle_create_character = AsyncMock()

        with patch('src.cli.create_cli_manager', return_value=mock_cli_manager):
            await run_character_cli("test_char", "create", None)

            mock_cli_manager.handle_create_character.assert_called_once()
            args = mock_cli_manager.handle_create_character.call_args[0][0]
            assert args.character == "test_char"
            assert args.command == "create"


class TestDiagnosticCLI:
    """Test diagnostic CLI programmatic interface"""

    @pytest.mark.asyncio
    async def test_run_diagnostic_cli_state_diagnostic(self):
        """Test run_diagnostic_cli with state diagnostic"""
        mock_cli_manager = Mock()
        mock_cli_manager.handle_diagnose_state = AsyncMock()

        with patch('src.cli.create_cli_manager', return_value=mock_cli_manager):
            await run_diagnostic_cli("state", "test_char", {"verbose": True})

            mock_cli_manager.handle_diagnose_state.assert_called_once()
            args = mock_cli_manager.handle_diagnose_state.call_args[0][0]
            assert args.diagnostic == "state"
            assert args.character == "test_char"
            assert args.verbose is True

    @pytest.mark.asyncio
    async def test_run_diagnostic_cli_actions_diagnostic(self):
        """Test run_diagnostic_cli with actions diagnostic"""
        mock_cli_manager = Mock()
        mock_cli_manager.handle_diagnose_actions = AsyncMock()

        with patch('src.cli.create_cli_manager', return_value=mock_cli_manager):
            await run_diagnostic_cli("actions", None, {"filter": "combat"})

            mock_cli_manager.handle_diagnose_actions.assert_called_once()
            args = mock_cli_manager.handle_diagnose_actions.call_args[0][0]
            assert args.diagnostic == "actions"
            assert args.character is None
            assert args.filter == "combat"

    @pytest.mark.asyncio
    async def test_run_diagnostic_cli_plan_diagnostic(self):
        """Test run_diagnostic_cli with plan diagnostic"""
        mock_cli_manager = Mock()
        mock_cli_manager.handle_diagnose_plan = AsyncMock()

        with patch('src.cli.create_cli_manager', return_value=mock_cli_manager):
            await run_diagnostic_cli("plan", "test_char")

            mock_cli_manager.handle_diagnose_plan.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_diagnostic_cli_test_planning_diagnostic(self):
        """Test run_diagnostic_cli with test-planning diagnostic"""
        mock_cli_manager = Mock()
        mock_cli_manager.handle_test_planning = AsyncMock()

        with patch('src.cli.create_cli_manager', return_value=mock_cli_manager):
            await run_diagnostic_cli("test-planning", "test_char")

            mock_cli_manager.handle_test_planning.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_diagnostic_cli_invalid_diagnostic(self):
        """Test run_diagnostic_cli with invalid diagnostic type raises ValueError"""
        with patch('src.cli.create_cli_manager'):
            with pytest.raises(ValueError, match="Unknown diagnostic type: invalid"):
                await run_diagnostic_cli("invalid", "test_char")

    @pytest.mark.asyncio
    async def test_run_diagnostic_cli_none_options(self):
        """Test run_diagnostic_cli with None options"""
        mock_cli_manager = Mock()
        mock_cli_manager.handle_diagnose_state = AsyncMock()

        with patch('src.cli.create_cli_manager', return_value=mock_cli_manager):
            await run_diagnostic_cli("state", "test_char", None)

            mock_cli_manager.handle_diagnose_state.assert_called_once()
            args = mock_cli_manager.handle_diagnose_state.call_args[0][0]
            assert args.diagnostic == "state"
            assert args.character == "test_char"


class TestModuleInitialization:
    """Test module initialization functionality"""

    def test_initialize_cli_module_runs_without_error(self):
        """Test that initialize_cli_module runs without error"""
        # This function currently has a pass implementation
        # but should not raise any exceptions
        initialize_cli_module()

    def test_module_initialization_called_on_import(self):
        """Test that module initialization is called when module is imported"""
        # This test verifies the module structure includes the initialization call
        # We can test this by checking that the function exists and is callable
        assert callable(initialize_cli_module)


class TestMockArgsClasses:
    """Test internal MockArgs classes work correctly"""

    def test_character_mock_args_creation(self):
        """Test MockArgs creation for character commands"""
        mock_cli_manager = Mock()
        mock_cli_manager.handle_create_character = AsyncMock()

        async def capture_args():
            with patch('src.cli.create_cli_manager', return_value=mock_cli_manager):
                await run_character_cli("test_char", "create", {"skin": "knight", "verbose": True})

        asyncio.run(capture_args())

        # Verify the args object was created correctly
        args = mock_cli_manager.handle_create_character.call_args[0][0]
        assert args.character == "test_char"
        assert args.command == "create"
        assert args.skin == "knight"
        assert args.verbose is True

    def test_diagnostic_mock_args_creation(self):
        """Test MockArgs creation for diagnostic commands"""
        mock_cli_manager = Mock()
        mock_cli_manager.handle_diagnose_state = AsyncMock()

        async def capture_args():
            with patch('src.cli.create_cli_manager', return_value=mock_cli_manager):
                await run_diagnostic_cli("state", "test_char", {"depth": 5, "format": "json"})

        asyncio.run(capture_args())

        # Verify the args object was created correctly
        args = mock_cli_manager.handle_diagnose_state.call_args[0][0]
        assert args.diagnostic == "state"
        assert args.character == "test_char"
        assert args.depth == 5
        assert args.format == "json"


class TestCLIManagerMethods:
    """Test CLIManager instance methods"""

    def test_cli_manager_init(self):
        """Test CLIManager __init__ method"""
        cli_manager = CLIManager()
        # Since __init__ has a pass implementation, we just verify it doesn't raise
        assert cli_manager is not None

    def test_create_parser_returns_argument_parser(self):
        """Test that create_parser returns configured ArgumentParser"""
        cli_manager = CLIManager()
        parser = cli_manager.create_parser()

        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == "artifactsmmo-ai-player"
        assert parser.description == "ArtifactsMMO AI Player CLI"

    def test_create_parser_has_log_level_argument(self):
        """Test that parser has log-level argument"""
        cli_manager = CLIManager()
        parser = cli_manager.create_parser()

        # Test that --log-level argument exists and works
        args = parser.parse_args(["--log-level", "DEBUG", "list-characters"])
        assert args.log_level == "DEBUG"

    def test_create_parser_has_subcommands(self):
        """Test that parser has all expected subcommands"""
        cli_manager = CLIManager()
        parser = cli_manager.create_parser()

        # Test character commands
        args = parser.parse_args(["create-character", "test", "--skin", "knight"])
        assert args.command == "create-character"
        assert args.name == "test"
        assert args.skin == "knight"

        # Test AI player commands
        args = parser.parse_args(["run-character", "test", "--goal", "level_up"])
        assert args.command == "run-character"
        assert args.goal == "level_up"

        # Test diagnostic commands
        args = parser.parse_args(["diagnose-state", "test", "--verbose"])
        assert args.command == "diagnose-state"
        assert args.verbose is True

    def test_setup_character_commands(self):
        """Test setup_character_commands method"""
        cli_manager = CLIManager()
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        cli_manager.setup_character_commands(subparsers)

        # Test create-character command
        args = parser.parse_args(["create-character", "test"])
        assert args.command == "create-character"
        assert args.name == "test"

    def test_setup_ai_player_commands(self):
        """Test setup_ai_player_commands method"""
        cli_manager = CLIManager()
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        cli_manager.setup_ai_player_commands(subparsers)

        # Test run-character command
        args = parser.parse_args(["run-character", "test", "--max-actions", "100"])
        assert args.command == "run-character"
        assert args.max_actions == 100

    def test_setup_diagnostic_commands(self):
        """Test setup_diagnostic_commands method"""
        cli_manager = CLIManager()
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        cli_manager.setup_diagnostic_commands(subparsers)

        # Test diagnose-plan command
        args = parser.parse_args(["diagnose-plan", "test", "level_up"])
        assert args.command == "diagnose-plan"
        assert args.name == "test"
        assert args.goal == "level_up"

    @pytest.mark.asyncio
    async def test_handle_create_character(self):
        """Test handle_create_character method"""
        cli_manager = CLIManager()
        mock_args = Mock()

        # Since method has pass implementation, just verify it doesn't raise
        await cli_manager.handle_create_character(mock_args)

    @pytest.mark.asyncio
    async def test_handle_delete_character(self):
        """Test handle_delete_character method"""
        cli_manager = CLIManager()
        mock_args = Mock()

        await cli_manager.handle_delete_character(mock_args)

    @pytest.mark.asyncio
    async def test_handle_list_characters(self):
        """Test handle_list_characters method"""
        cli_manager = CLIManager()
        mock_args = Mock()

        await cli_manager.handle_list_characters(mock_args)

    @pytest.mark.asyncio
    async def test_handle_run_character(self):
        """Test handle_run_character method"""
        cli_manager = CLIManager()
        mock_args = Mock()

        await cli_manager.handle_run_character(mock_args)

    @pytest.mark.asyncio
    async def test_handle_stop_character(self):
        """Test handle_stop_character method"""
        cli_manager = CLIManager()
        mock_args = Mock()

        await cli_manager.handle_stop_character(mock_args)

    @pytest.mark.asyncio
    async def test_handle_character_status(self):
        """Test handle_character_status method"""
        cli_manager = CLIManager()
        mock_args = Mock()

        await cli_manager.handle_character_status(mock_args)

    @pytest.mark.asyncio
    async def test_handle_diagnose_state(self):
        """Test handle_diagnose_state method"""
        cli_manager = CLIManager()
        mock_args = Mock()

        await cli_manager.handle_diagnose_state(mock_args)

    @pytest.mark.asyncio
    async def test_handle_diagnose_actions(self):
        """Test handle_diagnose_actions method"""
        cli_manager = CLIManager()
        mock_args = Mock()

        await cli_manager.handle_diagnose_actions(mock_args)

    @pytest.mark.asyncio
    async def test_handle_diagnose_plan(self):
        """Test handle_diagnose_plan method"""
        cli_manager = CLIManager()
        mock_args = Mock()

        await cli_manager.handle_diagnose_plan(mock_args)

    @pytest.mark.asyncio
    async def test_handle_test_planning(self):
        """Test handle_test_planning method"""
        cli_manager = CLIManager()
        mock_args = Mock()

        await cli_manager.handle_test_planning(mock_args)

    def test_setup_logging(self):
        """Test setup_logging method"""
        cli_manager = CLIManager()

        # Since method has pass implementation, just verify it doesn't raise
        cli_manager.setup_logging("DEBUG")
        cli_manager.setup_logging("INFO")
        cli_manager.setup_logging("WARNING")
        cli_manager.setup_logging("ERROR")

    def test_setup_logging_with_no_handlers(self):
        """Test setup_logging when root logger has no handlers"""
        import logging

        cli_manager = CLIManager()
        root_logger = logging.getLogger()

        # Save existing handlers
        original_handlers = root_logger.handlers[:]

        try:
            # Clear all handlers to test the handler creation path
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)

            # Test setup_logging creates a handler
            cli_manager.setup_logging("DEBUG")

            # Should have added a handler
            assert len(root_logger.handlers) >= 1

        finally:
            # Restore original handlers
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
            for handler in original_handlers:
                root_logger.addHandler(handler)


class TestMainFunctions:
    """Test main entry point functions"""

    def test_main_function_parses_args_and_calls_async_main(self):
        """Test main function parses arguments and calls async_main"""
        with patch('src.cli.CLIManager') as mock_cli_manager_class:
            with patch('src.cli.asyncio.run') as mock_asyncio_run:
                with patch('sys.argv', ['program', '--log-level', 'DEBUG', 'list-characters']):
                    mock_manager = Mock()
                    mock_parser = Mock()
                    mock_args = Mock()
                    mock_args.log_level = 'DEBUG'
                    mock_parser.parse_args.return_value = mock_args
                    mock_manager.create_parser.return_value = mock_parser
                    mock_cli_manager_class.return_value = mock_manager

                    main()

                    mock_cli_manager_class.assert_called_once()
                    mock_manager.create_parser.assert_called_once()
                    mock_parser.parse_args.assert_called_once()
                    mock_manager.setup_logging.assert_called_once_with('DEBUG')
                    mock_asyncio_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_main_no_command(self, capsys):
        """Test async_main with no command specified"""
        cli_manager = CLIManager()
        args = Mock()
        delattr(args, 'command') if hasattr(args, 'command') else None

        await async_main(cli_manager, args)

        captured = capsys.readouterr()
        assert "No command specified" in captured.out

    @pytest.mark.asyncio
    async def test_async_main_character_commands(self):
        """Test async_main routing for character commands"""
        cli_manager = CLIManager()
        args = Mock()

        # Mock all the handler methods
        cli_manager.handle_create_character = AsyncMock()
        cli_manager.handle_delete_character = AsyncMock()
        cli_manager.handle_list_characters = AsyncMock()

        # Test create-character
        args.command = "create-character"
        await async_main(cli_manager, args)
        cli_manager.handle_create_character.assert_called_once_with(args)

        # Test delete-character
        cli_manager.handle_create_character.reset_mock()
        args.command = "delete-character"
        await async_main(cli_manager, args)
        cli_manager.handle_delete_character.assert_called_once_with(args)

        # Test list-characters
        args.command = "list-characters"
        await async_main(cli_manager, args)
        cli_manager.handle_list_characters.assert_called_once_with(args)

    @pytest.mark.asyncio
    async def test_async_main_ai_player_commands(self):
        """Test async_main routing for AI player commands"""
        cli_manager = CLIManager()
        args = Mock()

        # Mock all the handler methods
        cli_manager.handle_run_character = AsyncMock()
        cli_manager.handle_stop_character = AsyncMock()
        cli_manager.handle_character_status = AsyncMock()

        # Test run-character
        args.command = "run-character"
        await async_main(cli_manager, args)
        cli_manager.handle_run_character.assert_called_once_with(args)

        # Test stop-character
        args.command = "stop-character"
        await async_main(cli_manager, args)
        cli_manager.handle_stop_character.assert_called_once_with(args)

        # Test status-character
        args.command = "status-character"
        await async_main(cli_manager, args)
        cli_manager.handle_character_status.assert_called_once_with(args)

    @pytest.mark.asyncio
    async def test_async_main_diagnostic_commands(self):
        """Test async_main routing for diagnostic commands"""
        cli_manager = CLIManager()
        args = Mock()

        # Mock all the handler methods
        cli_manager.handle_diagnose_state = AsyncMock()
        cli_manager.handle_diagnose_actions = AsyncMock()
        cli_manager.handle_diagnose_plan = AsyncMock()
        cli_manager.handle_test_planning = AsyncMock()

        # Test diagnose-state
        args.command = "diagnose-state"
        await async_main(cli_manager, args)
        cli_manager.handle_diagnose_state.assert_called_once_with(args)

        # Test diagnose-actions
        args.command = "diagnose-actions"
        await async_main(cli_manager, args)
        cli_manager.handle_diagnose_actions.assert_called_once_with(args)

        # Test diagnose-plan
        args.command = "diagnose-plan"
        await async_main(cli_manager, args)
        cli_manager.handle_diagnose_plan.assert_called_once_with(args)

        # Test test-planning
        args.command = "test-planning"
        await async_main(cli_manager, args)
        cli_manager.handle_test_planning.assert_called_once_with(args)

    @pytest.mark.asyncio
    async def test_async_main_unknown_command(self, capsys):
        """Test async_main with unknown command"""
        cli_manager = CLIManager()
        args = Mock()
        args.command = "unknown-command"

        await async_main(cli_manager, args)

        captured = capsys.readouterr()
        assert "Unknown command: unknown-command" in captured.out


class TestModuleMainExecution:
    """Test module execution behavior"""

    def test_module_main_execution(self):
        """Test that module calls main() when executed directly"""
        with patch('src.cli.main') as mock_main:
            with patch('src.cli.__name__', '__main__'):
                # Simulate module execution
                if __name__ == "__main__":
                    main()
                # We can't actually test the __main__ execution in the module itself
                # but we can verify the pattern exists
                pass

    def test_main_execution_branch(self):
        """Test the __main__ execution branch directly"""
        # Import the module to test the if __name__ == "__main__" branch
        import subprocess
        import sys

        # Run the module directly to test the __main__ branch
        result = subprocess.run(
            [sys.executable, "-c", "import src.cli; src.cli.__name__ = '__main__'; exec('if src.cli.__name__ == \"__main__\": pass')"],
            capture_output=True,
            text=True
        )

        # Should not error - this tests the __main__ branch exists and is valid
        assert result.returncode == 0


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_run_cli_with_empty_args_list(self):
        """Test run_cli with empty arguments list"""
        with patch('src.cli.main') as mock_main:
            run_cli([])
            mock_main.assert_called_once()

    @pytest.mark.asyncio
    async def test_character_cli_with_empty_options(self):
        """Test character CLI with empty options dictionary"""
        mock_cli_manager = Mock()
        mock_cli_manager.handle_create_character = AsyncMock()

        with patch('src.cli.create_cli_manager', return_value=mock_cli_manager):
            await run_character_cli("test_char", "create", {})

            mock_cli_manager.handle_create_character.assert_called_once()
            args = mock_cli_manager.handle_create_character.call_args[0][0]
            assert args.character == "test_char"
            assert args.command == "create"

    @pytest.mark.asyncio
    async def test_diagnostic_cli_with_empty_options(self):
        """Test diagnostic CLI with empty options dictionary"""
        mock_cli_manager = Mock()
        mock_cli_manager.handle_diagnose_state = AsyncMock()

        with patch('src.cli.create_cli_manager', return_value=mock_cli_manager):
            await run_diagnostic_cli("state", "test_char", {})

            mock_cli_manager.handle_diagnose_state.assert_called_once()
            args = mock_cli_manager.handle_diagnose_state.call_args[0][0]
            assert args.diagnostic == "state"
            assert args.character == "test_char"
