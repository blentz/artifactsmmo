"""Tests for bank commands."""

from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from artifactsmmo_cli.commands.bank import app


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_client_manager():
    """Mock the ClientManager."""
    with patch("artifactsmmo_cli.commands.bank.ClientManager") as mock:
        mock_instance = Mock()
        mock.return_value = mock_instance
        mock_instance.client = Mock()
        mock_instance.client.my_account = Mock()
        mock_instance.client.my_characters = Mock()
        yield mock_instance


@pytest.fixture
def mock_api_response():
    """Mock API response."""
    mock_response = Mock()
    mock_response.status_code = 200
    return mock_response


class TestListCommand:
    """Test list command functionality."""

    def test_list_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful list command."""
        with patch("artifactsmmo_api_client.api.my_account.get_bank_items_my_bank_items_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_data = [{"code": "iron_ore", "quantity": 50}, {"code": "copper_ore", "quantity": 25}]
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["list"])

                assert result.exit_code == 0

    def test_list_no_items(self, runner, mock_client_manager, mock_api_response):
        """Test list command with no items."""
        with patch("artifactsmmo_api_client.api.my_account.get_bank_items_my_bank_items_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, data=None, error="No bank items found")

                result = runner.invoke(app, ["list"])

                assert result.exit_code == 0
                assert "No bank items found" in result.stdout

    def test_list_api_exception(self, runner, mock_client_manager):
        """Test list command with API exception."""
        with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.bank.handle_api_error") as mock_error:
                mock_error.return_value = Mock(error="API Error")

                result = runner.invoke(app, ["list"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout


class TestDetailsCommand:
    """Test details command functionality."""

    def test_details_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful details command."""
        with patch("artifactsmmo_api_client.api.my_account.get_bank_details_my_bank_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_data = {"gold": 1000, "slots": 50, "next_expansion_cost": 500}
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["details"])

                assert result.exit_code == 0
                assert "Bank Gold: 1000" in result.stdout
                assert "Bank Slots: 50" in result.stdout
                assert "Expansion Cost: 500" in result.stdout

    def test_details_error(self, runner, mock_client_manager, mock_api_response):
        """Test details command with error."""
        with patch("artifactsmmo_api_client.api.my_account.get_bank_details_my_bank_get.sync") as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, data=None, error="Access denied")

                result = runner.invoke(app, ["details"])

                assert result.exit_code == 1
                assert "Access denied" in result.stdout

    def test_details_api_exception(self, runner, mock_client_manager):
        """Test details command with API exception."""
        with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.bank.handle_api_error") as mock_error:
                mock_error.return_value = Mock(error="API Error")

                result = runner.invoke(app, ["details"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout


class TestDepositGoldCommand:
    """Test deposit-gold command functionality."""

    def test_deposit_gold_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful deposit gold command."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_deposit_bank_gold_my_name_action_bank_deposit_gold_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, message="Gold deposited")

                result = runner.invoke(app, ["deposit-gold", "testchar", "100"])

                assert result.exit_code == 0
                assert "Gold deposited" in result.stdout

    def test_deposit_gold_with_cooldown(self, runner, mock_client_manager, mock_api_response):
        """Test deposit gold command with cooldown."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_deposit_bank_gold_my_name_action_bank_deposit_gold_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=10, message=None, error=None)

                result = runner.invoke(app, ["deposit-gold", "testchar", "100"])

                assert result.exit_code == 0
                assert "cooldown" in result.stdout

    def test_deposit_gold_error(self, runner, mock_client_manager, mock_api_response):
        """Test deposit gold command with error."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_deposit_bank_gold_my_name_action_bank_deposit_gold_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=None, error="Insufficient gold")

                result = runner.invoke(app, ["deposit-gold", "testchar", "100"])

                assert result.exit_code == 1
                assert "Insufficient gold" in result.stdout

    def test_deposit_gold_validation_error(self, runner):
        """Test deposit gold command with validation error."""
        result = runner.invoke(app, ["deposit-gold", "", "100"])
        assert result.exit_code == 1

    def test_deposit_gold_api_exception(self, runner, mock_client_manager):
        """Test deposit gold command with API exception."""
        with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.bank.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=None, error="API Error")

                result = runner.invoke(app, ["deposit-gold", "testchar", "100"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout

    def test_deposit_gold_api_exception_with_cooldown(self, runner, mock_client_manager):
        """Test deposit gold command with API exception and cooldown."""
        with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.bank.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=15, error=None)

                result = runner.invoke(app, ["deposit-gold", "testchar", "100"])

                assert result.exit_code == 1

    def test_withdraw_gold_api_exception_with_cooldown(self, runner, mock_client_manager):
        """Test withdraw gold command with API exception and cooldown."""
        with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.bank.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=8, error=None)

                result = runner.invoke(app, ["withdraw-gold", "testchar", "50"])

                assert result.exit_code == 1

    def test_deposit_item_api_exception_with_cooldown(self, runner, mock_client_manager):
        """Test deposit item command with API exception and cooldown."""
        with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.bank.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=5, error=None)

                result = runner.invoke(app, ["deposit-item", "testchar", "iron_ore", "10"])

                assert result.exit_code == 1

    def test_withdraw_item_api_exception_with_cooldown(self, runner, mock_client_manager):
        """Test withdraw item command with API exception and cooldown."""
        with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.bank.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=12, error=None)

                result = runner.invoke(app, ["withdraw-item", "testchar", "copper_ore", "5"])

                assert result.exit_code == 1

    def test_expand_api_exception_with_cooldown(self, runner, mock_client_manager):
        """Test expand command with API exception and cooldown."""
        with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.bank.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=20, error=None)

                result = runner.invoke(app, ["expand", "testchar"])

                assert result.exit_code == 1


class TestWithdrawGoldCommand:
    """Test withdraw-gold command functionality."""

    def test_withdraw_gold_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful withdraw gold command."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_withdraw_bank_gold_my_name_action_bank_withdraw_gold_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, message="Gold withdrawn")

                result = runner.invoke(app, ["withdraw-gold", "testchar", "50"])

                assert result.exit_code == 0
                assert "Gold withdrawn" in result.stdout

    def test_withdraw_gold_with_cooldown(self, runner, mock_client_manager, mock_api_response):
        """Test withdraw gold command with cooldown."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_withdraw_bank_gold_my_name_action_bank_withdraw_gold_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=8, message=None, error=None)

                result = runner.invoke(app, ["withdraw-gold", "testchar", "50"])

                assert result.exit_code == 0
                assert "cooldown" in result.stdout

    def test_withdraw_gold_error(self, runner, mock_client_manager, mock_api_response):
        """Test withdraw gold command with error."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_withdraw_bank_gold_my_name_action_bank_withdraw_gold_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=None, error="Insufficient bank gold")

                result = runner.invoke(app, ["withdraw-gold", "testchar", "50"])

                assert result.exit_code == 1
                assert "Insufficient bank gold" in result.stdout

    def test_withdraw_gold_validation_error(self, runner):
        """Test withdraw gold command with validation error."""
        result = runner.invoke(app, ["withdraw-gold", "", "50"])
        assert result.exit_code == 1

    def test_withdraw_gold_api_exception(self, runner, mock_client_manager):
        """Test withdraw gold command with API exception."""
        with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.bank.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=None, error="API Error")

                result = runner.invoke(app, ["withdraw-gold", "testchar", "50"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout


class TestDepositItemCommand:
    """Test deposit-item command functionality."""

    def test_deposit_item_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful deposit item command."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_deposit_bank_item_my_name_action_bank_deposit_item_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, message="Item deposited")

                result = runner.invoke(app, ["deposit-item", "testchar", "iron_ore", "10"])

                assert result.exit_code == 0
                assert "Item deposited" in result.stdout

    def test_deposit_item_with_cooldown(self, runner, mock_client_manager, mock_api_response):
        """Test deposit item command with cooldown."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_deposit_bank_item_my_name_action_bank_deposit_item_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=5, message=None, error=None)

                result = runner.invoke(app, ["deposit-item", "testchar", "iron_ore", "10"])

                assert result.exit_code == 0
                assert "cooldown" in result.stdout

    def test_deposit_item_error(self, runner, mock_client_manager, mock_api_response):
        """Test deposit item command with error."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_deposit_bank_item_my_name_action_bank_deposit_item_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=None, error="Item not found")

                result = runner.invoke(app, ["deposit-item", "testchar", "iron_ore", "10"])

                assert result.exit_code == 1
                assert "Item not found" in result.stdout

    def test_deposit_item_validation_error(self, runner):
        """Test deposit item command with validation error."""
        result = runner.invoke(app, ["deposit-item", "", "iron_ore", "10"])
        assert result.exit_code == 1

    def test_deposit_item_api_exception(self, runner, mock_client_manager):
        """Test deposit item command with API exception."""
        with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.bank.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=None, error="API Error")

                result = runner.invoke(app, ["deposit-item", "testchar", "iron_ore", "10"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout


class TestWithdrawItemCommand:
    """Test withdraw-item command functionality."""

    def test_withdraw_item_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful withdraw item command."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_withdraw_bank_item_my_name_action_bank_withdraw_item_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, message="Item withdrawn")

                result = runner.invoke(app, ["withdraw-item", "testchar", "copper_ore", "5"])

                assert result.exit_code == 0
                assert "Item withdrawn" in result.stdout

    def test_withdraw_item_with_cooldown(self, runner, mock_client_manager, mock_api_response):
        """Test withdraw item command with cooldown."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_withdraw_bank_item_my_name_action_bank_withdraw_item_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=12, message=None, error=None)

                result = runner.invoke(app, ["withdraw-item", "testchar", "copper_ore", "5"])

                assert result.exit_code == 0
                assert "cooldown" in result.stdout

    def test_withdraw_item_error(self, runner, mock_client_manager, mock_api_response):
        """Test withdraw item command with error."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_withdraw_bank_item_my_name_action_bank_withdraw_item_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=None, error="Insufficient quantity")

                result = runner.invoke(app, ["withdraw-item", "testchar", "copper_ore", "5"])

                assert result.exit_code == 1
                assert "Insufficient quantity" in result.stdout

    def test_withdraw_item_validation_error(self, runner):
        """Test withdraw item command with validation error."""
        result = runner.invoke(app, ["withdraw-item", "", "copper_ore", "5"])
        assert result.exit_code == 1

    def test_withdraw_item_api_exception(self, runner, mock_client_manager):
        """Test withdraw item command with API exception."""
        with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.bank.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=None, error="API Error")

                result = runner.invoke(app, ["withdraw-item", "testchar", "copper_ore", "5"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout


class TestExpandCommand:
    """Test expand command functionality."""

    def test_expand_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful expand command."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_buy_bank_expansion_my_name_action_bank_buy_expansion_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, message="Bank expanded")

                result = runner.invoke(app, ["expand", "testchar"])

                assert result.exit_code == 0
                assert "Bank expanded" in result.stdout

    def test_expand_with_cooldown(self, runner, mock_client_manager, mock_api_response):
        """Test expand command with cooldown."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_buy_bank_expansion_my_name_action_bank_buy_expansion_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=20, message=None, error=None)

                result = runner.invoke(app, ["expand", "testchar"])

                assert result.exit_code == 0
                assert "cooldown" in result.stdout

    def test_expand_error(self, runner, mock_client_manager, mock_api_response):
        """Test expand command with error."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_buy_bank_expansion_my_name_action_bank_buy_expansion_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=None, error="Insufficient gold")

                result = runner.invoke(app, ["expand", "testchar"])

                assert result.exit_code == 1
                assert "Insufficient gold" in result.stdout

    def test_expand_validation_error(self, runner):
        """Test expand command with validation error."""
        result = runner.invoke(app, ["expand", ""])
        assert result.exit_code == 1

    def test_expand_api_exception(self, runner, mock_client_manager):
        """Test expand command with API exception."""
        with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
            mock_handle.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.bank.handle_api_error") as mock_error:
                mock_error.return_value = Mock(cooldown_remaining=None, error="API Error")

                result = runner.invoke(app, ["expand", "testchar"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout


class TestBulkOperations:
    """Test bulk banking operations."""

    @pytest.fixture
    def mock_inventory(self):
        """Mock character inventory."""
        return [
            {"code": "iron_ore", "quantity": 10, "slot": 1},
            {"code": "copper_ore", "quantity": 5, "slot": 2},
            {"code": "wooden_sword", "quantity": 1, "slot": 3},
            {"code": "bread", "quantity": 3, "slot": 4},
        ]

    @pytest.fixture
    def mock_item_info(self):
        """Mock item information."""
        return {
            "iron_ore": {
                "code": "iron_ore",
                "name": "Iron Ore",
                "type": "ore",
                "subtype": "mining",
                "level": 1,
                "tradeable": True,
            },
            "copper_ore": {
                "code": "copper_ore",
                "name": "Copper Ore",
                "type": "ore",
                "subtype": "mining",
                "level": 1,
                "tradeable": True,
            },
            "wooden_sword": {
                "code": "wooden_sword",
                "name": "Wooden Sword",
                "type": "weapon",
                "subtype": "sword",
                "level": 1,
                "tradeable": True,
            },
            "bread": {
                "code": "bread",
                "name": "Bread",
                "type": "consumable",
                "subtype": "food",
                "level": 1,
                "tradeable": True,
            },
        }

    def test_get_character_inventory(self, mock_client_manager, mock_inventory):
        """Test getting character inventory."""
        with patch("artifactsmmo_cli.commands.bank.ClientManager") as mock_cm:
            mock_api = Mock()
            mock_cm.return_value.api = mock_api

            mock_response = Mock()
            mock_api.get_character.return_value = mock_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_character = Mock()
                mock_character.inventory = [
                    Mock(code="iron_ore", quantity=10, slot=1),
                    Mock(code="copper_ore", quantity=5, slot=2),
                ]
                mock_handle.return_value = Mock(success=True, data=mock_character)

                from artifactsmmo_cli.commands.bank import get_character_inventory

                result = get_character_inventory("testchar")

                assert len(result) == 2
                assert result[0]["code"] == "iron_ore"
                assert result[0]["quantity"] == 10

    def test_get_item_info(self, mock_client_manager):
        """Test getting item information."""
        with patch("artifactsmmo_api_client.api.items.get_item_items_code_get.sync") as mock_api:
            mock_response = Mock()
            mock_api.return_value = mock_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_item = Mock()
                mock_item.code = "iron_ore"
                mock_item.name = "Iron Ore"
                mock_item.type_ = "ore"
                mock_item.subtype = "mining"
                mock_item.level = 1
                mock_item.tradeable = True
                mock_handle.return_value = Mock(success=True, data=mock_item)

                from artifactsmmo_cli.commands.bank import get_item_info

                result = get_item_info("iron_ore")

                assert result["code"] == "iron_ore"
                assert result["name"] == "Iron Ore"
                assert result["type"] == "ore"

    def test_categorize_item(self):
        """Test item categorization."""
        from artifactsmmo_cli.commands.bank import categorize_item

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
        from artifactsmmo_cli.commands.bank import should_keep_item, categorize_item

        # Test equipment (should keep by default)
        weapon_info = {"type": "weapon", "subtype": "sword"}
        assert should_keep_item(weapon_info, keep_equipment=True, keep_consumables=False) == True
        assert should_keep_item(weapon_info, keep_equipment=False, keep_consumables=False) == False

        # Test consumables
        food_info = {"type": "consumable", "subtype": "food"}
        assert should_keep_item(food_info, keep_equipment=True, keep_consumables=True) == True
        assert should_keep_item(food_info, keep_equipment=True, keep_consumables=False) == False

        # Test currency (always keep)
        currency_info = {"type": "currency", "subtype": "gold"}
        assert should_keep_item(currency_info, keep_equipment=False, keep_consumables=False) == True

    def test_execute_single_deposit_success(self, mock_client_manager):
        """Test successful single deposit operation."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_deposit_bank_item_my_name_action_bank_deposit_item_post.sync"
        ) as mock_api:
            mock_response = Mock()
            mock_api.return_value = mock_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, cooldown_remaining=None, error=None)

                from artifactsmmo_cli.commands.bank import execute_single_deposit

                success, error, cooldown = execute_single_deposit("testchar", "iron_ore", 10)

                assert success == True
                assert error is None
                assert cooldown is None

    def test_execute_single_deposit_cooldown(self, mock_client_manager):
        """Test single deposit operation with cooldown."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_deposit_bank_item_my_name_action_bank_deposit_item_post.sync"
        ) as mock_api:
            mock_response = Mock()
            mock_api.return_value = mock_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=5, error=None)

                from artifactsmmo_cli.commands.bank import execute_single_deposit

                success, error, cooldown = execute_single_deposit("testchar", "iron_ore", 10)

                assert success == False
                assert error is None
                assert cooldown == 5

    def test_execute_single_deposit_error(self, mock_client_manager):
        """Test single deposit operation with error."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_deposit_bank_item_my_name_action_bank_deposit_item_post.sync"
        ) as mock_api:
            mock_response = Mock()
            mock_api.return_value = mock_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=None, error="Item not found")

                from artifactsmmo_cli.commands.bank import execute_single_deposit

                success, error, cooldown = execute_single_deposit("testchar", "iron_ore", 10)

                assert success == False
                assert error == "Item not found"
                assert cooldown is None


class TestDepositAllCommand:
    """Test deposit-all command functionality."""

    def test_deposit_all_success(self, runner, mock_client_manager):
        """Test successful deposit-all command."""
        # Mock inventory
        mock_inventory = [
            Mock(code="iron_ore", quantity=10, slot=1),
            Mock(code="copper_ore", quantity=5, slot=2),
        ]

        with patch("artifactsmmo_cli.commands.bank.get_character_inventory") as mock_get_inv:
            mock_get_inv.return_value = [
                {"code": "iron_ore", "quantity": 10, "slot": 1},
                {"code": "copper_ore", "quantity": 5, "slot": 2},
            ]

            with patch("artifactsmmo_cli.commands.bank.get_item_info") as mock_get_info:

                def mock_item_info(code):
                    items = {
                        "iron_ore": {
                            "code": "iron_ore",
                            "name": "Iron Ore",
                            "type": "ore",
                            "subtype": "mining",
                            "level": 1,
                            "tradeable": True,
                        },
                        "copper_ore": {
                            "code": "copper_ore",
                            "name": "Copper Ore",
                            "type": "ore",
                            "subtype": "mining",
                            "level": 1,
                            "tradeable": True,
                        },
                    }
                    return items.get(code)

                mock_get_info.side_effect = mock_item_info

                with patch("artifactsmmo_cli.commands.bank.execute_single_deposit") as mock_deposit:
                    mock_deposit.return_value = (True, None, None)

                    result = runner.invoke(app, ["deposit-all", "testchar"])

                    assert result.exit_code == 0
                    assert "Successfully processed" in result.stdout

    def test_deposit_all_no_inventory(self, runner, mock_client_manager):
        """Test deposit-all command with no inventory."""
        with patch("artifactsmmo_cli.commands.bank.get_character_inventory") as mock_get_inv:
            mock_get_inv.return_value = []

            result = runner.invoke(app, ["deposit-all", "testchar"])

            assert result.exit_code == 0
            assert "has no inventory items" in result.stdout

    def test_deposit_all_with_type_filter(self, runner, mock_client_manager):
        """Test deposit-all command with type filter."""
        with patch("artifactsmmo_cli.commands.bank.get_character_inventory") as mock_get_inv:
            mock_get_inv.return_value = [
                {"code": "iron_ore", "quantity": 10, "slot": 1},
                {"code": "wooden_sword", "quantity": 1, "slot": 2},
            ]

            with patch("artifactsmmo_cli.commands.bank.filter_items_by_type") as mock_filter:
                mock_filter.return_value = [
                    {
                        "code": "iron_ore",
                        "quantity": 10,
                        "slot": 1,
                        "item_info": {
                            "code": "iron_ore",
                            "name": "Iron Ore",
                            "type": "ore",
                            "subtype": "mining",
                            "level": 1,
                            "tradeable": True,
                        },
                    },
                ]

                with patch("artifactsmmo_cli.commands.bank.execute_single_deposit") as mock_deposit:
                    mock_deposit.return_value = (True, None, None)

                    result = runner.invoke(app, ["deposit-all", "testchar", "--type", "resource"])

                    assert result.exit_code == 0

    def test_deposit_all_keep_equipment(self, runner, mock_client_manager):
        """Test deposit-all command keeping equipment."""
        with patch("artifactsmmo_cli.commands.bank.get_character_inventory") as mock_get_inv:
            mock_get_inv.return_value = [
                {"code": "iron_ore", "quantity": 10, "slot": 1},
                {"code": "wooden_sword", "quantity": 1, "slot": 2},
            ]

            with patch("artifactsmmo_cli.commands.bank.get_item_info") as mock_get_info:

                def mock_item_info(code):
                    items = {
                        "iron_ore": {
                            "code": "iron_ore",
                            "name": "Iron Ore",
                            "type": "ore",
                            "subtype": "mining",
                            "level": 1,
                            "tradeable": True,
                        },
                        "wooden_sword": {
                            "code": "wooden_sword",
                            "name": "Wooden Sword",
                            "type": "weapon",
                            "subtype": "sword",
                            "level": 1,
                            "tradeable": True,
                        },
                    }
                    return items.get(code)

                mock_get_info.side_effect = mock_item_info

                with patch("artifactsmmo_cli.commands.bank.execute_single_deposit") as mock_deposit:
                    mock_deposit.return_value = (True, None, None)

                    result = runner.invoke(app, ["deposit-all", "testchar", "--keep-equipment"])

                    assert result.exit_code == 0
                    # Should only deposit iron_ore, not wooden_sword
                    assert mock_deposit.call_count == 1

    def test_deposit_all_with_cooldown(self, runner, mock_client_manager):
        """Test deposit-all command with cooldown handling."""
        with patch("artifactsmmo_cli.commands.bank.get_character_inventory") as mock_get_inv:
            mock_get_inv.return_value = [
                {"code": "iron_ore", "quantity": 10, "slot": 1},
            ]

            with patch("artifactsmmo_cli.commands.bank.get_item_info") as mock_get_info:
                mock_get_info.return_value = {
                    "code": "iron_ore",
                    "name": "Iron Ore",
                    "type": "ore",
                    "subtype": "mining",
                    "level": 1,
                    "tradeable": True,
                }

                with patch("artifactsmmo_cli.commands.bank.execute_single_deposit") as mock_deposit:
                    # First call returns cooldown, second call succeeds
                    mock_deposit.side_effect = [(False, None, 2), (True, None, None)]

                    with patch("time.sleep") as mock_sleep:
                        result = runner.invoke(app, ["deposit-all", "testchar"])

                        assert result.exit_code == 0
                        assert mock_sleep.called
                        assert mock_deposit.call_count == 2

    def test_deposit_all_with_error_continue(self, runner, mock_client_manager):
        """Test deposit-all command with error and continue-on-error."""
        with patch("artifactsmmo_cli.commands.bank.get_character_inventory") as mock_get_inv:
            mock_get_inv.return_value = [
                {"code": "iron_ore", "quantity": 10, "slot": 1},
                {"code": "copper_ore", "quantity": 5, "slot": 2},
            ]

            with patch("artifactsmmo_cli.commands.bank.get_item_info") as mock_get_info:

                def mock_item_info(code):
                    items = {
                        "iron_ore": {
                            "code": "iron_ore",
                            "name": "Iron Ore",
                            "type": "ore",
                            "subtype": "mining",
                            "level": 1,
                            "tradeable": True,
                        },
                        "copper_ore": {
                            "code": "copper_ore",
                            "name": "Copper Ore",
                            "type": "ore",
                            "subtype": "mining",
                            "level": 1,
                            "tradeable": True,
                        },
                    }
                    return items.get(code)

                mock_get_info.side_effect = mock_item_info

                with patch("artifactsmmo_cli.commands.bank.execute_single_deposit") as mock_deposit:
                    # First call fails, second call succeeds
                    mock_deposit.side_effect = [(False, "Item not found", None), (True, None, None)]

                    result = runner.invoke(app, ["deposit-all", "testchar", "--continue-on-error"])

                    assert result.exit_code == 0
                    assert "Failed to process" in result.stdout
                    assert mock_deposit.call_count == 2


class TestWithdrawAllCommand:
    """Test withdraw-all command functionality."""

    def test_withdraw_all_success(self, runner, mock_client_manager):
        """Test successful withdraw-all command."""
        # Mock bank items
        mock_bank_item = Mock()
        mock_bank_item.code = "iron_ore"
        mock_bank_item.quantity = 50

        with patch("artifactsmmo_api_client.api.my_account.get_bank_items_my_bank_items_get.sync") as mock_api:
            mock_response = Mock()
            mock_api.return_value = mock_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=[mock_bank_item])

                with patch("artifactsmmo_cli.commands.bank.get_item_info") as mock_get_info:
                    mock_get_info.return_value = {
                        "code": "iron_ore",
                        "name": "Iron Ore",
                        "type": "ore",
                        "subtype": "mining",
                        "level": 1,
                        "tradeable": True,
                    }

                    with patch("artifactsmmo_cli.commands.bank.execute_single_withdraw") as mock_withdraw:
                        mock_withdraw.return_value = (True, None, None)

                        result = runner.invoke(app, ["withdraw-all", "testchar", "iron_ore"])

                        assert result.exit_code == 0
                        assert "Successfully withdrew 50x Iron Ore" in result.stdout

    def test_withdraw_all_item_not_found(self, runner, mock_client_manager):
        """Test withdraw-all command with item not found in bank."""
        with patch("artifactsmmo_api_client.api.my_account.get_bank_items_my_bank_items_get.sync") as mock_api:
            mock_response = Mock()
            mock_api.return_value = mock_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=[])

                with patch("artifactsmmo_cli.commands.bank.validate_character_name") as mock_validate_char:
                    mock_validate_char.return_value = "testchar"

                    with patch("artifactsmmo_cli.commands.bank.validate_item_code") as mock_validate_item:
                        mock_validate_item.return_value = "iron_ore"

                        result = runner.invoke(app, ["withdraw-all", "testchar", "iron_ore"])

                        assert result.exit_code == 0
                        assert "not found in bank" in result.stdout

    def test_withdraw_all_zero_quantity(self, runner, mock_client_manager):
        """Test withdraw-all command with zero quantity in bank."""
        mock_bank_item = Mock()
        mock_bank_item.code = "iron_ore"
        mock_bank_item.quantity = 0

        with patch("artifactsmmo_api_client.api.my_account.get_bank_items_my_bank_items_get.sync") as mock_api:
            mock_response = Mock()
            mock_api.return_value = mock_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=[mock_bank_item])

                result = runner.invoke(app, ["withdraw-all", "testchar", "iron_ore"])

                assert result.exit_code == 0
                assert "No 'iron_ore' items in bank" in result.stdout

    def test_withdraw_all_with_cooldown(self, runner, mock_client_manager):
        """Test withdraw-all command with cooldown."""
        mock_bank_item = Mock()
        mock_bank_item.code = "iron_ore"
        mock_bank_item.quantity = 25

        with patch("artifactsmmo_api_client.api.my_account.get_bank_items_my_bank_items_get.sync") as mock_api:
            mock_response = Mock()
            mock_api.return_value = mock_response

            with patch("artifactsmmo_cli.commands.bank.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=[mock_bank_item])

                with patch("artifactsmmo_cli.commands.bank.get_item_info") as mock_get_info:
                    mock_get_info.return_value = {
                        "code": "iron_ore",
                        "name": "Iron Ore",
                        "type": "ore",
                        "subtype": "mining",
                        "level": 1,
                        "tradeable": True,
                    }

                    with patch("artifactsmmo_cli.commands.bank.execute_single_withdraw") as mock_withdraw:
                        mock_withdraw.return_value = (False, None, 5)

                        result = runner.invoke(app, ["withdraw-all", "testchar", "iron_ore"])

                        assert result.exit_code == 0
                        assert "cooldown" in result.stdout


class TestSmartExchangeCommand:
    """Test smart exchange command functionality."""

    def test_smart_exchange_success(self, runner, mock_client_manager):
        """Test successful smart exchange command."""
        with patch("artifactsmmo_cli.commands.bank.get_character_inventory") as mock_get_inv:
            mock_get_inv.return_value = [
                {"code": "iron_ore", "quantity": 10, "slot": 1},
                {"code": "wooden_sword", "quantity": 1, "slot": 2},
                {"code": "bread", "quantity": 3, "slot": 3},
            ]

            with patch("artifactsmmo_cli.commands.bank.get_item_info") as mock_get_info:

                def mock_item_info(code):
                    items = {
                        "iron_ore": {
                            "code": "iron_ore",
                            "name": "Iron Ore",
                            "type": "ore",
                            "subtype": "mining",
                            "level": 1,
                            "tradeable": True,
                        },
                        "wooden_sword": {
                            "code": "wooden_sword",
                            "name": "Wooden Sword",
                            "type": "weapon",
                            "subtype": "sword",
                            "level": 1,
                            "tradeable": True,
                        },
                        "bread": {
                            "code": "bread",
                            "name": "Bread",
                            "type": "consumable",
                            "subtype": "food",
                            "level": 1,
                            "tradeable": True,
                        },
                    }
                    return items.get(code)

                mock_get_info.side_effect = mock_item_info

                with patch("artifactsmmo_cli.commands.bank.execute_single_deposit") as mock_deposit:
                    mock_deposit.return_value = (True, None, None)

                    result = runner.invoke(app, ["exchange", "testchar"])

                    assert result.exit_code == 0
                    assert "Smart Exchange Plan" in result.stdout
                    # Should deposit iron_ore (resource) but keep wooden_sword (equipment) and bread (consumable with keep_consumables=True)
                    assert mock_deposit.call_count == 1

    def test_smart_exchange_no_items_to_deposit(self, runner, mock_client_manager):
        """Test smart exchange with no items to deposit."""
        with patch("artifactsmmo_cli.commands.bank.get_character_inventory") as mock_get_inv:
            mock_get_inv.return_value = [
                {"code": "wooden_sword", "quantity": 1, "slot": 1},
            ]

            with patch("artifactsmmo_cli.commands.bank.get_item_info") as mock_get_info:
                mock_get_info.return_value = {
                    "code": "wooden_sword",
                    "name": "Wooden Sword",
                    "type": "weapon",
                    "subtype": "sword",
                    "level": 1,
                    "tradeable": True,
                }

                result = runner.invoke(app, ["exchange", "testchar"])

                assert result.exit_code == 0
                assert "No items to deposit in smart exchange" in result.stdout

    def test_smart_exchange_no_deposit_resources(self, runner, mock_client_manager):
        """Test smart exchange with --no-deposit-resources."""
        with patch("artifactsmmo_cli.commands.bank.get_character_inventory") as mock_get_inv:
            mock_get_inv.return_value = [
                {"code": "iron_ore", "quantity": 10, "slot": 1},
                {"code": "wooden_sword", "quantity": 1, "slot": 2},
            ]

            with patch("artifactsmmo_cli.commands.bank.get_item_info") as mock_get_info:

                def mock_item_info(code):
                    items = {
                        "iron_ore": {
                            "code": "iron_ore",
                            "name": "Iron Ore",
                            "type": "ore",
                            "subtype": "mining",
                            "level": 1,
                            "tradeable": True,
                        },
                        "wooden_sword": {
                            "code": "wooden_sword",
                            "name": "Wooden Sword",
                            "type": "weapon",
                            "subtype": "sword",
                            "level": 1,
                            "tradeable": True,
                        },
                    }
                    return items.get(code)

                mock_get_info.side_effect = mock_item_info

                result = runner.invoke(app, ["exchange", "testchar", "--no-deposit-resources"])

                assert result.exit_code == 0
                assert "No items to deposit in smart exchange" in result.stdout

    def test_smart_exchange_no_keep_consumables(self, runner, mock_client_manager):
        """Test smart exchange with --no-keep-consumables."""
        with patch("artifactsmmo_cli.commands.bank.get_character_inventory") as mock_get_inv:
            mock_get_inv.return_value = [
                {"code": "bread", "quantity": 3, "slot": 1},
            ]

            with patch("artifactsmmo_cli.commands.bank.get_item_info") as mock_get_info:
                mock_get_info.return_value = {
                    "code": "bread",
                    "name": "Bread",
                    "type": "consumable",
                    "subtype": "food",
                    "level": 1,
                    "tradeable": True,
                }

                with patch("artifactsmmo_cli.commands.bank.execute_single_deposit") as mock_deposit:
                    mock_deposit.return_value = (True, None, None)

                    result = runner.invoke(app, ["exchange", "testchar", "--no-keep-consumables"])

                    assert result.exit_code == 0
                    # Should deposit bread since we're not keeping consumables
                    assert mock_deposit.call_count == 1


class TestDisplayOperationSummary:
    """Test operation summary display function."""

    def test_display_summary_success_only(self, runner):
        """Test displaying summary with only successful operations."""
        from artifactsmmo_cli.commands.bank import _display_operation_summary

        successful_ops = [
            ("iron_ore", "Iron Ore", 10),
            ("copper_ore", "Copper Ore", 5),
        ]
        failed_ops = []

        # This should not raise an exception
        _display_operation_summary("Test", successful_ops, failed_ops)

    def test_display_summary_with_failures(self, runner):
        """Test displaying summary with failed operations."""
        from artifactsmmo_cli.commands.bank import _display_operation_summary

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
        from artifactsmmo_cli.commands.bank import _display_operation_summary

        successful_ops = []
        failed_ops = []

        # This should not raise an exception
        _display_operation_summary("Test", successful_ops, failed_ops)
