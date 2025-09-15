"""Tests for GrandExchangeAction"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from artifactsmmo_api_client.models import (
    GEOrderReponseSchema as GrandExchangeOrderResponse,
    GEOrderSchema as GrandExchangeOrderStatusResponse,
    GECancelOrderSchema as OrderCancelResponse,
)

from ai_player.actions.grand_exchange_action import GrandExchangeAction, OrderResult
from ai_player.economic_intelligence import TradeDecision, TradeDecisionType
from ai_player.exceptions import InsufficientFundsError, InvalidOrderError, OrderNotFoundError


@pytest.fixture
def mock_api_client():
    return MagicMock()


@pytest.fixture
def mock_market_analyzer():
    return MagicMock()


@pytest.fixture
def mock_trading_strategy():
    return MagicMock()


@pytest.fixture
def mock_portfolio_manager():
    return MagicMock()


@pytest.fixture
def grand_exchange_action(mock_api_client, mock_market_analyzer, mock_trading_strategy, mock_portfolio_manager):
    return GrandExchangeAction(
        api_client=mock_api_client,
        market_analyzer=mock_market_analyzer,
        trading_strategy=mock_trading_strategy,
        portfolio_manager=mock_portfolio_manager,
    )


@pytest.mark.asyncio
async def test_place_buy_order_success(grand_exchange_action):
    """Test successful buy order placement"""
    with patch(
        "ai_player.actions.grand_exchange_action.create_buy_order",
        new_callable=AsyncMock,
    ) as mock_create_buy:
        mock_create_buy.return_value = GrandExchangeOrderResponse(
            data=GrandExchangeOrderStatusResponse(
                id="test_order_1",
                seller="test_seller",
                code="test_item",
                quantity=10,
                price=100,
                created_at=datetime.now(),
            )
        )

        result = await grand_exchange_action.place_buy_order("test_item", 10, 100)

        assert isinstance(result, OrderResult)
        assert result.order_id == "test_order_1"
        assert result.item_code == "test_item"
        assert result.quantity == 10
        assert result.price == 100
        assert result.type == "buy"
        assert result.status == "pending"
        assert result.remaining_quantity == 10
        assert result.total_cost == 1000


@pytest.mark.asyncio
async def test_place_buy_order_insufficient_funds(grand_exchange_action):
    """Test buy order with insufficient funds"""
    with patch(
        "ai_player.actions.grand_exchange_action.create_buy_order",
        new_callable=AsyncMock,
    ) as mock_create_buy:
        mock_create_buy.side_effect = Exception("insufficient funds")

        with pytest.raises(InsufficientFundsError):
            await grand_exchange_action.place_buy_order("test_item", 10, 100)


@pytest.mark.asyncio
async def test_place_sell_order_success(grand_exchange_action):
    """Test successful sell order placement"""
    with patch(
        "ai_player.actions.grand_exchange_action.create_sell_order",
        new_callable=AsyncMock,
    ) as mock_create_sell:
        mock_create_sell.return_value = GrandExchangeOrderResponse(
            data=GrandExchangeOrderStatusResponse(
                id="test_order_2",
                seller="test_seller",
                code="test_item",
                quantity=5,
                price=200,
                created_at=datetime.now(),
            )
        )

        result = await grand_exchange_action.place_sell_order("test_item", 5, 200)

        assert isinstance(result, OrderResult)
        assert result.order_id == "test_order_2"
        assert result.item_code == "test_item"
        assert result.quantity == 5
        assert result.price == 200
        assert result.type == "sell"
        assert result.status == "pending"
        assert result.remaining_quantity == 5
        assert result.total_cost == 1000


@pytest.mark.asyncio
async def test_cancel_order_success(grand_exchange_action):
    """Test successful order cancellation"""
    # Add an order to active_orders
    grand_exchange_action.active_orders["test_order"] = OrderResult(
        order_id="test_order",
        item_code="test_item",
        quantity=1,
        price=100,
        type="buy",
        status="pending",
        timestamp=datetime.now(),
    )

    with patch(
        "ai_player.actions.grand_exchange_action.cancel_ge_order",
        new_callable=AsyncMock,
    ) as mock_cancel:
        mock_cancel.return_value = OrderCancelResponse(id="test_order")

        result = await grand_exchange_action.cancel_order("test_order")
        assert result is True
        assert grand_exchange_action.active_orders["test_order"].status == "cancelled"


@pytest.mark.asyncio
async def test_check_order_status_completed(grand_exchange_action):
    """Test checking status of completed order"""
    # Add an order to active_orders
    test_order = OrderResult(
        order_id="test_order",
        item_code="test_item",
        quantity=10,
        price=100,
        type="buy",
        status="pending",
        timestamp=datetime.now(),
    )
    grand_exchange_action.active_orders["test_order"] = test_order

    with patch(
        "ai_player.actions.grand_exchange_action.get_order_status",
        new_callable=AsyncMock,
    ) as mock_status:
        mock_status.return_value = GrandExchangeOrderStatusResponse(
            id="test_order",
            seller="test_seller",
            code="test_item",
            quantity=0,  # Completed order has 0 remaining quantity
            price=98,
            created_at=datetime.now(),
        )

        result = await grand_exchange_action.check_order_status("test_order")
        assert result.status == "completed"
        assert result.filled_quantity == 0
        assert result.remaining_quantity == 0
        assert result.average_price == 98
        assert "test_order" not in grand_exchange_action.active_orders


@pytest.mark.asyncio
async def test_execute_trade_decision_buy(grand_exchange_action):
    """Test executing buy trade decision"""
    decision = TradeDecision(
        item_code="test_item",
        decision_type=TradeDecisionType.BUY,
        target_price=100,
        target_quantity=5,
        confidence=0.8,
        reasoning="Test trade",
        expected_profit=50,
        risk_level=0.2,
    )

    with patch.object(grand_exchange_action, "place_buy_order", new_callable=AsyncMock) as mock_buy:
        mock_buy.return_value = OrderResult(
            order_id="test_order",
            item_code="test_item",
            quantity=5,
            price=100,
            type="buy",
            status="pending",
            timestamp=datetime.now(),
        )

        result = await grand_exchange_action.execute_trade_decision(decision)
        assert result is not None
        assert result.item_code == "test_item"
        assert result.quantity == 5
        assert result.price == 100


@pytest.mark.asyncio
async def test_monitor_active_orders(grand_exchange_action):
    """Test monitoring multiple active orders"""
    # Add some test orders
    orders = {
        "order1": OrderResult(
            order_id="order1",
            item_code="item1",
            quantity=10,
            price=100,
            type="buy",
            status="pending",
            timestamp=datetime.now(),
        ),
        "order2": OrderResult(
            order_id="order2",
            item_code="item2",
            quantity=5,
            price=200,
            type="sell",
            status="pending",
            timestamp=datetime.now(),
        ),
    }
    grand_exchange_action.active_orders = orders

    with patch.object(grand_exchange_action, "check_order_status", new_callable=AsyncMock) as mock_check:
        mock_check.side_effect = [
            OrderResult(
                order_id="order1",
                item_code="item1",
                quantity=10,
                price=100,
                type="buy",
                status="completed",
                timestamp=datetime.now(),
                filled_quantity=10,
                remaining_quantity=0,
            ),
            OrderResult(
                order_id="order2",
                item_code="item2",
                quantity=5,
                price=200,
                type="sell",
                status="pending",
                timestamp=datetime.now(),
                filled_quantity=2,
                remaining_quantity=3,
            ),
        ]

        updated_orders = await grand_exchange_action.monitor_active_orders()
        assert len(updated_orders) == 2
        assert updated_orders["order1"].status == "completed"
        assert updated_orders["order2"].status == "pending"


def test_validate_order_params(grand_exchange_action):
    """Test order parameter validation"""
    # Valid parameters
    grand_exchange_action._validate_order_params("test_item", 10, 100)

    # Invalid parameters
    with pytest.raises(InvalidOrderError):
        grand_exchange_action._validate_order_params("", 10, 100)

    with pytest.raises(InvalidOrderError):
        grand_exchange_action._validate_order_params("test_item", 0, 100)

    with pytest.raises(InvalidOrderError):
        grand_exchange_action._validate_order_params("test_item", 10, 0)


def test_update_portfolio_buy(grand_exchange_action):
    """Test portfolio update after buy order completion"""
    order = OrderResult(
        order_id="test_order",
        item_code="test_item",
        quantity=10,
        price=100,
        type="buy",
        status="completed",
        timestamp=datetime.now(),
        filled_quantity=10,
        remaining_quantity=0,
        average_price=98.5,
    )

    grand_exchange_action._update_portfolio(order)
    grand_exchange_action.portfolio_manager.record_purchase.assert_called_once_with(
        item_code="test_item",
        quantity=10,
        price_per_item=98.5,
        timestamp=order.timestamp,
    )


def test_update_portfolio_sell(grand_exchange_action):
    """Test portfolio update after sell order completion"""
    order = OrderResult(
        order_id="test_order",
        item_code="test_item",
        quantity=5,
        price=200,
        type="sell",
        status="completed",
        timestamp=datetime.now(),
        filled_quantity=5,
        remaining_quantity=0,
        average_price=195.0,
    )

    grand_exchange_action._update_portfolio(order)
    grand_exchange_action.portfolio_manager.record_sale.assert_called_once_with(
        item_code="test_item",
        quantity=5,
        price_per_item=195.0,
        timestamp=order.timestamp,
    )
