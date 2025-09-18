"""Tests for action commands."""

from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from artifactsmmo_cli.commands.action import app


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
        assert result.exit_code == 1

    def test_move_api_exception(self, runner, mock_client_manager):
        """Test move command with API exception."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=None, error="API Error")

                result = runner.invoke(app, ["move", "testchar", "5", "10"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout

    def test_move_api_exception_with_cooldown(self, runner, mock_client_manager):
        """Test move command with API exception and cooldown."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

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
                from rich.text import Text

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
                from rich.text import Text

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
        assert result.exit_code == 1

    def test_fight_api_exception(self, runner, mock_client_manager):
        """Test fight command with API exception."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=None, error="API Error")

                result = runner.invoke(app, ["fight", "testchar"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout

    def test_fight_api_exception_with_cooldown(self, runner, mock_client_manager):
        """Test fight command with API exception and cooldown."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

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
        assert result.exit_code == 1

    def test_gather_api_exception(self, runner, mock_client_manager):
        """Test gather command with API exception."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=None, error="API Error")

                result = runner.invoke(app, ["gather", "testchar"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout

    def test_gather_api_exception_with_cooldown(self, runner, mock_client_manager):
        """Test gather command with API exception and cooldown."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

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
        assert result.exit_code == 1

    def test_rest_api_exception(self, runner, mock_client_manager):
        """Test rest command with API exception."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=None, error="API Error")

                result = runner.invoke(app, ["rest", "testchar"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout

    def test_rest_api_exception_with_cooldown(self, runner, mock_client_manager):
        """Test rest command with API exception and cooldown."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

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
        assert result.exit_code == 1

    def test_equip_api_exception(self, runner, mock_client_manager):
        """Test equip command with API exception."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=None, error="API Error")

                result = runner.invoke(app, ["equip", "testchar", "sword", "weapon"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout

    def test_equip_api_exception_with_cooldown(self, runner, mock_client_manager):
        """Test equip command with API exception and cooldown."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

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
        assert result.exit_code == 1

    def test_unequip_api_exception(self, runner, mock_client_manager):
        """Test unequip command with API exception."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=None, error="API Error")

                result = runner.invoke(app, ["unequip", "testchar", "weapon"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout

    def test_unequip_api_exception_with_cooldown(self, runner, mock_client_manager):
        """Test unequip command with API exception and cooldown."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

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
        assert result.exit_code == 1

    def test_use_api_exception(self, runner, mock_client_manager):
        """Test use command with API exception."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=None, error="API Error")

                result = runner.invoke(app, ["use", "testchar", "potion"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout

    def test_use_api_exception_with_cooldown(self, runner, mock_client_manager):
        """Test use command with API exception and cooldown."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

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
            from artifactsmmo_cli.models.responses import CLIResponse

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
            from artifactsmmo_cli.models.responses import CLIResponse

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
            from artifactsmmo_cli.models.responses import CLIResponse

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
            from artifactsmmo_cli.models.responses import CLIResponse

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
                from artifactsmmo_cli.models.responses import CLIResponse

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
            from artifactsmmo_cli.models.responses import CLIResponse

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
            from artifactsmmo_cli.models.responses import CLIResponse

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
        assert result.exit_code == 1

    def test_batch_results_accumulation(self, runner, mock_client_manager):
        """Test that batch results are properly accumulated."""
        # Mock the API client properly
        mock_client_manager.api.action_fight.return_value = Mock()

        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            from artifactsmmo_cli.models.responses import CLIResponse

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

    def test_batch_interrupt_handling(self, runner, mock_client_manager):
        """Test batch command handles interrupts gracefully."""
        # Mock the API client properly
        mock_client_manager.api.action_gathering.return_value = Mock()

        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            from artifactsmmo_cli.models.responses import CLIResponse

            # Create a side effect that sets interrupted after first call
            def set_interrupted_after_first_call(*args, **kwargs):
                import artifactsmmo_cli.commands.action as action_module

                action_module._interrupted = True
                return CLIResponse.success_response({"details": {"xp": 50}}, "Gathering completed")

            mock_handle.side_effect = set_interrupted_after_first_call

            result = runner.invoke(app, ["batch", "testchar", "gather", "--times", "10"])

            assert "Operation interrupted by user" in result.stdout


class TestActionExecutors:
    """Test action executor functions."""

    def test_execute_gather_action_success(self, mock_client_manager):
        """Test execute_gather_action with successful response."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=True, data={"details": {"xp": 50}})

            from artifactsmmo_cli.commands.action import execute_gather_action

            result = execute_gather_action("testchar")

            assert result.success is True
            mock_client_manager.api.action_gathering.assert_called_once_with(name="testchar")

    def test_execute_fight_action_success(self, mock_client_manager):
        """Test execute_fight_action with successful response."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=True, data={"fight": {"result": "win"}})

            from artifactsmmo_cli.commands.action import execute_fight_action

            result = execute_fight_action("testchar")

            assert result.success is True
            mock_client_manager.api.action_fight.assert_called_once_with(name="testchar")

    def test_execute_rest_action_success(self, mock_client_manager):
        """Test execute_rest_action with successful response."""
        with patch("artifactsmmo_cli.commands.action.handle_api_response") as mock_handle:
            mock_handle.return_value = Mock(success=True, data={})

            from artifactsmmo_cli.commands.action import execute_rest_action

            result = execute_rest_action("testchar")

            assert result.success is True
            mock_client_manager.api.action_rest.assert_called_once_with(name="testchar")

    def test_execute_action_with_exception(self, mock_client_manager):
        """Test action executor handles exceptions."""
        with patch("artifactsmmo_cli.commands.action.handle_api_error") as mock_handle_error:
            mock_handle_error.return_value = Mock(success=False, error="API Error")
            mock_client_manager.api.action_gathering.side_effect = Exception("API Error")

            from artifactsmmo_cli.commands.action import execute_gather_action

            result = execute_gather_action("testchar")

            assert result.success is False
            mock_handle_error.assert_called_once()


class TestBatchResults:
    """Test BatchResults class functionality."""

    def test_batch_results_initialization(self):
        """Test BatchResults initializes correctly."""
        from artifactsmmo_cli.commands.action import BatchResults

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
        from artifactsmmo_cli.commands.action import BatchResults

        results = BatchResults()

        # Test with fight data
        fight_data = {"fight": {"xp": 100, "gold": 25, "drops": [{"code": "leather", "quantity": 2}]}}
        results.add_success(fight_data)

        assert results.successful_actions == 1
        assert results.total_xp == 100
        assert results.total_gold == 25
        assert results.items_collected["leather"] == 2

    def test_batch_results_add_failure(self):
        """Test adding failed results."""
        from artifactsmmo_cli.commands.action import BatchResults

        results = BatchResults()
        results.add_failure("Test error")

        assert results.failed_actions == 1
        assert "Test error" in results.errors

    def test_batch_results_format_summary(self):
        """Test formatting results summary."""
        from artifactsmmo_cli.commands.action import BatchResults

        results = BatchResults()
        results.total_attempts = 5
        results.successful_actions = 4
        results.failed_actions = 1
        results.total_xp = 200
        results.total_gold = 50
        results.items_collected["wood"] = 10

        table = results.format_summary()
        assert table.title == "Batch Operation Summary"
