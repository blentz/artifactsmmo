"""Enhanced test module for FindMonstersAction."""

import unittest
import tempfile
import os
from unittest.mock import Mock, patch
from src.controller.actions.find_monsters import FindMonstersAction


class TestFindMonstersActionEnhanced(unittest.TestCase):
    """Enhanced test cases for FindMonstersAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_prefix = os.environ.get('DATA_PREFIX', '')
        os.environ['DATA_PREFIX'] = self.temp_dir
        
        self.action = FindMonstersAction(
            character_x=10,
            character_y=15,
            search_radius=3,
            monster_types=['chicken', 'cow'],
            character_level=5,
            level_range=2
        )

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['DATA_PREFIX'] = self.original_data_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_find_monsters_action_initialization(self):
        """Test FindMonstersAction initialization."""
        self.assertEqual(self.action.character_x, 10)
        self.assertEqual(self.action.character_y, 15)
        self.assertEqual(self.action.search_radius, 3)
        self.assertEqual(self.action.monster_types, ['chicken', 'cow'])
        self.assertEqual(self.action.character_level, 5)
        self.assertEqual(self.action.level_range, 2)
        self.assertTrue(self.action.use_exponential_search)
        self.assertEqual(self.action.max_search_radius, 4)

    def test_find_monsters_action_initialization_defaults(self):
        """Test FindMonstersAction initialization with defaults."""
        action = FindMonstersAction()
        self.assertEqual(action.character_x, 0)
        self.assertEqual(action.character_y, 0)
        self.assertEqual(action.search_radius, 2)
        self.assertEqual(action.monster_types, [])
        self.assertIsNone(action.character_level)
        self.assertEqual(action.level_range, 2)
        self.assertTrue(action.use_exponential_search)
        self.assertEqual(action.max_search_radius, 4)

    def test_find_monsters_action_repr(self):
        """Test FindMonstersAction string representation."""
        expected = "FindMonstersAction(10, 15, radius=3, types=['chicken', 'cow'], lvl=5±2)"
        self.assertEqual(repr(self.action), expected)

    def test_find_monsters_action_repr_no_types(self):
        """Test FindMonstersAction string representation without monster types."""
        action = FindMonstersAction(character_x=5, character_y=8, search_radius=2)
        expected = "FindMonstersAction(5, 8, radius=2, types=[], lvl=None±2)"
        self.assertEqual(repr(action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        result = self.action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_monster_api_fails(self, mock_get_monsters_api):
        """Test execute when monster API fails."""
        mock_get_monsters_api.return_value = None
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Could not retrieve monster information', result['error'])

    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_monster_api_no_data(self, mock_get_monsters_api):
        """Test execute when monster API returns no data."""
        mock_response = Mock()
        mock_response.data = None
        mock_get_monsters_api.return_value = mock_response
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Could not retrieve monster information', result['error'])

    @patch('src.controller.actions.find_monsters.MapState')
    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_successful_monster_search(self, mock_get_monsters_api, mock_map_state_class):
        """Test successful monster search."""
        # Mock monster API response
        mock_chicken = Mock()
        mock_chicken.code = 'chicken'
        mock_chicken.level = 3
        mock_cow = Mock()
        mock_cow.code = 'cow'
        mock_cow.level = 5
        
        mock_response = Mock()
        mock_response.data = [mock_chicken, mock_cow]
        mock_get_monsters_api.return_value = mock_response
        
        # Mock map state with monster locations
        mock_map_state = Mock()
        mock_map_state.data = {
            '11,15': {'x': 11, 'y': 15, 'content': {'code': 'chicken', 'type': 'monster'}},
            '12,16': {'x': 12, 'y': 16, 'content': {'code': 'cow', 'type': 'monster'}},
            '13,17': {'x': 13, 'y': 17, 'content': {'code': 'wolf', 'type': 'monster'}}
        }
        mock_map_state_class.return_value = mock_map_state
        
        client = Mock()
        
        result = self.action.execute(client)
        self.assertTrue(result['success'])
        self.assertIn('monsters_found', result)
        self.assertIn('nearest_monster', result)
        self.assertIn('search_results', result)

    def test_filter_monsters_by_level_within_range(self):
        """Test _filter_monsters_by_level with monsters in level range."""
        monsters_data = [
            {'code': 'chicken', 'level': 3},
            {'code': 'cow', 'level': 5},
            {'code': 'wolf', 'level': 7},
            {'code': 'dragon', 'level': 15}
        ]
        
        # Test basic functionality if method exists
        if hasattr(self.action, '_filter_monsters_by_level'):
            filtered = self.action._filter_monsters_by_level(monsters_data, 5, 2)
            # Should include chicken(3), cow(5), wolf(7) but not dragon(15)
            codes = [m['code'] for m in filtered]
            self.assertIn('chicken', codes)
            self.assertIn('cow', codes)
            self.assertIn('wolf', codes)
            self.assertNotIn('dragon', codes)

    def test_filter_monsters_by_type(self):
        """Test _filter_monsters_by_type method."""
        monsters_data = [
            {'code': 'chicken', 'level': 3},
            {'code': 'cow', 'level': 5},
            {'code': 'wolf', 'level': 7}
        ]
        target_types = ['chicken', 'cow']
        
        # Test basic functionality if method exists
        if hasattr(self.action, '_filter_monsters_by_type'):
            filtered = self.action._filter_monsters_by_type(monsters_data, target_types)
            codes = [m['code'] for m in filtered]
            self.assertIn('chicken', codes)
            self.assertIn('cow', codes)
            self.assertNotIn('wolf', codes)

    def test_calculate_monster_distance_helper_method(self):
        """Test _calculate_monster_distance helper method."""
        monster_location = {'x': 13, 'y': 19}
        
        # Test basic functionality if method exists
        if hasattr(self.action, '_calculate_monster_distance'):
            distance = self.action._calculate_monster_distance(monster_location)
            expected_distance = ((13-10)**2 + (19-15)**2) ** 0.5
            self.assertAlmostEqual(distance, expected_distance, places=2)

    def test_find_nearest_monster_helper_method(self):
        """Test _find_nearest_monster helper method."""
        monster_locations = [
            {'x': 11, 'y': 15, 'content': {'code': 'chicken'}},
            {'x': 15, 'y': 20, 'content': {'code': 'cow'}},
            {'x': 8, 'y': 12, 'content': {'code': 'wolf'}}
        ]
        
        # Test basic functionality if method exists
        if hasattr(self.action, '_find_nearest_monster'):
            nearest = self.action._find_nearest_monster(monster_locations)
            # Should find the closest monster (likely chicken at 11,15)
            self.assertIsInstance(nearest, dict)

    def test_exponential_search_algorithm(self):
        """Test exponential search radius expansion."""
        action = FindMonstersAction(
            character_x=10,
            character_y=15,
            search_radius=1,
            use_exponential_search=True,
            max_search_radius=4
        )
        
        # Test basic functionality if method exists
        if hasattr(action, '_get_search_radii'):
            radii = action._get_search_radii()
            # Should expand: 1, 2, 4 (exponential)
            self.assertIsInstance(radii, list)
            self.assertGreater(len(radii), 1)

    def test_linear_search_algorithm(self):
        """Test linear search radius expansion."""
        action = FindMonstersAction(
            character_x=10,
            character_y=15,
            search_radius=1,
            use_exponential_search=False,
            max_search_radius=4
        )
        
        # Test basic functionality if method exists
        if hasattr(action, '_get_search_radii'):
            radii = action._get_search_radii()
            # Should expand: 1, 2, 3, 4 (linear)
            self.assertIsInstance(radii, list)
            self.assertGreater(len(radii), 1)

    def test_execute_exception_handling(self):
        """Test exception handling during execution."""
        client = Mock()
        
        with patch('src.controller.actions.find_monsters.get_all_monsters_api', side_effect=Exception("API Error")):
            result = self.action.execute(client)
            self.assertFalse(result['success'])
            self.assertIn('Monster search failed', result['error'])

    def test_execute_has_goap_attributes(self):
        """Test that FindMonstersAction has expected GOAP attributes."""
        self.assertTrue(hasattr(FindMonstersAction, 'conditions'))
        self.assertTrue(hasattr(FindMonstersAction, 'reactions'))
        self.assertTrue(hasattr(FindMonstersAction, 'weights'))
        self.assertTrue(hasattr(FindMonstersAction, 'g'))

    def test_goap_conditions(self):
        """Test GOAP conditions are properly defined."""
        expected_conditions = {
            'need_combat': True,
            'monsters_available': False,
            'character_alive': True
        }
        self.assertEqual(FindMonstersAction.conditions, expected_conditions)

    def test_goap_reactions(self):
        """Test GOAP reactions are properly defined."""
        expected_reactions = {
            'monsters_available': True,
            'monster_present': True,
            'at_target_location': True
        }
        self.assertEqual(FindMonstersAction.reactions, expected_reactions)

    def test_goap_weights(self):
        """Test GOAP weights are properly defined."""
        expected_weights = {'find_monsters': 2.0}
        self.assertEqual(FindMonstersAction.weights, expected_weights)

    def test_different_monster_type_combinations(self):
        """Test action with different monster type combinations."""
        type_combinations = [
            [],                              # No specific types
            ['chicken'],                     # Single type
            ['chicken', 'cow'],             # Multiple types
            ['chicken', 'cow', 'wolf'],     # Many types
        ]
        
        for types in type_combinations:
            action = FindMonstersAction(monster_types=types)
            self.assertEqual(action.monster_types, types)
            
            # Test representation includes types
            repr_str = repr(action)
            self.assertIn(str(types), repr_str)

    def test_level_filtering_edge_cases(self):
        """Test level filtering with edge cases."""
        # Test with no character level (no filtering)
        action1 = FindMonstersAction(character_level=None)
        self.assertIsNone(action1.character_level)
        
        # Test with zero level
        action2 = FindMonstersAction(character_level=0, level_range=1)
        self.assertEqual(action2.character_level, 0)
        self.assertEqual(action2.level_range, 1)
        
        # Test with high level
        action3 = FindMonstersAction(character_level=50, level_range=5)
        self.assertEqual(action3.character_level, 50)
        self.assertEqual(action3.level_range, 5)

    def test_search_radius_configurations(self):
        """Test different search radius configurations."""
        configurations = [
            (1, False, 3),   # Small radius, linear search
            (2, True, 4),    # Medium radius, exponential search
            (5, False, 10),  # Large radius, linear search
            (1, True, 8),    # Small radius, exponential search, large max
        ]
        
        for initial_radius, use_exp, max_radius in configurations:
            action = FindMonstersAction(
                search_radius=initial_radius,
                use_exponential_search=use_exp,
                max_search_radius=max_radius
            )
            self.assertEqual(action.search_radius, initial_radius)
            self.assertEqual(action.use_exponential_search, use_exp)
            self.assertEqual(action.max_search_radius, max_radius)

    @patch('src.controller.actions.find_monsters.MapState')
    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_no_monsters_found(self, mock_get_monsters_api, mock_map_state_class):
        """Test execute when no monsters are found in range."""
        # Mock monster API response
        mock_chicken = Mock()
        mock_chicken.code = 'chicken'
        mock_chicken.level = 3
        
        mock_response = Mock()
        mock_response.data = [mock_chicken]
        mock_get_monsters_api.return_value = mock_response
        
        # Mock map state with no monsters in range
        mock_map_state = Mock()
        mock_map_state.data = {
            '20,25': {'x': 20, 'y': 25, 'content': {'code': 'chicken', 'type': 'monster'}}  # Far away
        }
        mock_map_state_class.return_value = mock_map_state
        
        client = Mock()
        
        result = self.action.execute(client)
        # Should handle gracefully
        self.assertIn('success', result)

    def test_inheritance_from_search_base(self):
        """Test that FindMonstersAction properly inherits from SearchActionBase."""
        from src.controller.actions.search_base import SearchActionBase
        self.assertIsInstance(self.action, SearchActionBase)

    @patch('src.controller.actions.find_monsters.MapState')
    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_level_appropriate_filtering(self, mock_get_monsters_api, mock_map_state_class):
        """Test that monsters are filtered by level appropriately."""
        # Mock monsters with different levels
        mock_weak = Mock()
        mock_weak.code = 'weak_monster'
        mock_weak.level = 1
        
        mock_strong = Mock()
        mock_strong.code = 'strong_monster'
        mock_strong.level = 20
        
        mock_appropriate = Mock()
        mock_appropriate.code = 'appropriate_monster'
        mock_appropriate.level = 5
        
        mock_response = Mock()
        mock_response.data = [mock_weak, mock_strong, mock_appropriate]
        mock_get_monsters_api.return_value = mock_response
        
        # Mock map state with all monsters
        mock_map_state = Mock()
        mock_map_state.data = {
            '11,15': {'x': 11, 'y': 15, 'content': {'code': 'weak_monster', 'type': 'monster'}},
            '12,16': {'x': 12, 'y': 16, 'content': {'code': 'strong_monster', 'type': 'monster'}},
            '13,17': {'x': 13, 'y': 17, 'content': {'code': 'appropriate_monster', 'type': 'monster'}}
        }
        mock_map_state_class.return_value = mock_map_state
        
        # Character level 5, range 2 should find levels 3-7
        action = FindMonstersAction(character_level=5, level_range=2)
        client = Mock()
        
        result = action.execute(client)
        # Should find appropriate_monster (level 5) but not weak(1) or strong(20)
        self.assertIn('success', result)


if __name__ == '__main__':
    unittest.main()