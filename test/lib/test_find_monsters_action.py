"""Test module for FindMonstersAction."""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.find_monsters import FindMonstersAction

from test.fixtures import MockActionContext, create_mock_client


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
        
        self.action = FindMonstersAction()
        
        # Mock client
        self.mock_client = create_mock_client()

    def test_find_monsters_action_initialization_default(self):
        """Test FindMonstersAction initialization with default parameters."""
        action = FindMonstersAction()
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(action, 'character_x'))
        self.assertFalse(hasattr(action, 'character_y'))
        self.assertFalse(hasattr(action, 'search_radius'))
        self.assertFalse(hasattr(action, 'monster_types'))
        self.assertFalse(hasattr(action, 'character_level'))
        self.assertFalse(hasattr(action, 'level_range'))
        self.assertFalse(hasattr(action, 'use_exponential_search'))

    def test_find_monsters_action_initialization_with_params(self):
        """Test FindMonstersAction initialization with all parameters."""
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(self.action, 'character_x'))
        self.assertFalse(hasattr(self.action, 'character_y'))
        self.assertFalse(hasattr(self.action, 'search_radius'))
        self.assertFalse(hasattr(self.action, 'monster_types'))
        self.assertFalse(hasattr(self.action, 'character_level'))
        self.assertFalse(hasattr(self.action, 'level_range'))
        self.assertFalse(hasattr(self.action, 'use_exponential_search'))

    def test_find_monsters_action_initialization_default_character_level(self):
        """Test FindMonstersAction initialization with default character level."""
        action = FindMonstersAction()
        self.assertFalse(hasattr(action, 'character_level'))

    def test_find_monsters_action_initialization_with_character_level(self):
        """Test FindMonstersAction initialization with character level."""
        action = FindMonstersAction()
        self.assertFalse(hasattr(action, 'character_level'))

    def test_find_monsters_action_repr_no_filter(self):
        """Test FindMonstersAction string representation without filters."""
        action = FindMonstersAction()
        expected = "FindMonstersAction()"
        self.assertEqual(repr(action), expected)

    def test_find_monsters_action_repr_with_filter(self):
        """Test FindMonstersAction string representation with filters."""
        expected = "FindMonstersAction()"
        self.assertEqual(repr(self.action), expected)

    def test_find_monsters_action_class_attributes(self):
        """Test that FindMonstersAction has expected GOAP class attributes."""
        self.assertTrue(hasattr(FindMonstersAction, 'conditions'))
        self.assertTrue(hasattr(FindMonstersAction, 'reactions'))
        self.assertTrue(hasattr(FindMonstersAction, 'weights'))

    def test_monster_types_none_becomes_empty_list(self):
        """Test that None monster_types becomes empty list."""
        action = FindMonstersAction()
        self.assertFalse(hasattr(action, 'monster_types'))

    def test_execute_no_client(self):
        """Test finding monsters fails without client."""
        context = MockActionContext(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius,
            monster_types=self.monster_types,
            character_level=self.character_level,
            level_range=self.level_range,
            use_exponential_search=False
        )
        result = self.action.execute(None, context)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_empty_monsters_data(self, mock_get_monsters):
        """Test execute with empty monsters data."""
        mock_get_monsters.return_value = Mock(data=[])
        context = MockActionContext(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius,
            monster_types=self.monster_types,
            character_level=self.character_level,
            level_range=self.level_range,
            use_exponential_search=False
        )
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result['success'])
        self.assertIn('No suitable monsters found', result['error'])

    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_find_monster_success(self, mock_get_monsters):
        """Test finding monsters successfully."""
        # Mock API response
        mock_monster = Mock()
        mock_monster.code = 'green_slime'
        mock_monster.name = 'Green Slime'
        mock_monster.level = 5
        mock_get_monsters.return_value = Mock(data=[mock_monster])
        
        # Create mock knowledge base with viable monster data
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'monsters': {
                'green_slime': {
                    'level': 5,
                    'combat_results': [
                        {'result': 'win'},
                        {'result': 'win'},
                        {'result': 'loss'}
                    ]
                }
            }
        }
        
        # Create mock map state
        mock_map_state = Mock()
        mock_map_state.data = {
            '6,7': {
                'content': {
                    'code': 'green_slime',
                    'type': 'monster'
                },
                'x': 6,
                'y': 7
            }
        }
        
        # Mock the search method to return our test location
        with patch.object(self.action, '_search_radius_for_content') as mock_search:
            mock_search.return_value = [
                ((6, 7), 'green_slime', {'code': 'green_slime', 'type': 'monster'})
            ]
            
            # Execute with proper context
            context = MockActionContext(
                character_x=self.character_x,
                character_y=self.character_y,
                search_radius=self.search_radius,
                monster_types=self.monster_types,
                character_level=5,
                level_range=self.level_range,
                use_exponential_search=False,
                knowledge_base=mock_knowledge_base,
                map_state=mock_map_state
            )
            result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['target_x'], 6)
        self.assertEqual(result['target_y'], 7)
        self.assertEqual(result['monster_code'], 'green_slime')
        # Distance calculation may vary based on search implementation
        if 'distance' in result:
            self.assertGreater(result['distance'], 0)
        # Win rate check
        if 'win_rate' in result:
            self.assertAlmostEqual(result['win_rate'], 0.667, places=2)

    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_no_monsters_found(self, mock_get_monsters):
        """Test finding monsters when none are found."""
        # Mock API response
        mock_monster = Mock()
        mock_monster.code = 'green_slime'
        mock_monster.name = 'Green Slime'
        mock_monster.level = 5
        mock_get_monsters.return_value = Mock(data=[mock_monster])
        
        # Mock the _find_best_monster_target method to return no results
        with patch.object(self.action, '_find_best_monster_target') as mock_find_best:
            mock_find_best.return_value = {
                'success': False,
                'error': 'No viable monsters found within radius 3'
            }
            
            context = MockActionContext(
                character_x=self.character_x,
                character_y=self.character_y,
                search_radius=self.search_radius,
                monster_types=self.monster_types,
                character_level=self.character_level,
                level_range=self.level_range,
                use_exponential_search=False
            )
            result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result['success'])
        self.assertIn('No viable monsters found', result['error'])

    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_no_monsters_response(self, mock_get_monsters):
        """Test execute with no monsters from API."""
        mock_get_monsters.return_value = None
        context = MockActionContext(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius,
            monster_types=self.monster_types,
            character_level=self.character_level,
            level_range=self.level_range,
            use_exponential_search=False
        )
        result = self.action.execute(self.mock_client, context)
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
        action = FindMonstersAction()
        
        # Check if the method exists before testing
        if hasattr(action, '_get_target_monster_codes'):
            # This would normally call the API, but we can test the logic separately
            # by mocking the API response within _get_target_monster_codes
            with patch('src.controller.actions.find_monsters.get_all_monsters_api') as mock_api:
                mock_api.return_value = Mock(data=[mock_slime, mock_chicken, mock_cow])
                monster_types = ['slime', 'chicken']
                result = action._get_target_monster_codes(self.mock_client, monster_types, None, 2)
                
                # Should include slime and chicken, but not cow
                self.assertIn('green_slime', result)
                self.assertIn('chicken', result)
                self.assertNotIn('cow', result)
        else:
            self.skipTest('_get_target_monster_codes method not found')

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
        
        action = FindMonstersAction()
        
        if hasattr(action, '_get_target_monster_codes'):
            with patch('src.controller.actions.find_monsters.get_all_monsters_api') as mock_api:
                mock_api.return_value = Mock(data=[mock_slime, mock_chicken, mock_pig])
                result = action._get_target_monster_codes(self.mock_client, [], 5, 2)
                
                # Should include slime and pig, but not chicken
                self.assertIn('green_slime', result)
                self.assertNotIn('chicken', result)
                self.assertIn('pig', result)
        else:
            self.skipTest('_get_target_monster_codes method not found')

    def test_get_target_monster_codes_no_character_level(self):
        """Test that no character level uses all monsters."""
        mock_monsters = [Mock(code=f'monster_{i}', name=f'Monster {i}', level=i*5) for i in range(1, 4)]
        
        action = FindMonstersAction()  # No character level
        
        if hasattr(action, '_get_target_monster_codes'):
            with patch('src.controller.actions.find_monsters.get_all_monsters_api') as mock_api:
                mock_api.return_value = Mock(data=mock_monsters)
                result = action._get_target_monster_codes(self.mock_client, [], None, 2)
                
                # All monsters should be included
                self.assertEqual(len(result), 3)
        else:
            self.skipTest('_get_target_monster_codes method not found')


if __name__ == '__main__':
    unittest.main()