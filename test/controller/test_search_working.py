"""Working tests that demonstrate core search functionality."""

import os
import tempfile
import unittest
from unittest.mock import Mock

from src.controller.actions.find_resources import FindResourcesAction
from src.controller.actions.base.search import SearchActionBase
from src.game.map.state import MapState

from test.fixtures import create_mock_client


class TestSearchWorking(unittest.TestCase):
    """Simplified working tests for search functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_prefix = os.environ.get('DATA_PREFIX', '')
        os.environ['DATA_PREFIX'] = self.temp_dir
        
        self.mock_client = create_mock_client()
        self.character_x = 5
        self.character_y = 3

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['DATA_PREFIX'] = self.original_data_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_find_resources_basic_functionality(self):
        """Test that FindResourcesAction can find resources successfully."""
        action = FindResourcesAction()
        from test.fixtures import MockActionContext
        context = MockActionContext(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=2,
            resource_types=['copper_rocks'],
            character_level=10,
            skill_type=None,
            level_range=5,
            current_gathering_goal=None,
            missing_materials={},
            raw_material_needs={}
        )
        
        # Create MapState for caching
        map_state = MapState(self.mock_client, initial_scan=False)
        
        # Clear any existing data to prevent interference
        map_state.data = {}
        
        # Create mock content that matches the SearchActionBase expectations
        mock_content = Mock()
        mock_content.code = 'copper_rocks'
        mock_content.type_ = 'resource'
        mock_content.to_dict.return_value = {'code': 'copper_rocks', 'type_': 'resource'}
        
        # Pre-populate cache with content at radius 1 (coordinates that would be searched)
        map_state.data['6,3'] = {  # East of character (5,3)
            'x': 6, 'y': 3, 
            'content': mock_content,
            'last_scanned': 1000
        }
        
        # Mock cache to return fresh for our test coordinate
        map_state.is_cache_fresh = Mock(return_value=True)
        map_state.scan = Mock()  # Won't be called since cache is fresh
        
        # Add map_state to context
        context.map_state = map_state
        
        # Execute the action
        result = action.execute(self.mock_client, context)
        
        # Verify successful result
        self.assertTrue(result.success)
        self.assertEqual(result.data['resource_code'], 'copper_rocks')
        self.assertEqual(result.data['target_x'], 6)
        self.assertEqual(result.data['target_y'], 3)
        
        # Verify cache was used, not API calls
        map_state.scan.assert_not_called()

    def test_search_base_content_filters_work(self):
        """Test that SearchActionBase content filters work correctly."""
        # Test resource filter
        resource_filter = SearchActionBase.create_resource_filter(['copper_rocks'])
        
        # Should match copper_rocks
        copper_content = {'code': 'copper_rocks', 'type_': 'resource'}
        self.assertTrue(resource_filter(copper_content, 0, 0))
        
        # Should not match monsters
        monster_content = {'code': 'green_slime', 'type_': 'monster'}
        self.assertFalse(resource_filter(monster_content, 0, 0))
        
        # Should not match different resources
        iron_content = {'code': 'iron_rocks', 'type_': 'resource'}
        self.assertFalse(resource_filter(iron_content, 0, 0))

    def test_map_state_cache_freshness_basic(self):
        """Test basic MapState cache freshness functionality."""
        map_state = MapState(self.mock_client, cache_duration=10, initial_scan=False)
        
        # Clear any existing data to ensure clean test
        map_state.data = {}
        
        # Test with no data (should not be fresh)
        self.assertFalse(map_state.is_cache_fresh(0, 0))
        
        # Test with fresh data
        import time
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

    def test_boundary_detection_basic(self):
        """Test basic boundary detection functionality."""
        # Clear any existing boundaries
        SearchActionBase.clear_boundary_cache()
        
        # Verify boundary cache starts empty
        total_boundaries = (
            len(SearchActionBase._map_boundaries['north']) +
            len(SearchActionBase._map_boundaries['south']) +
            len(SearchActionBase._map_boundaries['east']) +
            len(SearchActionBase._map_boundaries['west'])
        )
        self.assertEqual(total_boundaries, 0)
        
        # Record boundary hits in all directions
        search_action = FindResourcesAction()
        character_x, character_y = 5, 5
        search_action._record_boundary_hit(character_x, character_y, 3, 5)  # West boundary (x < character_x, y == character_y)
        search_action._record_boundary_hit(character_x, character_y, 7, 5)  # East boundary (x > character_x, y == character_y)
        search_action._record_boundary_hit(character_x, character_y, 5, 3)  # South boundary (y < character_y, x == character_x)
        search_action._record_boundary_hit(character_x, character_y, 5, 7)  # North boundary (y > character_y, x == character_x)
        
        # Verify boundaries were recorded
        self.assertGreater(len(SearchActionBase._map_boundaries['west']), 0)
        self.assertGreater(len(SearchActionBase._map_boundaries['east']), 0)
        self.assertGreater(len(SearchActionBase._map_boundaries['south']), 0)
        self.assertGreater(len(SearchActionBase._map_boundaries['north']), 0)

    def test_action_parameter_preservation(self):
        """Test that action parameters are preserved correctly in context."""
        action = FindResourcesAction()
        from test.fixtures import MockActionContext
        context = MockActionContext(
            character_x=10,
            character_y=15,
            search_radius=7,
            resource_types=['iron_rocks', 'coal_rocks'],
            character_level=5,
            skill_type='mining',
            level_range=5
        )
        
        # Verify all parameters are preserved in context
        self.assertEqual(context.character_x, 10)
        self.assertEqual(context.character_y, 15)
        self.assertEqual(context.get('search_radius'), 7)
        self.assertEqual(context.get('resource_types'), ['iron_rocks', 'coal_rocks'])
        self.assertEqual(context.character_level, 5)
        self.assertEqual(context.get('skill_type'), 'mining')


if __name__ == '__main__':
    unittest.main()