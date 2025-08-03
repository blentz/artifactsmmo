"""
Economic Data Collection

This module contains the MarketDataCollector class for collecting and managing
market data from the Grand Exchange API.
"""

from datetime import datetime, timedelta

from artifactsmmo_api_client.api.grand_exchange.get_ge_sell_history_grandexchange_history_code_get import (
        asyncio as get_ge_history,
        )
from artifactsmmo_api_client.api.grand_exchange.get_ge_sell_orders_grandexchange_orders_get import (
        asyncio as get_ge_orders,
        )
from artifactsmmo_api_client.client import Client

from .economic_models import PriceData


class MarketDataCollector:
    """Collects and manages market data from Grand Exchange"""

    def __init__(self, api_client):
        self.api_client = api_client
        self.price_history = {}
        self.last_update = {}

    async def fetch_current_prices(self, item_codes: list[str]) -> dict[str, PriceData]:
        """Fetch current Grand Exchange prices for items"""
        prices = {}
        client = Client(base_url="https://api.artifactsmmo.com")

        for item_code in item_codes:
            orders_response = await get_ge_orders(client=client, code=item_code, page=1, size=50)

            if orders_response and orders_response.data:
                orders = orders_response.data
                if orders:
                    best_sell_order = min(orders, key=lambda x: x.price)

                    prices[item_code] = PriceData(
                            item_code=item_code,
                            timestamp=datetime.now(),
                            buy_price=best_sell_order.price,
                            sell_price=best_sell_order.price,
                            quantity_available=sum(order.quantity for order in orders)
                            )

                    self.last_update[item_code] = datetime.now()


        return prices

    async def fetch_market_history(self, item_code: str, days: int = 7) -> list[PriceData]:
        """Fetch historical price data for item"""
        history_data = []
        client = Client(base_url="https://api.artifactsmmo.com")

        history_response = await get_ge_history(client=client, code=item_code, page=1, size=100)

        if history_response and history_response.data:
            cutoff_date = datetime.now() - timedelta(days=days)

            for sale in history_response.data:
                if sale.sold_at >= cutoff_date:
                    history_data.append(PriceData(
                        item_code=item_code,
                        timestamp=sale.sold_at,
                        buy_price=sale.price,
                        sell_price=sale.price,
                        quantity_available=sale.quantity
                        ))

        return sorted(history_data, key=lambda x: x.timestamp)

    def store_price_data(self, price_data: PriceData) -> None:
        """Store price data in local cache"""
        if price_data.item_code not in self.price_history:
            self.price_history[price_data.item_code] = []

        self.price_history[price_data.item_code].append(price_data)

        self.price_history[price_data.item_code].sort(key=lambda x: x.timestamp)

        max_history_size = 1000
        if len(self.price_history[price_data.item_code]) > max_history_size:
            self.price_history[price_data.item_code] = self.price_history[price_data.item_code][-max_history_size:]

    def get_price_history(self, item_code: str, hours: int = 24) -> list[PriceData]:
        """Get price history from local cache"""
        if item_code not in self.price_history:
            return []

        cutoff_time = datetime.now() - timedelta(hours=hours)

        return [
                price_data for price_data in self.price_history[item_code]
                if price_data.timestamp >= cutoff_time
                ]

    def cleanup_old_data(self, max_age_days: int = 30) -> None:
        """Remove old price data to manage memory"""
        cutoff_time = datetime.now() - timedelta(days=max_age_days)

        for item_code in list(self.price_history.keys()):
            self.price_history[item_code] = [
                    price_data for price_data in self.price_history[item_code]
                    if price_data.timestamp >= cutoff_time
                    ]

            if not self.price_history[item_code]:
                del self.price_history[item_code]

    async def update_all_tracked_items(self) -> None:
        """Update prices for all items being tracked"""
        tracked_items = list(self.price_history.keys())
        if tracked_items:
            current_prices = await self.fetch_current_prices(tracked_items)
            for item_code, price_data in current_prices.items():
                self.store_price_data(price_data)

    def add_item_to_tracking(self, item_code: str) -> None:
        """Add item to regular price tracking"""
        if item_code not in self.price_history:
            self.price_history[item_code] = []

    def remove_item_from_tracking(self, item_code: str) -> None:
        """Remove item from tracking"""
        if item_code in self.price_history:
            del self.price_history[item_code]
        if item_code in self.last_update:
            del self.last_update[item_code]
