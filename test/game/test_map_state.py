"""Comprehensive unit tests for MapState class."""

import unittest
import tempfile
import os
import time
from unittest.mock import patch, Mock, MagicMock
from src.game.map.state import MapState
from test.fixtures import create_mock_client


class TestMapState(unittest.TestCase):
    """Test cases for MapState class with proper isolation."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = create_mock_client()
        # Create temporary directory for test data
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: os.rmdir(self.temp_dir) if os.path.exists(self.temp_dir) else None)

    @patch('src.game.map.state.DATA_PREFIX')
    def test_map_state_initialization_default_name(self, mock_data_prefix):
        """Test MapState initialization with default name."""
        mock_data_prefix.__str__ = Mock(return_value=self.temp_dir)
        mock_data_prefix.__add__ = Mock(return_value=f"{self.temp_dir}/map.yaml")
        
        with patch('src.game.map.state.YamlData.__init__', return_value=None):
            with patch.object(MapState, 'scan', return_value={}):
                state = MapState(self.mock_client)
                
                self.assertEqual(state._client, self.mock_client)
                self.assertIsInstance(state.data, dict)

    @patch('src.game.map.state.DATA_PREFIX')
    def test_map_state_initialization_no_initial_scan(self, mock_data_prefix):
        """Test MapState initialization with initial_scan=False."""
        mock_data_prefix.__str__ = Mock(return_value=self.temp_dir)
        mock_data_prefix.__add__ = Mock(return_value=f"{self.temp_dir}/map.yaml")
        
        with patch('src.game.map.state.YamlData.__init__', return_value=None):
            state = MapState(self.mock_client, initial_scan=False)
            
            # Should not have any scan data
            self.assertEqual(state.data, {})
            self.assertEqual(state._client, self.mock_client)

    @patch('src.game.map.state.DATA_PREFIX')
    def test_map_state_initialization_no_client(self, mock_data_prefix):
        """Test MapState initialization without client."""
        mock_data_prefix.__str__ = Mock(return_value=self.temp_dir)
        mock_data_prefix.__add__ = Mock(return_value=f"{self.temp_dir}/map.yaml")
        
        with patch('src.game.map.state.YamlData.__init__', return_value=None):
            state = MapState(None)
            
            # Should handle no client gracefully
            self.assertIsNone(state._client)
            self.assertEqual(state.data, {})

    @patch('src.game.map.state.DATA_PREFIX')
    @patch('time.time', return_value=1000.0)
    @patch('src.game.map.state.get_map_x_y')
    def test_scan_success(self, mock_get_map, mock_time, mock_data_prefix):
        """Test successful scan operation."""
        mock_data_prefix.__str__ = Mock(return_value=self.temp_dir)
        mock_data_prefix.__add__ = Mock(return_value=f"{self.temp_dir}/map.yaml")
        
        # Mock API response
        mock_response = Mock()
        mock_map_data = Mock()
        mock_map_data.to_dict.return_value = {
            'name': 'test_location',
            'content': {'type': 'resource', 'code': 'iron_ore'},
            'x': 5,
            'y': 10
        }
        mock_response.data = mock_map_data
        mock_get_map.return_value = mock_response
        
        with patch('src.game.map.state.YamlData.__init__', return_value=None):
            with patch.object(MapState, 'save'):
                state = MapState(self.mock_client, initial_scan=False)
                state.data = {}  # Ensure empty data
                
                # Perform scan
                result = state.scan(5, 10)
                
                # Verify API was called
                mock_get_map.assert_called_with(5, 10, client=self.mock_client)
                
                # Verify data was stored
                self.assertIn('5,10', state.data)
                self.assertEqual(state.data['5,10']['x'], 5)
                self.assertEqual(state.data['5,10']['y'], 10)
                self.assertEqual(state.data['5,10']['last_scanned'], 1000.0)
                
                # Verify result is returned
                self.assertEqual(result, state.data)

    @patch('src.game.map.state.DATA_PREFIX')
    @patch('src.game.map.state.get_map_x_y')
    def test_scan_boundary_response(self, mock_get_map, mock_data_prefix):
        """Test scan with boundary response (404)."""
        mock_data_prefix.__str__ = Mock(return_value=self.temp_dir)
        mock_data_prefix.__add__ = Mock(return_value=f"{self.temp_dir}/map.yaml")
        
        # Mock API returning None for boundary
        mock_get_map.return_value = None
        
        with patch('src.game.map.state.YamlData.__init__', return_value=None):
            state = MapState(self.mock_client, initial_scan=False)
            state.data = {}
            
            # Perform scan
            result = state.scan(100, 100)
            
            # Should return None and not store data
            self.assertIsNone(result)
            self.assertNotIn('100,100', state.data)

    @patch('src.game.map.state.DATA_PREFIX')
    @patch('time.time', return_value=1000.0)
    def test_is_cache_fresh(self, mock_time, mock_data_prefix):
        """Test cache freshness checking."""
        mock_data_prefix.__str__ = Mock(return_value=self.temp_dir)
        mock_data_prefix.__add__ = Mock(return_value=f"{self.temp_dir}/map.yaml")
        
        with patch('src.game.map.state.YamlData.__init__', return_value=None):
            state = MapState(self.mock_client, initial_scan=False, cache_duration=300)
            state.data = {}
            
            # Test with no data
            self.assertFalse(state.is_cache_fresh(5, 10))
            
            # Test with fresh data (100 seconds ago)
            state.data['5,10'] = {'last_scanned': 900.0}  # 100 seconds ago
            self.assertTrue(state.is_cache_fresh(5, 10))
            
            # Test with expired data (400 seconds ago)
            state.data['5,10'] = {'last_scanned': 600.0}  # 400 seconds ago
            self.assertFalse(state.is_cache_fresh(5, 10))
            
            # Test with missing last_scanned
            state.data['5,10'] = {'x': 5, 'y': 10}
            self.assertFalse(state.is_cache_fresh(5, 10))

    @patch('src.game.map.state.DATA_PREFIX')
    @patch('time.time', return_value=1000.0)
    @patch('src.game.map.state.get_map_x_y')
    def test_scan_with_cache_hit(self, mock_get_map, mock_time, mock_data_prefix):
        """Test scan with cache hit."""
        mock_data_prefix.__str__ = Mock(return_value=self.temp_dir)
        mock_data_prefix.__add__ = Mock(return_value=f"{self.temp_dir}/map.yaml")
        
        with patch('src.game.map.state.YamlData.__init__', return_value=None):
            state = MapState(self.mock_client, initial_scan=False, cache_duration=300)
            
            # Add fresh cached data
            state.data = {
                '5,10': {
                    'x': 5,
                    'y': 10,
                    'last_scanned': 950.0  # 50 seconds ago, within 300s cache
                }
            }
            
            # Perform scan
            result = state.scan(5, 10, cache=True)
            
            # Should not call API due to cache hit
            mock_get_map.assert_not_called()
            
            # Should return cached data
            self.assertEqual(result, state.data)

    @patch('src.game.map.state.DATA_PREFIX')
    @patch('time.time', return_value=1000.0)
    @patch('src.game.map.state.get_map_x_y')
    def test_scan_with_cache_miss(self, mock_get_map, mock_time, mock_data_prefix):
        """Test scan with cache miss (expired)."""
        mock_data_prefix.__str__ = Mock(return_value=self.temp_dir)
        mock_data_prefix.__add__ = Mock(return_value=f"{self.temp_dir}/map.yaml")
        
        # Mock fresh API response
        mock_response = Mock()
        mock_map_data = Mock()
        mock_map_data.to_dict.return_value = {'x': 5, 'y': 10}
        mock_response.data = mock_map_data
        mock_get_map.return_value = mock_response
        
        with patch('src.game.map.state.YamlData.__init__', return_value=None):
            with patch.object(MapState, 'save'):
                state = MapState(self.mock_client, initial_scan=False, cache_duration=300)
                
                # Add expired cached data
                state.data = {
                    '5,10': {
                        'x': 5,
                        'y': 10,
                        'last_scanned': 600.0  # 400 seconds ago, beyond 300s cache
                    }
                }
                
                # Perform scan
                result = state.scan(5, 10, cache=True)
                
                # Should call API due to cache miss
                mock_get_map.assert_called_once_with(5, 10, client=self.mock_client)
                
                # Should update data with new timestamp
                self.assertEqual(state.data['5,10']['last_scanned'], 1000.0)

    @patch('src.game.map.state.DATA_PREFIX')
    def test_set_learning_callback(self, mock_data_prefix):
        """Test setting learning callback."""
        mock_data_prefix.__str__ = Mock(return_value=self.temp_dir)
        mock_data_prefix.__add__ = Mock(return_value=f"{self.temp_dir}/map.yaml")
        
        with patch('src.game.map.state.YamlData.__init__', return_value=None):
            state = MapState(self.mock_client, initial_scan=False)
            
            callback = Mock()
            state.set_learning_callback(callback)
            
            self.assertEqual(state._learning_callback, callback)

    @patch('src.game.map.state.DATA_PREFIX')
    @patch('time.time', return_value=1000.0)
    @patch('src.game.map.state.get_map_x_y')
    def test_scan_with_learning_callback(self, mock_get_map, mock_time, mock_data_prefix):
        """Test scan triggering learning callback."""
        mock_data_prefix.__str__ = Mock(return_value=self.temp_dir)
        mock_data_prefix.__add__ = Mock(return_value=f"{self.temp_dir}/map.yaml")
        
        # Mock API response with content
        mock_response = Mock()
        mock_map_data = Mock()
        mock_map_data.content = {'type': 'resource', 'code': 'iron_ore'}  # Has content
        mock_map_data.to_dict.return_value = {
            'content': {'type': 'resource', 'code': 'iron_ore'}
        }
        mock_response.data = mock_map_data
        mock_get_map.return_value = mock_response
        
        with patch('src.game.map.state.YamlData.__init__', return_value=None):
            with patch.object(MapState, 'save'):
                state = MapState(self.mock_client, initial_scan=False)
                state.data = {}
                
                # Set learning callback
                callback = Mock()
                state.set_learning_callback(callback)
                
                # Perform scan
                state.scan(5, 10)
                
                # Callback should be called
                callback.assert_called_once_with(5, 10, mock_response)


if __name__ == '__main__':
    unittest.main()