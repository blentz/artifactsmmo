"""Tests for action commands."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx

from artifactsmmo_cli.commands.action import (
    BatchResults,
    app,
    execute_fight_action,
    execute_gather_action,
    execute_rest_action,
)
from tests.test_commands.conftest import api_error, api_response, cooldown_status, unexpected_status


def character_at(x: int, y: int) -> SimpleNamespace:
    """Build a character API payload at the given position."""
    return api_response(SimpleNamespace(name="testchar", x=x, y=y))


def maps_page(tiles: list[SimpleNamespace]) -> SimpleNamespace:
    """Build a maps page API payload."""
    return api_response(SimpleNamespace(data=tiles, pages=1))


class TestMoveCommand:
    """Test move command functionality."""

    def test_move_success(self, runner, stub_api):
        """Test successful move command."""
        stub_api.action_move.return_value = api_response(Mock())

        result = runner.invoke(app, ["move", "testchar", "5", "10"])

        assert result.exit_code == 0
        assert "Moved testchar to (5, 10)" in result.stdout

    def test_move_error(self, runner, stub_api):
        """Test move command with error."""
        stub_api.action_move.return_value = api_error(490, "Invalid location")

        result = runner.invoke(app, ["move", "testchar", "5", "10"])

        assert result.exit_code == 1
        assert "Invalid location" in result.stdout

    def test_move_validation_error(self, runner):
        """Test move command with validation error."""
        result = runner.invoke(app, ["move", "", "5", "10"])
        assert result.exit_code != 0

    def test_move_api_exception(self, runner, stub_api):
        """Test move command with API exception."""
        stub_api.action_move.side_effect = unexpected_status(478, "API Error")

        result = runner.invoke(app, ["move", "testchar", "5", "10"])

        assert result.exit_code == 1
        assert "API Error" in result.stdout

    def test_move_api_exception_with_cooldown(self, runner, stub_api):
        """Test move command with API exception and cooldown."""
        stub_api.action_move.side_effect = cooldown_status(15)

        result = runner.invoke(app, ["move", "testchar", "5", "10"])

        assert result.exit_code == 1
        assert "cooldown" in result.stdout.lower()


class TestFightCommand:
    """Test fight command functionality."""

    def test_fight_success(self, runner, stub_api):
        """Test successful fight command."""
        stub_api.action_fight.return_value = api_response(Mock())

        result = runner.invoke(app, ["fight", "testchar"])

        assert result.exit_code == 0
        assert "testchar engaged in combat" in result.stdout

    def test_fight_success_with_detailed_results(self, runner, stub_api):
        """Test successful fight command with detailed combat results."""
        fight_data = {
            "result": "win",
            "xp": 150,
            "gold": 75,
            "drops": [{"code": "iron_ore", "quantity": 2}, {"code": "leather", "quantity": 1}],
        }

        stub_api.action_fight.return_value = api_response({"fight": fight_data})

        result = runner.invoke(app, ["fight", "testchar"])

        assert result.exit_code == 0
        assert "Victory!" in result.stdout
        assert "XP gained: 150" in result.stdout
        assert "Gold gained: 75" in result.stdout
        assert "2x iron_ore" in result.stdout

    def test_fight_success_with_loss(self, runner, stub_api):
        """Test fight command with loss result."""
        fight_data = {"result": "loss", "xp": 25, "gold": 0}

        stub_api.action_fight.return_value = api_response({"fight": fight_data})

        result = runner.invoke(app, ["fight", "testchar"])

        assert result.exit_code == 0
        assert "Defeat!" in result.stdout
        assert "XP gained: 25" in result.stdout

    def test_fight_success_without_fight_data(self, runner, stub_api):
        """Test fight command when API response doesn't contain fight data."""
        stub_api.action_fight.return_value = api_response({"some_other_field": "value"})

        result = runner.invoke(app, ["fight", "testchar"])

        assert result.exit_code == 0
        assert "testchar engaged in combat" in result.stdout

    def test_fight_error(self, runner, stub_api):
        """Test fight command with error."""
        stub_api.action_fight.return_value = api_error(598, "No monster found")

        result = runner.invoke(app, ["fight", "testchar"])

        assert result.exit_code == 1
        assert "No monster found" in result.stdout

    def test_fight_validation_error(self, runner):
        """Test fight command with validation error."""
        result = runner.invoke(app, ["fight", ""])
        assert result.exit_code != 0

    def test_fight_api_exception(self, runner, stub_api):
        """Test fight command with API exception."""
        stub_api.action_fight.side_effect = unexpected_status(478, "API Error")

        result = runner.invoke(app, ["fight", "testchar"])

        assert result.exit_code == 1
        assert "API Error" in result.stdout

    def test_fight_api_exception_with_cooldown(self, runner, stub_api):
        """Test fight command with API exception and cooldown."""
        stub_api.action_fight.side_effect = cooldown_status(20)

        result = runner.invoke(app, ["fight", "testchar"])

        assert result.exit_code == 1
        assert "cooldown" in result.stdout.lower()


class TestGatherCommand:
    """Test gather command functionality."""

    def test_gather_success(self, runner, stub_api):
        """Test successful gather command."""
        stub_api.action_gathering.return_value = api_response(Mock())

        result = runner.invoke(app, ["gather", "testchar"])

        assert result.exit_code == 0
        assert "testchar gathered resources" in result.stdout

    def test_gather_error(self, runner, stub_api):
        """Test gather command with error."""
        stub_api.action_gathering.return_value = api_error(598, "No resources found")

        result = runner.invoke(app, ["gather", "testchar"])

        assert result.exit_code == 1
        assert "No resources found" in result.stdout

    def test_gather_validation_error(self, runner):
        """Test gather command with validation error."""
        result = runner.invoke(app, ["gather", ""])
        assert result.exit_code != 0

    def test_gather_api_exception(self, runner, stub_api):
        """Test gather command with API exception."""
        stub_api.action_gathering.side_effect = unexpected_status(478, "API Error")

        result = runner.invoke(app, ["gather", "testchar"])

        assert result.exit_code == 1
        assert "API Error" in result.stdout

    def test_gather_api_exception_with_cooldown(self, runner, stub_api):
        """Test gather command with API exception and cooldown."""
        stub_api.action_gathering.side_effect = cooldown_status(25)

        result = runner.invoke(app, ["gather", "testchar"])

        assert result.exit_code == 1
        assert "cooldown" in result.stdout.lower()


class TestRestCommand:
    """Test rest command functionality."""

    def test_rest_success(self, runner, stub_api):
        """Test successful rest command."""
        stub_api.action_rest.return_value = api_response(Mock())

        result = runner.invoke(app, ["rest", "testchar"])

        assert result.exit_code == 0
        assert "testchar is resting" in result.stdout

    def test_rest_error(self, runner, stub_api):
        """Test rest command with error."""
        stub_api.action_rest.return_value = api_error(486, "Cannot rest here")

        result = runner.invoke(app, ["rest", "testchar"])

        assert result.exit_code == 1
        assert "Cannot rest here" in result.stdout

    def test_rest_validation_error(self, runner):
        """Test rest command with validation error."""
        result = runner.invoke(app, ["rest", ""])
        assert result.exit_code != 0

    def test_rest_api_exception(self, runner, stub_api):
        """Test rest command with API exception."""
        stub_api.action_rest.side_effect = unexpected_status(478, "API Error")

        result = runner.invoke(app, ["rest", "testchar"])

        assert result.exit_code == 1
        assert "API Error" in result.stdout

    def test_rest_api_exception_with_cooldown(self, runner, stub_api):
        """Test rest command with API exception and cooldown."""
        stub_api.action_rest.side_effect = cooldown_status(10)

        result = runner.invoke(app, ["rest", "testchar"])

        assert result.exit_code == 1
        assert "cooldown" in result.stdout.lower()


class TestEquipCommand:
    """Test equip command functionality."""

    def test_equip_success(self, runner, stub_api):
        """Test successful equip command."""
        stub_api.action_equip_item.return_value = api_response(Mock())

        result = runner.invoke(app, ["equip", "testchar", "sword", "weapon"])

        assert result.exit_code == 0
        assert "Equipped sword on testchar" in result.stdout

    def test_equip_with_quantity(self, runner, stub_api):
        """Test equip command with quantity."""
        stub_api.action_equip_item.return_value = api_response(Mock())

        result = runner.invoke(app, ["equip", "testchar", "arrow", "utility1", "--quantity", "50"])

        assert result.exit_code == 0
        assert "Equipped arrow on testchar" in result.stdout
        assert stub_api.action_equip_item.call_args.kwargs["body"].quantity == 50

    def test_equip_error(self, runner, stub_api):
        """Test equip command with error."""
        stub_api.action_equip_item.return_value = api_error(404, "Item not found")

        result = runner.invoke(app, ["equip", "testchar", "sword", "weapon"])

        assert result.exit_code == 1
        assert "Item not found" in result.stdout

    def test_equip_validation_error(self, runner):
        """Test equip command with validation error."""
        result = runner.invoke(app, ["equip", "", "sword", "weapon"])
        assert result.exit_code != 0

    def test_equip_api_exception(self, runner, stub_api):
        """Test equip command with API exception."""
        stub_api.action_equip_item.side_effect = unexpected_status(478, "API Error")

        result = runner.invoke(app, ["equip", "testchar", "sword", "weapon"])

        assert result.exit_code == 1
        assert "API Error" in result.stdout

    def test_equip_api_exception_with_cooldown(self, runner, stub_api):
        """Test equip command with API exception and cooldown."""
        stub_api.action_equip_item.side_effect = cooldown_status(5)

        result = runner.invoke(app, ["equip", "testchar", "sword", "weapon"])

        assert result.exit_code == 1
        assert "cooldown" in result.stdout.lower()


class TestUnequipCommand:
    """Test unequip command functionality."""

    def test_unequip_success(self, runner, stub_api):
        """Test successful unequip command."""
        stub_api.action_unequip_item.return_value = api_response(Mock())

        result = runner.invoke(app, ["unequip", "testchar", "weapon"])

        assert result.exit_code == 0
        assert "Unequipped weapon from testchar" in result.stdout

    def test_unequip_with_quantity(self, runner, stub_api):
        """Test unequip command with quantity."""
        stub_api.action_unequip_item.return_value = api_response(Mock())

        result = runner.invoke(app, ["unequip", "testchar", "utility1", "--quantity", "25"])

        assert result.exit_code == 0
        assert "Unequipped utility1 from testchar" in result.stdout
        assert stub_api.action_unequip_item.call_args.kwargs["body"].quantity == 25

    def test_unequip_error(self, runner, stub_api):
        """Test unequip command with error."""
        stub_api.action_unequip_item.return_value = api_error(491, "No item equipped")

        result = runner.invoke(app, ["unequip", "testchar", "weapon"])

        assert result.exit_code == 1
        assert "No item equipped" in result.stdout

    def test_unequip_validation_error(self, runner):
        """Test unequip command with validation error."""
        result = runner.invoke(app, ["unequip", "", "weapon"])
        assert result.exit_code != 0

    def test_unequip_api_exception(self, runner, stub_api):
        """Test unequip command with API exception."""
        stub_api.action_unequip_item.side_effect = unexpected_status(478, "API Error")

        result = runner.invoke(app, ["unequip", "testchar", "weapon"])

        assert result.exit_code == 1
        assert "API Error" in result.stdout

    def test_unequip_api_exception_with_cooldown(self, runner, stub_api):
        """Test unequip command with API exception and cooldown."""
        stub_api.action_unequip_item.side_effect = cooldown_status(3)

        result = runner.invoke(app, ["unequip", "testchar", "weapon"])

        assert result.exit_code == 1
        assert "cooldown" in result.stdout.lower()


class TestUseCommand:
    """Test use command functionality."""

    def test_use_success(self, runner, stub_api):
        """Test successful use command."""
        stub_api.action_use_item.return_value = api_response(Mock())

        result = runner.invoke(app, ["use", "testchar", "potion"])

        assert result.exit_code == 0
        assert "Used 1x potion" in result.stdout

    def test_use_with_quantity(self, runner, stub_api):
        """Test use command with quantity."""
        stub_api.action_use_item.return_value = api_response(Mock())

        result = runner.invoke(app, ["use", "testchar", "potion", "--quantity", "3"])

        assert result.exit_code == 0
        assert "Used 3x potion" in result.stdout

    def test_use_error(self, runner, stub_api):
        """Test use command with error."""
        stub_api.action_use_item.return_value = api_error(404, "Item not found")

        result = runner.invoke(app, ["use", "testchar", "potion"])

        assert result.exit_code == 1
        assert "Item not found" in result.stdout

    def test_use_validation_error(self, runner):
        """Test use command with validation error."""
        result = runner.invoke(app, ["use", "", "potion"])
        assert result.exit_code != 0

    def test_use_api_exception(self, runner, stub_api):
        """Test use command with API exception."""
        stub_api.action_use_item.side_effect = unexpected_status(478, "API Error")

        result = runner.invoke(app, ["use", "testchar", "potion"])

        assert result.exit_code == 1
        assert "API Error" in result.stdout

    def test_use_api_exception_with_cooldown(self, runner, stub_api):
        """Test use command with API exception and cooldown."""
        stub_api.action_use_item.side_effect = cooldown_status(8)

        result = runner.invoke(app, ["use", "testchar", "potion"])

        assert result.exit_code == 1
        assert "cooldown" in result.stdout.lower()


class TestBatchCommand:
    """Test batch command functionality."""

    @patch("time.sleep")
    def test_batch_gather_success(self, mock_sleep, runner, stub_api):
        """Test successful batch gather command."""
        stub_api.action_gathering.return_value = api_response(
            {"details": {"xp": 50, "items": [{"code": "wood", "quantity": 2}]}}
        )

        result = runner.invoke(app, ["batch", "testchar", "gather", "--times", "3"])

        assert result.exit_code == 0
        assert "Starting batch gather operation" in result.stdout
        assert "Batch Operation Summary" in result.stdout
        assert stub_api.action_gathering.call_count == 3

    @patch("time.sleep")
    def test_batch_fight_success(self, mock_sleep, runner, stub_api):
        """Test successful batch fight command."""
        stub_api.action_fight.return_value = api_response(
            {"fight": {"result": "win", "xp": 100, "gold": 25, "drops": [{"code": "leather", "quantity": 1}]}}
        )

        result = runner.invoke(app, ["batch", "testchar", "fight", "--times", "2"])

        assert result.exit_code == 0
        assert "Starting batch fight operation" in result.stdout
        assert "Batch Operation Summary" in result.stdout
        assert stub_api.action_fight.call_count == 2

    @patch("time.sleep")
    def test_batch_rest_success(self, mock_sleep, runner, stub_api):
        """Test successful batch rest command."""
        stub_api.action_rest.return_value = api_response({})

        result = runner.invoke(app, ["batch", "testchar", "rest", "--times", "5"])

        assert result.exit_code == 0
        assert "Starting batch rest operation" in result.stdout
        assert "Batch Operation Summary" in result.stdout
        assert stub_api.action_rest.call_count == 5

    def test_batch_invalid_action(self, runner, stub_api):
        """Test batch command with invalid action."""
        result = runner.invoke(app, ["batch", "testchar", "invalid", "--times", "3"])

        assert result.exit_code == 1
        assert "Invalid action 'invalid'" in result.stdout

    def test_batch_invalid_times(self, runner, stub_api):
        """Test batch command with invalid times."""
        result = runner.invoke(app, ["batch", "testchar", "gather", "--times", "0"])

        assert result.exit_code == 1
        assert "Number of times must be greater than 0" in result.stdout

    @patch("time.sleep")
    def test_batch_with_cooldown_no_wait(self, mock_sleep, runner, stub_api):
        """Test batch command with cooldown and no wait flag."""
        stub_api.action_gathering.side_effect = [
            api_response({"details": {"xp": 50}}),
            cooldown_status(30),
        ]

        result = runner.invoke(app, ["batch", "testchar", "gather", "--times", "2"])

        assert result.exit_code == 1  # Should exit on cooldown without wait flag
        assert "Action on cooldown" in result.stdout
        assert stub_api.action_gathering.call_count == 2

    @patch("time.sleep")
    def test_batch_with_cooldown_and_wait(self, mock_sleep, runner, stub_api):
        """Test batch command with cooldown and wait flag."""
        # First call succeeds, second has cooldown, third succeeds after wait
        stub_api.action_gathering.side_effect = [
            api_response({"details": {"xp": 50}}),
            cooldown_status(2),
            api_response({"details": {"xp": 50}}),
        ]

        result = runner.invoke(app, ["batch", "testchar", "gather", "--times", "2", "--wait-cooldown"])

        assert result.exit_code == 0
        assert "Waiting" in result.stdout
        assert stub_api.action_gathering.call_count == 3  # Original + retry after cooldown
        assert mock_sleep.call_count >= 2  # Should sleep for cooldown

    @patch("time.sleep")
    def test_batch_continue_on_error(self, mock_sleep, runner, stub_api):
        """Test batch command with continue on error flag."""
        # First succeeds, second fails, third succeeds
        stub_api.action_gathering.side_effect = [
            api_response({"details": {"xp": 50}}),
            api_error(598, "No resources found"),
            api_response({"details": {"xp": 50}}),
        ]

        result = runner.invoke(app, ["batch", "testchar", "gather", "--times", "3", "--continue-on-error"])

        assert result.exit_code == 0  # Should not exit on error with continue flag
        assert "No resources found" in result.stdout
        assert stub_api.action_gathering.call_count == 3

    @patch("time.sleep")
    def test_batch_stop_on_error(self, mock_sleep, runner, stub_api):
        """Test batch command stops on error without continue flag."""
        # First succeeds, second fails
        stub_api.action_gathering.side_effect = [
            api_response({"details": {"xp": 50}}),
            api_error(598, "No resources found"),
        ]

        result = runner.invoke(app, ["batch", "testchar", "gather", "--times", "3"])

        assert result.exit_code == 1  # Should exit on error without continue flag
        assert "No resources found" in result.stdout
        assert stub_api.action_gathering.call_count == 2  # Should stop after error

    def test_batch_validation_error(self, runner):
        """Test batch command with validation error."""
        result = runner.invoke(app, ["batch", "", "gather", "--times", "3"])
        assert result.exit_code != 0

    @patch("time.sleep")
    def test_batch_results_accumulation(self, mock_sleep, runner, stub_api):
        """Test that batch results are properly accumulated."""
        stub_api.action_fight.side_effect = [
            api_response(
                {"fight": {"result": "win", "xp": 100, "gold": 25, "drops": [{"code": "leather", "quantity": 2}]}}
            ),
            api_response(
                {"fight": {"result": "win", "xp": 150, "gold": 30, "drops": [{"code": "iron_ore", "quantity": 1}]}}
            ),
        ]

        result = runner.invoke(app, ["batch", "testchar", "fight", "--times", "2"])

        assert result.exit_code == 0
        assert "Total XP Gained" in result.stdout
        assert "Total Gold Gained" in result.stdout
        assert "Items Collected" in result.stdout
        # Accumulated totals: 250 XP, 55 gold
        assert "250" in result.stdout
        assert "55" in result.stdout

    def test_batch_outer_exception_handler(self, runner, stub_api):
        """A caught error raised during batch setup hits the outer handler (lines 885-886).

        NOTE: the outer except clause is unreachable through the real internals
        (inner branches handle everything), so the in-module validator import is
        patched to force the path.
        """
        with patch("artifactsmmo_cli.commands.action.validate_character_name") as mock_validate:
            mock_validate.side_effect = unexpected_status(500, "batch crash")

            result = runner.invoke(app, ["batch", "testchar", "gather", "--times", "2"])

            assert result.exit_code == 1
            assert "Batch operation failed" in result.stdout


class TestActionExecutors:
    """Test action executor functions."""

    def test_execute_gather_action_success(self, stub_api):
        """Test execute_gather_action with successful response."""
        stub_api.action_gathering.return_value = api_response({"details": {"xp": 50}})

        result = execute_gather_action("testchar")

        assert result.success is True
        assert result.data == {"details": {"xp": 50}}
        stub_api.action_gathering.assert_called_once_with(name="testchar")

    def test_execute_fight_action_success(self, stub_api):
        """Test execute_fight_action with successful response."""
        stub_api.action_fight.return_value = api_response({"fight": {"result": "win"}})

        result = execute_fight_action("testchar")

        assert result.success is True
        assert result.data == {"fight": {"result": "win"}}
        stub_api.action_fight.assert_called_once_with(name="testchar")

    def test_execute_rest_action_success(self, stub_api):
        """Test execute_rest_action with successful response."""
        stub_api.action_rest.return_value = api_response({})

        result = execute_rest_action("testchar")

        assert result.success is True
        stub_api.action_rest.assert_called_once_with(name="testchar")

    def test_execute_action_with_exception(self, stub_api):
        """Test action executor handles exceptions."""
        stub_api.action_gathering.side_effect = unexpected_status(478, "missing items")

        result = execute_gather_action("testchar")

        assert result.success is False
        assert "Missing required items" in result.error


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

    def test_execute_fight_action_exception(self, stub_api):
        """Test execute_fight_action handles exceptions."""
        stub_api.action_fight.side_effect = unexpected_status(478, "fight error")

        result = execute_fight_action("testchar")

        assert result.success is False
        assert "fight error" in result.error

    def test_execute_rest_action_exception(self, stub_api):
        """Test execute_rest_action handles exceptions."""
        stub_api.action_rest.side_effect = unexpected_status(478, "rest error")

        result = execute_rest_action("testchar")

        assert result.success is False
        assert "rest error" in result.error


class TestGatherCommandSuccessNoData:
    """Test gather command success path when no details key present."""

    def test_gather_success_no_details(self, runner, stub_api):
        """Test gather success when data has no 'details' key."""
        stub_api.action_gathering.return_value = api_response({"other": "value"})

        result = runner.invoke(app, ["gather", "testchar"])

        assert result.exit_code == 0
        assert "testchar gathered resources" in result.stdout

    def test_gather_success_with_details(self, runner, stub_api):
        """Test gather success when data has 'details' key."""
        stub_api.action_gathering.return_value = api_response({"details": {"xp": 50, "items": []}})

        result = runner.invoke(app, ["gather", "testchar"])

        assert result.exit_code == 0
        assert "XP gained: 50" in result.stdout


class TestGotoCommand:
    """Test goto_location command."""

    def test_goto_already_at_destination(self, runner, stub_api):
        """Test goto when character is already at the destination."""
        stub_api.get_character.return_value = character_at(5, 10)

        result = runner.invoke(app, ["goto", "testchar", "5 10"])

        assert result.exit_code == 0
        assert "already at the destination" in result.stdout

    def test_goto_coordinate_args(self, runner, stub_api):
        """Test goto with separate X Y coordinate arguments."""
        stub_api.get_character.return_value = character_at(5, 10)

        result = runner.invoke(app, ["goto", "testchar", "5", "10"])

        assert result.exit_code == 0
        assert "already at the destination" in result.stdout

    def test_goto_invalid_x_coordinate(self, runner, stub_api):
        """Test goto with invalid X coordinate when Y is provided."""
        stub_api.get_character.return_value = character_at(0, 0)

        result = runner.invoke(app, ["goto", "testchar", "notanumber", "10"])

        assert result.exit_code == 1
        assert "not a valid X coordinate" in result.stdout

    def test_goto_named_location(self, runner, stub_api):
        """Test goto resolves a named location to coordinates."""
        stub_api.get_character.return_value = character_at(2, 3)
        bank_tile = SimpleNamespace(x=2, y=3, content=SimpleNamespace(type="bank"))

        with patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync") as mock_maps:
            mock_maps.return_value = maps_page([bank_tile])

            result = runner.invoke(app, ["goto", "testchar", "bank"])

        assert result.exit_code == 0
        assert "already at the destination" in result.stdout

    def test_goto_named_location_not_found(self, runner, stub_api):
        """Test goto with a named location that cannot be resolved."""
        stub_api.get_character.return_value = character_at(0, 0)

        with patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync") as mock_maps:
            mock_maps.side_effect = unexpected_status(404, "Location not found")

            result = runner.invoke(app, ["goto", "testchar", "unknownplace"])

        assert result.exit_code == 1
        assert "Could not find location" in result.stdout

    def test_goto_character_position_error(self, runner, stub_api):
        """Test goto when character position cannot be retrieved."""
        stub_api.get_character.side_effect = httpx.ConnectError("Character not found")

        result = runner.invoke(app, ["goto", "testchar", "bank"])

        assert result.exit_code == 1
        assert "Could not get character position" in result.stdout

    def test_goto_move_success(self, runner, stub_api):
        """A single move to the destination is issued (server routes the path)."""
        stub_api.get_character.return_value = character_at(0, 0)
        stub_api.action_move.return_value = api_response(Mock())

        result = runner.invoke(app, ["goto", "testchar", "3 0"])

        assert result.exit_code == 0
        assert "reached destination" in result.stdout
        # exactly one move issued — the client does not walk tile-by-tile
        stub_api.action_move.assert_called_once()

    def test_goto_move_cooldown_no_wait(self, runner, stub_api):
        """Test goto with move blocked by cooldown and no-wait-cooldown."""
        stub_api.get_character.return_value = character_at(0, 0)
        stub_api.action_move.side_effect = cooldown_status(5)

        result = runner.invoke(app, ["goto", "testchar", "3 0", "--no-wait-cooldown"])

        assert "Move blocked by cooldown" in result.stdout

    def test_goto_move_error(self, runner, stub_api):
        """Test goto with the move returning a non-cooldown error."""
        stub_api.get_character.return_value = character_at(0, 0)
        stub_api.action_move.return_value = api_error(490, "Move failed")

        result = runner.invoke(app, ["goto", "testchar", "3 0"])

        assert "Move failed" in result.stdout

    def test_goto_show_path_confirmed(self, runner, stub_api):
        """Test goto with --show-path that the user confirms."""
        stub_api.get_character.return_value = character_at(0, 0)
        stub_api.action_move.return_value = api_response(Mock())

        result = runner.invoke(app, ["goto", "testchar", "2 0", "--show-path"], input="y\n")

        assert result.exit_code == 0
        assert "Move to (2, 0)?" in result.stdout
        assert "reached destination" in result.stdout

    def test_goto_show_path_cancelled(self, runner, stub_api):
        """Test goto with --show-path that the user cancels."""
        stub_api.get_character.return_value = character_at(0, 0)

        result = runner.invoke(app, ["goto", "testchar", "2 0", "--show-path"], input="n\n")

        assert result.exit_code == 0
        assert "cancelled" in result.stdout
        stub_api.action_move.assert_not_called()

    @patch("time.sleep")
    def test_goto_move_cooldown_wait_retry_success(self, mock_sleep, runner, stub_api):
        """Test goto waits out a cooldown and the retried move succeeds."""
        stub_api.get_character.return_value = character_at(0, 0)
        stub_api.action_move.side_effect = [
            cooldown_status(1),
            api_response(Mock()),
        ]

        result = runner.invoke(app, ["goto", "testchar", "3 0"])

        assert result.exit_code == 0
        assert "reached destination" in result.stdout
        assert stub_api.action_move.call_count == 2

    @patch("time.sleep")
    def test_goto_move_cooldown_wait_retry_failure(self, mock_sleep, runner, stub_api):
        """Test goto waits out a cooldown but the retried move still fails."""
        stub_api.get_character.return_value = character_at(0, 0)
        stub_api.action_move.side_effect = [
            cooldown_status(1),
            api_error(490, "Move failed after cooldown"),
        ]

        result = runner.invoke(app, ["goto", "testchar", "3 0"])

        assert "Move failed after cooldown" in result.stdout

    def test_goto_move_exception_no_cooldown(self, runner, stub_api):
        """Test goto when the move raises an exception without a cooldown."""
        stub_api.get_character.return_value = character_at(0, 0)
        stub_api.action_move.side_effect = httpx.ConnectError("Network error")

        result = runner.invoke(app, ["goto", "testchar", "3 0"])

        assert "Could not connect to API" in result.stdout

    def test_goto_move_exception_cooldown_no_wait(self, runner, stub_api):
        """Test goto when the move raises a cooldown exception with no-wait-cooldown."""
        stub_api.get_character.return_value = character_at(0, 0)
        stub_api.action_move.side_effect = cooldown_status(5)

        result = runner.invoke(app, ["goto", "testchar", "3 0", "--no-wait-cooldown"])

        assert "Move blocked by cooldown" in result.stdout

    @patch("time.sleep")
    def test_goto_move_exception_cooldown_wait_retry_success(self, mock_sleep, runner, stub_api):
        """Test goto recovers when the first move raises a cooldown and the retry succeeds."""
        stub_api.get_character.return_value = character_at(0, 0)
        stub_api.action_move.side_effect = [
            cooldown_status(1),
            api_response(Mock()),
        ]

        result = runner.invoke(app, ["goto", "testchar", "3 0"])

        assert result.exit_code == 0
        assert "reached destination" in result.stdout

    @patch("time.sleep")
    def test_goto_move_exception_cooldown_wait_retry_failure(self, mock_sleep, runner, stub_api):
        """Test goto when the first move raises a cooldown and the retry returns failure."""
        stub_api.get_character.return_value = character_at(0, 0)
        stub_api.action_move.side_effect = [
            cooldown_status(1),
            api_error(490, "Move failed after cooldown"),
        ]

        result = runner.invoke(app, ["goto", "testchar", "3 0"])

        assert "Move failed after cooldown" in result.stdout

    @patch("time.sleep")
    def test_goto_move_exception_cooldown_wait_retry_exception(self, mock_sleep, runner, stub_api):
        """Test goto when both the first move and the retry raise exceptions."""
        stub_api.get_character.return_value = character_at(0, 0)
        stub_api.action_move.side_effect = [
            cooldown_status(1),
            unexpected_status(500, "Retry failed"),
        ]

        result = runner.invoke(app, ["goto", "testchar", "3 0"])

        assert result.exit_code == 0
        assert "Retry failed" in result.stdout

    def test_goto_navigation_failed_outer_exception(self, runner, stub_api):
        """Test goto outer exception handler when destination parsing fails.

        NOTE: the outer except clause is unreachable through the real internals
        (every failure mode is handled by an inner try/except), so the in-module
        parse_destination import is patched to force the path.
        """
        stub_api.get_character.return_value = character_at(0, 0)

        with patch(
            "artifactsmmo_cli.commands.action.parse_destination",
            side_effect=httpx.ConnectError("Unexpected parse error"),
        ):
            result = runner.invoke(app, ["goto", "testchar", "bank"])

            assert result.exit_code == 1
            assert "Navigation failed" in result.stdout


class TestShowPathCommand:
    """Test show_path_command (action path)."""

    def test_path_already_there(self, runner, stub_api):
        """Test path command when already at destination."""
        stub_api.get_character.return_value = character_at(5, 5)

        result = runner.invoke(app, ["path", "testchar", "5 5"])

        assert result.exit_code == 0
        assert "already at the destination" in result.stdout

    def test_path_with_steps(self, runner, stub_api):
        """Test path command showing multi-step path."""
        stub_api.get_character.return_value = character_at(0, 0)

        result = runner.invoke(app, ["path", "testchar", "2 0"])

        assert result.exit_code == 0
        assert "Total moves: 2" in result.stdout
        assert "Total distance: 2" in result.stdout

    def test_path_coordinate_args(self, runner, stub_api):
        """Test path command with separate X Y coordinate arguments."""
        stub_api.get_character.return_value = character_at(0, 0)

        result = runner.invoke(app, ["path", "testchar", "3", "4"])

        assert result.exit_code == 0
        assert "Total moves: 4" in result.stdout

    def test_path_invalid_x_coordinate(self, runner, stub_api):
        """Test path command with invalid X coordinate when Y is provided."""
        stub_api.get_character.return_value = character_at(0, 0)

        result = runner.invoke(app, ["path", "testchar", "notanumber", "10"])

        assert result.exit_code == 1
        assert "not a valid X coordinate" in result.stdout

    def test_path_named_location(self, runner, stub_api):
        """Test path command with named location."""
        stub_api.get_character.return_value = character_at(0, 0)
        bank_tile = SimpleNamespace(x=1, y=1, content=SimpleNamespace(type="bank"))

        with patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync") as mock_maps:
            mock_maps.return_value = maps_page([bank_tile])

            result = runner.invoke(app, ["path", "testchar", "bank"])

        assert result.exit_code == 0
        assert "Total moves: 1" in result.stdout

    def test_path_named_location_not_found(self, runner, stub_api):
        """Test path command with named location that cannot be resolved."""
        stub_api.get_character.return_value = character_at(0, 0)

        with patch("artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync") as mock_maps:
            mock_maps.side_effect = unexpected_status(404, "Not found")

            result = runner.invoke(app, ["path", "testchar", "nowhere"])

        assert result.exit_code == 1
        assert "Could not find location" in result.stdout

    def test_path_character_position_error(self, runner, stub_api):
        """Test path command when character position cannot be retrieved."""
        stub_api.get_character.side_effect = httpx.ConnectError("Character not found")

        result = runner.invoke(app, ["path", "testchar", "bank"])

        assert result.exit_code == 1
        assert "Could not get character position" in result.stdout

    def test_path_calculation_error(self, runner, stub_api):
        """Test path command when calculation raises an unexpected error.

        NOTE: the outer except clause is unreachable through the real internals
        (calculate_path is pure and never raises), so the in-module import is
        patched to force the path.
        """
        stub_api.get_character.return_value = character_at(0, 0)

        with patch(
            "artifactsmmo_cli.commands.action.calculate_path",
            side_effect=httpx.ConnectError("Calculation failed"),
        ):
            result = runner.invoke(app, ["path", "testchar", "1 1"])

            assert result.exit_code == 1
            assert "Path calculation failed" in result.stdout


class TestBatchCommandCooldownRetry:
    """Test batch command cooldown-retry branches (lines 846, 855-866)."""

    @patch("time.sleep")
    def test_batch_cooldown_retry_fight_success(self, mock_sleep, runner, stub_api):
        """Test batch fight: cooldown then successful retry shows combat result."""
        fight_data = {"fight": {"result": "win", "xp": 80, "gold": 10, "drops": []}}
        stub_api.action_fight.side_effect = [
            cooldown_status(1),
            api_response(fight_data),
        ]

        result = runner.invoke(app, ["batch", "testchar", "fight", "--times", "1", "--wait-cooldown"])

        assert result.exit_code == 0
        assert "Victory!" in result.stdout
        assert "XP gained: 80" in result.stdout

    @patch("time.sleep")
    def test_batch_cooldown_retry_gather_success(self, mock_sleep, runner, stub_api):
        """Test batch gather: cooldown then successful retry shows gathering result."""
        gather_data = {"details": {"xp": 40, "items": [{"code": "copper", "quantity": 1}]}}
        stub_api.action_gathering.side_effect = [
            cooldown_status(1),
            api_response(gather_data),
        ]

        result = runner.invoke(app, ["batch", "testchar", "gather", "--times", "1", "--wait-cooldown"])

        assert result.exit_code == 0
        assert "XP gained: 40" in result.stdout
        assert "1x copper" in result.stdout

    @patch("time.sleep")
    def test_batch_cooldown_retry_rest_success(self, mock_sleep, runner, stub_api):
        """Test batch rest: cooldown then successful retry shows generic success."""
        stub_api.action_rest.side_effect = [
            cooldown_status(1),
            api_response({}),
        ]

        result = runner.invoke(app, ["batch", "testchar", "rest", "--times", "1", "--wait-cooldown"])

        assert result.exit_code == 0
        assert "testchar is resting" in result.stdout

    @patch("time.sleep")
    def test_batch_cooldown_retry_failure_stop(self, mock_sleep, runner, stub_api):
        """Test batch: cooldown retry fails, stops (continue_on_error=False)."""
        stub_api.action_gathering.side_effect = [
            cooldown_status(1),
            api_error(598, "Action failed after cooldown"),
        ]

        result = runner.invoke(app, ["batch", "testchar", "gather", "--times", "1", "--wait-cooldown"])

        assert result.exit_code == 1
        assert "Action failed after cooldown" in result.stdout

    @patch("time.sleep")
    def test_batch_cooldown_retry_failure_continue(self, mock_sleep, runner, stub_api):
        """Test batch: cooldown retry fails but continues (continue_on_error=True)."""
        stub_api.action_gathering.side_effect = [
            cooldown_status(1),
            api_error(598, "Action failed after cooldown"),
            api_response({}),
        ]

        result = runner.invoke(
            app,
            ["batch", "testchar", "gather", "--times", "2", "--wait-cooldown", "--continue-on-error"],
        )

        assert result.exit_code == 0
        assert "Action failed after cooldown" in result.stdout
