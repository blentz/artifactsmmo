"""Unit tests for SearchActionBase MapState caching integration."""

import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from src.controller.actions.search_base import SearchActionBase
from src.game.map.state import MapState

from test.fixtures import create_mock_client


class TestSearchBaseCaching(unittest.TestCase):
    """Test SearchActionBase MapState caching integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = create_mock_client()
        self.search_action = SearchActionBase()
        self.character_x = 5
        self.character_y = 3
        self.search_radius = 2
        
        # Create temporary MapState for testing
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        self.temp_file.close()
        
        # Mock MapState with short cache duration for testing
        self.map_state = Mock(spec=MapState)
        self.map_state.data = {}
        self.map_state.cache_duration = 1  # 1 second for quick testing

    def tearDown(self):
        """Clean up test fixtures."""
        import os
        try:
            os.unlink(self.temp_file.name)
        except:
            pass

    def test_unified_search_with_mapstate_cache_hit(self):
        """Test unified search uses MapState cache when data is fresh."""
        # Setup fresh cache hit - place content at radius 1 from character (5,3)
        self.map_state.is_cache_fresh.return_value = True
        # Create mock content object that has the expected attributes
        mock_content = Mock()
        mock_content.code = 'copper_rocks'
        mock_content.type_ = 'resource'
        mock_content.to_dict.return_value = {'code': 'copper_rocks', 'type_': 'resource'}
        
        self.map_state.data = {
            '6,3': {  # This is at radius 1 from character at (5,3)
                'x': 6, 'y': 3, 
                'content': mock_content,
                'last_scanned': time.time()
            }
        }
        
        # Create content filter that matches copper_rocks
        def content_filter(content_dict, x, y):
            return content_dict.get('code') == 'copper_rocks'
        
        # Execute search
        result = self.search_action.unified_search(
            self.mock_client,
            self.character_x,
            self.character_y,
            self.search_radius,
            content_filter, 
            map_state=self.map_state
        )
        
        # Verify cache was used (is_cache_fresh called but scan not called)
        self.map_state.is_cache_fresh.assert_called()
        self.map_state.scan.assert_not_called()
        
        # Verify successful result
        self.assertTrue(result['success'])
        self.assertEqual(result['location'], (6, 3))
        self.assertEqual(result['content_code'], 'copper_rocks')

    def test_unified_search_with_mapstate_cache_miss(self):
        """Test unified search refreshes cache when data is stale."""
        # Setup cache miss
        self.map_state.is_cache_fresh.return_value = False
        
        # Mock scan to update cache
        def mock_scan(x, y, cache=True):
            coord_key = f"{x},{y}"
            # Create mock content object for iron_rocks
            mock_iron_content = Mock()
            mock_iron_content.code = 'iron_rocks'
            mock_iron_content.type_ = 'resource'
            mock_iron_content.to_dict.return_value = {'code': 'iron_rocks', 'type_': 'resource'}
            
            self.map_state.data[coord_key] = {
                'x': x, 'y': y, 'content': mock_iron_content,
                'last_scanned': time.time()
            }
            return self.map_state.data  # Return the data structure like real scan() does
        
        self.map_state.scan.side_effect = mock_scan
        
        # Create content filter that matches iron_rocks
        def content_filter(content_dict, x, y):
            return content_dict.get('code') == 'iron_rocks'
        
        # Execute search
        result = self.search_action.unified_search(
            self.mock_client,
            self.character_x,
            self.character_y,
            self.search_radius,
            content_filter,
            map_state=self.map_state
        )
        
        # Verify cache refresh was triggered
        self.map_state.is_cache_fresh.assert_called()
        self.map_state.scan.assert_called()
        
        # Verify successful result
        self.assertTrue(result['success'])
        self.assertEqual(result['content_code'], 'iron_rocks')

    def test_unified_search_without_mapstate_fallback(self):
        """Test unified search falls back to direct API when MapState unavailable."""
        # Mock API response
        mock_response = Mock()
        mock_response.data = Mock()
        
        # Create mock content for coal_rocks
        mock_coal_content = Mock()
        mock_coal_content.code = 'coal_rocks'
        mock_coal_content.type_ = 'resource'
        mock_coal_content.to_dict.return_value = {'code': 'coal_rocks', 'type_': 'resource'}
        
        mock_response.data.to_dict.return_value = {
            'x': 6, 'y': 3, 'content': mock_coal_content  # Place at radius 1
        }
        
        # Create content filter
        def content_filter(content_dict, x, y):
            return content_dict.get('code') == 'coal_rocks'
        
        with patch('src.controller.actions.search_base.get_map_api', return_value=mock_response):
            # Execute search without MapState
            result = self.search_action.unified_search(
                self.mock_client,
                self.character_x,
                self.character_y,
                self.search_radius,
                content_filter,
                map_state=None  # No MapState provided
            )
        
        # Verify successful result using direct API
        self.assertTrue(result['success'])
        self.assertEqual(result['content_code'], 'coal_rocks')

    def test_unified_search_with_mapstate_scan_exception(self):
        """Test unified search handles MapState scan exceptions."""
        # Setup cache miss
        self.map_state.is_cache_fresh.return_value = False
        
        # Mock scan to raise 404 exception (boundary case)
        self.map_state.scan.side_effect = Exception("404")
        
        # Create content filter
        def content_filter(content_dict, x, y):
            return True
        
        # Execute search - should handle exception gracefully
        result = self.search_action.unified_search(
            self.mock_client,
            self.character_x,
            self.character_y,
            self.search_radius,
            content_filter,
            map_state=self.map_state
        )
        
        # Verify exception was handled (no content found due to boundary)
        self.assertFalse(result['success'])
        self.assertIn("No matching content found", result.get('error', ''))

    def test_content_filter_factory_methods_work_with_cache(self):
        """Test that built-in content filters work with cached data."""
        # Setup cached data with various content types
        self.map_state.is_cache_fresh.return_value = True
        
        # Create mock content objects for different types
        mock_copper = Mock()
        mock_copper.code = 'copper_rocks'
        mock_copper.type_ = 'resource'
        mock_copper.to_dict.return_value = {'code': 'copper_rocks', 'type_': 'resource'}
        
        mock_slime = Mock()
        mock_slime.code = 'green_slime'
        mock_slime.type_ = 'monster'
        mock_slime.to_dict.return_value = {'code': 'green_slime', 'type_': 'monster'}
        
        mock_workshop = Mock()
        mock_workshop.code = 'weaponcrafting'
        mock_workshop.type_ = 'workshop'
        mock_workshop.to_dict.return_value = {'code': 'weaponcrafting', 'type_': 'workshop'}
        
        self.map_state.data = {
            '4,3': {  # Radius 1 west
                'content': mock_copper,
                'last_scanned': time.time()
            },
            '5,4': {  # Radius 1 south
                'content': mock_slime,
                'last_scanned': time.time()
            },
            '6,3': {  # Radius 1 east
                'content': mock_workshop,
                'last_scanned': time.time()
            }
        }
        
        # Test resource filter
        resource_filter = SearchActionBase.create_resource_filter(['copper_rocks'])
        result = self.search_action.unified_search(
            self.mock_client,
            self.character_x,
            self.character_y,
            self.search_radius,
            resource_filter,
            map_state=self.map_state
        )
        self.assertTrue(result['success'])
        self.assertEqual(result['content_code'], 'copper_rocks')
        
        # Test monster filter  
        monster_filter = SearchActionBase.create_monster_filter(['green_slime'])
        result = self.search_action.unified_search(
            self.mock_client,
            self.character_x,
            self.character_y,
            self.search_radius,
            monster_filter,
            map_state=self.map_state
        )
        self.assertTrue(result['success'])
        self.assertEqual(result['content_code'], 'green_slime')
        
        # Test workshop filter
        workshop_filter = SearchActionBase.create_workshop_filter('weaponcrafting')
        result = self.search_action.unified_search(
            self.mock_client,
            self.character_x,
            self.character_y,
            self.search_radius,
            workshop_filter,
            map_state=self.map_state
        )
        self.assertTrue(result['success'])
        self.assertEqual(result['content_code'], 'weaponcrafting')

    def test_boundary_detection_integrates_with_cache(self):
        """Test that boundary detection works properly with MapState caching."""
        # Setup cache miss
        self.map_state.is_cache_fresh.return_value = False
        
        # Mock scan to raise boundary exception
        self.map_state.scan.side_effect = Exception("404 not found")
        
        # Create content filter
        def content_filter(content_dict, x, y):
            return True
        
        # Execute search
        result = self.search_action.unified_search(
            self.mock_client,
            self.character_x,
            self.character_y,
            self.search_radius,
            content_filter,
            map_state=self.map_state
        )
        
        # Verify boundary was recorded
        self.assertTrue(len(SearchActionBase._map_boundaries['north']) + 
                       len(SearchActionBase._map_boundaries['south']) + 
                       len(SearchActionBase._map_boundaries['east']) + 
                       len(SearchActionBase._map_boundaries['west']) > 0)
        
        # Clear boundaries for other tests
        SearchActionBase.clear_boundary_cache()


if __name__ == '__main__':
    unittest.main()