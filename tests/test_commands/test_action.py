"""Tests for action commands."""

from unittest.mock import Mock, patch

import httpx
import pytest
from artifactsmmo_api_client.errors import UnexpectedStatus
from rich.text import Text
from typer.testing import CliRunner

from artifactsmmo_cli.commands.action import (
    BatchResults,
    app,
    execute_fight_action,
    execute_gather_action,
    execute_rest_action,
)
from artifactsmmo_cli.models.responses import CLIResponse
from artifactsmmo_cli.utils.pathfinding import PathResult, PathStep


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_client_manager():
    """Mock the ClientManager."""
    with patch("artifactsmmo_cli.commands.action.ClientManager") as mock:
        mock_instance = Mock()
        mock.return_value = mock_instance
        mock_instance.client = Mock()
        mock_instance.client.my_characters = Mock()
        yield mock_instance


@pytest.fixture
def mock_api_response():
    """Mock API response."""
    mock_response = Mock()
    mock_response.status_code = 200
    return mock_response


class TestMoveCommand:
    """Test move command functionality."""

    def test_move_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful move command."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=True, message="Move completed")

            result = runner.invoke(app, ["move", "testchar", "5", "10"])

            assert result.exit_code == 0
            assert "Move completed" in result.stdout

    def test_move_with_cooldown(self, runner, mock_client_manager, mock_api_response):
        """Test move command with cooldown."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=False, cooldown_remaining=30, message=None, error=None)

            result = runner.invoke(app, ["move", "testchar", "5", "10"])

            assert result.exit_code == 0
            assert "cooldown" in result.stdout

    def test_move_error(self, runner, mock_client_manager, mock_api_response):
        """Test move command with error."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=False, cooldown_remaining=None, error="Invalid location")

            result = runner.invoke(app, ["move", "testchar", "5", "10"])

            assert result.exit_code == 1
            assert "Invalid location" in result.stdout

    def test_move_validation_error(self, runner):
        """Test move command with validation error."""
        result = runner.invoke(app, ["move", "", "5", "10"])
        assert result.exit_code != 0

    def test_move_api_exception(self, runner, mock_client_manager):
        """Test move command with API exception."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = UnexpectedStatus(status_code=478, content=b"{}")

            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=None, error="API Error")

                result = runner.invoke(app, ["move", "testchar", "5", "10"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout

    def test_move_api_exception_with_cooldown(self, runner, mock_client_manager):
        """Test move command with API exception and cooldown."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = UnexpectedStatus(status_code=478, content=b"{}")

            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=15, error=None)

                result = runner.invoke(app, ["move", "testchar", "5", "10"])

                assert result.exit_code == 1


class TestFightCommand:
    """Test fight command functionality."""

    def test_fight_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful fight command."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=True, message="Combat completed")

            result = runner.invoke(app, ["fight", "testchar"])

            assert result.exit_code == 0
            assert "Combat completed" in result.stdout

    def test_fight_success_with_detailed_results(self, runner, mock_client_manager, mock_api_response):
        """Test successful fight command with detailed combat results."""
        fight_data = {
            "result": "win",
            "xp": 150,
            "gold": 75,
            "drops": [{"code": "iron_ore", "quantity": 2}, {"code": "leather", "quantity": 1}],
        }

        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=True, data={"fight": fight_data}, message="Combat completed")

            with patch("artifactsmmo_cli.commands.action.format_combat_result") as mock_format:
                mock_format.return_value = Text(
                    "🗡️ Victory! | XP gained: 150 | Gold gained: 75 | Items dropped: 2x iron_ore, 1x leather"
                )

                result = runner.invoke(app, ["fight", "testchar"])

                assert result.exit_code == 0
                mock_format.assert_called_once_with(fight_data)

    def test_fight_success_with_loss(self, runner, mock_client_manager, mock_api_response):
        """Test fight command with loss result."""
        fight_data = {"result": "loss", "xp": 25, "gold": 0}

        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=True, data={"fight": fight_data}, message="Combat completed")

            with patch("artifactsmmo_cli.commands.action.format_combat_result") as mock_format:
                mock_format.return_value = Text("💀 Defeat! | XP gained: 25")

                result = runner.invoke(app, ["fight", "testchar"])

                assert result.exit_code == 0
                mock_format.assert_called_once_with(fight_data)

    def test_fight_success_without_fight_data(self, runner, mock_client_manager, mock_api_response):
        """Test fight command when API response doesn't contain fight data."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(
                success=True, data={"some_other_field": "value"}, message="Combat completed"
            )

            result = runner.invoke(app, ["fight", "testchar"])

            assert result.exit_code == 0
            assert "Combat completed" in result.stdout

    def test_fight_with_cooldown(self, runner, mock_client_manager, mock_api_response):
        """Test fight command with cooldown."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=False, cooldown_remaining=20, message=None, error=None)

            result = runner.invoke(app, ["fight", "testchar"])

            assert result.exit_code == 0
            assert "cooldown" in result.stdout

    def test_fight_error(self, runner, mock_client_manager, mock_api_response):
        """Test fight command with error."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=False, cooldown_remaining=None, error="No monster found")

            result = runner.invoke(app, ["fight", "testchar"])

            assert result.exit_code == 1
            assert "No monster found" in result.stdout

    def test_fight_validation_error(self, runner):
        """Test fight command with validation error."""
        result = runner.invoke(app, ["fight", ""])
        assert result.exit_code != 0

    def test_fight_api_exception(self, runner, mock_client_manager):
        """Test fight command with API exception."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = UnexpectedStatus(status_code=478, content=b"{}")

            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=None, error="API Error")

                result = runner.invoke(app, ["fight", "testchar"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout

    def test_fight_api_exception_with_cooldown(self, runner, mock_client_manager):
        """Test fight command with API exception and cooldown."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = UnexpectedStatus(status_code=478, content=b"{}")

            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=20, error=None)

                result = runner.invoke(app, ["fight", "testchar"])

                assert result.exit_code == 1


class TestGatherCommand:
    """Test gather command functionality."""

    def test_gather_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful gather command."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=True, message="Gathering completed")

            result = runner.invoke(app, ["gather", "testchar"])

            assert result.exit_code == 0
            assert "Gathering completed" in result.stdout

    def test_gather_with_cooldown(self, runner, mock_client_manager, mock_api_response):
        """Test gather command with cooldown."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=False, cooldown_remaining=25, message=None, error=None)

            result = runner.invoke(app, ["gather", "testchar"])

            assert result.exit_code == 0
            assert "cooldown" in result.stdout

    def test_gather_error(self, runner, mock_client_manager, mock_api_response):
        """Test gather command with error."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=False, cooldown_remaining=None, error="No resources found")

            result = runner.invoke(app, ["gather", "testchar"])

            assert result.exit_code == 1
            assert "No resources found" in result.stdout

    def test_gather_validation_error(self, runner):
        """Test gather command with validation error."""
        result = runner.invoke(app, ["gather", ""])
        assert result.exit_code != 0

    def test_gather_api_exception(self, runner, mock_client_manager):
        """Test gather command with API exception."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = UnexpectedStatus(status_code=478, content=b"{}")

            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=None, error="API Error")

                result = runner.invoke(app, ["gather", "testchar"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout

    def test_gather_api_exception_with_cooldown(self, runner, mock_client_manager):
        """Test gather command with API exception and cooldown."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = UnexpectedStatus(status_code=478, content=b"{}")

            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=25, error=None)

                result = runner.invoke(app, ["gather", "testchar"])

                assert result.exit_code == 1


class TestRestCommand:
    """Test rest command functionality."""

    def test_rest_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful rest command."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=True, message="Rest completed")

            result = runner.invoke(app, ["rest", "testchar"])

            assert result.exit_code == 0
            assert "Rest completed" in result.stdout

    def test_rest_with_cooldown(self, runner, mock_client_manager, mock_api_response):
        """Test rest command with cooldown."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=False, cooldown_remaining=10, message=None, error=None)

            result = runner.invoke(app, ["rest", "testchar"])

            assert result.exit_code == 0
            assert "cooldown" in result.stdout

    def test_rest_error(self, runner, mock_client_manager, mock_api_response):
        """Test rest command with error."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=False, cooldown_remaining=None, error="Cannot rest here")

            result = runner.invoke(app, ["rest", "testchar"])

            assert result.exit_code == 1
            assert "Cannot rest here" in result.stdout

    def test_rest_validation_error(self, runner):
        """Test rest command with validation error."""
        result = runner.invoke(app, ["rest", ""])
        assert result.exit_code != 0

    def test_rest_api_exception(self, runner, mock_client_manager):
        """Test rest command with API exception."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = UnexpectedStatus(status_code=478, content=b"{}")

            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=None, error="API Error")

                result = runner.invoke(app, ["rest", "testchar"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout

    def test_rest_api_exception_with_cooldown(self, runner, mock_client_manager):
        """Test rest command with API exception and cooldown."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = UnexpectedStatus(status_code=478, content=b"{}")

            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=10, error=None)

                result = runner.invoke(app, ["rest", "testchar"])

                assert result.exit_code == 1


class TestEquipCommand:
    """Test equip command functionality."""

    def test_equip_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful equip command."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=True, message="Item equipped")

            result = runner.invoke(app, ["equip", "testchar", "sword", "weapon"])

            assert result.exit_code == 0
            assert "Item equipped" in result.stdout

    def test_equip_with_quantity(self, runner, mock_client_manager, mock_api_response):
        """Test equip command with quantity."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=True, message="Item equipped")

            result = runner.invoke(app, ["equip", "testchar", "arrow", "utility1", "--quantity", "50"])

            assert result.exit_code == 0
            assert "Item equipped" in result.stdout

    def test_equip_with_cooldown(self, runner, mock_client_manager, mock_api_response):
        """Test equip command with cooldown."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=False, cooldown_remaining=5, message=None, error=None)

            result = runner.invoke(app, ["equip", "testchar", "sword", "weapon"])

            assert result.exit_code == 0
            assert "cooldown" in result.stdout

    def test_equip_error(self, runner, mock_client_manager, mock_api_response):
        """Test equip command with error."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=False, cooldown_remaining=None, error="Item not found")

            result = runner.invoke(app, ["equip", "testchar", "sword", "weapon"])

            assert result.exit_code == 1
            assert "Item not found" in result.stdout

    def test_equip_validation_error(self, runner):
        """Test equip command with validation error."""
        result = runner.invoke(app, ["equip", "", "sword", "weapon"])
        assert result.exit_code != 0

    def test_equip_api_exception(self, runner, mock_client_manager):
        """Test equip command with API exception."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = UnexpectedStatus(status_code=478, content=b"{}")

            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=None, error="API Error")

                result = runner.invoke(app, ["equip", "testchar", "sword", "weapon"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout

    def test_equip_api_exception_with_cooldown(self, runner, mock_client_manager):
        """Test equip command with API exception and cooldown."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = UnexpectedStatus(status_code=478, content=b"{}")

            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=5, error=None)

                result = runner.invoke(app, ["equip", "testchar", "sword", "weapon"])

                assert result.exit_code == 1


class TestUnequipCommand:
    """Test unequip command functionality."""

    def test_unequip_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful unequip command."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=True, message="Item unequipped")

            result = runner.invoke(app, ["unequip", "testchar", "weapon"])

            assert result.exit_code == 0
            assert "Item unequipped" in result.stdout

    def test_unequip_with_quantity(self, runner, mock_client_manager, mock_api_response):
        """Test unequip command with quantity."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=True, message="Item unequipped")

            result = runner.invoke(app, ["unequip", "testchar", "utility1", "--quantity", "25"])

            assert result.exit_code == 0
            assert "Item unequipped" in result.stdout

    def test_unequip_with_cooldown(self, runner, mock_client_manager, mock_api_response):
        """Test unequip command with cooldown."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=False, cooldown_remaining=3, message=None, error=None)

            result = runner.invoke(app, ["unequip", "testchar", "weapon"])

            assert result.exit_code == 0
            assert "cooldown" in result.stdout

    def test_unequip_error(self, runner, mock_client_manager, mock_api_response):
        """Test unequip command with error."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=False, cooldown_remaining=None, error="No item equipped")

            result = runner.invoke(app, ["unequip", "testchar", "weapon"])

            assert result.exit_code == 1
            assert "No item equipped" in result.stdout

    def test_unequip_validation_error(self, runner):
        """Test unequip command with validation error."""
        result = runner.invoke(app, ["unequip", "", "weapon"])
        assert result.exit_code != 0

    def test_unequip_api_exception(self, runner, mock_client_manager):
        """Test unequip command with API exception."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = UnexpectedStatus(status_code=478, content=b"{}")

            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=None, error="API Error")

                result = runner.invoke(app, ["unequip", "testchar", "weapon"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout

    def test_unequip_api_exception_with_cooldown(self, runner, mock_client_manager):
        """Test unequip command with API exception and cooldown."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = UnexpectedStatus(status_code=478, content=b"{}")

            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=3, error=None)

                result = runner.invoke(app, ["unequip", "testchar", "weapon"])

                assert result.exit_code == 1


class TestUseCommand:
    """Test use command functionality."""

    def test_use_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful use command."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=True, message="Item used")

            result = runner.invoke(app, ["use", "testchar", "potion"])

            assert result.exit_code == 0
            assert "Item used" in result.stdout

    def test_use_with_quantity(self, runner, mock_client_manager, mock_api_response):
        """Test use command with quantity."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=True, message="Item used")

            result = runner.invoke(app, ["use", "testchar", "potion", "--quantity", "3"])

            assert result.exit_code == 0
            assert "Item used" in result.stdout

    def test_use_with_cooldown(self, runner, mock_client_manager, mock_api_response):
        """Test use command with cooldown."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=False, cooldown_remaining=8, message=None, error=None)

            result = runner.invoke(app, ["use", "testchar", "potion"])

            assert result.exit_code == 0
            assert "cooldown" in result.stdout

    def test_use_error(self, runner, mock_client_manager, mock_api_response):
        """Test use command with error."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=False, cooldown_remaining=None, error="Item not found")

            result = runner.invoke(app, ["use", "testchar", "potion"])

            assert result.exit_code == 1
            assert "Item not found" in result.stdout

    def test_use_validation_error(self, runner):
        """Test use command with validation error."""
        result = runner.invoke(app, ["use", "", "potion"])
        assert result.exit_code != 0

    def test_use_api_exception(self, runner, mock_client_manager):
        """Test use command with API exception."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = UnexpectedStatus(status_code=478, content=b"{}")

            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=None, error="API Error")

                result = runner.invoke(app, ["use", "testchar", "potion"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout

    def test_use_api_exception_with_cooldown(self, runner, mock_client_manager):
        """Test use command with API exception and cooldown."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = UnexpectedStatus(status_code=478, content=b"{}")

            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=8, error=None)

                result = runner.invoke(app, ["use", "testchar", "potion"])

                assert result.exit_code == 1


class TestBatchCommand:
    """Test batch command functionality."""

    def test_batch_gather_success(self, runner, mock_client_manager):
        """Test successful batch gather command."""
        # Mock the API client properly
        mock_client_manager.api.action_gathering.return_value = Mock()

        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            # Mock successful gather responses
            mock_handle.return_value = CLIResponse.success_response(
                {"details": {"xp": 50, "items": [{"code": "wood", "quantity": 2}]}}, "Gathering completed"
            )

            result = runner.invoke(app, ["batch", "testchar", "gather", "--times", "3"])

            assert result.exit_code == 0
            assert "Starting batch gather operation" in result.stdout
            assert "Batch Operation Summary" in result.stdout
            assert mock_handle.call_count == 3

    def test_batch_fight_success(self, runner, mock_client_manager):
        """Test successful batch fight command."""
        # Mock the API client properly
        mock_client_manager.api.action_fight.return_value = Mock()

        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            # Mock successful fight responses
            mock_handle.return_value = CLIResponse.success_response(
                {"fight": {"result": "win", "xp": 100, "gold": 25, "drops": [{"code": "leather", "quantity": 1}]}},
                "Combat completed",
            )

            result = runner.invoke(app, ["batch", "testchar", "fight", "--times", "2"])

            assert result.exit_code == 0
            assert "Starting batch fight operation" in result.stdout
            assert "Batch Operation Summary" in result.stdout
            assert mock_handle.call_count == 2

    def test_batch_rest_success(self, runner, mock_client_manager):
        """Test successful batch rest command."""
        # Mock the API client properly
        mock_client_manager.api.action_rest.return_value = Mock()

        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            # Mock successful rest responses
            mock_handle.return_value = CLIResponse.success_response({}, "Rest completed")

            result = runner.invoke(app, ["batch", "testchar", "rest", "--times", "5"])

            assert result.exit_code == 0
            assert "Starting batch rest operation" in result.stdout
            assert "Batch Operation Summary" in result.stdout
            assert mock_handle.call_count == 5

    def test_batch_invalid_action(self, runner, mock_client_manager):
        """Test batch command with invalid action."""
        result = runner.invoke(app, ["batch", "testchar", "invalid", "--times", "3"])

        assert result.exit_code == 1
        assert "Invalid action 'invalid'" in result.stdout

    def test_batch_invalid_times(self, runner, mock_client_manager):
        """Test batch command with invalid times."""
        result = runner.invoke(app, ["batch", "testchar", "gather", "--times", "0"])

        assert result.exit_code == 1
        assert "Number of times must be greater than 0" in result.stdout

    def test_batch_with_cooldown_no_wait(self, runner, mock_client_manager):
        """Test batch command with cooldown and no wait flag."""
        # Mock the API client properly
        mock_client_manager.api.action_gathering.return_value = Mock()

        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            # First call succeeds, second has cooldown
            mock_handle.side_effect = [
                CLIResponse.success_response({"details": {"xp": 50}}, "Gathering completed"),
                CLIResponse.cooldown_response(30),
            ]

            result = runner.invoke(app, ["batch", "testchar", "gather", "--times", "2"])

            assert result.exit_code == 1  # Should exit on cooldown without wait flag
            assert "Action on cooldown" in result.stdout
            assert mock_handle.call_count == 2

    def test_batch_with_cooldown_and_wait(self, runner, mock_client_manager):
        """Test batch command with cooldown and wait flag."""
        # Mock the API client properly
        mock_client_manager.api.action_gathering.return_value = Mock()

        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            with patch("time.sleep") as mock_sleep:  # Mock sleep to speed up test
                # First call succeeds, second has cooldown, third succeeds after wait
                mock_handle.side_effect = [
                    CLIResponse.success_response({"details": {"xp": 50}}, "Gathering completed"),
                    CLIResponse.cooldown_response(2),  # Short cooldown for test
                    CLIResponse.success_response({"details": {"xp": 50}}, "Gathering completed"),
                ]

                result = runner.invoke(app, ["batch", "testchar", "gather", "--times", "2", "--wait-cooldown"])

                assert result.exit_code == 0
                assert "Waiting" in result.stdout
                assert mock_handle.call_count == 3  # Original + retry after cooldown
                assert mock_sleep.call_count >= 2  # Should sleep for cooldown

    def test_batch_continue_on_error(self, runner, mock_client_manager):
        """Test batch command with continue on error flag."""
        # Mock the API client properly
        mock_client_manager.api.action_gathering.return_value = Mock()

        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            # First succeeds, second fails, third succeeds
            mock_handle.side_effect = [
                CLIResponse.success_response({"details": {"xp": 50}}, "Gathering completed"),
                CLIResponse.error_response("No resources found"),
                CLIResponse.success_response({"details": {"xp": 50}}, "Gathering completed"),
            ]

            result = runner.invoke(app, ["batch", "testchar", "gather", "--times", "3", "--continue-on-error"])

            assert result.exit_code == 0  # Should not exit on error with continue flag
            assert "No resources found" in result.stdout
            assert mock_handle.call_count == 3

    def test_batch_stop_on_error(self, runner, mock_client_manager):
        """Test batch command stops on error without continue flag."""
        # Mock the API client properly
        mock_client_manager.api.action_gathering.return_value = Mock()

        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            # First succeeds, second fails
            mock_handle.side_effect = [
                CLIResponse.success_response({"details": {"xp": 50}}, "Gathering completed"),
                CLIResponse.error_response("No resources found"),
            ]

            result = runner.invoke(app, ["batch", "testchar", "gather", "--times", "3"])

            assert result.exit_code == 1  # Should exit on error without continue flag
            assert "No resources found" in result.stdout
            assert mock_handle.call_count == 2  # Should stop after error

    def test_batch_validation_error(self, runner):
        """Test batch command with validation error."""
        result = runner.invoke(app, ["batch", "", "gather", "--times", "3"])
        assert result.exit_code != 0

    def test_batch_results_accumulation(self, runner, mock_client_manager):
        """Test that batch results are properly accumulated."""
        # Mock the API client properly
        mock_client_manager.api.action_fight.return_value = Mock()

        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            # Mock multiple successful fight responses with different rewards
            mock_handle.side_effect = [
                CLIResponse.success_response(
                    {"fight": {"result": "win", "xp": 100, "gold": 25, "drops": [{"code": "leather", "quantity": 2}]}},
                    "Combat completed",
                ),
                CLIResponse.success_response(
                    {"fight": {"result": "win", "xp": 150, "gold": 30, "drops": [{"code": "iron_ore", "quantity": 1}]}},
                    "Combat completed",
                ),
            ]

            result = runner.invoke(app, ["batch", "testchar", "fight", "--times", "2"])

            assert result.exit_code == 0
            assert "Total XP Gained" in result.stdout
            assert "Total Gold Gained" in result.stdout
            assert "Items Collected" in result.stdout
            # Should show accumulated totals: 250 XP, 55 gold, 2x leather + 1x iron_ore

    def test_batch_outer_exception_handler(self, runner, mock_client_manager):
        """A caught error raised during batch setup hits the outer handler (lines 885-886)."""
        with patch("artifactsmmo_cli.commands.action.validate_character_name") as mock_validate:
            mock_validate.side_effect = UnexpectedStatus(status_code=500, content=b"batch crash")

            result = runner.invoke(app, ["batch", "testchar", "gather", "--times", "2"])

            assert result.exit_code == 1
            assert "Batch operation failed" in result.stdout


class TestActionExecutors:
    """Test action executor functions."""

    def test_execute_gather_action_success(self, mock_client_manager):
        """Test execute_gather_action with successful response."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=True, data={"details": {"xp": 50}})

            result = execute_gather_action("testchar")

            assert result.success is True
            mock_client_manager.api.action_gathering.assert_called_once_with(name="testchar")

    def test_execute_fight_action_success(self, mock_client_manager):
        """Test execute_fight_action with successful response."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=True, data={"fight": {"result": "win"}})

            result = execute_fight_action("testchar")

            assert result.success is True
            mock_client_manager.api.action_fight.assert_called_once_with(name="testchar")

    def test_execute_rest_action_success(self, mock_client_manager):
        """Test execute_rest_action with successful response."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=True, data={})

            result = execute_rest_action("testchar")

            assert result.success is True
            mock_client_manager.api.action_rest.assert_called_once_with(name="testchar")

    def test_execute_action_with_exception(self, mock_client_manager):
        """Test action executor handles exceptions."""
        with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_handle_error:
            mock_handle_error.return_value = Mock(success=False, error="API Error")
            mock_client_manager.api.action_gathering.side_effect = UnexpectedStatus(status_code=478, content=b"{}")

            result = execute_gather_action("testchar")

            assert result.success is False
            mock_handle_error.assert_called_once()


class TestBatchResults:
    """Test BatchResults class functionality."""

    def test_batch_results_initialization(self):
        """Test BatchResults initializes correctly."""
        results = BatchResults()
        assert results.total_attempts == 0
        assert results.successful_actions == 0
        assert results.failed_actions == 0
        assert results.total_xp == 0
        assert results.total_gold == 0
        assert len(results.items_collected) == 0
        assert len(results.errors) == 0

    def test_batch_results_add_success(self):
        """Test adding successful results."""
        results = BatchResults()

        # Test with fight data
        fight_data = {"fight": {"xp": 100, "gold": 25, "drops": [{"code": "leather", "quantity": 2}]}}
        results.add_success(fight_data)

        assert results.successful_actions == 1
        assert results.total_xp == 100
        assert results.total_gold == 25
        assert results.items_collected["leather"] == 2

    def test_batch_results_add_success_xp_from_details(self):
        """Test add_success extracts XP from details dict."""
        results = BatchResults()
        results.add_success({"details": {"xp": 75, "gold": 10, "items": [{"code": "wood", "quantity": 3}]}})

        assert results.successful_actions == 1
        assert results.total_xp == 75
        assert results.total_gold == 10
        assert results.items_collected["wood"] == 3

    def test_batch_results_add_success_xp_direct(self):
        """Test add_success extracts XP and gold from top-level keys."""
        results = BatchResults()
        results.add_success({"xp": 50, "gold": 20})

        assert results.total_xp == 50
        assert results.total_gold == 20

    def test_batch_results_add_success_no_data(self):
        """Test add_success with no data increments only successful_actions."""
        results = BatchResults()
        results.add_success(None)

        assert results.successful_actions == 1
        assert results.total_xp == 0
        assert results.total_gold == 0

    def test_batch_results_add_failure(self):
        """Test adding failed results."""
        results = BatchResults()
        results.add_failure("Test error")

        assert results.failed_actions == 1
        assert "Test error" in results.errors

    def test_batch_results_format_summary(self):
        """Test formatting results summary."""
        results = BatchResults()
        results.total_attempts = 5
        results.successful_actions = 4
        results.failed_actions = 1
        results.total_xp = 200
        results.total_gold = 50
        results.items_collected["wood"] = 10

        table = results.format_summary()
        assert table.title == "Batch Operation Summary"

    def test_batch_results_format_summary_no_attempts(self):
        """Test formatting results summary with zero attempts (no division by zero)."""
        results = BatchResults()
        results.total_attempts = 0

        table = results.format_summary()
        assert table.title == "Batch Operation Summary"


class TestExecuteActionExceptions:
    """Test exception branches in executor functions."""

    def test_execute_fight_action_exception(self):
        """Test execute_fight_action handles exceptions."""
        with patch("artifactsmmo_cli.commands.action.ClientManager") as mock_cm:
            mock_cm.return_value.api.action_fight.side_effect = UnexpectedStatus(status_code=478, content=b"{}")
            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_err:
                mock_err.return_value = Mock(success=False, error="fight error")

                result = execute_fight_action("testchar")

                assert result.success is False
                mock_err.assert_called_once()

    def test_execute_rest_action_exception(self):
        """Test execute_rest_action handles exceptions."""
        with patch("artifactsmmo_cli.commands.action.ClientManager") as mock_cm:
            mock_cm.return_value.api.action_rest.side_effect = UnexpectedStatus(status_code=478, content=b"{}")
            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_err:
                mock_err.return_value = Mock(success=False, error="rest error")

                result = execute_rest_action("testchar")

                assert result.success is False
                mock_err.assert_called_once()


class TestGatherCommandSuccessNoData:
    """Test gather command success path when no details key present."""

    def test_gather_success_no_details(self, runner, mock_client_manager):
        """Test gather success when data has no 'details' key."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=True, data={"other": "value"}, message="Gathering completed")

            result = runner.invoke(app, ["gather", "testchar"])

            assert result.exit_code == 0
            assert "Gathering completed" in result.stdout

    def test_gather_success_with_details(self, runner, mock_client_manager):
        """Test gather success when data has 'details' key."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            with patch("artifactsmmo_cli.commands.action.format_gathering_result") as mock_fmt:
                mock_fmt.return_value = Text("Gathered resources")
                mock_handle.return_value = Mock(
                    success=True, data={"details": {"xp": 50, "items": []}}, message="Gathering completed"
                )

                result = runner.invoke(app, ["gather", "testchar"])

                assert result.exit_code == 0
                mock_fmt.assert_called_once()


class TestGotoCommand:
    """Test goto_location command."""

    def test_goto_already_at_destination(self, runner, mock_client_manager):
        """Test goto when character is already at the destination."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(5, 10)):
            with patch("artifactsmmo_cli.commands.action.parse_destination", return_value=(5, 10)):
                with patch("artifactsmmo_cli.commands.action.validate_coordinates", return_value=(5, 10)):
                    result = runner.invoke(app, ["goto", "testchar", "5 10"])

                    assert result.exit_code == 0
                    assert "already at the destination" in result.stdout

    def test_goto_coordinate_args(self, runner, mock_client_manager):
        """Test goto with separate X Y coordinate arguments."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(5, 10)):
            with patch("artifactsmmo_cli.commands.action.validate_coordinates", return_value=(5, 10)):
                result = runner.invoke(app, ["goto", "testchar", "5", "10"])

                assert result.exit_code == 0
                assert "already at the destination" in result.stdout

    def test_goto_invalid_x_coordinate(self, runner, mock_client_manager):
        """Test goto with invalid X coordinate when Y is provided."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(0, 0)):
            result = runner.invoke(app, ["goto", "testchar", "notanumber", "10"])

            assert result.exit_code == 1
            assert "not a valid X coordinate" in result.stdout

    def test_goto_named_location(self, runner, mock_client_manager):
        """Test goto resolves a named location to coordinates."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(2, 3)):
            with patch("artifactsmmo_cli.commands.action.parse_destination", return_value="bank"):
                with patch("artifactsmmo_cli.commands.action.resolve_named_location", return_value=(2, 3)):
                    result = runner.invoke(app, ["goto", "testchar", "bank"])

                    assert result.exit_code == 0
                    assert "already at the destination" in result.stdout

    def test_goto_named_location_not_found(self, runner, mock_client_manager):
        """Test goto with a named location that cannot be resolved."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(0, 0)):
            with patch("artifactsmmo_cli.commands.action.parse_destination", return_value="unknownplace"):
                with patch(
                    "artifactsmmo_cli.commands.action.resolve_named_location",
                    side_effect=ValueError("Location not found"),
                ):
                    result = runner.invoke(app, ["goto", "testchar", "unknownplace"])

                    assert result.exit_code == 1
                    assert "Could not find location" in result.stdout

    def test_goto_character_position_error(self, runner, mock_client_manager):
        """Test goto when character position cannot be retrieved."""
        with patch(
            "artifactsmmo_cli.commands.action.get_character_position",
            side_effect=httpx.ConnectError("Character not found"),
        ):
            result = runner.invoke(app, ["goto", "testchar", "bank"])

            assert result.exit_code == 1
            assert "Could not get character position" in result.stdout

    def test_goto_move_success(self, runner, mock_client_manager):
        """A single move to the destination is issued (server routes the path)."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(0, 0)):
            with patch("artifactsmmo_cli.commands.action.parse_destination", return_value=(3, 0)):
                with patch("artifactsmmo_cli.commands.action.validate_coordinates", return_value=(3, 0)):
                    with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_resp:
                        mock_resp.return_value = Mock(success=True, cooldown_remaining=None, error=None)

                        result = runner.invoke(app, ["goto", "testchar", "3 0"])

                        assert result.exit_code == 0
                        assert "reached destination" in result.stdout
                        # exactly one move issued — the client does not walk tile-by-tile
                        mock_client_manager.api.action_move.assert_called_once()

    def test_goto_move_cooldown_no_wait(self, runner, mock_client_manager):
        """Test goto with move blocked by cooldown and no-wait-cooldown."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(0, 0)):
            with patch("artifactsmmo_cli.commands.action.parse_destination", return_value=(3, 0)):
                with patch("artifactsmmo_cli.commands.action.validate_coordinates", return_value=(3, 0)):
                    with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_resp:
                        mock_resp.return_value = Mock(success=False, cooldown_remaining=5, error=None)

                        result = runner.invoke(app, ["goto", "testchar", "3 0", "--no-wait-cooldown"])

                        assert "Move blocked by cooldown" in result.stdout

    def test_goto_move_error(self, runner, mock_client_manager):
        """Test goto with the move returning a non-cooldown error."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(0, 0)):
            with patch("artifactsmmo_cli.commands.action.parse_destination", return_value=(3, 0)):
                with patch("artifactsmmo_cli.commands.action.validate_coordinates", return_value=(3, 0)):
                    with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_resp:
                        mock_resp.return_value = Mock(success=False, cooldown_remaining=None, error="Move failed")

                        result = runner.invoke(app, ["goto", "testchar", "3 0"])

                        assert "Move failed" in result.stdout

    def test_goto_show_path_confirmed(self, runner, mock_client_manager):
        """Test goto with --show-path that the user confirms."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(0, 0)):
            with patch("artifactsmmo_cli.commands.action.parse_destination", return_value=(2, 0)):
                with patch("artifactsmmo_cli.commands.action.validate_coordinates", return_value=(2, 0)):
                    with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_resp:
                        mock_resp.return_value = Mock(success=True, cooldown_remaining=None, error=None)

                        result = runner.invoke(app, ["goto", "testchar", "2 0", "--show-path"], input="y\n")

                        assert result.exit_code == 0
                        assert "Move to (2, 0)?" in result.stdout
                        assert "reached destination" in result.stdout

    def test_goto_show_path_cancelled(self, runner, mock_client_manager):
        """Test goto with --show-path that the user cancels."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(0, 0)):
            with patch("artifactsmmo_cli.commands.action.parse_destination", return_value=(2, 0)):
                with patch("artifactsmmo_cli.commands.action.validate_coordinates", return_value=(2, 0)):
                    result = runner.invoke(app, ["goto", "testchar", "2 0", "--show-path"], input="n\n")

                    assert result.exit_code == 0
                    assert "cancelled" in result.stdout
                    mock_client_manager.api.action_move.assert_not_called()

    def test_goto_move_cooldown_wait_retry_success(self, runner, mock_client_manager):
        """Test goto waits out a cooldown and the retried move succeeds."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(0, 0)):
            with patch("artifactsmmo_cli.commands.action.parse_destination", return_value=(3, 0)):
                with patch("artifactsmmo_cli.commands.action.validate_coordinates", return_value=(3, 0)):
                    with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_resp:
                        mock_resp.side_effect = [
                            Mock(success=False, cooldown_remaining=1, error=None),
                            Mock(success=True, cooldown_remaining=None, error=None),
                        ]

                        with patch("time.sleep"):
                            result = runner.invoke(app, ["goto", "testchar", "3 0"])

                        assert result.exit_code == 0
                        assert "reached destination" in result.stdout
                        assert mock_client_manager.api.action_move.call_count == 2

    def test_goto_move_cooldown_wait_retry_failure(self, runner, mock_client_manager):
        """Test goto waits out a cooldown but the retried move still fails."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(0, 0)):
            with patch("artifactsmmo_cli.commands.action.parse_destination", return_value=(3, 0)):
                with patch("artifactsmmo_cli.commands.action.validate_coordinates", return_value=(3, 0)):
                    with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_resp:
                        mock_resp.side_effect = [
                            Mock(success=False, cooldown_remaining=1, error=None),
                            Mock(success=False, cooldown_remaining=None, error="Move failed after cooldown"),
                        ]

                        with patch("time.sleep"):
                            result = runner.invoke(app, ["goto", "testchar", "3 0"])

                        assert "Move failed after cooldown" in result.stdout

    def test_goto_move_exception_no_cooldown(self, runner, mock_client_manager):
        """Test goto when the move raises an exception without a cooldown."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(0, 0)):
            with patch("artifactsmmo_cli.commands.action.parse_destination", return_value=(3, 0)):
                with patch("artifactsmmo_cli.commands.action.validate_coordinates", return_value=(3, 0)):
                    with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_resp:
                        mock_resp.side_effect = httpx.ConnectError("Network error")

                        with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_err:
                            mock_err.return_value = Mock(success=False, cooldown_remaining=None, error="Network error")

                            result = runner.invoke(app, ["goto", "testchar", "3 0"])

                        assert "Network error" in result.stdout

    def test_goto_move_exception_cooldown_no_wait(self, runner, mock_client_manager):
        """Test goto when the move raises a cooldown exception with no-wait-cooldown."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(0, 0)):
            with patch("artifactsmmo_cli.commands.action.parse_destination", return_value=(3, 0)):
                with patch("artifactsmmo_cli.commands.action.validate_coordinates", return_value=(3, 0)):
                    with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_resp:
                        mock_resp.side_effect = httpx.ConnectError("cooldown error")

                        with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_err:
                            mock_err.return_value = Mock(success=False, cooldown_remaining=5, error=None)

                            result = runner.invoke(app, ["goto", "testchar", "3 0", "--no-wait-cooldown"])

                        assert "Move blocked by cooldown" in result.stdout

    def test_goto_move_exception_cooldown_wait_retry_success(self, runner, mock_client_manager):
        """Test goto recovers when the first move raises a cooldown and the retry succeeds."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(0, 0)):
            with patch("artifactsmmo_cli.commands.action.parse_destination", return_value=(3, 0)):
                with patch("artifactsmmo_cli.commands.action.validate_coordinates", return_value=(3, 0)):
                    with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_resp:
                        mock_resp.side_effect = [
                            httpx.ConnectError("cooldown"),
                            Mock(success=True, cooldown_remaining=None, error=None),
                        ]

                        with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_err:
                            mock_err.return_value = Mock(success=False, cooldown_remaining=1, error=None)

                            with patch("time.sleep"):
                                result = runner.invoke(app, ["goto", "testchar", "3 0"])

                        assert result.exit_code == 0
                        assert "reached destination" in result.stdout

    def test_goto_move_exception_cooldown_wait_retry_failure(self, runner, mock_client_manager):
        """Test goto when the first move raises a cooldown and the retry returns failure."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(0, 0)):
            with patch("artifactsmmo_cli.commands.action.parse_destination", return_value=(3, 0)):
                with patch("artifactsmmo_cli.commands.action.validate_coordinates", return_value=(3, 0)):
                    with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_resp:
                        mock_resp.side_effect = [
                            httpx.ConnectError("cooldown"),
                            Mock(success=False, cooldown_remaining=None, error="Move failed after cooldown"),
                        ]

                        with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_err:
                            mock_err.return_value = Mock(success=False, cooldown_remaining=1, error=None)

                            with patch("time.sleep"):
                                result = runner.invoke(app, ["goto", "testchar", "3 0"])

                        assert "Move failed after cooldown" in result.stdout

    def test_goto_move_exception_cooldown_wait_retry_exception(self, runner, mock_client_manager):
        """Test goto when both the first move and the retry raise exceptions."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(0, 0)):
            with patch("artifactsmmo_cli.commands.action.parse_destination", return_value=(3, 0)):
                with patch("artifactsmmo_cli.commands.action.validate_coordinates", return_value=(3, 0)):
                    with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_resp:
                        mock_resp.side_effect = httpx.ConnectError("api error")

                        with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_err:
                            mock_err.side_effect = [
                                Mock(success=False, cooldown_remaining=1, error=None),
                                Mock(success=False, cooldown_remaining=None, error="Retry failed"),
                            ]

                            with patch("time.sleep"):
                                result = runner.invoke(app, ["goto", "testchar", "3 0"])

                        assert result.exit_code == 0
                        assert "Retry failed" in result.stdout

    def test_goto_navigation_failed_outer_exception(self, runner, mock_client_manager):
        """Test goto outer exception handler when destination parsing fails."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(0, 0)):
            with patch(
                "artifactsmmo_cli.commands.action.parse_destination",
                side_effect=httpx.ConnectError("Unexpected parse error"),
            ):
                result = runner.invoke(app, ["goto", "testchar", "bank"])

                assert result.exit_code == 1
                assert "Navigation failed" in result.stdout


class TestShowPathCommand:
    """Test show_path_command (action path)."""

    def _make_path_result(self, steps=None):
        """Build a mock PathResult."""
        if steps is None:
            steps = []
        step_objs = [PathStep(x=s[0], y=s[1]) for s in steps]
        return PathResult(steps=step_objs, total_distance=len(steps), estimated_time=len(steps) * 5)

    def test_path_already_there(self, runner, mock_client_manager):
        """Test path command when already at destination."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(5, 5)):
            with patch("artifactsmmo_cli.commands.action.parse_destination", return_value=(5, 5)):
                with patch("artifactsmmo_cli.commands.action.validate_coordinates", return_value=(5, 5)):
                    with patch("artifactsmmo_cli.commands.action.calculate_path") as mock_path:
                        mock_path.return_value = self._make_path_result([])

                        result = runner.invoke(app, ["path", "testchar", "5 5"])

                        assert result.exit_code == 0
                        assert "already at the destination" in result.stdout

    def test_path_with_steps(self, runner, mock_client_manager):
        """Test path command showing multi-step path."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(0, 0)):
            with patch("artifactsmmo_cli.commands.action.parse_destination", return_value=(2, 0)):
                with patch("artifactsmmo_cli.commands.action.validate_coordinates", return_value=(2, 0)):
                    with patch("artifactsmmo_cli.commands.action.calculate_path") as mock_path:
                        mock_path.return_value = self._make_path_result([(1, 0), (2, 0)])

                        result = runner.invoke(app, ["path", "testchar", "2 0"])

                        assert result.exit_code == 0
                        assert "Total moves" in result.stdout
                        assert "Total distance" in result.stdout

    def test_path_coordinate_args(self, runner, mock_client_manager):
        """Test path command with separate X Y coordinate arguments."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(0, 0)):
            with patch("artifactsmmo_cli.commands.action.validate_coordinates", return_value=(3, 4)):
                with patch("artifactsmmo_cli.commands.action.calculate_path") as mock_path:
                    mock_path.return_value = self._make_path_result([])

                    result = runner.invoke(app, ["path", "testchar", "3", "4"])

                    assert result.exit_code == 0

    def test_path_invalid_x_coordinate(self, runner, mock_client_manager):
        """Test path command with invalid X coordinate when Y is provided."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(0, 0)):
            result = runner.invoke(app, ["path", "testchar", "notanumber", "10"])

            assert result.exit_code == 1
            assert "not a valid X coordinate" in result.stdout

    def test_path_named_location(self, runner, mock_client_manager):
        """Test path command with named location."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(0, 0)):
            with patch("artifactsmmo_cli.commands.action.parse_destination", return_value="bank"):
                with patch("artifactsmmo_cli.commands.action.resolve_named_location", return_value=(1, 1)):
                    with patch("artifactsmmo_cli.commands.action.calculate_path") as mock_path:
                        mock_path.return_value = self._make_path_result([(1, 1)])

                        result = runner.invoke(app, ["path", "testchar", "bank"])

                        assert result.exit_code == 0
                        assert "Total moves" in result.stdout

    def test_path_named_location_not_found(self, runner, mock_client_manager):
        """Test path command with named location that cannot be resolved."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(0, 0)):
            with patch("artifactsmmo_cli.commands.action.parse_destination", return_value="nowhere"):
                with patch(
                    "artifactsmmo_cli.commands.action.resolve_named_location",
                    side_effect=ValueError("Not found"),
                ):
                    result = runner.invoke(app, ["path", "testchar", "nowhere"])

                    assert result.exit_code == 1
                    assert "Could not find location" in result.stdout

    def test_path_character_position_error(self, runner, mock_client_manager):
        """Test path command when character position cannot be retrieved."""
        with patch(
            "artifactsmmo_cli.commands.action.get_character_position",
            side_effect=httpx.ConnectError("Character not found"),
        ):
            result = runner.invoke(app, ["path", "testchar", "bank"])

            assert result.exit_code == 1
            assert "Could not get character position" in result.stdout

    def test_path_calculation_error(self, runner, mock_client_manager):
        """Test path command when calculation raises an unexpected error."""
        with patch("artifactsmmo_cli.commands.action.get_character_position", return_value=(0, 0)):
            with patch("artifactsmmo_cli.commands.action.parse_destination", return_value=(1, 1)):
                with patch("artifactsmmo_cli.commands.action.validate_coordinates", return_value=(1, 1)):
                    with patch(
                        "artifactsmmo_cli.commands.action.calculate_path",
                        side_effect=httpx.ConnectError("Calculation failed"),
                    ):
                        result = runner.invoke(app, ["path", "testchar", "1 1"])

                        assert result.exit_code == 1
                        assert "Path calculation failed" in result.stdout


class TestBatchCommandCooldownRetry:
    """Test batch command cooldown-retry branches (lines 846, 855-866)."""

    def test_batch_cooldown_retry_fight_success(self, runner, mock_client_manager):
        """Test batch fight: cooldown then successful retry shows combat result."""
        mock_client_manager.api.action_fight.return_value = Mock()

        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            with patch("time.sleep"):
                fight_data = {"fight": {"result": "win", "xp": 80, "gold": 10, "drops": []}}
                mock_handle.side_effect = [
                    CLIResponse.cooldown_response(1),
                    CLIResponse.success_response(fight_data, "Combat completed"),
                ]

                with patch("artifactsmmo_cli.commands.action.format_combat_result") as mock_fmt:
                    mock_fmt.return_value = Text("Victory!")

                    result = runner.invoke(
                        app, ["batch", "testchar", "fight", "--times", "1", "--wait-cooldown"]
                    )

                assert result.exit_code == 0
                mock_fmt.assert_called_once_with(fight_data["fight"])

    def test_batch_cooldown_retry_gather_success(self, runner, mock_client_manager):
        """Test batch gather: cooldown then successful retry shows gathering result."""
        mock_client_manager.api.action_gathering.return_value = Mock()

        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            with patch("time.sleep"):
                gather_data = {"details": {"xp": 40, "items": [{"code": "copper", "quantity": 1}]}}
                mock_handle.side_effect = [
                    CLIResponse.cooldown_response(1),
                    CLIResponse.success_response(gather_data, "Gathered"),
                ]

                with patch("artifactsmmo_cli.commands.action.format_gathering_result") as mock_fmt:
                    mock_fmt.return_value = Text("Gathered copper!")

                    result = runner.invoke(
                        app, ["batch", "testchar", "gather", "--times", "1", "--wait-cooldown"]
                    )

                assert result.exit_code == 0
                mock_fmt.assert_called_once_with(gather_data["details"])

    def test_batch_cooldown_retry_rest_success(self, runner, mock_client_manager):
        """Test batch rest: cooldown then successful retry shows generic success."""
        mock_client_manager.api.action_rest.return_value = Mock()

        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            with patch("time.sleep"):
                mock_handle.side_effect = [
                    CLIResponse.cooldown_response(1),
                    CLIResponse.success_response({}, "Rest completed"),
                ]

                result = runner.invoke(
                    app, ["batch", "testchar", "rest", "--times", "1", "--wait-cooldown"]
                )

                assert result.exit_code == 0
                assert "Rest completed" in result.stdout

    def test_batch_cooldown_retry_failure_stop(self, runner, mock_client_manager):
        """Test batch: cooldown retry fails, stops (continue_on_error=False)."""
        mock_client_manager.api.action_gathering.return_value = Mock()

        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            with patch("time.sleep"):
                mock_handle.side_effect = [
                    CLIResponse.cooldown_response(1),
                    CLIResponse.error_response("Action failed after cooldown"),
                ]

                result = runner.invoke(
                    app, ["batch", "testchar", "gather", "--times", "1", "--wait-cooldown"]
                )

                assert result.exit_code == 1
                assert "Action failed after cooldown" in result.stdout

    def test_batch_cooldown_retry_failure_continue(self, runner, mock_client_manager):
        """Test batch: cooldown retry fails but continues (continue_on_error=True)."""
        mock_client_manager.api.action_gathering.return_value = Mock()

        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            with patch("time.sleep"):
                mock_handle.side_effect = [
                    CLIResponse.cooldown_response(1),
                    CLIResponse.error_response("Action failed after cooldown"),
                    CLIResponse.success_response({}, "Success"),
                ]

                result = runner.invoke(
                    app,
                    ["batch", "testchar", "gather", "--times", "2", "--wait-cooldown", "--continue-on-error"],
                )

                assert result.exit_code == 0
