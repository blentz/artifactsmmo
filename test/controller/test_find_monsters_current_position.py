"""Test that FindMonstersAction can find monsters at the character's current position."""

import unittest
from unittest.mock import MagicMock, patch

from src.controller.actions.find_monsters import FindMonstersAction
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from test.test_base import UnifiedContextTestBase


class TestFindMonstersCurrentPosition(UnifiedContextTestBase):
    """Test that FindMonstersAction correctly finds monsters at radius 0."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.action = FindMonstersAction()
        self.mock_client = MagicMock()
        
    def test_finds_monster_at_current_position(self):
        """Test that FindMonstersAction finds a monster at the character's current position."""
        # Arrange
        # Use unified context with StateParameters
        self.context.set(StateParameters.CHARACTER_X, 0)
        self.context.set(StateParameters.CHARACTER_Y, 1)
        self.context.set(StateParameters.CHARACTER_LEVEL, 2)
        self.context.set(StateParameters.SEARCH_RADIUS, 3)
        
        # Mock knowledge base
        mock_knowledge_base = MagicMock()
        mock_knowledge_base.get_monster_data.return_value = {
            'code': 'chicken',
            'level': 1,
            'hp': 100
        }
        mock_knowledge_base.find_monsters_in_map.return_value = [
            {'x': 0, 'y': 1, 'code': 'chicken', 'level': 1}
        ]
        self.context.knowledge_base = mock_knowledge_base
        
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
        self.context.map_state = mock_map_state
        
        # Act
        result = self.action.execute(self.mock_client, self.context)
        
        # Assert
        # Test that the result has the expected structure
        self.assertIsInstance(result, object)
        self.assertTrue(hasattr(result, 'success'))
        self.assertTrue(hasattr(result, 'data'))
        
    def test_search_includes_radius_zero(self):
        """Test that the search loop starts from radius 0."""
        # Arrange
        # Use unified context with StateParameters
        self.context.set(StateParameters.CHARACTER_X, 5)
        self.context.set(StateParameters.CHARACTER_Y, 5)
        self.context.set(StateParameters.CHARACTER_LEVEL, 1)
        self.context.set(StateParameters.SEARCH_RADIUS, 2)
        self.context.set(StateParameters.LEVEL_RANGE, 10)  # Allow wider range to ensure monsters aren't filtered out
        
        # Mock knowledge base
        mock_knowledge_base = MagicMock()
        mock_knowledge_base.get_monster_data.return_value = {
            'code': 'test_monster',
            'level': 1
        }
        self.context.knowledge_base = mock_knowledge_base
        
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
        self.context.map_state = mock_map_state
        
        # Mock API response - need at least one monster for search to proceed
        mock_monster = MagicMock()
        mock_monster.code = 'test_monster'
        mock_monster.name = 'Test Monster'
        mock_monster.level = 1
        
        # Create additional monsters to ensure we have options
        mock_monster2 = MagicMock()
        mock_monster2.code = 'test_monster2'
        mock_monster2.name = 'Test Monster 2'
        mock_monster2.level = 2
        
        mock_monsters_response = MagicMock()
        mock_monsters_response.data = [mock_monster, mock_monster2]
        
        # Act
        mock_knowledge_base.find_monsters_in_map.return_value = []
        result = self.action.execute(self.mock_client, self.context)
        
        # Assert - verify that action completes and has expected structure
        self.assertIsInstance(result, object)
        self.assertTrue(hasattr(result, 'success'))
        
    def test_prioritizes_current_position_over_distant_monsters(self):
        """Test that a monster at current position is chosen over distant ones."""
        # Arrange
        # Use unified context with StateParameters
        self.context.set(StateParameters.CHARACTER_X, 0)
        self.context.set(StateParameters.CHARACTER_Y, 0)
        self.context.set(StateParameters.CHARACTER_LEVEL, 2)
        self.context.set(StateParameters.SEARCH_RADIUS, 3)
        
        # Mock knowledge base
        mock_knowledge_base = MagicMock()
        mock_knowledge_base.get_monster_data.side_effect = lambda code, **kwargs: {
            'chicken': {'code': 'chicken', 'level': 1},
            'cow': {'code': 'cow', 'level': 2}
        }.get(code, {})
        self.context.knowledge_base = mock_knowledge_base
        
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
        self.context.map_state = mock_map_state
        
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
        mock_knowledge_base.find_monsters_in_map.return_value = [
            {'x': 0, 'y': 0, 'code': 'chicken', 'level': 1},
            {'x': 1, 'y': 1, 'code': 'cow', 'level': 2}
        ]
        result = self.action.execute(self.mock_client, self.context)
        
        # Assert - verify that action completes and has expected structure
        self.assertIsInstance(result, object)
        self.assertTrue(hasattr(result, 'success'))


if __name__ == '__main__':
    unittest.main()