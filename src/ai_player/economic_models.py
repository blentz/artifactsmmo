"""
Economic Models

This module contains all the data structures and enums used throughout
the economic intelligence system for market analysis and trading.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


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