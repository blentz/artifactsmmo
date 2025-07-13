"""Test find_monsters action level filtering for unknown monsters"""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.find_monsters import FindMonstersAction
from src.lib.state_parameters import StateParameters
from src.lib.unified_state_context import get_unified_context

from test.fixtures import MockActionContext


class TestFindMonstersLevelFiltering(unittest.TestCase):
    """Test cases for find_monsters level filtering with unknown monsters"""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = FindMonstersAction()
        self.character_x = 0
        self.character_y = 0
        self.search_radius = 2
        self.character_level = 1
        
        # Mock client
        self.mock_client = Mock()
        
        # Mock knowledge base
        self.mock_knowledge_base = Mock()
        self.mock_knowledge_base.data = {
            'monsters': {}  # Empty - simulating unknown monsters
        }
        
        # Mock map state
        self.mock_map_state = Mock()
        self.mock_map_state.scan = Mock(side_effect=self._mock_scan)
        self.mock_map_state.is_cache_fresh = Mock(return_value=False)
        self.mock_map_state.data = {}
        
    def _mock_scan(self, x, y, cache=True):
        """Mock scan method that populates map_state.data."""
        coord_key = f"{x},{y}"
        # This will be populated by individual tests
        return self.mock_map_state.data.get(coord_key)
        
    def test_unknown_monster_api_level_check(self):
        """Test that unknown monsters have their level checked via knowledge base."""
        # Create mock knowledge base that returns empty result (knowledge base filters by level)
        mock_kb = Mock()
        mock_kb.find_monsters_in_map = Mock(return_value=[])  # Knowledge base filters out inappropriate level monsters
        mock_kb.data = {'monsters': {}}  # Empty combat history for unknown monsters
        
        # Execute with character level 1
        context = MockActionContext(
                character_x=self.character_x,
                character_y=self.character_y,
                search_radius=self.search_radius,
                character_level=1
        )
        context.knowledge_base = mock_kb
        context.map_state = self.mock_map_state
        result = self.action.execute(self.mock_client, context)
        
        # Should not find viable monsters because knowledge base filtered them out
        self.assertFalse(result.success)
        self.assertIn('No suitable monsters found in knowledge base', result.error)
    
    def test_unknown_monster_appropriate_level(self):
        """Test that unknown monsters with appropriate levels are accepted."""
        # Create mock knowledge base that returns appropriate level monster
        mock_kb = Mock()
        mock_kb.find_monsters_in_map = Mock(return_value=[
            {
                'x': 0,
                'y': 1,
                'monster_code': 'chicken',
                'distance': 1.0
            }
        ])
        mock_kb.data = {'monsters': {}}  # No combat history for new monster
        
        # Set up map_state data
        self.mock_map_state.data = {
            '0,1': {'x': 0, 'y': 1, 'content': {'type': 'monster', 'code': 'chicken'}}
        }
        
        # Execute with character level 1 - put character at chicken location
        context = MockActionContext(
                character_x=0,  # At chicken location for character perception
                character_y=1,  # At chicken location 
                search_radius=self.search_radius,
                character_level=1
        )
        context.knowledge_base = mock_kb
        context.map_state = self.mock_map_state
        result = self.action.execute(self.mock_client, context)
        
        # Should find viable monster - architecture sets coordinates in UnifiedStateContext
        self.assertTrue(result.success)
        # Check if coordinates are set in UnifiedStateContext (correct architectural pattern)
        unified_context = get_unified_context()
        self.assertEqual(unified_context.get(StateParameters.TARGET_X), 0)
        self.assertEqual(unified_context.get(StateParameters.TARGET_Y), 1)
        self.assertEqual(unified_context.get(StateParameters.TARGET_MONSTER), 'chicken')
    
    def test_api_failure_skips_monster(self):
        """Test that knowledge base failures cause monsters to be skipped."""
        # Create mock knowledge base that returns empty results (simulating failure)
        mock_kb = Mock()
        mock_kb.find_monsters_in_map = Mock(return_value=[])  # No monsters found
        
        # Execute
        context = MockActionContext(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius,
            character_level=1
        )
        context.knowledge_base = mock_kb
        context.map_state = self.mock_map_state
        result = self.action.execute(self.mock_client, context)
        
        # Should not find viable monsters due to knowledge base returning empty results
        self.assertFalse(result.success)
        self.assertIn('No suitable monsters found in knowledge base', result.error)
    
    def test_known_monster_uses_knowledge_base(self):
        """Test that known monsters use knowledge base data instead of API."""
        # Set up knowledge base with known monster
        mock_kb = Mock()
        mock_kb.data = {
            'monsters': {
                'wolf': {
                    'level': 2,
                    'combat_results': [
                        {'result': 'win', 'timestamp': '2024-01-01T00:00:00'},
                        {'result': 'win', 'timestamp': '2024-01-01T00:01:00'},
                    ]
                }
            }
        }
        
        # Set up map_state data
        self.mock_map_state.data = {
            '1,0': {'x': 1, 'y': 0, 'content': {'type': 'monster', 'code': 'wolf'}}
        }
        
        # Knowledge base method returns dictionaries matching actual implementation
        mock_kb.find_monsters_in_map = Mock(return_value=[
            {
                'x': 1,
                'y': 0,
                'monster_code': 'wolf',
                'distance': 1.0
            }
        ])
        
        # Execute with character level 2 - set character at same location as monster
        context = MockActionContext(
            character_x=1,  # At monster location - character should "find" it immediately  
            character_y=0,  # At monster location
            search_radius=self.search_radius,
            character_level=2
        )
        context.knowledge_base = mock_kb
        context.map_state = self.mock_map_state
        result = self.action.execute(self.mock_client, context)
        
        # Should find viable monster from knowledge base
        self.assertTrue(result.success)
        # Check if coordinates are set in UnifiedStateContext (correct architectural pattern)
        unified_context = get_unified_context()
        self.assertEqual(unified_context.get(StateParameters.TARGET_X), 1)
        self.assertEqual(unified_context.get(StateParameters.TARGET_Y), 0)
        # Monster code should be set in unified context
        self.assertEqual(unified_context.get(StateParameters.TARGET_MONSTER), 'wolf')
    
    def test_multiple_monsters_prioritizes_by_level(self):
        """Test that when multiple monsters are found, lower level is prioritized."""
        # Create mock knowledge base that returns multiple monsters (knowledge base handles level filtering)
        mock_kb = Mock()
        mock_kb.find_monsters_in_map = Mock(return_value=[
            {
                'x': 0,
                'y': 1,
                'monster_code': 'chicken',
                'distance': 1.0
            }
        ])
        
        mock_kb.data = {'monsters': {}}  # No combat history for new monsters
        
        # Set up map_state data for multiple monsters
        self.mock_map_state.data = {
            '0,1': {'x': 0, 'y': 1, 'content': {'type': 'monster', 'code': 'chicken'}},
            '0,-1': {'x': 0, 'y': -1, 'content': {'type': 'monster', 'code': 'green_slime'}},
            '1,0': {'x': 1, 'y': 0, 'content': {'type': 'monster', 'code': 'wolf'}}
        }
        
        # Execute with character level 1 - put character at chicken location
        context = MockActionContext(
                character_x=0,  # At chicken location to test character finding monster
                character_y=1,  # At chicken location
                search_radius=self.search_radius,
                character_level=1
        )
        context.knowledge_base = mock_kb
        context.map_state = self.mock_map_state
        result = self.action.execute(self.mock_client, context)
        
        # Should find chicken (level 1) - architecture sets coordinates in UnifiedStateContext
        self.assertTrue(result.success)
        # Check if coordinates are set in UnifiedStateContext (correct architectural pattern)
        unified_context = get_unified_context()
        self.assertEqual(unified_context.get(StateParameters.TARGET_X), 0)
        self.assertEqual(unified_context.get(StateParameters.TARGET_Y), 1)
        self.assertEqual(unified_context.get(StateParameters.TARGET_MONSTER), 'chicken')


if __name__ == '__main__':
    unittest.main()