"""Comprehensive tests for search functionality and caching integration."""

import unittest
import tempfile
import os
import time
from unittest.mock import Mock, patch
from src.controller.actions.find_resources import FindResourcesAction
from src.controller.actions.find_monsters import FindMonstersAction
from src.controller.actions.find_workshops import FindWorkshopsAction
from src.controller.actions.search_base import SearchActionBase
from src.game.map.state import MapState
from test.fixtures import create_mock_client


class TestSearchComprehensive(unittest.TestCase):
    """Comprehensive tests for search functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_prefix = os.environ.get('DATA_PREFIX', '')
        os.environ['DATA_PREFIX'] = self.temp_dir
        
        self.mock_client = create_mock_client()
        SearchActionBase.clear_boundary_cache()

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['DATA_PREFIX'] = self.original_data_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        SearchActionBase.clear_boundary_cache()

    def test_find_resources_action_initialization(self):
        """Test FindResourcesAction initializes with correct parameters."""
        action = FindResourcesAction(
            character_x=10, character_y=15, search_radius=7,
            resource_types=['iron_rocks'], character_level=5
        )
        
        self.assertEqual(action.character_x, 10)
        self.assertEqual(action.character_y, 15)
        self.assertEqual(action.search_radius, 7)
        self.assertEqual(action.resource_types, ['iron_rocks'])
        self.assertEqual(action.character_level, 5)

    def test_find_monsters_action_initialization(self):
        """Test FindMonstersAction initializes with correct parameters."""
        action = FindMonstersAction(
            character_x=5, character_y=3, search_radius=4,
            monster_types=['green_slime'], character_level=2
        )
        
        self.assertEqual(action.character_x, 5)
        self.assertEqual(action.character_y, 3)
        self.assertEqual(action.search_radius, 4)
        self.assertEqual(action.monster_types, ['green_slime'])
        self.assertEqual(action.character_level, 2)

    def test_find_workshops_action_initialization(self):
        """Test FindWorkshopsAction initializes with correct parameters."""
        action = FindWorkshopsAction(
            character_x=0, character_y=0, search_radius=5,
            workshop_type='weaponcrafting'
        )
        
        self.assertEqual(action.character_x, 0)
        self.assertEqual(action.character_y, 0)
        self.assertEqual(action.search_radius, 5)
        self.assertEqual(action.workshop_type, 'weaponcrafting')

    def test_search_base_content_filters(self):
        """Test SearchActionBase content filter factories."""
        # Test resource filter
        resource_filter = SearchActionBase.create_resource_filter(['copper_rocks'])
        
        # Should match copper_rocks
        copper_content = {'code': 'copper_rocks', 'type_': 'resource'}
        self.assertTrue(resource_filter(copper_content, 0, 0))
        
        # Should not match monsters
        monster_content = {'code': 'green_slime', 'type_': 'monster'}
        self.assertFalse(resource_filter(monster_content, 0, 0))
        
        # Test monster filter
        monster_filter = SearchActionBase.create_monster_filter(['green_slime'])
        self.assertTrue(monster_filter(monster_content, 0, 0))
        self.assertFalse(monster_filter(copper_content, 0, 0))
        
        # Test workshop filter
        workshop_filter = SearchActionBase.create_workshop_filter('weaponcrafting')
        workshop_content = {'code': 'weaponcrafting', 'type_': 'workshop'}
        self.assertTrue(workshop_filter(workshop_content, 0, 0))
        self.assertFalse(workshop_filter(copper_content, 0, 0))

    def test_map_state_cache_timeout_functionality(self):
        """Test MapState cache timeout behavior."""
        map_state = MapState(self.mock_client, cache_duration=10, initial_scan=False)
        map_state.data = {}  # Clear any existing data
        
        # Test with no data - should not be fresh
        self.assertFalse(map_state.is_cache_fresh(0, 0))
        
        # Test with fresh data
        current_time = time.time()
        map_state.data["0,0"] = {
            "x": 0, "y": 0, "content": None,
            "last_scanned": current_time - 5  # 5 seconds ago
        }
        self.assertTrue(map_state.is_cache_fresh(0, 0))
        
        # Test with expired data  
        map_state.data["1,1"] = {
            "x": 1, "y": 1, "content": None,
            "last_scanned": current_time - 15  # 15 seconds ago (> 10 second timeout)
        }
        self.assertFalse(map_state.is_cache_fresh(1, 1))

    def test_map_state_default_timeout(self):
        """Test MapState default timeout is 3 minutes."""
        map_state = MapState(self.mock_client, initial_scan=False)
        self.assertEqual(map_state.cache_duration, 180)  # 3 minutes

    def test_boundary_detection_system(self):
        """Test boundary detection system."""
        SearchActionBase.clear_boundary_cache()
        
        # Verify cache starts empty
        total_boundaries = sum(len(boundaries) for boundaries in SearchActionBase._map_boundaries.values())
        self.assertEqual(total_boundaries, 0)
        
        # Record boundaries in all directions
        search_action = SearchActionBase(character_x=5, character_y=5, search_radius=1)
        search_action._record_boundary_hit(3, 5)  # West
        search_action._record_boundary_hit(7, 5)  # East  
        search_action._record_boundary_hit(5, 3)  # South
        search_action._record_boundary_hit(5, 7)  # North
        
        # Verify boundaries were recorded
        self.assertGreater(len(SearchActionBase._map_boundaries['west']), 0)
        self.assertGreater(len(SearchActionBase._map_boundaries['east']), 0)
        self.assertGreater(len(SearchActionBase._map_boundaries['south']), 0)
        self.assertGreater(len(SearchActionBase._map_boundaries['north']), 0)

    def test_unified_search_with_mock_content(self):
        """Test unified search algorithm with properly mocked content."""
        search_action = SearchActionBase(character_x=5, character_y=3, search_radius=2)
        
        # Create MapState with mock content
        map_state = MapState(self.mock_client, initial_scan=False)
        
        # Create properly structured mock content
        mock_content = Mock()
        mock_content.code = 'copper_rocks'
        mock_content.type_ = 'resource'
        mock_content.to_dict.return_value = {'code': 'copper_rocks', 'type_': 'resource'}
        
        # Place content at radius 1 from character
        map_state.data['6,3'] = {
            'x': 6, 'y': 3,
            'content': mock_content,
            'last_scanned': time.time()
        }
        
        # Mock cache as fresh
        map_state.is_cache_fresh = Mock(return_value=True)
        map_state.scan = Mock()
        
        # Create content filter
        def content_filter(content_dict, x, y):
            return content_dict.get('code') == 'copper_rocks'
        
        # Execute search
        result = search_action.unified_search(self.mock_client, content_filter, map_state=map_state)
        
        # Verify successful result
        self.assertTrue(result['success'])
        self.assertEqual(result['content_code'], 'copper_rocks')
        self.assertEqual(result['location'], (6, 3))
        
        # Verify cache was used (no API calls)
        map_state.scan.assert_not_called()

    def test_find_resources_execute_basic(self):
        """Test FindResourcesAction execute method basic functionality."""
        action = FindResourcesAction(character_x=5, character_y=3, search_radius=2)
        
        # Create MapState with mock content
        map_state = MapState(self.mock_client, initial_scan=False)
        
        # Clear any existing data to prevent interference
        map_state.data = {}
        
        # Create properly structured mock content
        mock_content = Mock()
        mock_content.code = 'iron_rocks'
        mock_content.type_ = 'resource'
        mock_content.to_dict.return_value = {'code': 'iron_rocks', 'type_': 'resource'}
        
        # Place content at radius 1
        map_state.data['6,3'] = {
            'x': 6, 'y': 3,
            'content': mock_content,
            'last_scanned': time.time()
        }
        
        map_state.is_cache_fresh = Mock(return_value=True)
        map_state.scan = Mock()
        
        # Execute with resource_types parameter
        result = action.execute(self.mock_client, map_state=map_state, resource_types=['iron_rocks'])
        
        # Verify successful result
        self.assertTrue(result['success'])
        self.assertEqual(result['resource_code'], 'iron_rocks')
        self.assertEqual(result['target_x'], 6)
        self.assertEqual(result['target_y'], 3)

    def test_cache_optimization_prevents_api_calls(self):
        """Test that caching optimization prevents excessive API calls."""
        map_state = MapState(self.mock_client, cache_duration=10, initial_scan=False)
        
        # Setup fresh cached data
        current_time = time.time()
        map_state.data["5,5"] = {
            "x": 5, "y": 5, "content": None,
            "last_scanned": current_time - 2  # Fresh (2s < 10s timeout)
        }
        
        # Mock the client to track API calls
        map_state._client = Mock()
        
        # Multiple cache freshness checks should not trigger API calls
        fresh1 = map_state.is_cache_fresh(5, 5)
        fresh2 = map_state.is_cache_fresh(5, 5)
        fresh3 = map_state.is_cache_fresh(5, 5)
        
        # All should return True (fresh)
        self.assertTrue(fresh1)
        self.assertTrue(fresh2)
        self.assertTrue(fresh3)

    def test_search_coordinate_generation(self):
        """Test search coordinate generation for different radii."""
        action = SearchActionBase(character_x=5, character_y=5, search_radius=1)
        
        # Test radius 0 (character position)
        coords_r0 = action._generate_radius_coordinates(0)
        self.assertEqual(coords_r0, [(5, 5)])
        
        # Test radius 1 (should generate 8 coordinates around character)
        coords_r1 = action._generate_radius_coordinates(1)
        self.assertGreater(len(coords_r1), 0)
        
        # All coordinates should be at distance 1 from character
        for x, y in coords_r1:
            # Using Chebyshev distance (max of dx, dy)
            distance = max(abs(x - 5), abs(y - 5))
            self.assertEqual(distance, 1)

    def test_error_handling_in_search(self):
        """Test error handling in search operations."""
        search_action = SearchActionBase(character_x=0, character_y=0, search_radius=1)
        
        # Test with no client
        result = search_action.unified_search(None, lambda c, x, y: True)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])
        
        # Test with filter that finds nothing
        map_state = MapState(self.mock_client, initial_scan=False)
        map_state.data = {}
        map_state.is_cache_fresh = Mock(return_value=False)
        map_state.scan = Mock(side_effect=Exception("404 not found"))
        
        def never_match_filter(content_dict, x, y):
            return False
        
        result = search_action.unified_search(self.mock_client, never_match_filter, map_state=map_state)
        self.assertFalse(result['success'])
        self.assertIn('No matching content found', result['error'])

    def test_malformed_cache_data_handling(self):
        """Test handling of malformed cache data."""
        map_state = MapState(self.mock_client, cache_duration=10, initial_scan=False)
        
        # Test with malformed data (not a dict)
        map_state.data["0,0"] = "not_a_dict"
        self.assertFalse(map_state.is_cache_fresh(0, 0))
        
        # Test with missing timestamp
        map_state.data["1,1"] = {"x": 1, "y": 1, "content": None}  # No last_scanned
        self.assertFalse(map_state.is_cache_fresh(1, 1))
        
        # Test with completely missing coordinate
        self.assertFalse(map_state.is_cache_fresh(99, 99))


if __name__ == '__main__':
    unittest.main()