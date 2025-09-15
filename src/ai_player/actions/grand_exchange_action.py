"""
Grand Exchange Action for ArtifactsMMO AI Player

This module implements the Grand Exchange trading functionality, allowing the AI player
to execute trades, monitor orders, and manage its trading portfolio.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from artifactsmmo_api_client.api.my_characters.action_ge_buy_item_my_name_action_grandexchange_buy_post import (
    asyncio as create_buy_order,
)
from artifactsmmo_api_client.api.my_characters.action_ge_create_sell_order_my_name_action_grandexchange_sell_post import (
    asyncio as create_sell_order,
)
from artifactsmmo_api_client.api.my_characters.action_ge_cancel_sell_order_my_name_action_grandexchange_cancel_post import (
    asyncio as cancel_ge_order,
)
from artifactsmmo_api_client.api.grand_exchange.get_ge_sell_orders_grandexchange_orders_get import (
    asyncio as get_order_status,
)
from artifactsmmo_api_client.client import Client

from ..economic_intelligence import TradeDecision, TradeDecisionType
from ..exceptions import InsufficientFundsError, InvalidOrderError, OrderNotFoundError


@dataclass
class OrderResult:
    """Result of a Grand Exchange order operation"""

    order_id: str
    item_code: str
    quantity: int
    price: int
    type: str  # 'buy' or 'sell'
    status: str
    timestamp: datetime
    filled_quantity: int = 0
    remaining_quantity: int = 0
    total_cost: int = 0
    average_price: float = 0.0


class GrandExchangeAction:
    """Executes and manages Grand Exchange trading operations"""

    def __init__(self, api_client, market_analyzer, trading_strategy, portfolio_manager):
        """Initialize GrandExchangeAction"""
        self.api_client = api_client
        self.market_analyzer = market_analyzer
        self.trading_strategy = trading_strategy
        self.portfolio_manager = portfolio_manager
        self.active_orders: Dict[str, OrderResult] = {}
        self.client = Client(base_url="https://api.artifactsmmo.com")

    async def place_buy_order(self, item_code: str, quantity: int, price: int) -> OrderResult:
        """Place a buy order on the Grand Exchange"""
        self._validate_order_params(item_code, quantity, price)

        try:
            response = await create_buy_order(
                client=self.client,
                json_body={
                    "item_code": item_code,
                    "quantity": quantity,
                    "price": price,
                },
            )

            if not response or not response.data or not response.data.id:
                raise InvalidOrderError("Failed to create buy order - invalid response")

            order_result = OrderResult(
                order_id=response.data.id,
                item_code=item_code,
                quantity=quantity,
                price=price,
                type="buy",
                status="pending",
                timestamp=datetime.now(),
                remaining_quantity=quantity,
                total_cost=quantity * price,
            )

            self.active_orders[response.data.id] = order_result
            return order_result

        except Exception as e:
            if "insufficient funds" in str(e).lower():
                raise InsufficientFundsError(f"Insufficient funds to place buy order: {e}")
            raise InvalidOrderError(f"Failed to place buy order: {e}")

    async def place_sell_order(self, item_code: str, quantity: int, price: int) -> OrderResult:
        """Place a sell order on the Grand Exchange"""
        self._validate_order_params(item_code, quantity, price)

        try:
            response = await create_sell_order(
                client=self.client,
                json_body={
                    "item_code": item_code,
                    "quantity": quantity,
                    "price": price,
                },
            )

            if not response or not response.data or not response.data.id:
                raise InvalidOrderError("Failed to create sell order - invalid response")

            order_result = OrderResult(
                order_id=response.data.id,
                item_code=item_code,
                quantity=quantity,
                price=price,
                type="sell",
                status="pending",
                timestamp=datetime.now(),
                remaining_quantity=quantity,
                total_cost=quantity * price,
            )

            self.active_orders[response.data.id] = order_result
            return order_result

        except Exception as e:
            if "insufficient items" in str(e).lower():
                raise InsufficientFundsError(f"Insufficient items to place sell order: {e}")
            raise InvalidOrderError(f"Failed to place sell order: {e}")

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order"""
        if order_id not in self.active_orders:
            raise OrderNotFoundError(f"Order {order_id} not found in active orders")

        try:
            response = await cancel_ge_order(client=self.client, order_id=order_id)
            if response and response.id == order_id:
                if order_id in self.active_orders:
                    self.active_orders[order_id].status = "cancelled"
                return True
            return False
        except Exception as e:
            raise InvalidOrderError(f"Failed to cancel order: {e}")

    async def check_order_status(self, order_id: str) -> OrderResult:
        """Check the status of an order"""
        if order_id not in self.active_orders:
            raise OrderNotFoundError(f"Order {order_id} not found in active orders")

        try:
            response = await get_order_status(client=self.client, order_id=order_id)
            if not response:
                raise InvalidOrderError(f"Failed to get status for order {order_id}")

            order = self.active_orders[order_id]
            # Map API fields to our internal representation
            order.status = "completed" if response.quantity == 0 else "pending"
            order.filled_quantity = response.quantity
            order.remaining_quantity = response.quantity
            order.average_price = response.price

            if order.status == "completed":
                self._update_portfolio(order)
                del self.active_orders[order_id]

            return order

        except Exception as e:
            raise InvalidOrderError(f"Failed to check order status: {e}")

    async def execute_trade_decision(self, decision: TradeDecision) -> Optional[OrderResult]:
        """Execute a trade based on a TradeDecision"""
        if not decision.target_quantity or not decision.target_price:
            raise InvalidOrderError("Trade decision must specify quantity and price")

        try:
            if decision.decision_type == TradeDecisionType.BUY:
                return await self.place_buy_order(
                    decision.item_code,
                    decision.target_quantity,
                    decision.target_price,
                )
            elif decision.decision_type == TradeDecisionType.SELL:
                return await self.place_sell_order(
                    decision.item_code,
                    decision.target_quantity,
                    decision.target_price,
                )
            return None

        except (InsufficientFundsError, InvalidOrderError) as e:
            # Log error but don't raise - trade decisions can fail
            print(f"Failed to execute trade decision: {e}")
            return None

    async def monitor_active_orders(self) -> Dict[str, OrderResult]:
        """Monitor and update status of active orders"""
        updated_orders = {}

        for order_id in list(self.active_orders.keys()):
            try:
                order = await self.check_order_status(order_id)
                updated_orders[order_id] = order
            except (OrderNotFoundError, InvalidOrderError) as e:
                print(f"Error monitoring order {order_id}: {e}")
                # Remove failed orders from tracking
                if order_id in self.active_orders:
                    del self.active_orders[order_id]

        return updated_orders

    def _validate_order_params(self, item_code: str, quantity: int, price: int) -> None:
        """Validate order parameters"""
        if not item_code:
            raise InvalidOrderError("Item code is required")
        if quantity <= 0:
            raise InvalidOrderError("Quantity must be positive")
        if price <= 0:
            raise InvalidOrderError("Price must be positive")

    def _update_portfolio(self, order: OrderResult) -> None:
        """Update portfolio after trade execution"""
        if order.status != "completed":
            return

        if order.type == "buy":
            self.portfolio_manager.record_purchase(
                item_code=order.item_code,
                quantity=order.filled_quantity,
                price_per_item=order.average_price,
                timestamp=order.timestamp,
            )
        else:
            self.portfolio_manager.record_sale(
                item_code=order.item_code,
                quantity=order.filled_quantity,
                price_per_item=order.average_price,
                timestamp=order.timestamp,
            )
