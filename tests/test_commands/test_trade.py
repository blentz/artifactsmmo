"""Tests for trade commands."""

from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from artifactsmmo_cli.commands.trade import app


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_client_manager():
    """Mock the ClientManager."""
    with patch("artifactsmmo_cli.commands.trade.ClientManager") as mock:
        mock_instance = Mock()
        mock.return_value = mock_instance
        mock_instance.client = Mock()
        yield mock_instance


@pytest.fixture
def mock_api_response():
    """Mock API response."""
    mock_response = Mock()
    mock_response.status_code = 200
    return mock_response


class TestTradeCommands:
    """Test trade command functionality."""

    def test_ge_buy_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful GE buy command."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_ge_buy_item_my_name_action_grandexchange_buy_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.trade.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, message="Purchase completed")

                result = runner.invoke(app, ["ge-buy", "testchar", "order123", "5"])

                assert result.exit_code == 0
                assert "Purchase completed" in result.stdout
                mock_api.assert_called_once()

    def test_ge_buy_validation_error(self, runner):
        """Test GE buy with invalid input."""
        result = runner.invoke(app, ["ge-buy", "", "order123", "5"])
        assert result.exit_code == 1

    def test_ge_sell_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful GE sell command."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_ge_create_sell_order_my_name_action_grandexchange_sell_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.trade.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, message="Sell order created")

                result = runner.invoke(app, ["ge-sell", "testchar", "iron_ore", "10", "100"])

                assert result.exit_code == 0
                assert "Sell order created" in result.stdout
                mock_api.assert_called_once()

    def test_ge_sell_invalid_price(self, runner):
        """Test GE sell with invalid price."""
        result = runner.invoke(app, ["ge-sell", "testchar", "iron_ore", "10", "0"])
        assert result.exit_code == 1

    def test_ge_orders_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful GE orders list command."""
        with patch(
            "artifactsmmo_api_client.api.my_account.get_ge_sell_orders_my_grandexchange_orders_get.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            mock_order = Mock()
            mock_order.id = "order123"
            mock_order.code = "iron_ore"
            mock_order.quantity = 10
            mock_order.price = 100
            mock_order.status = "active"

            mock_data = Mock()
            mock_data.data = [mock_order]

            with patch("artifactsmmo_cli.commands.trade.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["ge-orders"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_ge_orders_empty(self, runner, mock_client_manager, mock_api_response):
        """Test GE orders list with no orders."""
        with patch(
            "artifactsmmo_api_client.api.my_account.get_ge_sell_orders_my_grandexchange_orders_get.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.trade.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=Mock(data=[]))

                result = runner.invoke(app, ["ge-orders"])

                assert result.exit_code == 0
                assert "No orders found" in result.stdout

    def test_ge_cancel_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful GE cancel command."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_ge_cancel_sell_order_my_name_action_grandexchange_cancel_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.trade.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, message="Order cancelled")

                result = runner.invoke(app, ["ge-cancel", "testchar", "order123"])

                assert result.exit_code == 0
                assert "Order cancelled" in result.stdout
                mock_api.assert_called_once()

    def test_cooldown_handling(self, runner, mock_client_manager, mock_api_response):
        """Test cooldown handling in trade commands."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_ge_buy_item_my_name_action_grandexchange_buy_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.trade.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=30, error=None)

                result = runner.invoke(app, ["ge-buy", "testchar", "order123", "5"])

                assert result.exit_code == 0
                assert "cooldown" in result.stdout.lower()

    def test_api_error_handling(self, runner, mock_client_manager):
        """Test API error handling in trade commands."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_ge_buy_item_my_name_action_grandexchange_buy_post.sync"
        ) as mock_api:
            mock_api.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.trade.handle_api_error") as mock_handle:
                mock_handle.return_value = Mock(cooldown_remaining=None, error="API Error")

                result = runner.invoke(app, ["ge-buy", "testchar", "order123", "5"])

                assert result.exit_code == 1
                assert "API Error" in result.stdout

    def test_api_error_with_cooldown(self, runner, mock_client_manager):
        """Test API error handling with cooldown in trade commands."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_ge_buy_item_my_name_action_grandexchange_buy_post.sync"
        ) as mock_api:
            mock_api.side_effect = Exception("API Error")

            with patch("artifactsmmo_cli.commands.trade.handle_api_error") as mock_handle:
                mock_handle.return_value = Mock(cooldown_remaining=25, error=None)

                result = runner.invoke(app, ["ge-buy", "testchar", "order123", "5"])

                assert result.exit_code == 1

    def test_ge_sell_error_response(self, runner, mock_client_manager, mock_api_response):
        """Test GE sell command with error response."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_ge_create_sell_order_my_name_action_grandexchange_sell_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.trade.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=None, error="Sell failed")

                result = runner.invoke(app, ["ge-sell", "testchar", "iron_ore", "10", "100"])

                assert result.exit_code == 1
                assert "Sell failed" in result.stdout

    def test_ge_buy_error_response(self, runner, mock_client_manager, mock_api_response):
        """Test GE buy command with error response."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_ge_buy_item_my_name_action_grandexchange_buy_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.trade.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=None, error="Buy failed")

                result = runner.invoke(app, ["ge-buy", "testchar", "order123", "5"])

                assert result.exit_code == 1
                assert "Buy failed" in result.stdout

    def test_ge_cancel_error_response(self, runner, mock_client_manager, mock_api_response):
        """Test GE cancel command with error response."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_ge_cancel_sell_order_my_name_action_grandexchange_cancel_post.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.trade.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=False, cooldown_remaining=None, error="Cancel failed")

                result = runner.invoke(app, ["ge-cancel", "testchar", "order123"])

        assert result.exit_code == 1
        assert "Cancel failed" in result.stdout

    def test_prices_command_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful prices command."""
        with patch(
            "artifactsmmo_api_client.api.grand_exchange.get_ge_sell_orders_grandexchange_orders_get.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            mock_order = Mock()
            mock_order.price = 100
            mock_order.quantity = 10
            mock_order.seller = "testuser"
            mock_order.created_at = "2023-01-01T12:00:00Z"

            mock_data = Mock()
            mock_data.data = [mock_order]

            with patch("artifactsmmo_cli.commands.trade.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["prices", "iron_ore"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_prices_command_no_orders(self, runner, mock_client_manager, mock_api_response):
        """Test prices command with no orders."""
        with patch(
            "artifactsmmo_api_client.api.grand_exchange.get_ge_sell_orders_grandexchange_orders_get.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            mock_data = Mock()
            mock_data.data = []

            with patch("artifactsmmo_cli.commands.trade.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["prices", "iron_ore"])

                assert result.exit_code == 0
                assert "No active orders found" in result.stdout

    def test_orders_command_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful orders command."""
        with patch(
            "artifactsmmo_api_client.api.grand_exchange.get_ge_sell_orders_grandexchange_orders_get.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            mock_order = Mock()
            mock_order.code = "iron_ore"
            mock_order.quantity = 10
            mock_order.price = 100
            mock_order.seller = "testuser"
            mock_order.created_at = "2023-01-01T12:00:00Z"

            mock_data = Mock()
            mock_data.data = [mock_order]
            mock_data.total = 1
            mock_data.pages = 1

            with patch("artifactsmmo_cli.commands.trade.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["orders", "--item", "iron_ore"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_orders_command_with_filters(self, runner, mock_client_manager, mock_api_response):
        """Test orders command with filters."""
        with patch(
            "artifactsmmo_api_client.api.grand_exchange.get_ge_sell_orders_grandexchange_orders_get.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            mock_data = Mock()
            mock_data.data = []
            mock_data.total = 0
            mock_data.pages = 0

            with patch("artifactsmmo_cli.commands.trade.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["orders", "--item", "iron_ore", "--seller", "testuser"])

                assert result.exit_code == 0
                mock_api.assert_called_once_with(
                    client=mock_client_manager.client, code="iron_ore", seller="testuser", page=1, size=20
                )

    def test_history_command_personal(self, runner, mock_client_manager, mock_api_response):
        """Test personal history command."""
        with patch(
            "artifactsmmo_api_client.api.my_account.get_ge_sell_history_my_grandexchange_history_get.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            mock_sale = Mock()
            mock_sale.code = "iron_ore"
            mock_sale.quantity = 5
            mock_sale.price = 100
            mock_sale.seller = "testuser"
            mock_sale.buyer = "buyer"
            mock_sale.sold_at = "2023-01-01T12:00:00Z"

            mock_data = Mock()
            mock_data.data = [mock_sale]
            mock_data.total = 1
            mock_data.pages = 1

            with patch("artifactsmmo_cli.commands.trade.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["history", "testchar"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_history_command_public(self, runner, mock_client_manager, mock_api_response):
        """Test public history command."""
        with patch(
            "artifactsmmo_api_client.api.grand_exchange.get_ge_sell_history_grandexchange_history_code_get.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            mock_data = Mock()
            mock_data.data = []
            mock_data.total = 0
            mock_data.pages = 0

            with patch("artifactsmmo_cli.commands.trade.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["history", "--item", "iron_ore"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_history_command_no_item_error(self, runner, mock_client_manager):
        """Test history command without item for public history."""
        result = runner.invoke(app, ["history"])
        assert result.exit_code == 1
        assert "Item code is required" in result.stdout

    def test_analyze_command_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful analyze command."""
        with (
            patch(
                "artifactsmmo_api_client.api.grand_exchange.get_ge_sell_orders_grandexchange_orders_get.sync"
            ) as mock_orders_api,
            patch(
                "artifactsmmo_api_client.api.grand_exchange.get_ge_sell_history_grandexchange_history_code_get.sync"
            ) as mock_history_api,
        ):
            mock_orders_api.return_value = mock_api_response
            mock_history_api.return_value = mock_api_response

            mock_order = Mock()
            mock_order.price = 100
            mock_order.quantity = 10
            mock_order.seller = "testuser"
            mock_order.created_at = "2023-01-01T12:00:00Z"

            mock_sale = Mock()
            mock_sale.price = 95
            mock_sale.quantity = 5

            mock_orders_data = Mock()
            mock_orders_data.data = [mock_order]

            mock_history_data = Mock()
            mock_history_data.data = [mock_sale]

            with patch("artifactsmmo_cli.commands.trade.handle_api_response") as mock_handle:
                mock_handle.side_effect = [
                    Mock(success=True, data=mock_orders_data),
                    Mock(success=True, data=mock_history_data),
                ]

                result = runner.invoke(app, ["analyze", "iron_ore"])

                assert result.exit_code == 0
                assert mock_orders_api.called
                assert mock_history_api.called

    def test_analyze_command_no_data(self, runner, mock_client_manager, mock_api_response):
        """Test analyze command with no market data."""
        with (
            patch(
                "artifactsmmo_api_client.api.grand_exchange.get_ge_sell_orders_grandexchange_orders_get.sync"
            ) as mock_orders_api,
            patch(
                "artifactsmmo_api_client.api.grand_exchange.get_ge_sell_history_grandexchange_history_code_get.sync"
            ) as mock_history_api,
        ):
            mock_orders_api.return_value = mock_api_response
            mock_history_api.return_value = mock_api_response

            with patch("artifactsmmo_cli.commands.trade.handle_api_response") as mock_handle:
                mock_handle.side_effect = [Mock(success=False, data=None), Mock(success=False, data=None)]

                result = runner.invoke(app, ["analyze", "iron_ore"])

                assert result.exit_code == 0
                assert "No market data found" in result.stdout

    def test_trending_command_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful trending command."""
        with patch(
            "artifactsmmo_api_client.api.grand_exchange.get_ge_sell_orders_grandexchange_orders_get.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            mock_order1 = Mock()
            mock_order1.code = "iron_ore"
            mock_order1.quantity = 10
            mock_order1.price = 100

            mock_order2 = Mock()
            mock_order2.code = "iron_ore"
            mock_order2.quantity = 5
            mock_order2.price = 95

            mock_data = Mock()
            mock_data.data = [mock_order1, mock_order2]

            with patch("artifactsmmo_cli.commands.trade.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["trending", "--limit", "5"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_opportunities_command_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful opportunities command."""
        with patch(
            "artifactsmmo_api_client.api.grand_exchange.get_ge_sell_orders_grandexchange_orders_get.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            mock_order1 = Mock()
            mock_order1.code = "iron_ore"
            mock_order1.price = 50

            mock_order2 = Mock()
            mock_order2.code = "iron_ore"
            mock_order2.price = 100

            mock_data = Mock()
            mock_data.data = [mock_order1, mock_order2]

            with patch("artifactsmmo_cli.commands.trade.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["opportunities", "--min-margin", "0.5"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_opportunities_command_no_opportunities(self, runner, mock_client_manager, mock_api_response):
        """Test opportunities command with no opportunities found."""
        with patch(
            "artifactsmmo_api_client.api.grand_exchange.get_ge_sell_orders_grandexchange_orders_get.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            mock_order = Mock()
            mock_order.code = "iron_ore"
            mock_order.price = 100

            mock_data = Mock()
            mock_data.data = [mock_order]

            with patch("artifactsmmo_cli.commands.trade.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["opportunities", "--min-margin", "0.5"])

                assert result.exit_code == 0
                assert "No opportunities found" in result.stdout

    def test_spread_command_success(self, runner, mock_client_manager, mock_api_response):
        """Test successful spread command."""
        with patch(
            "artifactsmmo_api_client.api.grand_exchange.get_ge_sell_orders_grandexchange_orders_get.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            mock_order1 = Mock()
            mock_order1.code = "iron_ore"
            mock_order1.price = 50

            mock_order2 = Mock()
            mock_order2.code = "iron_ore"
            mock_order2.price = 100

            mock_data = Mock()
            mock_data.data = [mock_order1, mock_order2]

            with patch("artifactsmmo_cli.commands.trade.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["spread", "--limit", "5"])

                assert result.exit_code == 0
                mock_api.assert_called_once()

    def test_spread_command_no_spreads(self, runner, mock_client_manager, mock_api_response):
        """Test spread command with no spreads found."""
        with patch(
            "artifactsmmo_api_client.api.grand_exchange.get_ge_sell_orders_grandexchange_orders_get.sync"
        ) as mock_api:
            mock_api.return_value = mock_api_response

            mock_order = Mock()
            mock_order.code = "iron_ore"
            mock_order.price = 100

            mock_data = Mock()
            mock_data.data = [mock_order]

            with patch("artifactsmmo_cli.commands.trade.handle_api_response") as mock_handle:
                mock_handle.return_value = Mock(success=True, data=mock_data)

                result = runner.invoke(app, ["spread"])

                assert result.exit_code == 0
                assert "No items with multiple price points found" in result.stdout

    def test_market_analysis_helper_functions(self):
        """Test market analysis helper functions."""
        from artifactsmmo_cli.commands.trade import (
            calculate_price_stats,
            calculate_volume_stats,
            find_arbitrage_opportunities,
        )

        # Test price stats calculation
        mock_orders = []
        for price in [50, 75, 100]:
            order = Mock()
            order.price = price
            order.quantity = 10
            order.code = "iron_ore"
            mock_orders.append(order)

        price_stats = calculate_price_stats(mock_orders)
        assert price_stats["min"] == 50
        assert price_stats["max"] == 100
        assert price_stats["avg"] == 75

        # Test volume stats calculation
        volume_stats = calculate_volume_stats(mock_orders)
        assert volume_stats["total_quantity"] == 30
        assert volume_stats["total_orders"] == 3
        assert volume_stats["avg_quantity"] == 10

        # Test arbitrage opportunities
        opportunities = find_arbitrage_opportunities(mock_orders, 0.5)
        assert len(opportunities) == 1
        assert opportunities[0]["item"] == "iron_ore"
        assert opportunities[0]["profit_margin"] == 1.0

    def test_market_analysis_empty_data(self):
        """Test market analysis functions with empty data."""
        from artifactsmmo_cli.commands.trade import (
            calculate_price_stats,
            calculate_volume_stats,
            find_arbitrage_opportunities,
        )

        # Test with empty orders
        price_stats = calculate_price_stats([])
        assert price_stats["min"] == 0
        assert price_stats["max"] == 0
        assert price_stats["avg"] == 0

        volume_stats = calculate_volume_stats([])
        assert volume_stats["total_quantity"] == 0
        assert volume_stats["total_orders"] == 0
        assert volume_stats["avg_quantity"] == 0

        opportunities = find_arbitrage_opportunities([], 0.1)
        assert len(opportunities) == 0

    def test_invalid_item_code_validation(self, runner, mock_client_manager):
        """Test validation of invalid item codes in new commands."""
        result = runner.invoke(app, ["prices", ""])
        assert result.exit_code == 1

        result = runner.invoke(app, ["analyze", ""])
        assert result.exit_code == 1
