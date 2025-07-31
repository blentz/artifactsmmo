"""
Tests for Economic Models

This module tests all the data structures and enums used throughout
the economic intelligence system for market analysis and trading.
"""

from datetime import datetime

from src.ai_player.economic_models import (
    EconomicStrategy,
    MarketAnalysis,
    MarketTrend,
    PriceData,
    TradeDecision,
    TradeDecisionType,
)


class TestMarketTrend:
    """Test MarketTrend enum"""

    def test_market_trend_values(self):
        """Test all MarketTrend enum values"""
        assert MarketTrend.RISING.value == "rising"
        assert MarketTrend.FALLING.value == "falling"
        assert MarketTrend.STABLE.value == "stable"
        assert MarketTrend.VOLATILE.value == "volatile"


class TestTradeDecisionType:
    """Test TradeDecisionType enum"""

    def test_trade_decision_type_values(self):
        """Test all TradeDecisionType enum values"""
        assert TradeDecisionType.BUY.value == "buy"
        assert TradeDecisionType.SELL.value == "sell"
        assert TradeDecisionType.HOLD.value == "hold"
        assert TradeDecisionType.AVOID.value == "avoid"


class TestPriceData:
    """Test PriceData dataclass"""

    def test_price_data_creation(self):
        """Test creating PriceData with valid data"""
        timestamp = datetime.now()
        price_data = PriceData(
            item_code="copper_ore",
            timestamp=timestamp,
            buy_price=100,
            sell_price=120,
            quantity_available=50
        )

        assert price_data.item_code == "copper_ore"
        assert price_data.timestamp == timestamp
        assert price_data.buy_price == 100
        assert price_data.sell_price == 120
        assert price_data.quantity_available == 50

    def test_spread_calculation(self):
        """Test spread property calculation"""
        price_data = PriceData(
            item_code="copper_ore",
            timestamp=datetime.now(),
            buy_price=100,
            sell_price=120,
            quantity_available=50
        )

        assert price_data.spread == 20

    def test_spread_percentage_calculation(self):
        """Test spread percentage property calculation"""
        price_data = PriceData(
            item_code="copper_ore",
            timestamp=datetime.now(),
            buy_price=100,
            sell_price=120,
            quantity_available=50
        )

        assert price_data.spread_percentage == 20.0

    def test_spread_percentage_zero_buy_price(self):
        """Test spread percentage with zero buy price"""
        price_data = PriceData(
            item_code="copper_ore",
            timestamp=datetime.now(),
            buy_price=0,
            sell_price=120,
            quantity_available=50
        )

        assert price_data.spread_percentage == 0

    def test_negative_spread(self):
        """Test negative spread calculation"""
        price_data = PriceData(
            item_code="copper_ore",
            timestamp=datetime.now(),
            buy_price=120,
            sell_price=100,
            quantity_available=50
        )

        assert price_data.spread == -20
        assert abs(price_data.spread_percentage - (-16.666666666666668)) < 0.000001


class TestMarketAnalysis:
    """Test MarketAnalysis dataclass"""

    def create_sample_price_data(self) -> PriceData:
        """Create sample price data for testing"""
        return PriceData(
            item_code="copper_ore",
            timestamp=datetime.now(),
            buy_price=100,
            sell_price=120,
            quantity_available=50
        )

    def create_sample_market_analysis(self, **kwargs) -> MarketAnalysis:
        """Create sample market analysis for testing"""
        defaults = {
            "item_code": "copper_ore",
            "current_price": self.create_sample_price_data(),
            "trend": MarketTrend.STABLE,
            "volatility": 0.1,
            "volume": 1000,
            "average_price_7d": 105.0,
            "average_price_30d": 110.0,
            "predicted_price_1h": 102.0,
            "predicted_price_24h": 98.0,
            "confidence": 0.8
        }
        defaults.update(kwargs)
        return MarketAnalysis(**defaults)

    def test_market_analysis_creation(self):
        """Test creating MarketAnalysis with valid data"""
        price_data = self.create_sample_price_data()
        analysis = MarketAnalysis(
            item_code="copper_ore",
            current_price=price_data,
            trend=MarketTrend.RISING,
            volatility=0.15,
            volume=500,
            average_price_7d=95.0,
            average_price_30d=90.0,
            predicted_price_1h=105.0,
            predicted_price_24h=110.0,
            confidence=0.75
        )

        assert analysis.item_code == "copper_ore"
        assert analysis.current_price == price_data
        assert analysis.trend == MarketTrend.RISING
        assert analysis.volatility == 0.15
        assert analysis.volume == 500
        assert analysis.average_price_7d == 95.0
        assert analysis.average_price_30d == 90.0
        assert analysis.predicted_price_1h == 105.0
        assert analysis.predicted_price_24h == 110.0
        assert analysis.confidence == 0.75

    def test_is_good_buy_opportunity_falling_trend_below_7d(self):
        """Test buy opportunity: falling trend with price below 7d average"""
        analysis = self.create_sample_market_analysis(
            trend=MarketTrend.FALLING
        )
        # buy_price=100, average_price_7d=105, so 100 < 105 * 0.95 = 99.75 -> False
        assert not analysis.is_good_buy_opportunity()

        # Test with lower current price
        price_data = PriceData(
            item_code="copper_ore",
            timestamp=datetime.now(),
            buy_price=95,
            sell_price=115,
            quantity_available=50
        )
        analysis = self.create_sample_market_analysis(
            current_price=price_data,
            trend=MarketTrend.FALLING
        )
        # buy_price=95, average_price_7d=105, so 95 < 105 * 0.95 = 99.75 -> True
        assert analysis.is_good_buy_opportunity()

    def test_is_good_buy_opportunity_predicted_price_increase(self):
        """Test buy opportunity: predicted price increase with high confidence"""
        analysis = self.create_sample_market_analysis(
            predicted_price_1h=115.0,  # 115 > 100 * 1.1 = 110
            confidence=0.8  # > 0.7
        )
        assert analysis.is_good_buy_opportunity()

        # Test with low confidence
        analysis = self.create_sample_market_analysis(
            predicted_price_1h=115.0,
            confidence=0.6  # <= 0.7
        )
        assert not analysis.is_good_buy_opportunity()

    def test_is_good_buy_opportunity_below_30d_average(self):
        """Test buy opportunity: current price below 30d average"""
        analysis = self.create_sample_market_analysis(
            average_price_30d=120.0  # buy_price=100 < 120 * 0.9 = 108
        )
        assert analysis.is_good_buy_opportunity()

        # Test with higher 30d average where condition is false
        analysis = self.create_sample_market_analysis(
            average_price_30d=105.0  # buy_price=100 >= 105 * 0.9 = 94.5
        )
        assert not analysis.is_good_buy_opportunity()

    def test_is_good_sell_opportunity_rising_trend_above_7d(self):
        """Test sell opportunity: rising trend with price above 7d average"""
        price_data = PriceData(
            item_code="copper_ore",
            timestamp=datetime.now(),
            buy_price=100,
            sell_price=115,
            quantity_available=50
        )
        analysis = self.create_sample_market_analysis(
            current_price=price_data,
            trend=MarketTrend.RISING,
            average_price_7d=105.0  # sell_price=115 > 105 * 1.05 = 110.25
        )
        assert analysis.is_good_sell_opportunity()

        # Test with lower sell price
        price_data = PriceData(
            item_code="copper_ore",
            timestamp=datetime.now(),
            buy_price=100,
            sell_price=108,
            quantity_available=50
        )
        analysis = self.create_sample_market_analysis(
            current_price=price_data,
            trend=MarketTrend.RISING,
            average_price_7d=105.0  # sell_price=108 <= 105 * 1.05 = 110.25
        )
        assert not analysis.is_good_sell_opportunity()

    def test_is_good_sell_opportunity_predicted_price_decrease(self):
        """Test sell opportunity: predicted price decrease with high confidence"""
        price_data = PriceData(
            item_code="copper_ore",
            timestamp=datetime.now(),
            buy_price=100,
            sell_price=120,
            quantity_available=50
        )
        analysis = self.create_sample_market_analysis(
            current_price=price_data,
            predicted_price_1h=105.0,  # 105 < 120 * 0.9 = 108
            confidence=0.8  # > 0.7
        )
        assert analysis.is_good_sell_opportunity()

        # Test with low confidence
        analysis = self.create_sample_market_analysis(
            current_price=price_data,
            predicted_price_1h=105.0,
            confidence=0.6  # <= 0.7
        )
        assert not analysis.is_good_sell_opportunity()

    def test_is_good_sell_opportunity_above_30d_average(self):
        """Test sell opportunity: current price above 30d average"""
        price_data = PriceData(
            item_code="copper_ore",
            timestamp=datetime.now(),
            buy_price=100,
            sell_price=125,
            quantity_available=50
        )
        analysis = self.create_sample_market_analysis(
            current_price=price_data,
            average_price_30d=110.0  # sell_price=125 > 110 * 1.1 = 121
        )
        assert analysis.is_good_sell_opportunity()

        # Test with higher 30d average where condition is false
        analysis = self.create_sample_market_analysis(
            current_price=price_data,
            average_price_30d=115.0  # sell_price=125 > 115 * 1.1 = 126.5, still true from other conditions
        )
        # This will still be true due to other conditions, let's test with much higher price
        price_data_lower = PriceData(
            item_code="copper_ore",
            timestamp=datetime.now(),
            buy_price=100,
            sell_price=110,
            quantity_available=50
        )
        analysis = self.create_sample_market_analysis(
            current_price=price_data_lower,
            average_price_30d=105.0,  # sell_price=110 <= 105 * 1.1 = 115.5
            trend=MarketTrend.STABLE,  # Not rising
            predicted_price_1h=112.0,  # 112 >= 110 * 0.9 = 99, not decreasing
            confidence=0.8
        )
        assert not analysis.is_good_sell_opportunity()


class TestTradeDecision:
    """Test TradeDecision dataclass"""

    def create_sample_trade_decision(self, **kwargs) -> TradeDecision:
        """Create sample trade decision for testing"""
        defaults = {
            "item_code": "copper_ore",
            "decision_type": TradeDecisionType.BUY,
            "target_price": 95,
            "target_quantity": 100,
            "confidence": 0.8,
            "reasoning": "Price below 7-day average",
            "expected_profit": 500,
            "risk_level": 0.3
        }
        defaults.update(kwargs)
        return TradeDecision(**defaults)

    def test_trade_decision_creation(self):
        """Test creating TradeDecision with valid data"""
        decision = TradeDecision(
            item_code="iron_ore",
            decision_type=TradeDecisionType.SELL,
            target_price=150,
            target_quantity=50,
            confidence=0.9,
            reasoning="Rising trend with high volume",
            expected_profit=750,
            risk_level=0.2
        )

        assert decision.item_code == "iron_ore"
        assert decision.decision_type == TradeDecisionType.SELL
        assert decision.target_price == 150
        assert decision.target_quantity == 50
        assert decision.confidence == 0.9
        assert decision.reasoning == "Rising trend with high volume"
        assert decision.expected_profit == 750
        assert decision.risk_level == 0.2

    def test_calculate_roi(self):
        """Test ROI calculation"""
        decision = self.create_sample_trade_decision(
            expected_profit=500
        )

        roi = decision.calculate_roi(1000)
        assert roi == 50.0  # 500/1000 * 100 = 50%

    def test_calculate_roi_zero_investment(self):
        """Test ROI calculation with zero investment"""
        decision = self.create_sample_trade_decision(
            expected_profit=500
        )

        roi = decision.calculate_roi(0)
        assert roi == 0

    def test_calculate_roi_negative_profit(self):
        """Test ROI calculation with negative profit (loss)"""
        decision = self.create_sample_trade_decision(
            expected_profit=-200
        )

        roi = decision.calculate_roi(1000)
        assert roi == -20.0  # -200/1000 * 100 = -20%


class TestEconomicStrategy:
    """Test EconomicStrategy dataclass"""

    def test_economic_strategy_creation(self):
        """Test creating EconomicStrategy with valid data"""
        strategy = EconomicStrategy(
            risk_tolerance=0.7,
            profit_margin_threshold=0.15,
            max_investment_percentage=0.25,
            preferred_trade_types=["ores", "gems"],
            avoid_items=["food", "consumables"]
        )

        assert strategy.risk_tolerance == 0.7
        assert strategy.profit_margin_threshold == 0.15
        assert strategy.max_investment_percentage == 0.25
        assert strategy.preferred_trade_types == ["ores", "gems"]
        assert strategy.avoid_items == ["food", "consumables"]

    def test_economic_strategy_conservative(self):
        """Test conservative economic strategy"""
        strategy = EconomicStrategy(
            risk_tolerance=0.2,
            profit_margin_threshold=0.05,
            max_investment_percentage=0.1,
            preferred_trade_types=["basic_materials"],
            avoid_items=["rare_items", "volatile_items"]
        )

        assert strategy.risk_tolerance == 0.2
        assert strategy.profit_margin_threshold == 0.05
        assert strategy.max_investment_percentage == 0.1

    def test_economic_strategy_aggressive(self):
        """Test aggressive economic strategy"""
        strategy = EconomicStrategy(
            risk_tolerance=0.9,
            profit_margin_threshold=0.3,
            max_investment_percentage=0.5,
            preferred_trade_types=["rare_items", "gems", "equipment"],
            avoid_items=[]
        )

        assert strategy.risk_tolerance == 0.9
        assert strategy.profit_margin_threshold == 0.3
        assert strategy.max_investment_percentage == 0.5
        assert strategy.avoid_items == []
