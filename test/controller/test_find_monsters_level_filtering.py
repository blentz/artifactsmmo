"""Test find_monsters action level filtering for unknown monsters"""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.find_monsters import FindMonstersAction

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
        # Create mock knowledge base that returns monsters but filters by level
        mock_kb = Mock()
        mock_kb.find_monsters_in_map = Mock(return_value=[
            {
                'x': 1, 'y': 1, 'code': 'green_slime', 'level': 4,
                'monster_code': 'green_slime',
                'monster_data': {'level': 4},
                'content_data': {'type': 'monster', 'code': 'green_slime'},
                'distance': 1.4
            }
        ])
        mock_kb.get_monster_data = Mock(return_value={'level': 4})
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
        
        # Should not find viable monsters because level 4 > level 1 + 1
        self.assertFalse(result.success)
        self.assertIn('No viable monsters found within radius', result.error)
    
    def test_unknown_monster_appropriate_level(self):
        """Test that unknown monsters with appropriate levels are accepted."""
        # Create mock knowledge base that returns appropriate level monster
        mock_kb = Mock()
        mock_kb.find_monsters_in_map = Mock(return_value=[
            {
                'x': 0, 'y': 1, 'code': 'chicken', 'level': 1,
                'monster_code': 'chicken',
                'monster_data': {'level': 1},
                'content_data': {'type': 'monster', 'code': 'chicken'},
                'distance': 1.0
            }
        ])
        mock_kb.get_monster_data = Mock(return_value={'level': 1})
        mock_kb.data = {'monsters': {}}  # No combat history for new monster
        
        # Set up map_state data
        self.mock_map_state.data = {
            '0,1': {'x': 0, 'y': 1, 'content': {'type': 'monster', 'code': 'chicken'}}
        }
        
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
        
        # Should find viable monster because level 1 <= level 1 + 1
        self.assertTrue(result.success)
        self.assertEqual(result.data.get('target_x'), 0)
        self.assertEqual(result.data.get('target_y'), 1)
        self.assertEqual(result.data.get('monster_code'), 'chicken')
    
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
        self.assertIn('No suitable monsters found in cached map data within radius', result.error)
    
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
        mock_kb.find_monsters_in_map = Mock(return_value=[
            {
                'x': 1, 'y': 0, 'code': 'wolf', 'level': 2,
                'monster_code': 'wolf',
                'monster_data': {
                    'level': 2,
                    'combat_results': [
                        {'result': 'win', 'timestamp': '2024-01-01T00:00:00'},
                        {'result': 'win', 'timestamp': '2024-01-01T00:01:00'},
                    ]
                },
                'content_data': {'type': 'monster', 'code': 'wolf'},
                'distance': 1.0
            }
        ])
        mock_kb.get_monster_data = Mock(return_value={
            'level': 2,
            'combat_results': [
                {'result': 'win', 'timestamp': '2024-01-01T00:00:00'},
                {'result': 'win', 'timestamp': '2024-01-01T00:01:00'},
            ]
        })
        
        # Set up map_state data
        self.mock_map_state.data = {
            '1,0': {'x': 1, 'y': 0, 'content': {'type': 'monster', 'code': 'wolf'}}
        }
        
        # Execute with character level 2
        context = MockActionContext(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius,
            character_level=2
        )
        context.knowledge_base = mock_kb
        context.map_state = self.mock_map_state
        result = self.action.execute(self.mock_client, context)
        
        # Should find viable monster from knowledge base
        if not result.success:
            print(f"DEBUG: Result = {result}")
        self.assertTrue(result.success)
        self.assertEqual(result.data.get('target_x'), 1)
        self.assertEqual(result.data.get('target_y'), 0)
        self.assertEqual(result.data.get('monster_code'), 'wolf')
    
    def test_multiple_monsters_prioritizes_by_level(self):
        """Test that when multiple monsters are found, lower level is prioritized."""
        # Create mock knowledge base that returns multiple monsters
        mock_kb = Mock()
        mock_kb.find_monsters_in_map = Mock(return_value=[
            {
                'x': 0, 'y': 1, 'code': 'chicken', 'level': 1,
                'monster_code': 'chicken',
                'monster_data': {'level': 1},
                'content_data': {'type': 'monster', 'code': 'chicken'},
                'distance': 1.0
            },
            {
                'x': 1, 'y': 0, 'code': 'wolf', 'level': 2,
                'monster_code': 'wolf',
                'monster_data': {'level': 2},
                'content_data': {'type': 'monster', 'code': 'wolf'},
                'distance': 1.0
            }
            # green_slime (level 4) would be filtered out by knowledge base for character level 1
        ])
        
        def mock_get_monster_data(code, client=None):
            monster_levels = {
                'chicken': {'level': 1},
                'green_slime': {'level': 4},
                'wolf': {'level': 2}
            }
            return monster_levels.get(code)
        mock_kb.get_monster_data = Mock(side_effect=mock_get_monster_data)
        mock_kb.data = {'monsters': {}}  # No combat history for new monsters
        
        # Set up map_state data for multiple monsters
        self.mock_map_state.data = {
            '0,1': {'x': 0, 'y': 1, 'content': {'type': 'monster', 'code': 'chicken'}},
            '0,-1': {'x': 0, 'y': -1, 'content': {'type': 'monster', 'code': 'green_slime'}},
            '1,0': {'x': 1, 'y': 0, 'content': {'type': 'monster', 'code': 'wolf'}}
        }
        
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
        
        # Should find chicken (level 1) over wolf (level 2), and skip slime (level 4)
        self.assertTrue(result.success)
        self.assertEqual(result.data.get('target_x'), 0)
        self.assertEqual(result.data.get('target_y'), 1)
        self.assertEqual(result.data.get('monster_code'), 'chicken')


if __name__ == '__main__':
    unittest.main()