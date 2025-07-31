"""
Tests for Economic Data Collection

This module tests the MarketDataCollector class for collecting and managing
market data from the Grand Exchange API.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ai_player.economic_data_collection import MarketDataCollector
from src.ai_player.economic_models import PriceData


class TestMarketDataCollector:
    """Test MarketDataCollector class"""
    
    def test_init(self):
        """Test MarketDataCollector initialization"""
        api_client = Mock()
        collector = MarketDataCollector(api_client)
        
        assert collector.api_client is api_client
        assert collector.price_history == {}
        assert collector.last_update == {}
    
    @pytest.mark.asyncio
    @patch('src.ai_player.economic_data_collection.get_ge_orders')
    @patch('src.ai_player.economic_data_collection.Client')
    async def test_fetch_current_prices_success(self, mock_client, mock_get_orders):
        """Test successful current price fetching"""
        # Setup mock response
        mock_order = Mock()
        mock_order.price = 100
        mock_order.quantity = 50
        
        mock_response = Mock()
        mock_response.data = [mock_order]
        mock_get_orders.return_value = mock_response
        
        api_client = Mock()
        collector = MarketDataCollector(api_client)
        
        result = await collector.fetch_current_prices(['copper_ore'])
        
        assert 'copper_ore' in result
        price_data = result['copper_ore']
        assert isinstance(price_data, PriceData)
        assert price_data.item_code == 'copper_ore'
        assert price_data.buy_price == 100
        assert price_data.sell_price == 100
        assert price_data.quantity_available == 50
        assert 'copper_ore' in collector.last_update
    
    @pytest.mark.asyncio
    @patch('src.ai_player.economic_data_collection.get_ge_orders')
    @patch('src.ai_player.economic_data_collection.Client')
    async def test_fetch_current_prices_empty_response(self, mock_client, mock_get_orders):
        """Test handling empty API response"""
        mock_get_orders.return_value = None
        
        api_client = Mock()
        collector = MarketDataCollector(api_client)
        
        result = await collector.fetch_current_prices(['copper_ore'])
        
        assert result == {}
    
    @pytest.mark.asyncio
    @patch('src.ai_player.economic_data_collection.get_ge_orders')
    @patch('src.ai_player.economic_data_collection.Client')
    async def test_fetch_current_prices_exception(self, mock_client, mock_get_orders):
        """Test handling API exceptions"""
        mock_get_orders.side_effect = Exception("API Error")
        
        api_client = Mock()
        collector = MarketDataCollector(api_client)
        
        result = await collector.fetch_current_prices(['copper_ore'])
        
        assert result == {}
    
    @pytest.mark.asyncio
    @patch('src.ai_player.economic_data_collection.get_ge_history')
    @patch('src.ai_player.economic_data_collection.Client')
    async def test_fetch_market_history_success(self, mock_client, mock_get_history):
        """Test successful market history fetching"""
        # Setup mock sale
        mock_sale = Mock()
        mock_sale.sold_at = datetime.now() - timedelta(days=1)
        mock_sale.price = 100
        mock_sale.quantity = 10
        
        mock_response = Mock()
        mock_response.data = [mock_sale]
        mock_get_history.return_value = mock_response
        
        api_client = Mock()
        collector = MarketDataCollector(api_client)
        
        result = await collector.fetch_market_history('copper_ore', days=7)
        
        assert len(result) == 1
        price_data = result[0]
        assert isinstance(price_data, PriceData)
        assert price_data.item_code == 'copper_ore'
        assert price_data.buy_price == 100
        assert price_data.sell_price == 100
        assert price_data.quantity_available == 10
    
    @pytest.mark.asyncio
    @patch('src.ai_player.economic_data_collection.get_ge_history')
    @patch('src.ai_player.economic_data_collection.Client')
    async def test_fetch_market_history_old_data_filtered(self, mock_client, mock_get_history):
        """Test that old data is filtered out"""
        # Setup mock sale that's too old
        mock_sale = Mock()
        mock_sale.sold_at = datetime.now() - timedelta(days=10)
        mock_sale.price = 100
        mock_sale.quantity = 10
        
        mock_response = Mock()
        mock_response.data = [mock_sale]
        mock_get_history.return_value = mock_response
        
        api_client = Mock()
        collector = MarketDataCollector(api_client)
        
        result = await collector.fetch_market_history('copper_ore', days=7)
        
        assert len(result) == 0
    
    @pytest.mark.asyncio
    @patch('src.ai_player.economic_data_collection.get_ge_history')
    @patch('src.ai_player.economic_data_collection.Client')
    async def test_fetch_market_history_exception(self, mock_client, mock_get_history):
        """Test handling API exceptions in history fetch"""
        mock_get_history.side_effect = Exception("API Error")
        
        api_client = Mock()
        collector = MarketDataCollector(api_client)
        
        result = await collector.fetch_market_history('copper_ore')
        
        assert result == []
    
    def test_store_price_data_new_item(self):
        """Test storing price data for new item"""
        api_client = Mock()
        collector = MarketDataCollector(api_client)
        
        price_data = PriceData(
            item_code='copper_ore',
            timestamp=datetime.now(),
            buy_price=100,
            sell_price=120,
            quantity_available=50
        )
        
        collector.store_price_data(price_data)
        
        assert 'copper_ore' in collector.price_history
        assert len(collector.price_history['copper_ore']) == 1
        assert collector.price_history['copper_ore'][0] is price_data
    
    def test_store_price_data_existing_item(self):
        """Test storing additional price data for existing item"""
        api_client = Mock()
        collector = MarketDataCollector(api_client)
        
        price_data1 = PriceData(
            item_code='copper_ore',
            timestamp=datetime.now() - timedelta(hours=1),
            buy_price=100,
            sell_price=120,
            quantity_available=50
        )
        
        price_data2 = PriceData(
            item_code='copper_ore',
            timestamp=datetime.now(),
            buy_price=110,
            sell_price=130,
            quantity_available=45
        )
        
        collector.store_price_data(price_data1)
        collector.store_price_data(price_data2)
        
        assert len(collector.price_history['copper_ore']) == 2
        # Should be sorted by timestamp
        assert collector.price_history['copper_ore'][0].buy_price == 100
        assert collector.price_history['copper_ore'][1].buy_price == 110
    
    def test_store_price_data_max_history_limit(self):
        """Test that price history is limited to max size"""
        api_client = Mock()
        collector = MarketDataCollector(api_client)
        
        # Store more than max history size
        base_time = datetime.now()
        for i in range(1100):  # More than 1000 max
            price_data = PriceData(
                item_code='copper_ore',
                timestamp=base_time + timedelta(minutes=i),
                buy_price=100 + i,
                sell_price=120 + i,
                quantity_available=50
            )
            collector.store_price_data(price_data)
        
        # Should be limited to 1000
        assert len(collector.price_history['copper_ore']) == 1000
        # Should keep the most recent ones
        assert collector.price_history['copper_ore'][-1].buy_price == 1199
    
    def test_get_price_history_empty(self):
        """Test getting price history for non-existent item"""
        api_client = Mock()
        collector = MarketDataCollector(api_client)
        
        result = collector.get_price_history('copper_ore')
        
        assert result == []
    
    def test_get_price_history_with_data(self):
        """Test getting price history with time filtering"""
        api_client = Mock()
        collector = MarketDataCollector(api_client)
        
        # Add old data (should be filtered out)
        old_price_data = PriceData(
            item_code='copper_ore',
            timestamp=datetime.now() - timedelta(hours=30),
            buy_price=100,
            sell_price=120,
            quantity_available=50
        )
        
        # Add recent data (should be included)
        recent_price_data = PriceData(
            item_code='copper_ore',
            timestamp=datetime.now() - timedelta(hours=1),
            buy_price=110,
            sell_price=130,
            quantity_available=45
        )
        
        collector.store_price_data(old_price_data)
        collector.store_price_data(recent_price_data)
        
        result = collector.get_price_history('copper_ore', hours=24)
        
        assert len(result) == 1
        assert result[0].buy_price == 110
    
    def test_cleanup_old_data(self):
        """Test cleanup of old price data"""
        api_client = Mock()
        collector = MarketDataCollector(api_client)
        
        # Add old data
        old_price_data = PriceData(
            item_code='copper_ore',
            timestamp=datetime.now() - timedelta(days=40),
            buy_price=100,
            sell_price=120,
            quantity_available=50
        )
        
        # Add recent data
        recent_price_data = PriceData(
            item_code='copper_ore',
            timestamp=datetime.now() - timedelta(days=1),
            buy_price=110,
            sell_price=130,
            quantity_available=45
        )
        
        collector.store_price_data(old_price_data)
        collector.store_price_data(recent_price_data)
        
        collector.cleanup_old_data(max_age_days=30)
        
        assert len(collector.price_history['copper_ore']) == 1
        assert collector.price_history['copper_ore'][0].buy_price == 110
    
    def test_cleanup_old_data_removes_empty_items(self):
        """Test that items with no data after cleanup are removed"""
        api_client = Mock()
        collector = MarketDataCollector(api_client)
        
        # Add only old data
        old_price_data = PriceData(
            item_code='copper_ore',
            timestamp=datetime.now() - timedelta(days=40),
            buy_price=100,
            sell_price=120,
            quantity_available=50
        )
        
        collector.store_price_data(old_price_data)
        collector.cleanup_old_data(max_age_days=30)
        
        assert 'copper_ore' not in collector.price_history
    
    @pytest.mark.asyncio
    async def test_update_all_tracked_items_empty(self):
        """Test updating tracked items when none exist"""
        api_client = Mock()
        collector = MarketDataCollector(api_client)
        
        await collector.update_all_tracked_items()
        
        # Should not crash and no items to update
        assert collector.price_history == {}
    
    @pytest.mark.asyncio
    @patch.object(MarketDataCollector, 'fetch_current_prices')
    async def test_update_all_tracked_items_with_data(self, mock_fetch):
        """Test updating tracked items with existing data"""
        api_client = Mock()
        collector = MarketDataCollector(api_client)
        
        # Setup existing tracking
        collector.price_history['copper_ore'] = []
        collector.price_history['iron_ore'] = []
        
        # Mock fetch response
        mock_price_data = PriceData(
            item_code='copper_ore',
            timestamp=datetime.now(),
            buy_price=100,
            sell_price=120,
            quantity_available=50
        )
        mock_fetch.return_value = {'copper_ore': mock_price_data}
        
        await collector.update_all_tracked_items()
        
        mock_fetch.assert_called_once_with(['copper_ore', 'iron_ore'])
        assert len(collector.price_history['copper_ore']) == 1
    
    def test_add_item_to_tracking_new(self):
        """Test adding new item to tracking"""
        api_client = Mock()
        collector = MarketDataCollector(api_client)
        
        collector.add_item_to_tracking('copper_ore')
        
        assert 'copper_ore' in collector.price_history
        assert collector.price_history['copper_ore'] == []
    
    def test_add_item_to_tracking_existing(self):
        """Test adding already tracked item doesn't reset data"""
        api_client = Mock()
        collector = MarketDataCollector(api_client)
        
        # Setup existing data
        price_data = PriceData(
            item_code='copper_ore',
            timestamp=datetime.now(),
            buy_price=100,
            sell_price=120,
            quantity_available=50
        )
        collector.price_history['copper_ore'] = [price_data]
        
        collector.add_item_to_tracking('copper_ore')
        
        # Should not reset existing data
        assert len(collector.price_history['copper_ore']) == 1
    
    def test_remove_item_from_tracking(self):
        """Test removing item from tracking"""
        api_client = Mock()
        collector = MarketDataCollector(api_client)
        
        # Setup data
        collector.price_history['copper_ore'] = []
        collector.last_update['copper_ore'] = datetime.now()
        
        collector.remove_item_from_tracking('copper_ore')
        
        assert 'copper_ore' not in collector.price_history
        assert 'copper_ore' not in collector.last_update
    
    def test_remove_item_from_tracking_nonexistent(self):
        """Test removing non-existent item doesn't crash"""
        api_client = Mock()
        collector = MarketDataCollector(api_client)
        
        # Should not crash
        collector.remove_item_from_tracking('copper_ore')
        
        assert 'copper_ore' not in collector.price_history
        assert 'copper_ore' not in collector.last_update