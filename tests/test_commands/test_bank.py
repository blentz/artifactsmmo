"""Tests for bank commands."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from artifactsmmo_cli.commands.bank import (
    _display_operation_summary,
    app,
    categorize_item,
    execute_single_deposit,
    execute_single_withdraw,
    filter_items_by_type,
    get_character_inventory,
    get_item_info,
    should_keep_item,
)
from tests.test_commands.conftest import api_error, api_response, cooldown_status, unexpected_status

BANK_ITEMS_SYNC = "artifactsmmo_api_client.api.my_account.get_bank_items_my_bank_items_get.sync"
BANK_DETAILS_SYNC = "artifactsmmo_api_client.api.my_account.get_bank_details_my_bank_get.sync"
ITEM_SYNC = "artifactsmmo_api_client.api.items.get_item_items_code_get.sync"
DEPOSIT_GOLD_SYNC = (
    "artifactsmmo_api_client.api.my_characters.action_deposit_bank_gold_my_name_action_bank_deposit_gold_post.sync"
)
WITHDRAW_GOLD_SYNC = (
    "artifactsmmo_api_client.api.my_characters.action_withdraw_bank_gold_my_name_action_bank_withdraw_gold_post.sync"
)
DEPOSIT_ITEM_SYNC = (
    "artifactsmmo_api_client.api.my_characters.action_deposit_bank_item_my_name_action_bank_deposit_item_post.sync"
)
WITHDRAW_ITEM_SYNC = (
    "artifactsmmo_api_client.api.my_characters.action_withdraw_bank_item_my_name_action_bank_withdraw_item_post.sync"
)
EXPAND_SYNC = (
    "artifactsmmo_api_client.api.my_characters.action_buy_bank_expansion_my_name_action_bank_buy_expansion_post.sync"
)

# Item database used to answer get_item stubs at the API boundary.
ITEM_DB = {
    "iron_ore": ("ore", "mining", "Iron Ore"),
    "copper_ore": ("ore", "mining", "Copper Ore"),
    "coal": ("ore", "mining", "Coal"),
    "wooden_sword": ("weapon", "sword", "Wooden Sword"),
    "bread": ("consumable", "food", "Bread"),
    "craft_mat": ("crafting_material", "crafting", "Crafting Material"),
}


def make_item(code: str) -> SimpleNamespace:
    """Build an item payload shaped like the generated ItemSchema."""
    type_, subtype, name = ITEM_DB[code]
    return SimpleNamespace(code=code, name=name, type_=type_, subtype=subtype, level=1, tradeable=True)


def item_lookup(client, code):
    """Side effect for the get_item endpoint: answer from ITEM_DB or 404."""
    if code in ITEM_DB:
        return api_response(make_item(code))
    return api_error(404, "Item not found")


def inventory_response(items: list[tuple[str, int, int]]) -> SimpleNamespace:
    """Build a get_character payload with the given (code, quantity, slot) inventory."""
    inventory = [SimpleNamespace(code=c, quantity=q, slot=s) for c, q, s in items]
    return api_response(SimpleNamespace(name="testchar", inventory=inventory))


class TestListCommand:
    """Test list command functionality."""

    def test_list_success(self, runner, stub_api):
        """Test successful list command."""
        with patch(BANK_ITEMS_SYNC) as mock_api:
            mock_api.return_value = api_response(
                [{"code": "iron_ore", "quantity": 50}, {"code": "copper_ore", "quantity": 25}]
            )

            result = runner.invoke(app, ["list"])

            assert result.exit_code == 0
            assert "iron_ore" in result.stdout

    def test_list_no_items(self, runner, stub_api):
        """Test list command with no items."""
        with patch(BANK_ITEMS_SYNC) as mock_api:
            mock_api.return_value = api_error(404, "No bank items found")

            result = runner.invoke(app, ["list"])

            assert result.exit_code == 0
            assert "No bank items found" in result.stdout

    def test_list_api_exception(self, runner, stub_api):
        """Test list command with API exception."""
        with patch(BANK_ITEMS_SYNC) as mock_api:
            mock_api.side_effect = unexpected_status(500, "API Error")

            result = runner.invoke(app, ["list"])

            assert result.exit_code == 1
            assert "API Error" in result.stdout


class TestDetailsCommand:
    """Test details command functionality."""

    def test_details_success(self, runner, stub_api):
        """Test successful details command."""
        with patch(BANK_DETAILS_SYNC) as mock_api:
            mock_api.return_value = api_response(Mock(gold=1000, slots=50, next_expansion_cost=500))

            result = runner.invoke(app, ["details"])

            assert result.exit_code == 0
            assert "Bank Gold: 1000" in result.stdout
            assert "Bank Slots: 50" in result.stdout
            assert "Expansion Cost: 500" in result.stdout

    def test_details_missing_expansion_cost(self, runner, stub_api):
        """Test details renders the MISSING marker when an API field is absent."""
        with patch(BANK_DETAILS_SYNC) as mock_api:
            mock_api.return_value = api_response(Mock(gold=1000, slots=50, next_expansion_cost=None))

            result = runner.invoke(app, ["details"])

            assert result.exit_code == 0
            assert "Bank Gold: 1000" in result.stdout
            assert "Expansion Cost: —" in result.stdout

    def test_details_error(self, runner, stub_api):
        """Test details command with error."""
        with patch(BANK_DETAILS_SYNC) as mock_api:
            mock_api.return_value = api_error(403, "Access denied")

            result = runner.invoke(app, ["details"])

            assert result.exit_code == 1
            assert "Access denied" in result.stdout

    def test_details_api_exception(self, runner, stub_api):
        """Test details command with API exception."""
        with patch(BANK_DETAILS_SYNC) as mock_api:
            mock_api.side_effect = unexpected_status(500, "API Error")

            result = runner.invoke(app, ["details"])

            assert result.exit_code == 1
            assert "API Error" in result.stdout


class TestDepositGoldCommand:
    """Test deposit-gold command functionality."""

    def test_deposit_gold_success(self, runner, stub_api):
        """Test successful deposit gold command."""
        with patch(DEPOSIT_GOLD_SYNC) as mock_api:
            mock_api.return_value = api_response(Mock())

            result = runner.invoke(app, ["deposit-gold", "testchar", "100"])

            assert result.exit_code == 0
            assert "Deposited 100 gold" in result.stdout

    def test_deposit_gold_with_cooldown(self, runner, stub_api):
        """Test deposit gold command with cooldown.

        NOTE: handle_api_response never produces a cooldown CLIResponse (cooldowns
        arrive as 499 errors through handle_api_error), so the command's
        response-cooldown branch is only reachable by patching the helper.
        """
        with patch(DEPOSIT_GOLD_SYNC) as mock_api:
            mock_api.return_value = Mock(status_code=200)

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=10, message=None, error=None)

                result = runner.invoke(app, ["deposit-gold", "testchar", "100"])

                assert result.exit_code == 0
                assert "cooldown" in result.stdout

    def test_deposit_gold_error(self, runner, stub_api):
        """Test deposit gold command with error."""
        with patch(DEPOSIT_GOLD_SYNC) as mock_api:
            mock_api.return_value = api_error(492, "Insufficient gold")

            result = runner.invoke(app, ["deposit-gold", "testchar", "100"])

            assert result.exit_code == 1
            assert "Insufficient gold" in result.stdout

    def test_deposit_gold_validation_error(self, runner):
        """Test deposit gold command with validation error."""
        result = runner.invoke(app, ["deposit-gold", "", "100"])
        assert result.exit_code == 2

    def test_deposit_gold_api_exception(self, runner, stub_api):
        """Test deposit gold command with API exception."""
        with patch(DEPOSIT_GOLD_SYNC) as mock_api:
            mock_api.side_effect = unexpected_status(500, "API Error")

            result = runner.invoke(app, ["deposit-gold", "testchar", "100"])

            assert result.exit_code == 1
            assert "API Error" in result.stdout

    def test_deposit_gold_api_exception_with_cooldown(self, runner, stub_api):
        """Deposit gold renders the cooldown message on a cooldown error (line 281)."""
        with patch(DEPOSIT_GOLD_SYNC) as mock_api:
            mock_api.side_effect = cooldown_status(15)

            result = runner.invoke(app, ["deposit-gold", "testchar", "100"])

            assert result.exit_code == 1
            assert "15" in result.stdout

    def test_withdraw_gold_api_exception_with_cooldown(self, runner, stub_api):
        """Withdraw gold renders the cooldown message on a cooldown error (line 316)."""
        with patch(WITHDRAW_GOLD_SYNC) as mock_api:
            mock_api.side_effect = cooldown_status(8)

            result = runner.invoke(app, ["withdraw-gold", "testchar", "50"])

            assert result.exit_code == 1
            assert "8" in result.stdout

    def test_deposit_item_api_exception_with_cooldown(self, runner, stub_api):
        """Deposit item renders the cooldown message on a cooldown error (line 353)."""
        with patch(DEPOSIT_ITEM_SYNC) as mock_api:
            mock_api.side_effect = cooldown_status(5)

            result = runner.invoke(app, ["deposit-item", "testchar", "iron_ore", "10"])

            assert result.exit_code == 1
            assert "5" in result.stdout

    def test_withdraw_item_api_exception_with_cooldown(self, runner, stub_api):
        """Withdraw item renders the cooldown message on a cooldown error (line 390)."""
        with patch(WITHDRAW_ITEM_SYNC) as mock_api:
            mock_api.side_effect = cooldown_status(12)

            result = runner.invoke(app, ["withdraw-item", "testchar", "copper_ore", "5"])

            assert result.exit_code == 1
            assert "12" in result.stdout

    def test_expand_api_exception_with_cooldown(self, runner, stub_api):
        """Expand renders the cooldown message on a cooldown error (line 418)."""
        with patch(EXPAND_SYNC) as mock_api:
            mock_api.side_effect = cooldown_status(20)

            result = runner.invoke(app, ["expand", "testchar"])

            assert result.exit_code == 1
            assert "20" in result.stdout


class TestWithdrawGoldCommand:
    """Test withdraw-gold command functionality."""

    def test_withdraw_gold_success(self, runner, stub_api):
        """Test successful withdraw gold command."""
        with patch(WITHDRAW_GOLD_SYNC) as mock_api:
            mock_api.return_value = api_response(Mock())

            result = runner.invoke(app, ["withdraw-gold", "testchar", "50"])

            assert result.exit_code == 0
            assert "Withdrew 50 gold" in result.stdout

    def test_withdraw_gold_with_cooldown(self, runner, stub_api):
        """Test withdraw gold command with cooldown (dead response-cooldown branch)."""
        with patch(WITHDRAW_GOLD_SYNC) as mock_api:
            mock_api.return_value = Mock(status_code=200)

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=8, message=None, error=None)

                result = runner.invoke(app, ["withdraw-gold", "testchar", "50"])

                assert result.exit_code == 0
                assert "cooldown" in result.stdout

    def test_withdraw_gold_error(self, runner, stub_api):
        """Test withdraw gold command with error."""
        with patch(WITHDRAW_GOLD_SYNC) as mock_api:
            mock_api.return_value = api_error(460, "Insufficient bank gold")

            result = runner.invoke(app, ["withdraw-gold", "testchar", "50"])

            assert result.exit_code == 1
            assert "Insufficient bank gold" in result.stdout

    def test_withdraw_gold_validation_error(self, runner):
        """Test withdraw gold command with validation error."""
        result = runner.invoke(app, ["withdraw-gold", "", "50"])
        assert result.exit_code == 2

    def test_withdraw_gold_api_exception(self, runner, stub_api):
        """Test withdraw gold command with API exception."""
        with patch(WITHDRAW_GOLD_SYNC) as mock_api:
            mock_api.side_effect = unexpected_status(500, "API Error")

            result = runner.invoke(app, ["withdraw-gold", "testchar", "50"])

            assert result.exit_code == 1
            assert "API Error" in result.stdout


class TestDepositItemCommand:
    """Test deposit-item command functionality."""

    def test_deposit_item_success(self, runner, stub_api):
        """Test successful deposit item command."""
        with patch(DEPOSIT_ITEM_SYNC) as mock_api:
            mock_api.return_value = api_response(Mock())

            result = runner.invoke(app, ["deposit-item", "testchar", "iron_ore", "10"])

            assert result.exit_code == 0
            assert "Deposited 10x iron_ore" in result.stdout

    def test_deposit_item_with_cooldown(self, runner, stub_api):
        """Test deposit item command with cooldown (dead response-cooldown branch)."""
        with patch(DEPOSIT_ITEM_SYNC) as mock_api:
            mock_api.return_value = Mock(status_code=200)

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=5, message=None, error=None)

                result = runner.invoke(app, ["deposit-item", "testchar", "iron_ore", "10"])

                assert result.exit_code == 0
                assert "cooldown" in result.stdout

    def test_deposit_item_error(self, runner, stub_api):
        """Test deposit item command with error."""
        with patch(DEPOSIT_ITEM_SYNC) as mock_api:
            mock_api.return_value = api_error(404, "Item not found")

            result = runner.invoke(app, ["deposit-item", "testchar", "iron_ore", "10"])

            assert result.exit_code == 1
            assert "Item not found" in result.stdout

    def test_deposit_item_validation_error(self, runner):
        """Test deposit item command with validation error."""
        result = runner.invoke(app, ["deposit-item", "", "iron_ore", "10"])
        assert result.exit_code == 2

    def test_deposit_item_api_exception(self, runner, stub_api):
        """Test deposit item command with API exception."""
        with patch(DEPOSIT_ITEM_SYNC) as mock_api:
            mock_api.side_effect = unexpected_status(500, "API Error")

            result = runner.invoke(app, ["deposit-item", "testchar", "iron_ore", "10"])

            assert result.exit_code == 1
            assert "API Error" in result.stdout


class TestWithdrawItemCommand:
    """Test withdraw-item command functionality."""

    def test_withdraw_item_success(self, runner, stub_api):
        """Test successful withdraw item command."""
        with patch(WITHDRAW_ITEM_SYNC) as mock_api:
            mock_api.return_value = api_response(Mock())

            result = runner.invoke(app, ["withdraw-item", "testchar", "copper_ore", "5"])

            assert result.exit_code == 0
            assert "Withdrew 5x copper_ore" in result.stdout

    def test_withdraw_item_with_cooldown(self, runner, stub_api):
        """Test withdraw item command with cooldown (dead response-cooldown branch)."""
        with patch(WITHDRAW_ITEM_SYNC) as mock_api:
            mock_api.return_value = Mock(status_code=200)

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=12, message=None, error=None)

                result = runner.invoke(app, ["withdraw-item", "testchar", "copper_ore", "5"])

                assert result.exit_code == 0
                assert "cooldown" in result.stdout

    def test_withdraw_item_error(self, runner, stub_api):
        """Test withdraw item command with error."""
        with patch(WITHDRAW_ITEM_SYNC) as mock_api:
            mock_api.return_value = api_error(471, "Insufficient quantity")

            result = runner.invoke(app, ["withdraw-item", "testchar", "copper_ore", "5"])

            assert result.exit_code == 1
            assert "Insufficient quantity" in result.stdout

    def test_withdraw_item_validation_error(self, runner):
        """Test withdraw item command with validation error."""
        result = runner.invoke(app, ["withdraw-item", "", "copper_ore", "5"])
        assert result.exit_code == 2

    def test_withdraw_item_api_exception(self, runner, stub_api):
        """Test withdraw item command with API exception."""
        with patch(WITHDRAW_ITEM_SYNC) as mock_api:
            mock_api.side_effect = unexpected_status(500, "API Error")

            result = runner.invoke(app, ["withdraw-item", "testchar", "copper_ore", "5"])

            assert result.exit_code == 1
            assert "API Error" in result.stdout


class TestExpandCommand:
    """Test expand command functionality."""

    def test_expand_success(self, runner, stub_api):
        """Test successful expand command."""
        with patch(EXPAND_SYNC) as mock_api:
            mock_api.return_value = api_response(Mock())

            result = runner.invoke(app, ["expand", "testchar"])

            assert result.exit_code == 0
            assert "Bank expansion purchased" in result.stdout

    def test_expand_with_cooldown(self, runner, stub_api):
        """Test expand command with cooldown (dead response-cooldown branch)."""
        with patch(EXPAND_SYNC) as mock_api:
            mock_api.return_value = Mock(status_code=200)

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=20, message=None, error=None)

                result = runner.invoke(app, ["expand", "testchar"])

                assert result.exit_code == 0
                assert "cooldown" in result.stdout

    def test_expand_error(self, runner, stub_api):
        """Test expand command with error."""
        with patch(EXPAND_SYNC) as mock_api:
            mock_api.return_value = api_error(492, "Insufficient gold")

            result = runner.invoke(app, ["expand", "testchar"])

            assert result.exit_code == 1
            assert "Insufficient gold" in result.stdout

    def test_expand_validation_error(self, runner):
        """Test expand command with validation error."""
        result = runner.invoke(app, ["expand", ""])
        assert result.exit_code == 2

    def test_expand_api_exception(self, runner, stub_api):
        """Test expand command with API exception."""
        with patch(EXPAND_SYNC) as mock_api:
            mock_api.side_effect = unexpected_status(500, "API Error")

            result = runner.invoke(app, ["expand", "testchar"])

            assert result.exit_code == 1
            assert "API Error" in result.stdout


class TestBulkOperations:
    """Test bulk banking helpers against API-boundary stubs."""

    def test_get_character_inventory(self, stub_api):
        """Test getting character inventory."""
        stub_api.get_character.return_value = inventory_response(
            [("iron_ore", 10, 1), ("copper_ore", 5, 2)]
        )

        result = get_character_inventory("testchar")

        assert len(result) == 2
        assert result[0]["code"] == "iron_ore"
        assert result[0]["quantity"] == 10

    def test_get_item_info(self, stub_api):
        """Test getting item information."""
        with patch(ITEM_SYNC) as mock_api:
            mock_api.return_value = api_response(make_item("iron_ore"))

            result = get_item_info("iron_ore")

            assert result["code"] == "iron_ore"
            assert result["name"] == "Iron Ore"
            assert result["type"] == "ore"

    def test_categorize_item(self):
        """Test item categorization."""
        # Test ore categorization
        ore_item = {"type": "ore", "subtype": "mining"}
        assert categorize_item(ore_item) == "resource"

        # Test equipment categorization
        weapon_item = {"type": "weapon", "subtype": "sword"}
        assert categorize_item(weapon_item) == "equipment"

        # Test consumable categorization
        food_item = {"type": "consumable", "subtype": "food"}
        assert categorize_item(food_item) == "consumable"

        # Test unknown categorization
        unknown_item = {"type": "unknown", "subtype": "unknown"}
        assert categorize_item(unknown_item) == "other"

    def test_should_keep_item(self):
        """Test item keep logic."""
        # Test equipment (should keep by default)
        weapon_info = {"type": "weapon", "subtype": "sword"}
        assert should_keep_item(weapon_info, keep_equipment=True, keep_consumables=False)
        assert not should_keep_item(weapon_info, keep_equipment=False, keep_consumables=False)

        # Test consumables
        food_info = {"type": "consumable", "subtype": "food"}
        assert should_keep_item(food_info, keep_equipment=True, keep_consumables=True)
        assert not should_keep_item(food_info, keep_equipment=True, keep_consumables=False)

        # Test currency (always keep)
        currency_info = {"type": "currency", "subtype": "gold"}
        assert should_keep_item(currency_info, keep_equipment=False, keep_consumables=False)

    def test_execute_single_deposit_success(self, stub_api):
        """Test successful single deposit operation."""
        with patch(DEPOSIT_ITEM_SYNC) as mock_api:
            mock_api.return_value = api_response(Mock())

            success, error, cooldown = execute_single_deposit("testchar", "iron_ore", 10)

            assert success
            assert error is None
            assert cooldown is None

    def test_execute_single_deposit_cooldown(self, stub_api):
        """Test single deposit operation with cooldown.

        NOTE: handle_api_response never produces a cooldown CLIResponse, so the
        in-band cooldown branch is only reachable by patching the helper.
        """
        with patch(DEPOSIT_ITEM_SYNC) as mock_api:
            mock_api.return_value = Mock(status_code=200)

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=5, error=None)

                success, error, cooldown = execute_single_deposit("testchar", "iron_ore", 10)

                assert not success
                assert error is None
                assert cooldown == 5

    def test_execute_single_deposit_error(self, stub_api):
        """Test single deposit operation with error."""
        with patch(DEPOSIT_ITEM_SYNC) as mock_api:
            mock_api.return_value = api_error(404, "Item not found")

            success, error, cooldown = execute_single_deposit("testchar", "iron_ore", 10)

            assert not success
            assert "Item not found" in error
            assert cooldown is None


class TestDepositAllCommand:
    """Test deposit-all command functionality."""

    def test_deposit_all_success(self, runner, stub_api):
        """Test successful deposit-all command."""
        stub_api.get_character.return_value = inventory_response(
            [("iron_ore", 10, 1), ("copper_ore", 5, 2)]
        )

        with patch(ITEM_SYNC, side_effect=item_lookup), patch(DEPOSIT_ITEM_SYNC) as mock_deposit:
            mock_deposit.return_value = api_response(Mock())

            result = runner.invoke(app, ["deposit-all", "testchar"])

            assert result.exit_code == 0
            assert "Successfully processed" in result.stdout
            assert mock_deposit.call_count == 2

    def test_deposit_all_no_inventory(self, runner, stub_api):
        """Test deposit-all command with no inventory."""
        stub_api.get_character.return_value = inventory_response([])

        result = runner.invoke(app, ["deposit-all", "testchar"])

        assert result.exit_code == 0
        assert "has no inventory items" in result.stdout

    def test_deposit_all_with_type_filter(self, runner, stub_api):
        """Test deposit-all command with type filter."""
        stub_api.get_character.return_value = inventory_response(
            [("iron_ore", 10, 1), ("wooden_sword", 1, 2)]
        )

        with patch(ITEM_SYNC, side_effect=item_lookup), patch(DEPOSIT_ITEM_SYNC) as mock_deposit:
            mock_deposit.return_value = api_response(Mock())

            result = runner.invoke(app, ["deposit-all", "testchar", "--type", "resource"])

            assert result.exit_code == 0
            # The type filter keeps only the ore; the sword is never deposited.
            assert mock_deposit.call_count == 1

    def test_deposit_all_keep_equipment(self, runner, stub_api):
        """Test deposit-all command keeping equipment."""
        stub_api.get_character.return_value = inventory_response(
            [("iron_ore", 10, 1), ("wooden_sword", 1, 2)]
        )

        with patch(ITEM_SYNC, side_effect=item_lookup), patch(DEPOSIT_ITEM_SYNC) as mock_deposit:
            mock_deposit.return_value = api_response(Mock())

            result = runner.invoke(app, ["deposit-all", "testchar", "--keep-equipment"])

            assert result.exit_code == 0
            # Should only deposit iron_ore, not wooden_sword
            assert mock_deposit.call_count == 1

    def test_deposit_all_with_cooldown(self, runner, stub_api):
        """Test deposit-all command with cooldown handling."""
        stub_api.get_character.return_value = inventory_response([("iron_ore", 10, 1)])

        with patch(ITEM_SYNC, side_effect=item_lookup), patch(DEPOSIT_ITEM_SYNC) as mock_deposit:
            # First call hits a cooldown error, the retry succeeds
            mock_deposit.side_effect = [cooldown_status(2), api_response(Mock())]

            with patch("time.sleep") as mock_sleep:
                result = runner.invoke(app, ["deposit-all", "testchar"])

                assert result.exit_code == 0
                assert mock_sleep.called
                assert mock_deposit.call_count == 2

    def test_deposit_all_empty_after_type_filter(self, runner, stub_api):
        """Test deposit-all when type filter leaves no items."""
        stub_api.get_character.return_value = inventory_response([("iron_ore", 10, 1)])

        with patch(ITEM_SYNC, side_effect=item_lookup):
            result = runner.invoke(app, ["deposit-all", "testchar", "--type", "equipment"])

            assert result.exit_code == 0
            assert "No items of type 'equipment'" in result.stdout

    def test_deposit_all_item_info_none_skips_item(self, runner, stub_api):
        """Test deposit-all skips items where the item lookup fails."""
        stub_api.get_character.return_value = inventory_response([("mystery_item", 1, 1)])

        with patch(ITEM_SYNC, side_effect=item_lookup):
            result = runner.invoke(app, ["deposit-all", "testchar"])

            assert result.exit_code == 0
            assert "No items to deposit" in result.stdout

    def test_deposit_all_all_items_kept(self, runner, stub_api):
        """Test deposit-all when all items are marked to keep."""
        stub_api.get_character.return_value = inventory_response([("wooden_sword", 1, 1)])

        with patch(ITEM_SYNC, side_effect=item_lookup):
            result = runner.invoke(app, ["deposit-all", "testchar"])

            assert result.exit_code == 0
            assert "No items to deposit (all items are marked to keep)" in result.stdout

    def test_deposit_all_cooldown_retry_fails_stops(self, runner, stub_api):
        """Test deposit-all stops when cooldown retry also fails and continue_on_error is False."""
        stub_api.get_character.return_value = inventory_response(
            [("iron_ore", 10, 1), ("copper_ore", 5, 2)]
        )

        with patch(ITEM_SYNC, side_effect=item_lookup), patch(DEPOSIT_ITEM_SYNC) as mock_deposit:
            # First call hits a cooldown, retry also fails
            mock_deposit.side_effect = [cooldown_status(1), api_error(461, "retry failed")]

            with patch("time.sleep"):
                result = runner.invoke(app, ["deposit-all", "testchar"])

                assert result.exit_code == 0
                assert mock_deposit.call_count == 2

    def test_deposit_all_error_stops_without_continue(self, runner, stub_api):
        """Test deposit-all stops on error when continue_on_error is False."""
        stub_api.get_character.return_value = inventory_response(
            [("iron_ore", 10, 1), ("copper_ore", 5, 2)]
        )

        with patch(ITEM_SYNC, side_effect=item_lookup), patch(DEPOSIT_ITEM_SYNC) as mock_deposit:
            # First call fails with error (no cooldown)
            mock_deposit.side_effect = [api_error(461, "deposit error"), api_response(Mock())]

            result = runner.invoke(app, ["deposit-all", "testchar"])

            assert result.exit_code == 0
            # Without --continue-on-error, should stop after first failure
            assert mock_deposit.call_count == 1

    def test_deposit_all_exception_handler(self, runner, stub_api):
        """Test deposit-all exception handler exits with code 1.

        NOTE: the outer except clause is unreachable through the real internals
        (get_character_inventory swallows its own errors), so the in-module
        helper import is patched to force the path.
        """
        with patch("artifactsmmo_cli.commands.bank.get_character_inventory") as mock_get_inv:
            mock_get_inv.side_effect = unexpected_status(500, "unexpected error")

            result = runner.invoke(app, ["deposit-all", "testchar"])

            assert result.exit_code == 1
            assert "unexpected error" in result.stdout

    def test_deposit_all_with_error_continue(self, runner, stub_api):
        """Test deposit-all command with error and continue-on-error."""
        stub_api.get_character.return_value = inventory_response(
            [("iron_ore", 10, 1), ("copper_ore", 5, 2)]
        )

        with patch(ITEM_SYNC, side_effect=item_lookup), patch(DEPOSIT_ITEM_SYNC) as mock_deposit:
            # First call fails, second call succeeds
            mock_deposit.side_effect = [api_error(404, "Item not found"), api_response(Mock())]

            result = runner.invoke(app, ["deposit-all", "testchar", "--continue-on-error"])

            assert result.exit_code == 0
            assert "Failed to process" in result.stdout
            assert mock_deposit.call_count == 2


class TestWithdrawAllCommand:
    """Test withdraw-all command functionality."""

    def test_withdraw_all_success(self, runner, stub_api):
        """Test successful withdraw-all command."""
        bank_item = SimpleNamespace(code="iron_ore", quantity=50)

        with (
            patch(BANK_ITEMS_SYNC) as mock_bank,
            patch(ITEM_SYNC, side_effect=item_lookup),
            patch(WITHDRAW_ITEM_SYNC) as mock_withdraw,
        ):
            mock_bank.return_value = api_response([bank_item])
            mock_withdraw.return_value = api_response(Mock())

            result = runner.invoke(app, ["withdraw-all", "testchar", "iron_ore"])

            assert result.exit_code == 0
            assert "Successfully withdrew 50x Iron Ore" in result.stdout

    def test_withdraw_all_item_not_found(self, runner, stub_api):
        """Test withdraw-all command with item not found in bank."""
        with patch(BANK_ITEMS_SYNC) as mock_bank:
            mock_bank.return_value = api_response([])

            result = runner.invoke(app, ["withdraw-all", "testchar", "iron_ore"])

            assert result.exit_code == 0
            assert "not found in bank" in result.stdout

    def test_withdraw_all_zero_quantity(self, runner, stub_api):
        """Test withdraw-all command with zero quantity in bank."""
        bank_item = SimpleNamespace(code="iron_ore", quantity=0)

        with patch(BANK_ITEMS_SYNC) as mock_bank:
            mock_bank.return_value = api_response([bank_item])

            result = runner.invoke(app, ["withdraw-all", "testchar", "iron_ore"])

            assert result.exit_code == 0
            assert "No 'iron_ore' items in bank" in result.stdout

    def test_withdraw_all_bank_retrieval_fails(self, runner, stub_api):
        """Test withdraw-all when bank item retrieval fails."""
        with patch(BANK_ITEMS_SYNC) as mock_bank:
            mock_bank.return_value = api_error(500, "Bank unavailable")

            result = runner.invoke(app, ["withdraw-all", "testchar", "iron_ore"])

            assert result.exit_code == 1
            assert "Could not retrieve bank items" in result.stdout

    def test_withdraw_all_withdrawal_error(self, runner, stub_api):
        """Test withdraw-all when withdrawal fails with an error."""
        bank_item = SimpleNamespace(code="iron_ore", quantity=10)

        with (
            patch(BANK_ITEMS_SYNC) as mock_bank,
            patch(ITEM_SYNC, side_effect=item_lookup),
            patch(WITHDRAW_ITEM_SYNC) as mock_withdraw,
        ):
            mock_bank.return_value = api_response([bank_item])
            mock_withdraw.return_value = api_error(497, "Inventory full")

            result = runner.invoke(app, ["withdraw-all", "testchar", "iron_ore"])

            assert result.exit_code == 1
            assert "Inventory full" in result.stdout

    def test_withdraw_all_exception_handler(self, runner, stub_api):
        """Test withdraw-all exception handler exits with code 1."""
        with patch(BANK_ITEMS_SYNC) as mock_bank:
            mock_bank.side_effect = unexpected_status(500, "connection error")

            result = runner.invoke(app, ["withdraw-all", "testchar", "iron_ore"])

            assert result.exit_code == 1
            assert "connection error" in result.stdout

    def test_withdraw_all_with_cooldown(self, runner, stub_api):
        """Test withdraw-all command with cooldown."""
        bank_item = SimpleNamespace(code="iron_ore", quantity=25)

        with (
            patch(BANK_ITEMS_SYNC) as mock_bank,
            patch(ITEM_SYNC, side_effect=item_lookup),
            patch(WITHDRAW_ITEM_SYNC) as mock_withdraw,
        ):
            mock_bank.return_value = api_response([bank_item])
            mock_withdraw.side_effect = cooldown_status(5)

            result = runner.invoke(app, ["withdraw-all", "testchar", "iron_ore"])

            assert result.exit_code == 0
            assert "cooldown" in result.stdout


class TestSmartExchangeCommand:
    """Test smart exchange command functionality."""

    def test_smart_exchange_success(self, runner, stub_api):
        """Test successful smart exchange command."""
        stub_api.get_character.return_value = inventory_response(
            [("iron_ore", 10, 1), ("wooden_sword", 1, 2), ("bread", 3, 3)]
        )

        with patch(ITEM_SYNC, side_effect=item_lookup), patch(DEPOSIT_ITEM_SYNC) as mock_deposit:
            mock_deposit.return_value = api_response(Mock())

            result = runner.invoke(app, ["exchange", "testchar"])

            assert result.exit_code == 0
            assert "Smart Exchange Plan" in result.stdout
            # Should deposit iron_ore (resource) but keep wooden_sword (equipment)
            # and bread (consumable with keep_consumables=True)
            assert mock_deposit.call_count == 1

    def test_smart_exchange_no_items_to_deposit(self, runner, stub_api):
        """Test smart exchange with no items to deposit."""
        stub_api.get_character.return_value = inventory_response([("wooden_sword", 1, 1)])

        with patch(ITEM_SYNC, side_effect=item_lookup):
            result = runner.invoke(app, ["exchange", "testchar"])

            assert result.exit_code == 0
            assert "No items to deposit in smart exchange" in result.stdout

    def test_smart_exchange_no_deposit_resources(self, runner, stub_api):
        """Test smart exchange with --no-deposit-resources."""
        stub_api.get_character.return_value = inventory_response(
            [("iron_ore", 10, 1), ("wooden_sword", 1, 2)]
        )

        with patch(ITEM_SYNC, side_effect=item_lookup):
            result = runner.invoke(app, ["exchange", "testchar", "--no-deposit-resources"])

            assert result.exit_code == 0
            assert "No items to deposit in smart exchange" in result.stdout

    def test_smart_exchange_no_inventory(self, runner, stub_api):
        """Test smart exchange with no inventory items."""
        stub_api.get_character.return_value = inventory_response([])

        result = runner.invoke(app, ["exchange", "testchar"])

        assert result.exit_code == 0
        assert "has no inventory items" in result.stdout

    def test_smart_exchange_item_info_none_skips(self, runner, stub_api):
        """Test smart exchange skips items where the item lookup fails."""
        stub_api.get_character.return_value = inventory_response([("mystery_item", 5, 1)])

        with patch(ITEM_SYNC, side_effect=item_lookup):
            result = runner.invoke(app, ["exchange", "testchar"])

            assert result.exit_code == 0
            assert "No items to deposit in smart exchange" in result.stdout

    def test_smart_exchange_resource_no_deposit(self, runner, stub_api):
        """Test smart exchange keeps resources when deposit_resources is False."""
        stub_api.get_character.return_value = inventory_response([("iron_ore", 10, 1)])

        with patch(ITEM_SYNC, side_effect=item_lookup):
            result = runner.invoke(app, ["exchange", "testchar", "--no-deposit-resources"])

            assert result.exit_code == 0
            assert "No items to deposit in smart exchange" in result.stdout

    def test_smart_exchange_cooldown_retry_fails(self, runner, stub_api):
        """Test smart exchange cooldown handling when retry also fails."""
        stub_api.get_character.return_value = inventory_response(
            [("iron_ore", 10, 1), ("coal", 5, 2)]
        )

        with patch(ITEM_SYNC, side_effect=item_lookup), patch(DEPOSIT_ITEM_SYNC) as mock_deposit:
            # cooldown on first, retry also fails
            mock_deposit.side_effect = [cooldown_status(1), api_error(461, "retry failed")]

            with patch("time.sleep"):
                result = runner.invoke(app, ["exchange", "testchar"])

                assert result.exit_code == 0
                assert mock_deposit.call_count == 2

    def test_smart_exchange_cooldown_retry_succeeds(self, runner, stub_api):
        """Test smart exchange cooldown handling when retry succeeds."""
        stub_api.get_character.return_value = inventory_response([("iron_ore", 10, 1)])

        with patch(ITEM_SYNC, side_effect=item_lookup), patch(DEPOSIT_ITEM_SYNC) as mock_deposit:
            # First call hits a cooldown, retry succeeds
            mock_deposit.side_effect = [cooldown_status(1), api_response(Mock())]

            with patch("time.sleep"):
                result = runner.invoke(app, ["exchange", "testchar"])

                assert result.exit_code == 0
                assert mock_deposit.call_count == 2

    def test_smart_exchange_error_stops_without_continue(self, runner, stub_api):
        """Test smart exchange stops on error when continue_on_error is False."""
        stub_api.get_character.return_value = inventory_response(
            [("iron_ore", 10, 1), ("coal", 5, 2)]
        )

        with patch(ITEM_SYNC, side_effect=item_lookup), patch(DEPOSIT_ITEM_SYNC) as mock_deposit:
            mock_deposit.side_effect = [api_error(461, "deposit error"), api_response(Mock())]

            result = runner.invoke(app, ["exchange", "testchar"])

            assert result.exit_code == 0
            assert mock_deposit.call_count == 1

    def test_smart_exchange_exception_handler(self, runner, stub_api):
        """Test smart exchange exception handler exits with code 1.

        NOTE: the outer except clause is unreachable through the real internals
        (get_character_inventory swallows its own errors), so the in-module
        helper import is patched to force the path.
        """
        with patch("artifactsmmo_cli.commands.bank.get_character_inventory") as mock_get_inv:
            mock_get_inv.side_effect = unexpected_status(500, "unexpected error")

            result = runner.invoke(app, ["exchange", "testchar"])

            assert result.exit_code == 1
            assert "unexpected error" in result.stdout

    def test_smart_exchange_keeps_crafting_utility_currency(self, runner, stub_api):
        """Test smart exchange keeps crafting, utility, and currency items."""
        stub_api.get_character.return_value = inventory_response([("craft_mat", 5, 1)])

        with patch(ITEM_SYNC, side_effect=item_lookup):
            result = runner.invoke(app, ["exchange", "testchar"])

            assert result.exit_code == 0
            assert "No items to deposit in smart exchange" in result.stdout

    def test_smart_exchange_no_keep_consumables(self, runner, stub_api):
        """Test smart exchange with --no-keep-consumables."""
        stub_api.get_character.return_value = inventory_response([("bread", 3, 1)])

        with patch(ITEM_SYNC, side_effect=item_lookup), patch(DEPOSIT_ITEM_SYNC) as mock_deposit:
            mock_deposit.return_value = api_response(Mock())

            result = runner.invoke(app, ["exchange", "testchar", "--no-keep-consumables"])

            assert result.exit_code == 0
            # Should deposit bread since we're not keeping consumables
            assert mock_deposit.call_count == 1


class TestHelperFunctions:
    """Test helper/utility functions for error and edge-case branches."""

    def test_get_character_inventory_exception(self, stub_api):
        """Test get_character_inventory returns [] on exception."""
        stub_api.get_character.side_effect = unexpected_status(500, "boom")

        result = get_character_inventory("testchar")
        assert result == []

    def test_get_character_inventory_failed_response(self, stub_api):
        """Test get_character_inventory returns [] when the API returns an error."""
        stub_api.get_character.return_value = api_error(498, "Character not found")

        result = get_character_inventory("testchar")
        assert result == []

    def test_get_item_info_exception(self, stub_api):
        """Test get_item_info returns None on exception."""
        with patch(ITEM_SYNC) as mock_api:
            mock_api.side_effect = unexpected_status(500, "boom")

            result = get_item_info("iron_ore")
            assert result is None

    def test_get_item_info_failed_response(self, stub_api):
        """Test get_item_info returns None when the API returns an error."""
        with patch(ITEM_SYNC) as mock_api:
            mock_api.return_value = api_error(404, "Item not found")

            result = get_item_info("iron_ore")
            assert result is None

    def test_filter_items_by_type_item_info_none(self, stub_api):
        """Test filter_items_by_type skips items where the item lookup fails."""
        inventory = [
            {"code": "unknown_item", "quantity": 5, "slot": 1},
        ]

        with patch(ITEM_SYNC, side_effect=item_lookup):
            result = filter_items_by_type(inventory, "resource")
            assert result == []

    def test_filter_items_by_type_matching(self, stub_api):
        """Test filter_items_by_type returns items matching the requested category."""
        inventory = [
            {"code": "iron_ore", "quantity": 5, "slot": 1},
            {"code": "wooden_sword", "quantity": 1, "slot": 2},
        ]

        with patch(ITEM_SYNC, side_effect=item_lookup):
            result = filter_items_by_type(inventory, "resource")
            assert len(result) == 1
            assert result[0]["code"] == "iron_ore"

    def test_execute_single_deposit_exception_with_cooldown(self, stub_api):
        """Test execute_single_deposit exception path returns cooldown."""
        with patch(DEPOSIT_ITEM_SYNC) as mock_api:
            mock_api.side_effect = cooldown_status(7)

            success, error, cooldown = execute_single_deposit("testchar", "iron_ore", 10)
            assert success is False
            assert error is None
            assert cooldown == 7

    def test_execute_single_deposit_exception_with_error(self, stub_api):
        """Test execute_single_deposit exception path returns error string."""
        with patch(DEPOSIT_ITEM_SYNC) as mock_api:
            mock_api.side_effect = unexpected_status(500, "connection lost")

            success, error, cooldown = execute_single_deposit("testchar", "iron_ore", 10)
            assert success is False
            assert "connection lost" in error
            assert cooldown is None

    def test_execute_single_withdraw_success(self, stub_api):
        """Test execute_single_withdraw success path."""
        with patch(WITHDRAW_ITEM_SYNC) as mock_api:
            mock_api.return_value = api_response(Mock())

            success, error, cooldown = execute_single_withdraw("testchar", "iron_ore", 10)
            assert success is True
            assert error is None
            assert cooldown is None

    def test_execute_single_withdraw_cooldown(self, stub_api):
        """Test execute_single_withdraw cooldown path.

        NOTE: handle_api_response never produces a cooldown CLIResponse, so the
        in-band cooldown branch is only reachable by patching the helper.
        """
        with patch(WITHDRAW_ITEM_SYNC) as mock_api:
            mock_api.return_value = Mock(status_code=200)

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=9, error=None)

                success, error, cooldown = execute_single_withdraw("testchar", "iron_ore", 10)
                assert success is False
                assert error is None
                assert cooldown == 9

    def test_execute_single_withdraw_error(self, stub_api):
        """Test execute_single_withdraw error path."""
        with patch(WITHDRAW_ITEM_SYNC) as mock_api:
            mock_api.return_value = api_error(471, "Not enough items")

            success, error, cooldown = execute_single_withdraw("testchar", "iron_ore", 10)
            assert success is False
            assert "Not enough items" in error
            assert cooldown is None

    def test_execute_single_withdraw_exception_with_cooldown(self, stub_api):
        """Test execute_single_withdraw exception path returns cooldown."""
        with patch(WITHDRAW_ITEM_SYNC) as mock_api:
            mock_api.side_effect = cooldown_status(3)

            success, error, cooldown = execute_single_withdraw("testchar", "iron_ore", 10)
            assert success is False
            assert error is None
            assert cooldown == 3

    def test_execute_single_withdraw_exception_with_error(self, stub_api):
        """Test execute_single_withdraw exception path returns error string."""
        with patch(WITHDRAW_ITEM_SYNC) as mock_api:
            mock_api.side_effect = unexpected_status(500, "connection lost")

            success, error, cooldown = execute_single_withdraw("testchar", "iron_ore", 10)
            assert success is False
            assert "connection lost" in error
            assert cooldown is None


class TestDisplayOperationSummary:
    """Test operation summary display function."""

    def test_display_summary_success_only(self, runner):
        """Test displaying summary with only successful operations."""
        successful_ops = [
            ("iron_ore", "Iron Ore", 10),
            ("copper_ore", "Copper Ore", 5),
        ]
        failed_ops = []

        # This should not raise an exception
        _display_operation_summary("Test", successful_ops, failed_ops)

    def test_display_summary_with_failures(self, runner):
        """Test displaying summary with failed operations."""
        successful_ops = [
            ("iron_ore", "Iron Ore", 10),
        ]
        failed_ops = [
            ("copper_ore", "Copper Ore", 5, "Item not found"),
        ]

        # This should not raise an exception
        _display_operation_summary("Test", successful_ops, failed_ops)

    def test_display_summary_empty(self, runner):
        """Test displaying summary with no operations."""
        successful_ops = []
        failed_ops = []

        # This should not raise an exception
        _display_operation_summary("Test", successful_ops, failed_ops)
