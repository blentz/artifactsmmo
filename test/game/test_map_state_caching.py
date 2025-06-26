"""Unit tests for MapState caching functionality."""

import unittest
import tempfile
import time
from unittest.mock import Mock, patch

from src.game.map.state import MapState


class TestMapStateCaching(unittest.TestCase):
    
    def setUp(self):
        self.mock_client = Mock()
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @patch('src.game.map.state.get_map_x_y')
    def test_is_cache_fresh_no_data(self, mock_get_map):
        """Test cache freshness when no data exists."""
        with patch('src.game.map.state.DATA_PREFIX', self.temp_dir):
            map_state = MapState(client=self.mock_client, name="test_map", initial_scan=False, cache_duration=300)
            
            # No data exists for coordinates
            self.assertFalse(map_state.is_cache_fresh(5, 5))
    
    @patch('src.game.map.state.get_map_x_y')
    def test_is_cache_fresh_no_timestamp(self, mock_get_map):
        """Test cache freshness when data exists but no timestamp."""
        with patch('src.game.map.state.DATA_PREFIX', self.temp_dir):
            map_state = MapState(client=self.mock_client, name="test_map", initial_scan=False, cache_duration=300)
            
            # Add data without timestamp
            map_state.data["5,5"] = {"x": 5, "y": 5, "content": None}
            
            self.assertFalse(map_state.is_cache_fresh(5, 5))
    
    @patch('src.game.map.state.get_map_x_y')
    def test_is_cache_fresh_recent_timestamp(self, mock_get_map):
        """Test cache freshness with recent timestamp."""
        with patch('src.game.map.state.DATA_PREFIX', self.temp_dir):
            map_state = MapState(client=self.mock_client, name="test_map", initial_scan=False, cache_duration=300)
            
            # Add data with recent timestamp
            current_time = time.time()
            map_state.data["5,5"] = {
                "x": 5, "y": 5, "content": None,
                "last_scanned": current_time - 100  # 100 seconds ago, within 300 second cache
            }
            
            self.assertTrue(map_state.is_cache_fresh(5, 5))
    
    @patch('src.game.map.state.get_map_x_y')
    def test_is_cache_fresh_old_timestamp(self, mock_get_map):
        """Test cache freshness with old timestamp."""
        with patch('src.game.map.state.DATA_PREFIX', self.temp_dir):
            map_state = MapState(client=self.mock_client, name="test_map", initial_scan=False, cache_duration=300)
            
            # Add data with old timestamp
            current_time = time.time()
            map_state.data["5,5"] = {
                "x": 5, "y": 5, "content": None,
                "last_scanned": current_time - 400  # 400 seconds ago, beyond 300 second cache
            }
            
            self.assertFalse(map_state.is_cache_fresh(5, 5))
    
    @patch('src.game.map.state.get_map_x_y')
    def test_scan_uses_cache_when_fresh(self, mock_get_map):
        """Test that scan uses cache when data is fresh."""
        with patch('src.game.map.state.DATA_PREFIX', self.temp_dir):
            map_state = MapState(client=self.mock_client, name="test_map", initial_scan=False, cache_duration=300)
            
            # Pre-populate with fresh cache
            current_time = time.time()
            map_state.data["5,5"] = {
                "x": 5, "y": 5, "content": None,
                "last_scanned": current_time - 100  # Recent
            }
            
            # Scan should use cache and not call API
            result = map_state.scan(5, 5)
            
            self.assertIsNotNone(result)
            self.assertIn("5,5", result)
            mock_get_map.assert_not_called()
    
    @patch('src.game.map.state.get_map_x_y')
    def test_scan_calls_api_when_cache_stale(self, mock_get_map):
        """Test that scan calls API when cache is stale."""
        # Setup mock API response
        mock_tile = Mock()
        mock_tile.to_dict.return_value = {"x": 5, "y": 5, "content": None}
        mock_response = Mock()
        mock_response.data = mock_tile
        mock_get_map.return_value = mock_response
        
        with patch('src.game.map.state.DATA_PREFIX', self.temp_dir):
            map_state = MapState(client=self.mock_client, name="test_map", initial_scan=False, cache_duration=300)
            
            # Pre-populate with stale cache
            current_time = time.time()
            map_state.data["5,5"] = {
                "x": 5, "y": 5, "content": None,
                "last_scanned": current_time - 400  # Stale
            }
            
            # Scan should call API to refresh
            result = map_state.scan(5, 5, save_immediately=False)
            
            self.assertIsNotNone(result)
            mock_get_map.assert_called_once_with(5, 5, client=self.mock_client)
            
            # Verify cache was updated with new timestamp
            self.assertIn("5,5", map_state.data)
            self.assertIn("last_scanned", map_state.data["5,5"])
            self.assertGreater(map_state.data["5,5"]["last_scanned"], current_time - 50)
    
    @patch('src.game.map.state.get_map_x_y')
    def test_scan_calls_api_when_no_cache(self, mock_get_map):
        """Test that scan calls API when no cache exists."""
        # Setup mock API response
        mock_tile = Mock()
        mock_tile.to_dict.return_value = {"x": 5, "y": 5, "content": None}
        mock_tile.content = None
        mock_response = Mock()
        mock_response.data = mock_tile
        mock_get_map.return_value = mock_response
        
        with patch('src.game.map.state.DATA_PREFIX', self.temp_dir):
            map_state = MapState(client=self.mock_client, name="test_map", initial_scan=False, cache_duration=300)
            
            # No existing cache data
            self.assertEqual(len(map_state.data), 0)
            
            # Scan should call API
            result = map_state.scan(5, 5, save_immediately=False)
            
            self.assertIsNotNone(result)
            mock_get_map.assert_called_once_with(5, 5, client=self.mock_client)
            
            # Verify cache was created with timestamp
            self.assertIn("5,5", map_state.data)
            self.assertIn("last_scanned", map_state.data["5,5"])
    
    @patch('src.game.map.state.get_map_x_y')
    def test_cache_duration_customization(self, mock_get_map):
        """Test that custom cache duration is respected."""
        # Setup mock API response
        mock_tile = Mock()
        mock_tile.to_dict.return_value = {"x": 5, "y": 5, "content": None}
        mock_response = Mock()
        mock_response.data = mock_tile
        mock_get_map.return_value = mock_response
        
        with patch('src.game.map.state.DATA_PREFIX', self.temp_dir):
            # Short cache duration (60 seconds)
            map_state = MapState(client=self.mock_client, name="test_map", initial_scan=False, cache_duration=60)
            
            # Pre-populate with data that would be fresh for longer duration but stale for short duration
            current_time = time.time()
            map_state.data["5,5"] = {
                "x": 5, "y": 5, "content": None,
                "last_scanned": current_time - 100  # 100 seconds ago, beyond 60 second cache
            }
            
            # Should be considered stale with short cache duration
            self.assertFalse(map_state.is_cache_fresh(5, 5))
            
            # Scan should call API to refresh
            result = map_state.scan(5, 5, save_immediately=False)
            
            mock_get_map.assert_called_once()


if __name__ == '__main__':
    unittest.main()