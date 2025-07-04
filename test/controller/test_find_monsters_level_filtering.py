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
        """Test that unknown monsters have their level checked via API."""
        # Mock map API to return a location with a monster
        mock_map_response = Mock()
        mock_map_response.data = Mock()
        mock_map_response.data.x = 1
        mock_map_response.data.y = 1
        mock_map_response.data.content = Mock(type='monster', code='green_slime')
        mock_map_response.data.__dict__ = {'x': 1, 'y': 1, 'content': {'type': 'monster', 'code': 'green_slime'}}
        
        # Mock monster API to return level 4 slime
        mock_monster_response = Mock()
        mock_monster_response.data = [
            Mock(code='green_slime', level=4, name='Green Slime')
        ]
        
        # Mock function to return different responses based on coordinates
        def mock_get_map(x, y, client):
            if x == 1 and y == 1:
                return mock_map_response
            else:
                # Return empty location for other coordinates
                empty_response = Mock()
                empty_response.data = Mock()
                empty_response.data.x = x
                empty_response.data.y = y
                empty_response.data.content = None
                empty_response.data.__dict__ = {'x': x, 'y': y, 'content': None}
                return empty_response
        
        with patch('src.controller.actions.search_base.get_map_api', side_effect=mock_get_map), \
             patch('src.controller.actions.find_monsters.get_all_monsters_api', return_value=mock_monster_response):
            
            # Create mock knowledge base with get_monster_data method that returns level 4
            mock_kb = Mock()
            mock_kb.get_monster_data = Mock(return_value={'level': 4})  # Return monster data with level
            
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
            self.assertIn('No suitable monsters found matching criteria', result.error)
    
    def test_unknown_monster_appropriate_level(self):
        """Test that unknown monsters with appropriate levels are accepted."""
        # Mock map API to return a location with a monster
        mock_map_response = Mock()
        mock_map_response.data = Mock()
        mock_map_response.data.x = 0
        mock_map_response.data.y = 1
        mock_map_response.data.content = Mock(type='monster', code='chicken')
        mock_map_response.data.__dict__ = {'x': 0, 'y': 1, 'content': {'type': 'monster', 'code': 'chicken'}}
        
        # Mock monster API to return level 1 chicken
        mock_monster_response = Mock()
        mock_monster_response.data = [
            Mock(code='chicken', level=1, name='Chicken')
        ]
        
        # Mock function to return different responses based on coordinates
        def mock_get_map(x, y, client):
            if x == 0 and y == 1:
                return mock_map_response
            else:
                # Return empty location for other coordinates
                empty_response = Mock()
                empty_response.data = Mock()
                empty_response.data.x = x
                empty_response.data.y = y
                empty_response.data.content = None
                empty_response.data.__dict__ = {'x': x, 'y': y, 'content': None}
                return empty_response
        
        with patch('src.controller.actions.search_base.get_map_api', side_effect=mock_get_map), \
             patch('src.controller.actions.find_monsters.get_all_monsters_api', return_value=mock_monster_response):
            
            # Set up map_state data
            self.mock_map_state.data = {
                '0,1': {'x': 0, 'y': 1, 'content': {'type': 'monster', 'code': 'chicken'}}
            }
            
            # Create mock knowledge base with get_monster_data method that returns level 1
            mock_kb = Mock()
            mock_kb.get_monster_data = Mock(return_value={'level': 1})  # Return monster data with level
            
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
        """Test that API failures cause monsters to be skipped."""
        # Mock map API to return a location with a monster
        mock_map_response = Mock()
        mock_map_response.data = Mock()
        mock_map_response.data.x = 1
        mock_map_response.data.y = 1
        mock_map_response.data.content = Mock(type='monster', code='unknown_monster')
        mock_map_response.data.__dict__ = {'x': 1, 'y': 1, 'content': {'type': 'monster', 'code': 'unknown_monster'}}
        
        # Mock function to return different responses based on coordinates
        def mock_get_map(x, y, client):
            if x == 1 and y == 1:
                return mock_map_response
            else:
                # Return empty location for other coordinates
                empty_response = Mock()
                empty_response.data = Mock()
                empty_response.data.x = x
                empty_response.data.y = y
                empty_response.data.content = None
                empty_response.data.__dict__ = {'x': x, 'y': y, 'content': None}
                return empty_response
        
        # Mock monster API to fail
        with patch('src.controller.actions.search_base.get_map_api', side_effect=mock_get_map), \
             patch('src.controller.actions.find_monsters.get_all_monsters_api', side_effect=Exception("API Error")):
            
            # Create mock knowledge base with get_monster_data method that simulates API fallback failure
            mock_kb = Mock()
            mock_kb.get_monster_data = Mock(return_value=None)  # Simulating API fallback also failed
            
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
            
            # Should not find viable monsters due to API failure
            self.assertFalse(result.success)
            self.assertIn('No suitable monsters found matching criteria', result.error)
    
    def test_known_monster_uses_knowledge_base(self):
        """Test that known monsters use knowledge base data instead of API."""
        # Set up knowledge base with known monster
        self.mock_knowledge_base.data = {
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
        # Update get_monster_data to return the data
        self.mock_knowledge_base.get_monster_data = Mock(return_value={
            'level': 2,
            'combat_results': [
                {'result': 'win', 'timestamp': '2024-01-01T00:00:00'},
                {'result': 'win', 'timestamp': '2024-01-01T00:01:00'},
            ]
        })
        
        # Mock map API to return a wolf
        mock_map_response = Mock()
        mock_map_response.data = Mock()
        mock_map_response.data.x = 1
        mock_map_response.data.y = 0
        mock_map_response.data.content = Mock(type='monster', code='wolf')
        mock_map_response.data.__dict__ = {'x': 1, 'y': 0, 'content': {'type': 'monster', 'code': 'wolf'}}
        
        # Mock monster API to return wolf monster data
        mock_get_all_monsters = Mock()
        mock_monster_response = Mock()
        mock_monster_response.data = [
            Mock(code='wolf', name='Wolf', level=2)
        ]
        mock_get_all_monsters.return_value = mock_monster_response
        
        # Mock function to return different responses based on coordinates
        def mock_get_map(x, y, client):
            if x == 1 and y == 0:
                return mock_map_response
            else:
                # Return empty location for other coordinates
                empty_response = Mock()
                empty_response.data = Mock()
                empty_response.data.x = x
                empty_response.data.y = y
                empty_response.data.content = None
                empty_response.data.__dict__ = {'x': x, 'y': y, 'content': None}
                return empty_response
        
        with patch('src.controller.actions.search_base.get_map_api', side_effect=mock_get_map), \
             patch('src.controller.actions.find_monsters.get_all_monsters_api', mock_get_all_monsters):
            
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
            context.knowledge_base = self.mock_knowledge_base
            context.map_state = self.mock_map_state
            result = self.action.execute(self.mock_client, context)
            
            # Should find viable monster from knowledge base
            if not result.success:
                print(f"DEBUG: Result = {result}")
            self.assertTrue(result.success)
            self.assertEqual(result.data.get('target_x'), 1)
            self.assertEqual(result.data.get('target_y'), 0)
            self.assertEqual(result.data.get('monster_code'), 'wolf')
            
            # API is called once to get target monster codes (expected behavior)
            self.assertEqual(mock_get_all_monsters.call_count, 1)
    
    def test_multiple_monsters_prioritizes_by_level(self):
        """Test that when multiple monsters are found, lower level is prioritized."""
        # Mock map API to return multiple monsters
        def mock_maps_get(x, y, client):
            responses = {
                (0, 1): Mock(data=Mock(x=0, y=1, content=Mock(type='monster', code='chicken'), __dict__={'x': 0, 'y': 1, 'content': {'type': 'monster', 'code': 'chicken'}})),
                (0, -1): Mock(data=Mock(x=0, y=-1, content=Mock(type='monster', code='green_slime'), __dict__={'x': 0, 'y': -1, 'content': {'type': 'monster', 'code': 'green_slime'}})),
                (1, 0): Mock(data=Mock(x=1, y=0, content=Mock(type='monster', code='wolf'), __dict__={'x': 1, 'y': 0, 'content': {'type': 'monster', 'code': 'wolf'}}))
            }
            empty = Mock()
            empty.data = Mock(x=x, y=y, content=None, __dict__={'x': x, 'y': y, 'content': None})
            return responses.get((x, y), empty)
        
        # Mock monster API to return different levels
        def mock_get_monsters(client, code=None, size=100):
            monsters_data = {
                'chicken': Mock(code='chicken', level=1, name='Chicken'),
                'green_slime': Mock(code='green_slime', level=4, name='Green Slime'),
                'wolf': Mock(code='wolf', level=2, name='Wolf')
            }
            if code and code in monsters_data:
                return Mock(data=[monsters_data[code]])
            return Mock(data=list(monsters_data.values()))
        
        with patch('src.controller.actions.search_base.get_map_api', side_effect=mock_maps_get), \
             patch('src.controller.actions.find_monsters.get_all_monsters_api', side_effect=mock_get_monsters):
            
            # Set up map_state data for multiple monsters
            self.mock_map_state.data = {
                '0,1': {'x': 0, 'y': 1, 'content': {'type': 'monster', 'code': 'chicken'}},
                '0,-1': {'x': 0, 'y': -1, 'content': {'type': 'monster', 'code': 'green_slime'}},
                '1,0': {'x': 1, 'y': 0, 'content': {'type': 'monster', 'code': 'wolf'}}
            }
            
            # Create mock knowledge base with get_monster_data method that returns appropriate levels
            mock_kb = Mock()
            def mock_get_monster_data(code, client=None):
                monster_levels = {
                    'chicken': {'level': 1},
                    'green_slime': {'level': 4},
                    'wolf': {'level': 2}
                }
                return monster_levels.get(code)
            mock_kb.get_monster_data = Mock(side_effect=mock_get_monster_data)
            
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