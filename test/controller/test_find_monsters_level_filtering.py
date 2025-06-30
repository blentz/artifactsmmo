"""Test find_monsters action level filtering for unknown monsters"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from src.controller.actions.find_monsters import FindMonstersAction


class TestFindMonstersLevelFiltering(unittest.TestCase):
    """Test cases for find_monsters level filtering with unknown monsters"""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = FindMonstersAction(
            character_x=0,
            character_y=0,
            search_radius=2,
            character_level=1
        )
        
        # Mock client
        self.mock_client = Mock()
        
        # Mock knowledge base
        self.mock_knowledge_base = Mock()
        self.mock_knowledge_base.data = {
            'monsters': {}  # Empty - simulating unknown monsters
        }
        
        # Mock map state
        self.mock_map_state = Mock()
        self.mock_map_state.scan.return_value = []
        
    def test_unknown_monster_api_level_check(self):
        """Test that unknown monsters have their level checked via API."""
        # Mock map API to return a location with a monster
        mock_map_response = Mock()
        mock_map_response.data = Mock()
        mock_map_response.data.x = 1
        mock_map_response.data.y = 1
        mock_map_response.data.content = Mock()
        mock_map_response.data.content.type = 'monster'
        mock_map_response.data.content.code = 'green_slime'
        
        # Mock monster API to return level 4 slime
        mock_monster_response = Mock()
        mock_monster_response.data = [
            Mock(code='green_slime', level=4)
        ]
        
        with patch('src.controller.actions.find_monsters.maps_get_api', return_value=mock_map_response), \
             patch('src.controller.actions.find_monsters.get_all_monsters_api', return_value=mock_monster_response):
            
            # Execute with character level 1
            result = self.action.execute(
                client=self.mock_client,
                knowledge_base=self.mock_knowledge_base,
                map_state=self.mock_map_state,
                character_level=1
            )
            
            # Should not find viable monsters because level 4 > level 1 + 1
            self.assertFalse(result.get('success'))
            self.assertIn('No viable monsters found', result.get('error', ''))
    
    def test_unknown_monster_appropriate_level(self):
        """Test that unknown monsters with appropriate levels are accepted."""
        # Mock map API to return a location with a monster
        mock_map_response = Mock()
        mock_map_response.data = Mock()
        mock_map_response.data.x = 0
        mock_map_response.data.y = 1
        mock_map_response.data.content = Mock()
        mock_map_response.data.content.type = 'monster'
        mock_map_response.data.content.code = 'chicken'
        
        # Mock monster API to return level 1 chicken
        mock_monster_response = Mock()
        mock_monster_response.data = [
            Mock(code='chicken', level=1)
        ]
        
        with patch('src.controller.actions.find_monsters.maps_get_api', return_value=mock_map_response), \
             patch('src.controller.actions.find_monsters.get_all_monsters_api', return_value=mock_monster_response):
            
            # Execute with character level 1
            result = self.action.execute(
                client=self.mock_client,
                knowledge_base=self.mock_knowledge_base,
                map_state=self.mock_map_state,
                character_level=1
            )
            
            # Should find viable monster because level 1 <= level 1 + 1
            self.assertTrue(result.get('success'))
            self.assertEqual(result.get('target_x'), 0)
            self.assertEqual(result.get('target_y'), 1)
            self.assertEqual(result.get('monster_code'), 'chicken')
    
    def test_api_failure_skips_monster(self):
        """Test that API failures cause monsters to be skipped."""
        # Mock map API to return a location with a monster
        mock_map_response = Mock()
        mock_map_response.data = Mock()
        mock_map_response.data.x = 1
        mock_map_response.data.y = 1
        mock_map_response.data.content = Mock()
        mock_map_response.data.content.type = 'monster'
        mock_map_response.data.content.code = 'unknown_monster'
        
        # Mock monster API to fail
        with patch('src.controller.actions.find_monsters.maps_get_api', return_value=mock_map_response), \
             patch('src.controller.actions.find_monsters.get_all_monsters_api', side_effect=Exception("API Error")):
            
            # Execute
            result = self.action.execute(
                client=self.mock_client,
                knowledge_base=self.mock_knowledge_base,
                map_state=self.mock_map_state,
                character_level=1
            )
            
            # Should not find viable monsters due to API failure
            self.assertFalse(result.get('success'))
            self.assertIn('No viable monsters found', result.get('error', ''))
    
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
        
        # Mock map API to return a wolf
        mock_map_response = Mock()
        mock_map_response.data = Mock()
        mock_map_response.data.x = 1
        mock_map_response.data.y = 0
        mock_map_response.data.content = Mock()
        mock_map_response.data.content.type = 'monster'
        mock_map_response.data.content.code = 'wolf'
        
        # Mock monster API (should not be called)
        mock_get_all_monsters = Mock()
        
        with patch('src.controller.actions.find_monsters.maps_get_api', return_value=mock_map_response), \
             patch('src.controller.actions.find_monsters.get_all_monsters_api', mock_get_all_monsters):
            
            # Execute with character level 2
            result = self.action.execute(
                client=self.mock_client,
                knowledge_base=self.mock_knowledge_base,
                map_state=self.mock_map_state,
                character_level=2
            )
            
            # Should find viable monster from knowledge base
            self.assertTrue(result.get('success'))
            self.assertEqual(result.get('target_x'), 1)
            self.assertEqual(result.get('target_y'), 0)
            self.assertEqual(result.get('monster_code'), 'wolf')
            
            # API should not be called for known monster
            mock_get_all_monsters.assert_not_called()
    
    def test_multiple_monsters_prioritizes_by_level(self):
        """Test that when multiple monsters are found, lower level is prioritized."""
        # Mock map API to return multiple monsters
        def mock_maps_get(client, x, y):
            responses = {
                (0, 1): Mock(data=Mock(x=0, y=1, content=Mock(type='monster', code='chicken'))),
                (0, -1): Mock(data=Mock(x=0, y=-1, content=Mock(type='monster', code='green_slime'))),
                (1, 0): Mock(data=Mock(x=1, y=0, content=Mock(type='monster', code='wolf')))
            }
            return responses.get((x, y), Mock(data=Mock(x=x, y=y, content=None)))
        
        # Mock monster API to return different levels
        def mock_get_monsters(client, code=None):
            monsters_data = {
                'chicken': Mock(code='chicken', level=1),
                'green_slime': Mock(code='green_slime', level=4),
                'wolf': Mock(code='wolf', level=2)
            }
            if code and code in monsters_data:
                return Mock(data=[monsters_data[code]])
            return Mock(data=list(monsters_data.values()))
        
        with patch('src.controller.actions.find_monsters.maps_get_api', side_effect=mock_maps_get), \
             patch('src.controller.actions.find_monsters.get_all_monsters_api', side_effect=mock_get_monsters):
            
            # Execute with character level 1
            result = self.action.execute(
                client=self.mock_client,
                knowledge_base=self.mock_knowledge_base,
                map_state=self.mock_map_state,
                character_level=1
            )
            
            # Should find chicken (level 1) over wolf (level 2), and skip slime (level 4)
            self.assertTrue(result.get('success'))
            self.assertEqual(result.get('target_x'), 0)
            self.assertEqual(result.get('target_y'), 1)
            self.assertEqual(result.get('monster_code'), 'chicken')


if __name__ == '__main__':
    unittest.main()