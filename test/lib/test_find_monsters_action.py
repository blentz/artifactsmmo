"""Test module for FindMonstersAction."""

import unittest
from unittest.mock import Mock, patch
from src.controller.actions.find_monsters import FindMonstersAction


class TestFindMonstersAction(unittest.TestCase):
    """Test cases for FindMonstersAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.character_x = 5
        self.character_y = 5
        self.search_radius = 3
        self.monster_types = ['green_slime', 'chicken']
        self.character_level = 5
        self.level_range = 2
        
        self.action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius,
            monster_types=self.monster_types,
            character_level=self.character_level,
            level_range=self.level_range,
            use_exponential_search=False
        )
        
        # Mock client
        self.mock_client = Mock()

    def test_find_monsters_action_initialization_default(self):
        """Test FindMonstersAction initialization with default parameters."""
        action = FindMonstersAction()
        self.assertEqual(action.character_x, 0)
        self.assertEqual(action.character_y, 0)
        self.assertEqual(action.search_radius, 2)
        self.assertEqual(action.monster_types, [])
        self.assertIsNone(action.character_level)
        self.assertEqual(action.level_range, 2)
        self.assertTrue(action.use_exponential_search)

    def test_find_monsters_action_initialization_with_params(self):
        """Test FindMonstersAction initialization with all parameters."""
        self.assertEqual(self.action.character_x, self.character_x)
        self.assertEqual(self.action.character_y, self.character_y)
        self.assertEqual(self.action.search_radius, self.search_radius)
        self.assertEqual(self.action.monster_types, self.monster_types)
        self.assertEqual(self.action.character_level, self.character_level)
        self.assertEqual(self.action.level_range, self.level_range)
        self.assertFalse(self.action.use_exponential_search)

    def test_find_monsters_action_initialization_default_character_level(self):
        """Test FindMonstersAction initialization with default character level."""
        action = FindMonstersAction(character_x=1, character_y=2, search_radius=3)
        self.assertIsNone(action.character_level)

    def test_find_monsters_action_initialization_with_character_level(self):
        """Test FindMonstersAction initialization with character level."""
        action = FindMonstersAction(character_level=10)
        self.assertEqual(action.character_level, 10)

    def test_find_monsters_action_repr_no_filter(self):
        """Test FindMonstersAction string representation without filters."""
        action = FindMonstersAction(character_x=5, character_y=5, search_radius=3, use_exponential_search=False)
        expected = "FindMonstersAction(5, 5, radius=3)"
        self.assertEqual(repr(action), expected)

    def test_find_monsters_action_repr_with_filter(self):
        """Test FindMonstersAction string representation with filters."""
        expected = (f"FindMonstersAction({self.character_x}, {self.character_y}, "
                   f"radius={self.search_radius}, types={self.monster_types})")
        self.assertEqual(repr(self.action), expected)

    def test_find_monsters_action_class_attributes(self):
        """Test that FindMonstersAction has expected GOAP class attributes."""
        self.assertTrue(hasattr(FindMonstersAction, 'conditions'))
        self.assertTrue(hasattr(FindMonstersAction, 'reactions'))
        self.assertTrue(hasattr(FindMonstersAction, 'weights'))

    def test_monster_types_none_becomes_empty_list(self):
        """Test that None monster_types becomes empty list."""
        action = FindMonstersAction(monster_types=None)
        self.assertEqual(action.monster_types, [])

    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_no_client(self, mock_get_monsters):
        """Test finding monsters fails without client."""
        mock_get_monsters.side_effect = Exception("No client")
        result = self.action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No suitable monsters found', result['error'])

    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_empty_monsters_data(self, mock_get_monsters):
        """Test execute with empty monsters data."""
        mock_get_monsters.return_value = Mock(data=[])
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn('No suitable monsters found', result['error'])

    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    @patch('src.controller.actions.search_base.SearchActionBase.unified_search')
    def test_execute_find_monster_success(self, mock_unified_search, mock_get_monsters):
        """Test finding monsters successfully."""
        # Mock API response
        mock_monster = Mock()
        mock_monster.code = 'green_slime'
        mock_monster.name = 'Green Slime'
        mock_monster.level = 5
        mock_get_monsters.return_value = Mock(data=[mock_monster])
        
        # Mock search result
        mock_unified_search.return_value = {
            'success': True,
            'location': (6, 7),
            'monster_code': 'green_slime',
            'distance': 2.236
        }
        
        result = self.action.execute(self.mock_client)
        self.assertTrue(result['success'])
        self.assertEqual(result['location'], (6, 7))
        self.assertEqual(result['monster_code'], 'green_slime')
        self.assertAlmostEqual(result['distance'], 2.236, places=2)

    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    @patch('src.controller.actions.search_base.SearchActionBase.unified_search')
    def test_execute_no_monsters_found(self, mock_unified_search, mock_get_monsters):
        """Test finding monsters when none are found."""
        # Mock API response
        mock_monster = Mock()
        mock_monster.code = 'green_slime'
        mock_monster.name = 'Green Slime'
        mock_monster.level = 5
        mock_get_monsters.return_value = Mock(data=[mock_monster])
        
        # Mock search result
        mock_unified_search.return_value = {
            'success': False,
            'error': 'No matching content found within radius 3'
        }
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn('No viable monsters found', result['error'])

    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_no_monsters_response(self, mock_get_monsters):
        """Test execute with no monsters from API."""
        mock_get_monsters.return_value = None
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn('No suitable monsters found', result['error'])

    def test_get_target_monster_codes_type_filtering(self):
        """Test filtering monsters by type."""
        # Create mock monsters
        mock_slime = Mock()
        mock_slime.code = 'green_slime'
        mock_slime.name = 'Green Slime'
        mock_slime.level = 5
        
        mock_chicken = Mock()
        mock_chicken.code = 'chicken'
        mock_chicken.name = 'Chicken'
        mock_chicken.level = 4
        
        mock_cow = Mock()
        mock_cow.code = 'cow'
        mock_cow.name = 'Cow'
        mock_cow.level = 6
        
        # Test filtering with monster types
        action = FindMonstersAction(monster_types=['slime', 'chicken'])
        
        # This would normally call the API, but we can test the logic separately
        # by mocking the API response within _get_target_monster_codes
        with patch('src.controller.actions.find_monsters.get_all_monsters_api') as mock_api:
            mock_api.return_value = Mock(data=[mock_slime, mock_chicken, mock_cow])
            result = action._get_target_monster_codes(self.mock_client)
            
            # Should include slime and chicken, but not cow
            self.assertIn('green_slime', result)
            self.assertIn('chicken', result)
            self.assertNotIn('cow', result)

    def test_get_target_monster_codes_level_filtering(self):
        """Test filtering monsters by level range."""
        # Create mock monsters with different levels
        mock_slime = Mock()
        mock_slime.code = 'green_slime'
        mock_slime.name = 'Green Slime'
        mock_slime.level = 5  # Within range (5 ± 2)
        
        mock_chicken = Mock()
        mock_chicken.code = 'chicken'
        mock_chicken.name = 'Chicken'
        mock_chicken.level = 10  # Outside range
        
        mock_pig = Mock()
        mock_pig.code = 'pig'
        mock_pig.name = 'Pig'
        mock_pig.level = 3  # Within range
        
        action = FindMonstersAction(character_level=5, level_range=2)
        
        with patch('src.controller.actions.find_monsters.get_all_monsters_api') as mock_api:
            mock_api.return_value = Mock(data=[mock_slime, mock_chicken, mock_pig])
            result = action._get_target_monster_codes(self.mock_client)
            
            # Should include slime and pig, but not chicken
            self.assertIn('green_slime', result)
            self.assertNotIn('chicken', result)
            self.assertIn('pig', result)

    def test_get_target_monster_codes_no_character_level(self):
        """Test that no character level uses all monsters."""
        mock_monsters = [Mock(code=f'monster_{i}', name=f'Monster {i}', level=i*5) for i in range(1, 4)]
        
        action = FindMonstersAction()  # No character level
        
        with patch('src.controller.actions.find_monsters.get_all_monsters_api') as mock_api:
            mock_api.return_value = Mock(data=mock_monsters)
            result = action._get_target_monster_codes(self.mock_client)
            
            # All monsters should be included
            self.assertEqual(len(result), 3)


if __name__ == '__main__':
    unittest.main()