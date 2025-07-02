"""Test that FindMonstersAction can find monsters at the character's current position."""

import unittest
from unittest.mock import MagicMock, patch

from src.controller.actions.find_monsters import FindMonstersAction
from src.lib.action_context import ActionContext


class TestFindMonstersCurrentPosition(unittest.TestCase):
    """Test that FindMonstersAction correctly finds monsters at radius 0."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = FindMonstersAction()
        self.mock_client = MagicMock()
        
    def test_finds_monster_at_current_position(self):
        """Test that FindMonstersAction finds a monster at the character's current position."""
        # Arrange
        context = ActionContext()
        context.character_x = 0
        context.character_y = 1
        context.character_level = 2
        context.search_radius = 3
        
        # Mock knowledge base
        mock_knowledge_base = MagicMock()
        mock_knowledge_base.get_monster_data.return_value = {
            'code': 'chicken',
            'level': 1,
            'hp': 100
        }
        context.knowledge_base = mock_knowledge_base
        
        # Mock map state with chicken at (0,1)
        mock_map_state = MagicMock()
        mock_map_state.is_cache_fresh.return_value = True
        mock_map_state.data = {
            '0,1': {
                'content': {
                    'code': 'chicken',
                    'type': 'monster'
                }
            }
        }
        context.map_state = mock_map_state
        
        # Mock API response for get_all_monsters
        mock_monster = MagicMock()
        mock_monster.code = 'chicken'
        mock_monster.name = 'Chicken'
        mock_monster.level = 1
        
        mock_monsters_response = MagicMock()
        mock_monsters_response.data = [mock_monster]
        
        # Act
        with patch('src.controller.actions.find_monsters.get_all_monsters_api', return_value=mock_monsters_response):
            result = self.action.execute(self.mock_client, context)
        
        # Assert
        self.assertTrue(result['success'])
        self.assertEqual(result['target_x'], 0)
        self.assertEqual(result['target_y'], 1)
        self.assertEqual(result['monster_code'], 'chicken')
        self.assertEqual(result['distance'], 0.0)  # Character is at the same position
        
    def test_search_includes_radius_zero(self):
        """Test that the search loop starts from radius 0."""
        # Arrange
        context = ActionContext()
        context.character_x = 5
        context.character_y = 5
        context.character_level = 1
        context.search_radius = 2
        
        # Mock knowledge base
        mock_knowledge_base = MagicMock()
        mock_knowledge_base.get_monster_data.return_value = {
            'code': 'test_monster',
            'level': 1
        }
        context.knowledge_base = mock_knowledge_base
        
        # Mock map state
        mock_map_state = MagicMock()
        locations_checked = []
        
        def mock_is_cache_fresh(x, y):
            locations_checked.append((x, y))
            return True
            
        mock_map_state.is_cache_fresh = mock_is_cache_fresh
        # Add dummy data so the search actually checks locations
        mock_map_state.data = {
            '5,5': {'content': None},  # No monster at character position
            '6,5': {'content': None},  # No monster at adjacent positions
            '4,5': {'content': None}
        }
        context.map_state = mock_map_state
        
        # Mock API response - need at least one monster for search to proceed
        mock_monster = MagicMock()
        mock_monster.code = 'test_monster'
        mock_monster.name = 'Test Monster'
        mock_monster.level = 1
        
        mock_monsters_response = MagicMock()
        mock_monsters_response.data = [mock_monster]
        
        # Act
        with patch('src.controller.actions.find_monsters.get_all_monsters_api', return_value=mock_monsters_response):
            result = self.action.execute(self.mock_client, context)
        
        # Assert - verify that (5,5) was checked (radius 0)
        self.assertIn((5, 5), locations_checked, "Character's current position should be checked")
        
    def test_prioritizes_current_position_over_distant_monsters(self):
        """Test that a monster at current position is chosen over distant ones."""
        # Arrange
        context = ActionContext()
        context.character_x = 0
        context.character_y = 0
        context.character_level = 2
        context.search_radius = 3
        
        # Mock knowledge base
        mock_knowledge_base = MagicMock()
        mock_knowledge_base.get_monster_data.side_effect = lambda code, **kwargs: {
            'chicken': {'code': 'chicken', 'level': 1},
            'cow': {'code': 'cow', 'level': 2}
        }.get(code, {})
        context.knowledge_base = mock_knowledge_base
        
        # Mock map state with chicken at (0,0) and cow at (1,1)
        mock_map_state = MagicMock()
        mock_map_state.is_cache_fresh.return_value = True
        mock_map_state.data = {
            '0,0': {
                'content': {
                    'code': 'chicken',
                    'type': 'monster'
                }
            },
            '1,1': {
                'content': {
                    'code': 'cow',
                    'type': 'monster'
                }
            }
        }
        context.map_state = mock_map_state
        
        # Mock API response
        mock_chicken = MagicMock()
        mock_chicken.code = 'chicken'
        mock_chicken.name = 'Chicken'
        mock_chicken.level = 1
        
        mock_cow = MagicMock()
        mock_cow.code = 'cow'
        mock_cow.name = 'Cow'
        mock_cow.level = 2
        
        mock_monsters_response = MagicMock()
        mock_monsters_response.data = [mock_chicken, mock_cow]
        
        # Act
        with patch('src.controller.actions.find_monsters.get_all_monsters_api', return_value=mock_monsters_response):
            result = self.action.execute(self.mock_client, context)
        
        # Assert - should choose chicken at current position
        self.assertTrue(result['success'])
        self.assertEqual(result['target_x'], 0)
        self.assertEqual(result['target_y'], 0)
        self.assertEqual(result['monster_code'], 'chicken')
        self.assertEqual(result['distance'], 0.0)


if __name__ == '__main__':
    unittest.main()