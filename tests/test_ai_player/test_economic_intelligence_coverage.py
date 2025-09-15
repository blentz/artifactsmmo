"""
Economic Intelligence Coverage Tests

Targets specific uncovered lines in economic_intelligence.py to achieve higher coverage.
Focus on edge cases, exception handling, and specific conditions that trigger uncovered lines.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from src.ai_player.economic_intelligence import EconomicIntelligence, MarketTrend
from src.ai_player.economic_models import PriceData


class TestEconomicIntelligenceCoverage:
    """Coverage tests targeting specific uncovered lines in economic_intelligence.py"""

    @pytest.fixture
    def mock_api_client(self):
        """Create a mock API client"""
        api_client = Mock()
        return api_client

    @pytest.fixture
    def mock_economic_strategy(self):
        """Create a mock economic strategy"""
        strategy = Mock()
        return strategy

    @pytest.fixture
    def economic_intelligence(self, mock_api_client, mock_economic_strategy):
        """Create economic intelligence with mocked dependencies"""
        return EconomicIntelligence(api_client=mock_api_client, economic_strategy=mock_economic_strategy)

    def test_analyze_market_trend_with_less_than_3_prices(self, economic_intelligence):
        """Test analyze_market_trend with less than 3 price points - covers line 286"""
        # Create price history with only 1 price point
        price_history = [
            PriceData(
                item_code="test_item", timestamp=datetime.now(), buy_price=100, sell_price=100, quantity_available=10
            )
        ]

        result = economic_intelligence.market_analyzer.detect_trend(price_history)
        assert result == MarketTrend.STABLE

    def test_analyze_market_trend_with_exactly_2_prices(self, economic_intelligence):
        """Test analyze_market_trend with exactly 2 price points - covers line 286"""
        # Create price history with only 2 price points
        price_history = [
            PriceData(
                item_code="test_item",
                timestamp=datetime.now() - timedelta(hours=2),
                buy_price=100,
                sell_price=100,
                quantity_available=10,
            ),
            PriceData(
                item_code="test_item", timestamp=datetime.now(), buy_price=110, sell_price=110, quantity_available=10
            ),
        ]

        result = economic_intelligence.market_analyzer.detect_trend(price_history)
        assert result == MarketTrend.STABLE

    def test_analyze_market_trend_with_empty_prices_after_slicing(self, economic_intelligence):
        """Test analyze_market_trend edge case where prices list becomes empty after slicing - covers line 286"""
        # Create very old price history that will be filtered out
        old_time = datetime.now() - timedelta(days=30)
        price_history = [
            PriceData(item_code="test_item", timestamp=old_time, buy_price=100, sell_price=100, quantity_available=10)
        ]

        result = economic_intelligence.market_analyzer.detect_trend(price_history)
        assert result == MarketTrend.STABLE

    def test_calculate_volatility_with_insufficient_data(self, economic_intelligence):
        """Test calculate_volatility with insufficient price data - covers line 301"""
        # Create price history with only 1 price point
        price_history = [
            PriceData(
                item_code="test_item", timestamp=datetime.now(), buy_price=100, sell_price=100, quantity_available=10
            )
        ]

        result = economic_intelligence.calculate_volatility(price_history)
        assert result == 0.0

    def test_calculate_demand_score_with_zero_average_quantity(self, economic_intelligence):
        """Test calculate_demand_score when average quantity is zero - covers line 347"""
        # Create price history with zero quantities
        price_history = [
            PriceData(
                item_code="test_item",
                timestamp=datetime.now() - timedelta(hours=1),
                buy_price=100,
                sell_price=100,
                quantity_available=0,
            ),
            PriceData(
                item_code="test_item", timestamp=datetime.now(), buy_price=110, sell_price=110, quantity_available=0
            ),
        ]

        result = economic_intelligence.calculate_demand_score(price_history)
        assert result == 0.0

    def test_calculate_demand_score_with_empty_price_history(self, economic_intelligence):
        """Test calculate_demand_score with empty price history - covers line 349"""
        price_history = []

        result = economic_intelligence.calculate_demand_score(price_history)
        assert result == 0.0

    async def test_get_profitable_crafting_opportunities_with_no_current_prices(self, economic_intelligence):
        """Test get_profitable_crafting_opportunities when no current prices available - covers line 519"""
        # Mock to return empty prices
        economic_intelligence.data_collector = AsyncMock()
        economic_intelligence.data_collector.fetch_current_prices.return_value = {}

        result = await economic_intelligence.get_profitable_crafting_opportunities()
        assert result == []

    def test_calculate_crafting_profit_margin_with_missing_material_price(self, economic_intelligence):
        """Test calculate_crafting_profit_margin when material price is missing - covers lines 562-566"""
        recipe = Mock()
        recipe.code = "test_recipe"
        recipe.items = [Mock(code="missing_material", quantity=5), Mock(code="available_material", quantity=3)]
        recipe.quantity = 1

        current_prices = {
            "test_recipe": PriceData(
                item_code="test_recipe",
                timestamp=datetime.now(),
                buy_price=1000,
                sell_price=1000,
                quantity_available=10,
            ),
            "available_material": PriceData(
                item_code="available_material",
                timestamp=datetime.now(),
                buy_price=50,
                sell_price=50,
                quantity_available=10,
            ),
            # "missing_material" is intentionally missing
        }

        result = economic_intelligence.calculate_crafting_profit_margin(recipe, current_prices)
        assert result is None

    def test_calculate_crafting_profit_margin_with_missing_recipe_price(self, economic_intelligence):
        """Test calculate_crafting_profit_margin when recipe price is missing - covers line 568"""
        recipe = Mock()
        recipe.code = "missing_recipe"
        recipe.items = [Mock(code="material1", quantity=5)]
        recipe.quantity = 1

        current_prices = {
            "material1": PriceData(
                item_code="material1", timestamp=datetime.now(), buy_price=50, sell_price=50, quantity_available=10
            )
            # "missing_recipe" price is intentionally missing
        }

        result = economic_intelligence.calculate_crafting_profit_margin(recipe, current_prices)
        assert result is None

    def test_identify_market_manipulation_with_normal_prices(self, economic_intelligence):
        """Test identify_market_manipulation with normal price variations - covers lines 584-585"""
        # Create price history with normal variations (within expected range)
        base_time = datetime.now()
        price_history = []

        for i in range(10):
            price_history.append(
                PriceData(
                    item_code="test_item",
                    timestamp=base_time - timedelta(hours=i),
                    buy_price=100 + (i % 3),  # Small variations: 100, 101, 102, 100, 101, etc.
                    sell_price=100 + (i % 3),
                    quantity_available=10,
                )
            )

        result = economic_intelligence.identify_market_manipulation(price_history)
        assert result == []

    def test_identify_market_manipulation_with_insufficient_data(self, economic_intelligence):
        """Test identify_market_manipulation with insufficient price data - covers line 587"""
        # Create price history with only 1 data point
        price_history = [
            PriceData(
                item_code="test_item", timestamp=datetime.now(), buy_price=100, sell_price=100, quantity_available=10
            )
        ]

        result = economic_intelligence.identify_market_manipulation(price_history)
        assert result == []

    def test_calculate_seasonal_adjustment_with_insufficient_data(self, economic_intelligence):
        """Test calculate_seasonal_adjustment with insufficient historical data - covers line 600"""
        # Create price history with less than 7 days of data
        base_time = datetime.now()
        price_history = [
            PriceData(item_code="test_item", timestamp=base_time, buy_price=100, sell_price=100, quantity_available=10)
        ]

        result = economic_intelligence.calculate_seasonal_adjustment(price_history)
        assert result == 1.0

    def test_calculate_seasonal_adjustment_with_no_weekly_data(self, economic_intelligence):
        """Test calculate_seasonal_adjustment when no data for specific weekday - covers line 602"""
        # Create price history that doesn't include current weekday
        current_weekday = datetime.now().weekday()
        target_weekday = (current_weekday + 1) % 7  # Different weekday

        base_time = datetime.now() - timedelta(days=7)
        price_history = []

        # Add 7 days of data but skip the current weekday
        for i in range(7):
            day_time = base_time + timedelta(days=i)
            if day_time.weekday() != current_weekday:
                price_history.append(
                    PriceData(
                        item_code="test_item", timestamp=day_time, buy_price=100, sell_price=100, quantity_available=10
                    )
                )

        result = economic_intelligence.calculate_seasonal_adjustment(price_history)
        assert result == 1.0
