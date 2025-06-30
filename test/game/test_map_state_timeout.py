"""Unit tests for MapState cache timeout behavior."""

import unittest
import tempfile
import time
import os
from unittest.mock import Mock, patch, MagicMock
from src.game.map.state import MapState
from test.fixtures import create_mock_client


class TestMapStateTimeout(unittest.TestCase):
    """Test MapState cache timeout and refresh behavior."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_prefix = os.environ.get('DATA_PREFIX', '')
        os.environ['DATA_PREFIX'] = self.temp_dir
        
        self.mock_client = create_mock_client()
        self.mock_response = Mock()
        self.mock_data = Mock()
        self.mock_data.to_dict.return_value = {
            'x': 0, 'y': 0, 'type': 'grass', 'content': None,
            'name': 'test_location'
        }
        self.mock_response.data = self.mock_data

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['DATA_PREFIX'] = self.original_data_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('src.game.map.state.get_map_x_y')
    def test_cache_timeout_default_3_minutes(self, mock_get_map):
        """Test that default cache timeout is 3 minutes (180 seconds)."""
        mock_get_map.return_value = self.mock_response
        
        # Create MapState with default timeout
        map_state = MapState(self.mock_client, initial_scan=False)
        
        # Verify default timeout is 180 seconds (3 minutes)
        self.assertEqual(map_state.cache_duration, 180)

    def test_cache_freshness_within_timeout(self):
        """Test that cache is considered fresh within timeout period."""
        # Create MapState with 10 second timeout for predictable testing
        map_state = MapState(self.mock_client, cache_duration=10, initial_scan=False)
        
        # Manually set fresh data
        import time
        current_time = time.time()
        map_state.data["0,0"] = {
            "x": 0, "y": 0, "content": None,
            "last_scanned": current_time - 2  # 2 seconds ago (fresh)
        }
        
        # Check freshness - should be fresh (2s < 10s timeout)
        self.assertTrue(map_state.is_cache_fresh(0, 0))

    @patch('src.game.map.state.get_map_x_y')
    def test_cache_expiration_after_timeout(self, mock_get_map):
        """Test that cache expires after timeout period."""
        mock_get_map.return_value = self.mock_response
        
        # Create MapState with very short timeout for testing
        map_state = MapState(self.mock_client, cache_duration=0.1, initial_scan=False)
        
        # Scan a location
        map_state.scan(0, 0)
        self.assertTrue(map_state.is_cache_fresh(0, 0))
        
        # Wait for cache to expire
        time.sleep(0.2)
        
        # Check freshness after expiration - should be stale
        self.assertFalse(map_state.is_cache_fresh(0, 0))

    @patch('src.game.map.state.get_map_x_y')
    def test_cache_refresh_on_expired_scan(self, mock_get_map):
        """Test that scan() refreshes cache when data is expired."""
        mock_get_map.return_value = self.mock_response
        
        # Create MapState with short timeout
        map_state = MapState(self.mock_client, cache_duration=0.1, initial_scan=False)
        
        # Initial scan
        map_state.scan(0, 0)
        self.assertEqual(mock_get_map.call_count, 1)
        
        # Wait for cache to expire
        time.sleep(0.2)
        
        # Scan again - should trigger new API call
        map_state.scan(0, 0)
        self.assertEqual(mock_get_map.call_count, 2)

    def test_cache_no_refresh_when_fresh(self):
        """Test that scan() does not refresh cache when data is fresh."""
        # Create MapState with longer timeout
        map_state = MapState(self.mock_client, cache_duration=10, initial_scan=False)
        
        # Manually set fresh data
        import time
        current_time = time.time()
        map_state.data["0,0"] = {
            "x": 0, "y": 0, "content": None,
            "last_scanned": current_time - 2  # 2 seconds ago (fresh)
        }
        
        # Mock the scan method to track calls
        from unittest.mock import Mock
        original_api_call = map_state._client
        map_state._client = Mock()
        
        # Scan should not make API call because cache is fresh
        result = map_state.scan(0, 0)
        
        # Should return cached data without API call
        self.assertIsNotNone(result)
        map_state._client.assert_not_called()

    def test_cache_timeout_different_locations(self):
        """Test that cache timeout works independently for different locations."""
        # Create MapState with 10 second timeout for easy calculation
        map_state = MapState(self.mock_client, cache_duration=10, initial_scan=False)
        
        # Manually set timestamps to simulate different scan times
        current_time = time.time()
        
        # First location scanned 12 seconds ago (expired)
        map_state.data["0,0"] = {
            "x": 0, "y": 0, "content": None,
            "last_scanned": current_time - 12
        }
        
        # Second location scanned 5 seconds ago (fresh)
        map_state.data["1,1"] = {
            "x": 1, "y": 1, "content": None,
            "last_scanned": current_time - 5
        }
        
        # First location should be expired (12s > 10s), second still fresh (5s < 10s)
        self.assertFalse(map_state.is_cache_fresh(0, 0))
        self.assertTrue(map_state.is_cache_fresh(1, 1))

    def test_cache_data_structure_includes_timestamp(self):
        """Test that cached data includes last_scanned timestamp."""
        map_state = MapState(self.mock_client, cache_duration=10, initial_scan=False)
        
        # Manually add data with timestamp
        import time
        scan_time = time.time()
        coord_key = "0,0"
        map_state.data[coord_key] = {
            "x": 0, "y": 0, "content": None,
            "last_scanned": scan_time
        }
        
        # Check that cached data has timestamp
        self.assertIn(coord_key, map_state.data)
        self.assertIn('last_scanned', map_state.data[coord_key])
        
        # Verify timestamp exists and is correct
        timestamp = map_state.data[coord_key]['last_scanned']
        self.assertEqual(timestamp, scan_time)

    @patch('src.game.map.state.get_map_x_y')
    def test_cache_disabled_with_cache_false(self, mock_get_map):
        """Test that caching can be disabled by passing cache=False to scan()."""
        mock_get_map.return_value = self.mock_response
        
        map_state = MapState(self.mock_client, cache_duration=10, initial_scan=False)
        
        # Scan with caching disabled
        map_state.scan(0, 0, cache=False)
        self.assertEqual(mock_get_map.call_count, 1)
        
        # Scan again with caching disabled - should make new API call
        map_state.scan(0, 0, cache=False)
        self.assertEqual(mock_get_map.call_count, 2)

    @patch('src.game.map.state.get_map_x_y')
    def test_cache_custom_timeout_parameter(self, mock_get_map):
        """Test that custom cache timeout can be set during initialization."""
        mock_get_map.return_value = self.mock_response
        
        # Create MapState with custom timeout
        custom_timeout = 300  # 5 minutes
        map_state = MapState(self.mock_client, cache_duration=custom_timeout, initial_scan=False)
        
        # Verify custom timeout is set
        self.assertEqual(map_state.cache_duration, custom_timeout)

    @patch('src.game.map.state.get_map_x_y')
    def test_cache_missing_data_structure(self, mock_get_map):
        """Test cache freshness check with missing or malformed data."""
        mock_get_map.return_value = self.mock_response
        
        map_state = MapState(self.mock_client, cache_duration=10, initial_scan=False)
        
        # Test with completely missing coordinate
        self.assertFalse(map_state.is_cache_fresh(99, 99))
        
        # Test with coordinate that has malformed data (not a dict)
        map_state.data["0,0"] = "not_a_dict"
        self.assertFalse(map_state.is_cache_fresh(0, 0))  # Should handle gracefully
        
        # Test with coordinate missing timestamp
        map_state.data["0,0"] = {"x": 0, "y": 0, "content": None}  # No last_scanned
        self.assertFalse(map_state.is_cache_fresh(0, 0))


if __name__ == '__main__':
    unittest.main()