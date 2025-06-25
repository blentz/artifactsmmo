"""Test module for MapState."""

import unittest
from unittest.mock import patch, Mock
from src.game.map.state import MapState


class TestMapState(unittest.TestCase):
    """Test cases for MapState."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()

    @patch('src.game.map.state.DATA_PREFIX', '/tmp/test_data')
    @patch('src.game.map.state.YamlData.__init__')
    @patch('src.game.map.state.MapState.scan')
    def test_map_state_initialization_default_name(self, mock_scan, mock_yaml_init):
        """Test MapState initialization with default name."""
        mock_yaml_init.return_value = None
        mock_scan.return_value = {"data": {"test": "data"}}
        
        state = MapState(self.mock_client)
        
        # Check that YamlData.__init__ was called with correct filename
        args, kwargs = mock_yaml_init.call_args
        self.assertEqual(kwargs['filename'], "/tmp/test_data/map.yaml")
        
        self.assertEqual(state._client, self.mock_client)
        self.assertEqual(state.data, {"test": "data"})
        mock_scan.assert_called_once_with(x=0, y=0)

    @patch('src.game.map.state.DATA_PREFIX', '/tmp/test_data')
    @patch('src.game.map.state.YamlData.__init__')
    @patch('src.game.map.state.MapState.scan')
    def test_map_state_initialization_custom_name(self, mock_scan, mock_yaml_init):
        """Test MapState initialization with custom name."""
        mock_yaml_init.return_value = None
        mock_scan.return_value = {"direct": "data"}
        
        state = MapState(self.mock_client, name="custom_map")
        
        # Check that YamlData.__init__ was called with correct filename
        args, kwargs = mock_yaml_init.call_args
        self.assertEqual(kwargs['filename'], "/tmp/test_data/custom_map.yaml")
        
        self.assertEqual(state._client, self.mock_client)
        self.assertEqual(state.data, {"direct": "data"})

    @patch('src.game.map.state.DATA_PREFIX', '/tmp/test_data')
    @patch('src.game.map.state.YamlData.__init__')
    @patch('src.game.map.state.MapState.scan')
    def test_map_state_initialization_no_data_key(self, mock_scan, mock_yaml_init):
        """Test MapState initialization when scan returns data without 'data' key."""
        mock_yaml_init.return_value = None
        mock_scan.return_value = {"direct": "data"}
        
        state = MapState(self.mock_client)
        
        self.assertEqual(state.data, {"direct": "data"})

    @patch('src.game.map.state.DATA_PREFIX', '/tmp/test_data')
    @patch('src.game.map.state.YamlData.__init__')
    @patch('src.game.map.state.MapState.scan')
    def test_map_state_initialization_none_data(self, mock_scan, mock_yaml_init):
        """Test MapState initialization when scan returns None."""
        mock_yaml_init.return_value = None
        mock_scan.return_value = None
        
        state = MapState(self.mock_client)
        
        self.assertIsNone(state.data)

    @patch('src.game.map.state.DATA_PREFIX', '/tmp/test_data')
    @patch('src.game.map.state.YamlData.__init__')
    @patch('src.game.map.state.get_map_x_y')
    def test_scan_with_cache_hit(self, mock_get_map_x_y, mock_yaml_init):
        """Test scan method with cache hit."""
        mock_yaml_init.return_value = None
        
        # Create MapState but mock the scan to avoid API call in __init__
        with patch.object(MapState, 'scan', return_value={}):
            state = MapState(self.mock_client)
        
        # Set up the data with cached entry
        state.data = {"5,3": {"cached": "tile"}}
        
        # Restore the real scan method for testing
        MapState.scan = MapState.__dict__['scan']
        
        result = state.scan(5, 3, cache=True)
        
        # Should return cached data, not call API
        mock_get_map_x_y.assert_not_called()
        self.assertEqual(result, {"5,3": {"cached": "tile"}})

    @patch('src.game.map.state.DATA_PREFIX', '/tmp/test_data')
    @patch('src.game.map.state.YamlData.__init__')
    @patch('src.game.map.state.get_map_x_y')
    def test_scan_with_cache_miss(self, mock_get_map_x_y, mock_yaml_init):
        """Test scan method with cache miss."""
        mock_yaml_init.return_value = None
        
        # Mock API response
        mock_tile_data = Mock()
        mock_tile_data.to_dict.return_value = {"new": "tile", "x": 5, "y": 3}
        
        mock_response = Mock()
        mock_response.data = mock_tile_data
        mock_get_map_x_y.return_value = mock_response
        
        # Create MapState but mock the scan to avoid API call in __init__
        with patch.object(MapState, 'scan', return_value={}):
            state = MapState(self.mock_client)
        
        # Set up empty data
        state.data = {}
        
        # Restore the real scan method for testing
        MapState.scan = MapState.__dict__['scan']
        
        result = state.scan(5, 3, cache=True)
        
        # Should call API and cache result
        mock_get_map_x_y.assert_called_once_with(5, 3, client=self.mock_client)
        expected_data = {"5,3": {"new": "tile", "x": 5, "y": 3}}
        self.assertEqual(result, expected_data)
        self.assertEqual(state.data, expected_data)

    @patch('src.game.map.state.DATA_PREFIX', '/tmp/test_data')
    @patch('src.game.map.state.YamlData.__init__')
    @patch('src.game.map.state.get_map_x_y')
    def test_scan_with_cache_disabled(self, mock_get_map_x_y, mock_yaml_init):
        """Test scan method with cache disabled."""
        mock_yaml_init.return_value = None
        
        # Mock API response
        mock_tile_data = Mock()
        mock_tile_data.to_dict.return_value = {"fresh": "tile"}
        
        mock_response = Mock()
        mock_response.data = mock_tile_data
        mock_get_map_x_y.return_value = mock_response
        
        # Create MapState but mock the scan to avoid API call in __init__
        with patch.object(MapState, 'scan', return_value={}):
            state = MapState(self.mock_client)
        
        # Set up data with existing entry
        state.data = {"10,15": {"cached": "tile"}}
        
        # Restore the real scan method for testing
        MapState.scan = MapState.__dict__['scan']
        
        result = state.scan(10, 15, cache=False)
        
        # Should call API even though data exists
        mock_get_map_x_y.assert_called_once_with(10, 15, client=self.mock_client)
        expected_data = {"10,15": {"fresh": "tile"}}
        self.assertEqual(state.data, expected_data)

    @patch('src.game.map.state.DATA_PREFIX', '/tmp/test_data')
    @patch('src.game.map.state.YamlData.__init__')
    @patch.object(MapState, 'scan')
    def test_scan_around(self, mock_scan, mock_yaml_init):
        """Test scan_around method."""
        mock_yaml_init.return_value = None
        
        # Create MapState but avoid API call in __init__
        with patch.object(MapState, 'scan', return_value={}):
            state = MapState(self.mock_client)
        
        # Set up mock data
        state.data = {"test": "data"}
        mock_scan.return_value = state.data
        
        # Restore the real scan_around method for testing
        MapState.scan = mock_scan
        
        result = state.scan_around(origin=(5, 3), radius=1)
        
        # Should call scan for each tile in the radius
        expected_calls = []
        for y in range(2, 5):  # 3-1 to 3+1+1
            for x in range(4, 7):  # 5-1 to 5+1+1
                expected_calls.append(unittest.mock.call(x, y))
        
        self.assertEqual(mock_scan.call_count, 9)  # 3x3 grid
        self.assertEqual(result, {"test": "data"})

    @patch('src.game.map.state.DATA_PREFIX', '/tmp/test_data')
    @patch('src.game.map.state.YamlData.__init__')
    @patch.object(MapState, 'scan_around')
    def test_scan_map_for_found(self, mock_scan_around, mock_yaml_init):
        """Test scan_map_for method when item is found."""
        mock_yaml_init.return_value = None
        
        # Create MapState but avoid API call in __init__
        with patch.object(MapState, 'scan', return_value={}):
            state = MapState(self.mock_client)
        
        # Mock tile with content
        mock_content = Mock()
        mock_content.type = 'resource'
        mock_content.code = 'copper'
        
        mock_tile = Mock()
        mock_tile.content = mock_content
        
        # Mock scan_around response - needs to be iterable
        mock_scan_around.return_value = [("5,3", mock_tile)]
        
        result = state.scan_map_for("copper", origin=(5, 3), radius=2)
        
        mock_scan_around.assert_called_once_with(origin=(5, 3), radius=2)
        self.assertEqual(result, {"5,3": mock_tile})

    @patch('src.game.map.state.DATA_PREFIX', '/tmp/test_data')
    @patch('src.game.map.state.YamlData.__init__')
    @patch.object(MapState, 'scan_around')
    def test_scan_map_for_found_by_type(self, mock_scan_around, mock_yaml_init):
        """Test scan_map_for method when item is found by type."""
        mock_yaml_init.return_value = None
        
        # Create MapState but avoid API call in __init__
        with patch.object(MapState, 'scan', return_value={}):
            state = MapState(self.mock_client)
        
        # Mock tile with content
        mock_content = Mock()
        mock_content.type = 'resource'
        mock_content.code = 'iron'
        
        mock_tile = Mock()
        mock_tile.content = mock_content
        
        # Mock scan_around response
        mock_scan_around.return_value = [("10,8", mock_tile)]
        
        result = state.scan_map_for("resource", origin=(10, 8), radius=1)
        
        self.assertEqual(result, {"10,8": mock_tile})

    @patch('src.game.map.state.DATA_PREFIX', '/tmp/test_data')
    @patch('src.game.map.state.YamlData.__init__')
    @patch.object(MapState, 'scan_around')
    def test_scan_map_for_not_found(self, mock_scan_around, mock_yaml_init):
        """Test scan_map_for method when item is not found."""
        mock_yaml_init.return_value = None
        
        # Create MapState but avoid API call in __init__
        with patch.object(MapState, 'scan', return_value={}):
            state = MapState(self.mock_client)
        
        # Mock tile without target content
        mock_content = Mock()
        mock_content.type = 'workshop'
        mock_content.code = 'weapon_workshop'
        
        mock_tile = Mock()
        mock_tile.content = mock_content
        
        # Mock scan_around response
        mock_scan_around.return_value = [("7,9", mock_tile)]
        
        result = state.scan_map_for("copper", origin=(7, 9), radius=1)
        
        self.assertEqual(result, {})

    @patch('src.game.map.state.DATA_PREFIX', '/tmp/test_data')
    @patch('src.game.map.state.YamlData.__init__')
    @patch.object(MapState, 'scan_around')
    def test_scan_map_for_no_content(self, mock_scan_around, mock_yaml_init):
        """Test scan_map_for method when tile has no content."""
        mock_yaml_init.return_value = None
        
        # Create MapState but avoid API call in __init__
        with patch.object(MapState, 'scan', return_value={}):
            state = MapState(self.mock_client)
        
        # Mock tile without content
        mock_tile = Mock()
        mock_tile.content = None
        
        # Mock scan_around response
        mock_scan_around.return_value = [("0,0", mock_tile)]
        
        result = state.scan_map_for("anything", origin=(0, 0), radius=1)
        
        self.assertEqual(result, {})

    def test_map_state_class_attributes(self):
        """Test MapState class attributes."""
        self.assertIsNone(MapState._client)
        self.assertIsNone(MapState.data)


if __name__ == '__main__':
    unittest.main()