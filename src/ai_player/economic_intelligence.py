"""
Economic Intelligence System for ArtifactsMMO AI Player

This module provides market analysis, trading strategies, and economic decision-making
for the AI player. It integrates with the Grand Exchange and NPC trading systems
to optimize gold accumulation and resource acquisition.

The economic intelligence system works with the GOAP planner to generate economically
optimal goals and trading strategies that maximize character progression efficiency.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from artifactsmmo_api_client.api.grand_exchange.get_ge_sell_history_grandexchange_history_code_get import (
    asyncio as get_ge_history,
)
from artifactsmmo_api_client.api.grand_exchange.get_ge_sell_orders_grandexchange_orders_get import (
    asyncio as get_ge_orders,
)
from artifactsmmo_api_client.client import Client


class MarketTrend(Enum):
    """Market trend indicators"""
    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    VOLATILE = "volatile"


class TradeDecisionType(Enum):
    """Types of trade decisions"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    AVOID = "avoid"


@dataclass
class PriceData:
    """Historical price data for an item"""
    item_code: str
    timestamp: datetime
    buy_price: int
    sell_price: int
    quantity_available: int

    @property
    def spread(self) -> int:
        """Price spread (difference between buy and sell)"""
        return self.sell_price - self.buy_price

    @property
    def spread_percentage(self) -> float:
        """Spread as percentage of buy price"""
        return (self.spread / self.buy_price) * 100 if self.buy_price > 0 else 0


@dataclass
class MarketAnalysis:
    """Market analysis for a specific item"""
    item_code: str
    current_price: PriceData
    trend: MarketTrend
    volatility: float
    volume: int
    average_price_7d: float
    average_price_30d: float
    predicted_price_1h: float
    predicted_price_24h: float
    confidence: float

    def is_good_buy_opportunity(self) -> bool:
        """Determine if current price represents good buying opportunity"""
        if self.trend == MarketTrend.FALLING and self.current_price.buy_price < self.average_price_7d * 0.95:
            return True
        if self.predicted_price_1h > self.current_price.buy_price * 1.1 and self.confidence > 0.7:
            return True
        if self.current_price.buy_price < self.average_price_30d * 0.9:
            return True
        return False

    def is_good_sell_opportunity(self) -> bool:
        """Determine if current price represents good selling opportunity"""
        if self.trend == MarketTrend.RISING and self.current_price.sell_price > self.average_price_7d * 1.05:
            return True
        if self.predicted_price_1h < self.current_price.sell_price * 0.9 and self.confidence > 0.7:
            return True
        if self.current_price.sell_price > self.average_price_30d * 1.1:
            return True
        return False


@dataclass
class TradeDecision:
    """Represents a trading decision"""
    item_code: str
    decision_type: TradeDecisionType
    target_price: int
    target_quantity: int
    confidence: float
    reasoning: str
    expected_profit: int
    risk_level: float

    def calculate_roi(self, investment: int) -> float:
        """Calculate expected return on investment"""
        return (self.expected_profit / investment) * 100 if investment > 0 else 0


@dataclass
class EconomicStrategy:
    """Economic strategy configuration"""
    risk_tolerance: float  # 0.0 = very conservative, 1.0 = very aggressive
    profit_margin_threshold: float  # Minimum profit margin to consider trades
    max_investment_percentage: float  # Max % of gold to invest in single trade
    preferred_trade_types: list[str]  # Types of items to focus on
    avoid_items: list[str]  # Items to avoid trading


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
            try:
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

            except Exception:
                continue

        return prices

    async def fetch_market_history(self, item_code: str, days: int = 7) -> list[PriceData]:
        """Fetch historical price data for item"""
        history_data = []
        client = Client(base_url="https://api.artifactsmmo.com")

        try:
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

        except Exception:
            pass

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


class MarketAnalyzer:
    """Analyzes market data to identify trends and opportunities"""

    def __init__(self, data_collector: MarketDataCollector):
        self.data_collector = data_collector

    def analyze_item_market(self, item_code: str) -> MarketAnalysis:
        """Perform comprehensive market analysis for item"""
        price_history = self.data_collector.get_price_history(item_code, hours=168)  # 7 days

        if not price_history:
            raise ValueError(f"No price history available for {item_code}")

        current_price = price_history[-1]
        trend = self.detect_trend(price_history)
        volatility = self.calculate_volatility(price_history)

        volume = sum(p.quantity_available for p in price_history[-24:])  # Last 24 hours

        avg_7d = sum(p.buy_price for p in price_history[-168:]) / len(price_history[-168:]) if price_history[-168:] else current_price.buy_price
        avg_30d = sum(p.buy_price for p in price_history) / len(price_history) if price_history else current_price.buy_price

        pred_1h = self.predict_future_price(price_history, 1)
        pred_24h = self.predict_future_price(price_history, 24)

        confidence = max(0.1, min(0.9, 1.0 - volatility)) if len(price_history) > 10 else 0.3

        return MarketAnalysis(
            item_code=item_code,
            current_price=current_price,
            trend=trend,
            volatility=volatility,
            volume=volume,
            average_price_7d=avg_7d,
            average_price_30d=avg_30d,
            predicted_price_1h=pred_1h,
            predicted_price_24h=pred_24h,
            confidence=confidence
        )

    def detect_trend(self, price_history: list[PriceData]) -> MarketTrend:
        """Detect price trend from historical data"""
        if len(price_history) < 3:
            return MarketTrend.STABLE

        prices = [p.buy_price for p in price_history[-10:]]  # Look at last 10 data points

        if len(prices) < 3:
            return MarketTrend.STABLE

        # Calculate moving averages
        short_ma = sum(prices[-3:]) / 3
        long_ma = sum(prices) / len(prices)

        # Calculate price changes
        recent_change = (prices[-1] - prices[0]) / prices[0] if prices[0] > 0 else 0
        volatility = self.calculate_volatility(price_history[-10:])

        if volatility > 0.3:
            return MarketTrend.VOLATILE
        elif short_ma > long_ma * 1.05 and recent_change > 0.05:
            return MarketTrend.RISING
        elif short_ma < long_ma * 0.95 and recent_change < -0.05:
            return MarketTrend.FALLING
        else:
            return MarketTrend.STABLE

    def calculate_volatility(self, price_history: list[PriceData]) -> float:
        """Calculate price volatility"""
        if len(price_history) < 2:
            return 0.0

        prices = [p.buy_price for p in price_history]
        mean_price = sum(prices) / len(prices)

        variance = sum((price - mean_price) ** 2 for price in prices) / len(prices)
        std_dev = variance ** 0.5

        return std_dev / mean_price if mean_price > 0 else 0.0

    def predict_future_price(self, price_history: list[PriceData], hours_ahead: int) -> float:
        """Predict future price based on historical data"""
        if len(price_history) < 3:
            return price_history[-1].buy_price if price_history else 0.0

        prices = [p.buy_price for p in price_history[-10:]]  # Use last 10 data points

        # Simple linear regression for trend prediction
        n = len(prices)
        x_values = list(range(n))

        # Calculate slope and intercept
        sum_x = sum(x_values)
        sum_y = sum(prices)
        sum_xy = sum(x * y for x, y in zip(x_values, prices))
        sum_x2 = sum(x * x for x in x_values)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x) if (n * sum_x2 - sum_x * sum_x) != 0 else 0
        intercept = (sum_y - slope * sum_x) / n

        # Predict future price
        future_x = n + hours_ahead - 1
        predicted_price = slope * future_x + intercept

        # Apply some constraints to prevent unrealistic predictions
        current_price = prices[-1]
        max_change = current_price * 0.5  # Maximum 50% change

        if predicted_price > current_price + max_change:
            predicted_price = current_price + max_change
        elif predicted_price < current_price - max_change:
            predicted_price = current_price - max_change

        return max(1, predicted_price)  # Ensure price is at least 1

    def identify_arbitrage_opportunities(self, ge_prices: dict[str, PriceData],
                                       npc_prices: dict[str, int]) -> list[TradeDecision]:
        """Identify arbitrage opportunities between GE and NPCs"""
        opportunities = []

        for item_code in ge_prices:
            if item_code in npc_prices:
                ge_price = ge_prices[item_code]
                npc_price = npc_prices[item_code]

                # Check if we can buy from GE and sell to NPC for profit
                if npc_price > ge_price.buy_price * 1.1:  # 10% minimum profit margin
                    profit = npc_price - ge_price.buy_price
                    opportunities.append(TradeDecision(
                        item_code=item_code,
                        decision_type=TradeDecisionType.BUY,
                        target_price=ge_price.buy_price,
                        target_quantity=min(ge_price.quantity_available, 100),
                        confidence=0.9,
                        reasoning=f"Arbitrage: Buy GE {ge_price.buy_price}, sell NPC {npc_price}",
                        expected_profit=profit,
                        risk_level=0.1
                    ))

        return opportunities

    def find_profitable_crafting(self, character_state: dict[str, Any]) -> list[dict[str, Any]]:
        """Find profitable crafting opportunities"""
        opportunities = []

        # Get character's crafting levels to determine available recipes
        char_levels = {
            'weaponcrafting': character_state.get('weaponcrafting_level', 1),
            'gearcrafting': character_state.get('gearcrafting_level', 1),
            'jewelrycrafting': character_state.get('jewelrycrafting_level', 1),
            'cooking': character_state.get('cooking_level', 1),
            'alchemy': character_state.get('alchemy_level', 1)
        }

        # Common profitable crafting patterns based on skill levels
        crafting_opportunities = [
            {
                'skill': 'cooking',
                'min_level': 1,
                'materials': ['raw_beef', 'cooked_beef'],
                'profit_margin': 0.15,
                'craft_item': 'cooked_beef'
            },
            {
                'skill': 'weaponcrafting',
                'min_level': 5,
                'materials': ['copper_ore', 'ash_wood'],
                'profit_margin': 0.25,
                'craft_item': 'copper_sword'
            },
            {
                'skill': 'gearcrafting',
                'min_level': 3,
                'materials': ['wolf_hair', 'cowhide'],
                'profit_margin': 0.20,
                'craft_item': 'leather_armor'
            }
        ]

        for opportunity in crafting_opportunities:
            skill_level = char_levels.get(opportunity['skill'], 0)
            if skill_level >= opportunity['min_level']:
                opportunities.append({
                    'craft_item': opportunity['craft_item'],
                    'materials_needed': opportunity['materials'],
                    'estimated_profit_margin': opportunity['profit_margin'],
                    'required_skill': opportunity['skill'],
                    'required_level': opportunity['min_level']
                })

        return opportunities

    def analyze_seasonal_patterns(self, item_code: str) -> dict[str, float]:
        """Analyze seasonal price patterns"""
        patterns = {}

        # Get price history for analysis
        price_history = self.data_collector.get_price_history(item_code, hours=720)  # 30 days

        if len(price_history) < 10:
            return {
                'weekly_variance': 0.0,
                'daily_variance': 0.0,
                'peak_hour': 12,
                'low_hour': 6,
                'confidence': 0.1
            }

        # Analyze price patterns by hour and day
        hourly_prices = {}
        daily_prices = {}

        for price_data in price_history:
            hour = price_data.timestamp.hour
            day = price_data.timestamp.weekday()

            if hour not in hourly_prices:
                hourly_prices[hour] = []
            if day not in daily_prices:
                daily_prices[day] = []

            hourly_prices[hour].append(price_data.buy_price)
            daily_prices[day].append(price_data.buy_price)

        # Calculate average prices by hour and day
        hourly_averages = {h: sum(prices)/len(prices) for h, prices in hourly_prices.items()}
        daily_averages = {d: sum(prices)/len(prices) for d, prices in daily_prices.items()}

        # Find peak and low periods
        peak_hour = max(hourly_averages.keys(), key=lambda h: hourly_averages[h]) if hourly_averages else 12
        low_hour = min(hourly_averages.keys(), key=lambda h: hourly_averages[h]) if hourly_averages else 6

        # Calculate variance
        all_prices = [p.buy_price for p in price_history]
        mean_price = sum(all_prices) / len(all_prices)

        weekly_variance = 0.0
        daily_variance = 0.0

        if daily_averages:
            daily_variance = sum((avg - mean_price) ** 2 for avg in daily_averages.values()) / len(daily_averages)
            daily_variance = (daily_variance ** 0.5) / mean_price if mean_price > 0 else 0.0

        if hourly_averages:
            weekly_variance = sum((avg - mean_price) ** 2 for avg in hourly_averages.values()) / len(hourly_averages)
            weekly_variance = (weekly_variance ** 0.5) / mean_price if mean_price > 0 else 0.0

        patterns = {
            'weekly_variance': weekly_variance,
            'daily_variance': daily_variance,
            'peak_hour': peak_hour,
            'low_hour': low_hour,
            'confidence': min(0.9, len(price_history) / 100.0)
        }

        return patterns

    def calculate_market_efficiency(self, item_code: str) -> float:
        """Calculate how efficiently the market is pricing an item"""
        price_history = self.data_collector.get_price_history(item_code, hours=168)  # 7 days

        if len(price_history) < 10:
            return 0.5  # Neutral efficiency for insufficient data

        # Calculate price stability (lower volatility = higher efficiency)
        volatility = self.calculate_volatility(price_history)
        stability_score = max(0.0, 1.0 - volatility)

        # Calculate spread efficiency (lower spreads = higher efficiency)
        recent_spreads = [p.spread_percentage for p in price_history[-24:] if p.spread_percentage > 0]
        avg_spread = sum(recent_spreads) / len(recent_spreads) if recent_spreads else 10.0
        spread_efficiency = max(0.0, 1.0 - (avg_spread / 20.0))  # 20% spread = 0 efficiency

        # Calculate volume consistency (consistent volume = higher efficiency)
        volumes = [p.quantity_available for p in price_history if p.quantity_available > 0]
        if len(volumes) > 1:
            avg_volume = sum(volumes) / len(volumes)
            volume_variance = sum((v - avg_volume) ** 2 for v in volumes) / len(volumes)
            volume_std = volume_variance ** 0.5
            volume_consistency = max(0.0, 1.0 - (volume_std / avg_volume)) if avg_volume > 0 else 0.5
        else:
            volume_consistency = 0.5

        # Weighted efficiency score
        efficiency = (
            stability_score * 0.4 +
            spread_efficiency * 0.4 +
            volume_consistency * 0.2
        )

        return max(0.0, min(1.0, efficiency))


class TradingStrategy:
    """Implements various trading strategies"""

    def __init__(self, market_analyzer: MarketAnalyzer, strategy: EconomicStrategy):
        self.market_analyzer = market_analyzer
        self.strategy = strategy

    def generate_trade_decisions(self, character_state: dict[str, Any],
                               available_items: list[str]) -> list[TradeDecision]:
        """Generate trading decisions based on current market conditions"""
        decisions = []

        available_gold = character_state.get('character_gold', 0)
        max_investment = int(available_gold * self.strategy.max_investment_percentage)

        if max_investment < 100:  # Need minimum gold to trade
            return decisions

        for item_code in available_items:
            # Try different strategies for each item
            strategies = [
                self.momentum_trading_strategy,
                self.mean_reversion_strategy,
                self.value_investing_strategy,
                self.seasonal_strategy
            ]

            for strategy_func in strategies:
                decision = strategy_func(item_code)
                if decision and decision.confidence >= 0.6:
                    # Check if we have enough gold for this decision
                    if decision.decision_type == TradeDecisionType.BUY:
                        total_cost = decision.target_price * decision.target_quantity
                        if total_cost <= max_investment:
                            decisions.append(decision)
                            max_investment -= total_cost
                    else:
                        decisions.append(decision)

        # Sort by expected ROI and confidence
        decisions.sort(key=lambda d: d.calculate_roi(d.target_price * d.target_quantity) * d.confidence, reverse=True)

        return decisions[:5]  # Return top 5 decisions

    def momentum_trading_strategy(self, item_code: str) -> TradeDecision | None:
        """Buy rising items, sell falling items"""
        try:
            analysis = self.market_analyzer.analyze_item_market(item_code)
        except ValueError:
            return None

        if analysis.trend == MarketTrend.RISING and analysis.confidence > 0.6:
            # Buy on rising trend if price is below predicted future price
            if analysis.current_price.buy_price < analysis.predicted_price_1h * 0.95:
                profit_estimate = int((analysis.predicted_price_1h - analysis.current_price.buy_price) * 10)

                return TradeDecision(
                    item_code=item_code,
                    decision_type=TradeDecisionType.BUY,
                    target_price=analysis.current_price.buy_price,
                    target_quantity=min(10, analysis.current_price.quantity_available),
                    confidence=analysis.confidence,
                    reasoning=f"Momentum: Rising trend, predicted +{profit_estimate} in 1h",
                    expected_profit=profit_estimate,
                    risk_level=1.0 - analysis.confidence
                )

        elif analysis.trend == MarketTrend.FALLING and analysis.confidence > 0.6:
            # Sell on falling trend (if we own the item)
            predicted_loss = int((analysis.current_price.sell_price - analysis.predicted_price_1h) * 10)

            return TradeDecision(
                item_code=item_code,
                decision_type=TradeDecisionType.SELL,
                target_price=analysis.current_price.sell_price,
                target_quantity=10,
                confidence=analysis.confidence,
                reasoning=f"Momentum: Falling trend, avoid loss of {predicted_loss}",
                expected_profit=predicted_loss,
                risk_level=1.0 - analysis.confidence
            )

        return None

    def mean_reversion_strategy(self, item_code: str) -> TradeDecision | None:
        """Buy when below average, sell when above average"""
        try:
            analysis = self.market_analyzer.analyze_item_market(item_code)
        except ValueError:
            return None

        current_price = analysis.current_price.buy_price
        avg_7d = analysis.average_price_7d

        # Buy if current price is significantly below 7-day average
        if current_price < avg_7d * 0.85 and analysis.confidence > 0.5:
            profit_estimate = int((avg_7d - current_price) * 10)

            return TradeDecision(
                item_code=item_code,
                decision_type=TradeDecisionType.BUY,
                target_price=current_price,
                target_quantity=min(20, analysis.current_price.quantity_available),
                confidence=min(0.8, analysis.confidence + 0.2),
                reasoning=f"Mean reversion: {current_price} below 7d avg {avg_7d:.0f}",
                expected_profit=profit_estimate,
                risk_level=0.3
            )

        # Sell if current price is significantly above 7-day average
        elif current_price > avg_7d * 1.15 and analysis.confidence > 0.5:
            profit_estimate = int((current_price - avg_7d) * 10)

            return TradeDecision(
                item_code=item_code,
                decision_type=TradeDecisionType.SELL,
                target_price=analysis.current_price.sell_price,
                target_quantity=10,
                confidence=min(0.8, analysis.confidence + 0.2),
                reasoning=f"Mean reversion: {current_price} above 7d avg {avg_7d:.0f}",
                expected_profit=profit_estimate,
                risk_level=0.2
            )

        return None

    def arbitrage_strategy(self, character_state: dict[str, Any]) -> list[TradeDecision]:
        """Find and exploit price differences"""
        # This would need real NPC price data - for now return empty
        # In a real implementation, this would compare GE vs NPC prices
        return []

    def value_investing_strategy(self, item_code: str) -> TradeDecision | None:
        """Buy undervalued items, hold for long-term gains"""
        try:
            analysis = self.market_analyzer.analyze_item_market(item_code)
        except ValueError:
            return None

        current_price = analysis.current_price.buy_price
        avg_30d = analysis.average_price_30d

        # Look for items trading well below 30-day average with low volatility
        if (current_price < avg_30d * 0.8 and
            analysis.volatility < 0.2 and
            analysis.confidence > 0.7):

            profit_estimate = int((avg_30d - current_price) * 15)

            return TradeDecision(
                item_code=item_code,
                decision_type=TradeDecisionType.BUY,
                target_price=current_price,
                target_quantity=min(50, analysis.current_price.quantity_available),
                confidence=analysis.confidence,
                reasoning=f"Value: {current_price} vs 30d avg {avg_30d:.0f}, low volatility",
                expected_profit=profit_estimate,
                risk_level=0.1
            )

        return None

    def seasonal_strategy(self, item_code: str) -> TradeDecision | None:
        """Trade based on seasonal patterns"""
        patterns = self.market_analyzer.analyze_seasonal_patterns(item_code)

        if patterns['confidence'] < 0.5:
            return None

        try:
            analysis = self.market_analyzer.analyze_item_market(item_code)
        except ValueError:
            return None

        current_hour = datetime.now().hour

        # Buy near low hours, sell near peak hours
        if abs(current_hour - patterns['low_hour']) <= 2:
            profit_estimate = int(analysis.current_price.buy_price * patterns['daily_variance'] * 10)

            return TradeDecision(
                item_code=item_code,
                decision_type=TradeDecisionType.BUY,
                target_price=analysis.current_price.buy_price,
                target_quantity=min(15, analysis.current_price.quantity_available),
                confidence=patterns['confidence'],
                reasoning=f"Seasonal: Near low hour {patterns['low_hour']}, current {current_hour}",
                expected_profit=profit_estimate,
                risk_level=0.4
            )

        elif abs(current_hour - patterns['peak_hour']) <= 2:
            profit_estimate = int(analysis.current_price.sell_price * patterns['daily_variance'] * 10)

            return TradeDecision(
                item_code=item_code,
                decision_type=TradeDecisionType.SELL,
                target_price=analysis.current_price.sell_price,
                target_quantity=10,
                confidence=patterns['confidence'],
                reasoning=f"Seasonal: Near peak hour {patterns['peak_hour']}, current {current_hour}",
                expected_profit=profit_estimate,
                risk_level=0.3
            )

        return None

    def diversification_strategy(self, current_portfolio: dict[str, int]) -> list[TradeDecision]:
        """Diversify holdings to reduce risk"""
        decisions = []

        if not current_portfolio:
            return decisions

        total_value = sum(current_portfolio.values())

        # Identify overconcentrated holdings (>40% of portfolio)
        for item_code, value in current_portfolio.items():
            concentration = value / total_value

            if concentration > 0.4:
                # Recommend selling some of this item
                sell_quantity = int(value * 0.3)  # Sell 30% of holding

                decisions.append(TradeDecision(
                    item_code=item_code,
                    decision_type=TradeDecisionType.SELL,
                    target_price=0,  # Use market price
                    target_quantity=sell_quantity,
                    confidence=0.8,
                    reasoning=f"Diversification: Reduce {concentration:.1%} concentration",
                    expected_profit=0,
                    risk_level=0.1
                ))

        return decisions


class EconomicIntelligence:
    """Main economic intelligence system"""

    def __init__(self, api_client, economic_strategy: EconomicStrategy):
        self.api_client = api_client
        self.strategy = economic_strategy
        self.data_collector = MarketDataCollector(api_client)
        self.market_analyzer = MarketAnalyzer(self.data_collector)
        self.trading_strategy = TradingStrategy(self.market_analyzer, economic_strategy)
        self.portfolio = {}
        self.trade_history = []

    async def analyze_market_opportunities(self, character_state: dict[str, Any]) -> list[TradeDecision]:
        """Analyze current market for trading opportunities"""

        # Update market data for tracked items
        await self.data_collector.update_all_tracked_items()

        # Get commonly traded items for analysis
        tracked_items = ['copper_ore', 'iron_ore', 'coal', 'ash_wood', 'spruce_wood',
                        'raw_beef', 'cooked_beef', 'copper_sword', 'iron_sword']

        # Analyze each item for opportunities
        for item_code in tracked_items:
            self.data_collector.add_item_to_tracking(item_code)

        # Generate trade decisions using all strategies
        decisions = self.trading_strategy.generate_trade_decisions(character_state, tracked_items)

        # Add arbitrage opportunities
        arbitrage_decisions = self.trading_strategy.arbitrage_strategy(character_state)
        decisions.extend(arbitrage_decisions)

        # Filter by risk tolerance
        filtered_decisions = [
            d for d in decisions
            if d.risk_level <= self.strategy.risk_tolerance
        ]

        return filtered_decisions

    def optimize_buy_sell_decisions(self, character_state: dict[str, Any]) -> list[TradeDecision]:
        """Generate optimized buy/sell decisions"""
        available_gold = character_state.get('character_gold', 0)

        # Get all potential opportunities
        all_opportunities = []
        tracked_items = list(self.data_collector.price_history.keys())

        if tracked_items:
            all_opportunities = self.trading_strategy.generate_trade_decisions(
                character_state, tracked_items
            )

        # Optimize allocation
        allocation = self.calculate_investment_allocation(available_gold, all_opportunities)

        # Select decisions based on allocation
        optimized_decisions = []
        for decision in all_opportunities:
            if decision.item_code in allocation and allocation[decision.item_code] > 0:
                # Adjust quantity based on allocation
                max_quantity = allocation[decision.item_code] // decision.target_price
                decision.target_quantity = min(decision.target_quantity, max_quantity)

                if decision.target_quantity > 0:
                    optimized_decisions.append(decision)

        return optimized_decisions

    def calculate_investment_allocation(self, available_gold: int,
                                      opportunities: list[TradeDecision]) -> dict[str, int]:
        """Calculate how to allocate gold across opportunities"""
        allocation = {}

        if not opportunities or available_gold < 100:
            return allocation

        # Sort opportunities by score (ROI * confidence / risk)
        scored_opportunities = []
        for opp in opportunities:
            if opp.decision_type == TradeDecisionType.BUY:
                investment = opp.target_price * opp.target_quantity
                roi = opp.calculate_roi(investment)
                score = (roi * opp.confidence) / max(0.1, opp.risk_level)
                scored_opportunities.append((opp, score, investment))

        scored_opportunities.sort(key=lambda x: x[1], reverse=True)

        # Allocate gold proportionally to top opportunities
        max_investment = int(available_gold * self.strategy.max_investment_percentage)
        total_score = sum(score for _, score, _ in scored_opportunities[:5])

        if total_score > 0:
            for opp, score, investment in scored_opportunities[:5]:
                proportion = score / total_score
                allocated_amount = min(int(max_investment * proportion), investment)

                if allocated_amount >= opp.target_price:
                    allocation[opp.item_code] = allocated_amount

        return allocation

    def evaluate_trade_performance(self) -> dict[str, float]:
        """Evaluate historical trading performance"""
        if not self.trade_history:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'average_profit': 0.0,
                'total_profit': 0.0,
                'sharpe_ratio': 0.0
            }

        profitable_trades = [t for t in self.trade_history if t.get('profit', 0) > 0]
        total_profit = sum(t.get('profit', 0) for t in self.trade_history)

        performance = {
            'total_trades': len(self.trade_history),
            'win_rate': len(profitable_trades) / len(self.trade_history),
            'average_profit': total_profit / len(self.trade_history),
            'total_profit': total_profit,
            'sharpe_ratio': self._calculate_sharpe_ratio()
        }

        return performance

    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio for trade performance"""
        if len(self.trade_history) < 2:
            return 0.0

        profits = [t.get('profit', 0) for t in self.trade_history]
        mean_profit = sum(profits) / len(profits)

        variance = sum((p - mean_profit) ** 2 for p in profits) / len(profits)
        std_dev = variance ** 0.5

        return mean_profit / std_dev if std_dev > 0 else 0.0

    def adjust_strategy_based_on_performance(self) -> None:
        """Adjust strategy based on past performance"""
        performance = self.evaluate_trade_performance()

        if performance['total_trades'] < 10:
            return  # Need more data

        # Adjust risk tolerance based on win rate
        if performance['win_rate'] < 0.4:
            # Poor performance, reduce risk
            self.strategy.risk_tolerance = max(0.1, self.strategy.risk_tolerance * 0.9)
            self.strategy.max_investment_percentage = max(0.1, self.strategy.max_investment_percentage * 0.9)
        elif performance['win_rate'] > 0.7:
            # Good performance, can increase risk slightly
            self.strategy.risk_tolerance = min(1.0, self.strategy.risk_tolerance * 1.05)
            self.strategy.max_investment_percentage = min(0.5, self.strategy.max_investment_percentage * 1.05)

        # Adjust profit margin threshold based on average profit
        if performance['average_profit'] < 0:
            self.strategy.profit_margin_threshold = min(0.5, self.strategy.profit_margin_threshold * 1.2)

    def get_economic_goals(self, character_state: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate economic goals for GOAP system"""
        goals = []

        # Basic wealth building goal
        current_gold = character_state.get('character_gold', 0)
        if current_gold < 10000:
            goals.append({
                'goal_name': 'accumulate_wealth',
                'target_gold': min(current_gold * 2, 10000),
                'priority': 0.7,
                'method': 'trading'
            })

        # Market access goal
        at_ge = character_state.get('at_grand_exchange', False)
        if not at_ge and current_gold > 1000:
            goals.append({
                'goal_name': 'access_market',
                'target_location': 'grand_exchange',
                'priority': 0.8,
                'method': 'movement'
            })

        # Profitable trading goal
        if at_ge and current_gold > 500:
            goals.append({
                'goal_name': 'execute_profitable_trades',
                'min_profit_margin': self.strategy.profit_margin_threshold,
                'priority': 0.9,
                'method': 'trading'
            })

        return goals

    def should_prioritize_economics(self, character_state: dict[str, Any]) -> bool:
        """Determine if economic activities should be prioritized"""
        current_gold = character_state.get('character_gold', 0)
        character_level = character_state.get('character_level', 1)

        # Prioritize economics if:
        # 1. Low on gold relative to level
        # 2. At grand exchange with opportunities
        # 3. Have significant trading capital

        if current_gold < character_level * 100:
            return True  # Need gold for level

        at_ge = character_state.get('at_grand_exchange', False)
        if at_ge and current_gold > 1000:
            return True  # Can trade profitably

        if current_gold > 5000:
            return True  # Have significant capital to invest

        return False

    def estimate_wealth_building_efficiency(self, method: str, character_state: dict[str, Any]) -> float:
        """Estimate efficiency of different wealth building methods"""
        character_level = character_state.get('character_level', 1)
        current_gold = character_state.get('character_gold', 0)

        if method == 'trading':
            # Trading efficiency based on capital and market access
            if current_gold < 500:
                return 0.2  # Not enough capital

            at_ge = character_state.get('at_grand_exchange', False)
            if not at_ge:
                return 0.3  # Need to travel to market

            # Higher efficiency with more capital
            capital_factor = min(1.0, current_gold / 5000)
            return 0.5 + (capital_factor * 0.4)

        elif method == 'gathering':
            # Gathering efficiency based on skill levels
            gathering_skills = ['mining_level', 'woodcutting_level', 'fishing_level']
            avg_skill = sum(character_state.get(skill, 1) for skill in gathering_skills) / 3
            return min(0.8, 0.3 + (avg_skill / 45) * 0.5)

        elif method == 'crafting':
            # Crafting efficiency based on crafting skills
            crafting_skills = ['weaponcrafting_level', 'gearcrafting_level', 'cooking_level']
            avg_skill = sum(character_state.get(skill, 1) for skill in crafting_skills) / 3
            return min(0.7, 0.2 + (avg_skill / 45) * 0.5)

        elif method == 'combat':
            # Combat efficiency based on level and equipment
            combat_factor = min(1.0, character_level / 20)
            return 0.4 + (combat_factor * 0.3)

        return 0.1  # Unknown method


class PortfolioManager:
    """Manages character's item portfolio and investments"""

    def __init__(self):
        self.holdings = {}
        self.transaction_history = []

    def record_purchase(self, item_code: str, quantity: int, price_per_item: int,
                       timestamp: datetime) -> None:
        """Record item purchase"""
        if item_code not in self.holdings:
            self.holdings[item_code] = {'quantity': 0, 'avg_cost': 0, 'transactions': []}

        # Update average cost using weighted average
        current_holding = self.holdings[item_code]
        total_cost = (current_holding['quantity'] * current_holding['avg_cost']) + (quantity * price_per_item)
        total_quantity = current_holding['quantity'] + quantity

        current_holding['quantity'] = total_quantity
        current_holding['avg_cost'] = total_cost / total_quantity if total_quantity > 0 else 0

        # Record transaction
        transaction = {
            'type': 'buy',
            'quantity': quantity,
            'price': price_per_item,
            'timestamp': timestamp,
            'total_cost': quantity * price_per_item
        }
        current_holding['transactions'].append(transaction)
        self.transaction_history.append(transaction)

    def record_sale(self, item_code: str, quantity: int, price_per_item: int,
                   timestamp: datetime) -> None:
        """Record item sale"""
        if item_code not in self.holdings:
            self.holdings[item_code] = {'quantity': 0, 'avg_cost': 0, 'transactions': []}

        current_holding = self.holdings[item_code]

        # Calculate realized gain/loss
        avg_cost = current_holding['avg_cost']
        profit = (price_per_item - avg_cost) * quantity

        # Update holdings
        current_holding['quantity'] = max(0, current_holding['quantity'] - quantity)

        # Record transaction
        transaction = {
            'type': 'sell',
            'quantity': quantity,
            'price': price_per_item,
            'timestamp': timestamp,
            'total_revenue': quantity * price_per_item,
            'avg_cost': avg_cost,
            'profit': profit
        }
        current_holding['transactions'].append(transaction)
        self.transaction_history.append(transaction)

    def calculate_portfolio_value(self, current_prices: dict[str, int]) -> int:
        """Calculate current portfolio value"""
        total_value = 0

        for item_code, holding in self.holdings.items():
            if holding['quantity'] > 0 and item_code in current_prices:
                item_value = holding['quantity'] * current_prices[item_code]
                total_value += item_value

        return total_value

    def calculate_unrealized_gains(self, current_prices: dict[str, int]) -> dict[str, float]:
        """Calculate unrealized gains/losses for each holding"""
        unrealized_gains = {}

        for item_code, holding in self.holdings.items():
            if holding['quantity'] > 0 and item_code in current_prices:
                current_value = holding['quantity'] * current_prices[item_code]
                cost_basis = holding['quantity'] * holding['avg_cost']

                if cost_basis > 0:
                    gain_loss = current_value - cost_basis
                    gain_loss_pct = (gain_loss / cost_basis) * 100

                    unrealized_gains[item_code] = {
                        'absolute_gain': gain_loss,
                        'percentage_gain': gain_loss_pct,
                        'current_value': current_value,
                        'cost_basis': cost_basis
                    }

        return unrealized_gains

    def get_diversification_score(self) -> float:
        """Calculate portfolio diversification score"""
        if not self.holdings:
            return 0.0

        # Calculate total portfolio value using average costs
        total_value = sum(
            holding['quantity'] * holding['avg_cost']
            for holding in self.holdings.values()
            if holding['quantity'] > 0
        )

        if total_value == 0:
            return 0.0

        # Calculate concentration ratios
        concentrations = []
        for holding in self.holdings.values():
            if holding['quantity'] > 0:
                item_value = holding['quantity'] * holding['avg_cost']
                concentration = item_value / total_value
                concentrations.append(concentration)

        # Calculate Herfindahl-Hirschman Index (HHI)
        hhi = sum(c ** 2 for c in concentrations)

        # Convert to diversification score (1 = perfectly diversified, 0 = concentrated)
        diversification_score = 1.0 - hhi

        return max(0.0, min(1.0, diversification_score))

    def identify_rebalancing_needs(self, target_allocation: dict[str, float]) -> list[TradeDecision]:
        """Identify trades needed to rebalance portfolio"""
        rebalancing_decisions = []

        if not self.holdings or not target_allocation:
            return rebalancing_decisions

        # Calculate current portfolio value
        total_value = sum(
            holding['quantity'] * holding['avg_cost']
            for holding in self.holdings.values()
            if holding['quantity'] > 0
        )

        if total_value == 0:
            return rebalancing_decisions

        # Calculate current allocations
        current_allocations = {}
        for item_code, holding in self.holdings.items():
            if holding['quantity'] > 0:
                item_value = holding['quantity'] * holding['avg_cost']
                current_allocations[item_code] = item_value / total_value

        # Identify rebalancing needs
        for item_code, target_pct in target_allocation.items():
            current_pct = current_allocations.get(item_code, 0.0)
            difference = target_pct - current_pct

            # Only rebalance if difference is significant (>5%)
            if abs(difference) > 0.05:
                target_value = total_value * target_pct
                current_value = total_value * current_pct
                value_difference = target_value - current_value

                if value_difference > 0:
                    # Need to buy more
                    rebalancing_decisions.append(TradeDecision(
                        item_code=item_code,
                        decision_type=TradeDecisionType.BUY,
                        target_price=0,  # Use market price
                        target_quantity=int(abs(value_difference) / 100),  # Estimate quantity
                        confidence=0.8,
                        reasoning=f"Rebalance: {current_pct:.1%} -> {target_pct:.1%}",
                        expected_profit=0,
                        risk_level=0.2
                    ))
                else:
                    # Need to sell some
                    rebalancing_decisions.append(TradeDecision(
                        item_code=item_code,
                        decision_type=TradeDecisionType.SELL,
                        target_price=0,  # Use market price
                        target_quantity=int(abs(value_difference) / 100),  # Estimate quantity
                        confidence=0.8,
                        reasoning=f"Rebalance: {current_pct:.1%} -> {target_pct:.1%}",
                        expected_profit=0,
                        risk_level=0.2
                    ))

        return rebalancing_decisions

    def calculate_risk_metrics(self, price_history: dict[str, list[PriceData]]) -> dict[str, float]:
        """Calculate various risk metrics for portfolio"""
        metrics = {
            'portfolio_volatility': 0.0,
            'max_drawdown': 0.0,
            'value_at_risk_95': 0.0,
            'sharpe_ratio': 0.0,
            'beta': 1.0
        }

        if not self.holdings or not price_history:
            return metrics

        # Calculate portfolio returns over time

        # Simplified calculation using transaction history
        if len(self.transaction_history) > 1:
            daily_returns = []

            for i in range(1, len(self.transaction_history)):
                current_profit = self.transaction_history[i].get('profit', 0)
                if current_profit != 0:
                    # Calculate daily return
                    prev_value = abs(self.transaction_history[i-1].get('total_cost', 1))
                    daily_return = current_profit / prev_value
                    daily_returns.append(daily_return)

            if daily_returns:
                # Portfolio volatility (standard deviation of returns)
                mean_return = sum(daily_returns) / len(daily_returns)
                variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)
                metrics['portfolio_volatility'] = variance ** 0.5

                # Sharpe ratio (assuming risk-free rate of 0)
                metrics['sharpe_ratio'] = mean_return / metrics['portfolio_volatility'] if metrics['portfolio_volatility'] > 0 else 0

                # Value at Risk (95% confidence)
                sorted_returns = sorted(daily_returns)
                var_index = int(len(sorted_returns) * 0.05)
                if var_index < len(sorted_returns):
                    metrics['value_at_risk_95'] = abs(sorted_returns[var_index])

                # Max drawdown
                cumulative_returns = []
                cumulative = 0
                for ret in daily_returns:
                    cumulative += ret
                    cumulative_returns.append(cumulative)

                if cumulative_returns:
                    peak = cumulative_returns[0]
                    max_dd = 0
                    for cum_ret in cumulative_returns:
                        if cum_ret > peak:
                            peak = cum_ret
                        drawdown = (peak - cum_ret) / peak if peak != 0 else 0
                        max_dd = max(max_dd, drawdown)

                    metrics['max_drawdown'] = max_dd

        return metrics


class EconomicGoalGenerator:
    """Generates GOAP goals based on economic opportunities"""

    def __init__(self, economic_intelligence: EconomicIntelligence):
        self.economic_intelligence = economic_intelligence

    def generate_trading_goals(self, character_state: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate GOAP goals for trading activities"""
        goals = []

        current_gold = character_state.get('character_gold', 0)
        at_ge = character_state.get('at_grand_exchange', False)

        # Goal: Get to Grand Exchange for trading
        if not at_ge and current_gold > 500:
            goals.append({
                'name': 'reach_grand_exchange',
                'target_state': {'at_grand_exchange': True},
                'priority': 0.8,
                'estimated_duration': 300,  # 5 minutes
                'requirements': {'can_move': True},
                'method': 'movement'
            })

        # Goal: Execute profitable trades
        if at_ge and current_gold > 1000:
            goals.append({
                'name': 'execute_profitable_trade',
                'target_state': {
                    'character_gold': current_gold + int(current_gold * 0.1),
                    'profitable_trade_available': True
                },
                'priority': 0.9,
                'estimated_duration': 120,  # 2 minutes per trade
                'requirements': {'can_trade': True, 'market_access': True},
                'method': 'trading'
            })

        # Goal: Monitor market prices
        if at_ge:
            goals.append({
                'name': 'update_market_data',
                'target_state': {'market_data_fresh': True},
                'priority': 0.6,
                'estimated_duration': 60,  # 1 minute
                'requirements': {'market_access': True},
                'method': 'data_collection'
            })

        return goals

    def generate_wealth_building_goals(self, character_state: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate goals focused on wealth accumulation"""
        goals = []

        current_gold = character_state.get('character_gold', 0)
        character_level = character_state.get('character_level', 1)

        # Target gold based on character level
        target_gold = character_level * 1000

        if current_gold < target_gold:
            # Wealth accumulation through different methods
            wealth_methods = [
                {
                    'method': 'trading',
                    'efficiency': self.economic_intelligence.estimate_wealth_building_efficiency('trading', character_state),
                    'requirements': {'market_access': True, 'character_gold': 500}
                },
                {
                    'method': 'gathering',
                    'efficiency': self.economic_intelligence.estimate_wealth_building_efficiency('gathering', character_state),
                    'requirements': {'can_gather': True, 'resource_available': True}
                },
                {
                    'method': 'crafting',
                    'efficiency': self.economic_intelligence.estimate_wealth_building_efficiency('crafting', character_state),
                    'requirements': {'can_craft': True, 'has_crafting_materials': True}
                },
                {
                    'method': 'combat',
                    'efficiency': self.economic_intelligence.estimate_wealth_building_efficiency('combat', character_state),
                    'requirements': {'can_fight': True, 'safe_to_fight': True}
                }
            ]

            # Sort by efficiency
            wealth_methods.sort(key=lambda x: x['efficiency'], reverse=True)

            # Generate goals for top methods
            for i, method_info in enumerate(wealth_methods[:2]):
                method = method_info['method']
                efficiency = method_info['efficiency']

                if efficiency > 0.3:  # Only consider reasonably efficient methods
                    goals.append({
                        'name': f'wealth_building_{method}',
                        'target_state': {'character_gold': target_gold},
                        'priority': 0.7 + (efficiency * 0.2),
                        'estimated_duration': int(600 / efficiency),  # Inverse relationship
                        'requirements': method_info['requirements'],
                        'method': method,
                        'efficiency': efficiency
                    })

        return goals

    def generate_arbitrage_goals(self, opportunities: list[TradeDecision]) -> list[dict[str, Any]]:
        """Generate goals for arbitrage opportunities"""
        goals = []

        for opportunity in opportunities:
            if (opportunity.decision_type == TradeDecisionType.BUY and
                opportunity.confidence > 0.8 and
                opportunity.risk_level < 0.3):

                # High-confidence, low-risk arbitrage opportunity
                goals.append({
                    'name': f'arbitrage_{opportunity.item_code}',
                    'target_state': {
                        'arbitrage_opportunity': True,
                        'item_quantity': {opportunity.item_code: opportunity.target_quantity}
                    },
                    'priority': 0.95,  # Very high priority for arbitrage
                    'estimated_duration': 180,  # 3 minutes
                    'requirements': {
                        'can_trade': True,
                        'market_access': True,
                        'character_gold': opportunity.target_price * opportunity.target_quantity
                    },
                    'method': 'arbitrage',
                    'item_code': opportunity.item_code,
                    'expected_profit': opportunity.expected_profit,
                    'confidence': opportunity.confidence
                })

        return goals

    def prioritize_economic_goals(self, goals: list[dict[str, Any]],
                                 character_state: dict[str, Any]) -> list[dict[str, Any]]:
        """Prioritize economic goals based on efficiency and risk"""
        if not goals:
            return goals

        current_gold = character_state.get('character_gold', 0)
        character_level = character_state.get('character_level', 1)
        at_ge = character_state.get('at_grand_exchange', False)

        # Score each goal based on multiple factors
        scored_goals = []

        for goal in goals:
            base_priority = goal.get('priority', 0.5)
            efficiency = goal.get('efficiency', 0.5)
            expected_profit = goal.get('expected_profit', 0)
            confidence = goal.get('confidence', 0.5)
            estimated_duration = goal.get('estimated_duration', 300)

            # Calculate composite score
            score = base_priority

            # Boost score for high efficiency
            score += efficiency * 0.2

            # Boost score for high expected profit
            if expected_profit > 0:
                profit_factor = min(0.3, expected_profit / (current_gold + 1))
                score += profit_factor

            # Boost score for high confidence
            score += confidence * 0.1

            # Penalize for long duration
            duration_penalty = max(0, (estimated_duration - 300) / 1200)  # Penalty for >5 min
            score -= duration_penalty * 0.1

            # Context-specific adjustments
            method = goal.get('method', '')

            if method == 'trading' and not at_ge:
                score -= 0.2  # Penalize trading goals if not at market

            if method == 'movement' and current_gold < 100:
                score -= 0.1  # Penalize movement if very low on gold

            # Arbitrage gets bonus
            if method == 'arbitrage':
                score += 0.2

            # Wealth building bonus if poor
            if 'wealth_building' in goal.get('name', '') and current_gold < character_level * 500:
                score += 0.15

            scored_goals.append((goal, max(0.0, min(1.0, score))))

        # Sort by score (descending)
        scored_goals.sort(key=lambda x: x[1], reverse=True)

        # Return sorted goals
        prioritized_goals = [goal for goal, score in scored_goals]

        # Add score to goals for debugging
        for i, (goal, score) in enumerate(scored_goals):
            prioritized_goals[i]['computed_priority'] = score

        return prioritized_goals
