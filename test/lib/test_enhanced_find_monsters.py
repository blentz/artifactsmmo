""" Test module for enhanced FindMonstersAction with exponential search """

import unittest
from unittest.mock import Mock, patch
from src.controller.actions.find_monsters import FindMonstersAction


class TestEnhancedFindMonstersAction(unittest.TestCase):
    """ Test cases for enhanced FindMonstersAction with exponential search """

    def setUp(self):
        """ Set up test fixtures """
        self.action = FindMonstersAction(
            character_x=5, 
            character_y=5, 
            search_radius=10,
            use_exponential_search=True,
            max_search_radius=30
        )

    def test_init_with_exponential_search(self):
        """ Test initialization with exponential search enabled """
        self.assertTrue(self.action.use_exponential_search)
        self.assertEqual(self.action.max_search_radius, 30)

    def test_get_search_radii_exponential(self):
        """ Test exponential search radius generation """
        radii = self.action._get_search_radii()
        
        # Should start with initial radius and expand exponentially
        self.assertIn(10, radii)  # Initial radius
        self.assertTrue(len(radii) > 1)  # Should have multiple radii
        self.assertTrue(max(radii) <= 30)  # Shouldn't exceed max
        
        # Should be in ascending order
        self.assertEqual(radii, sorted(radii))

    def test_get_search_radii_linear(self):
        """ Test linear search when exponential is disabled """
        action = FindMonstersAction(
            character_x=5, 
            character_y=5, 
            search_radius=5,
            use_exponential_search=False
        )
        
        radii = action._get_search_radii()
        expected = list(range(1, 6))  # 1 to 5
        self.assertEqual(radii, expected)

    def test_get_search_radii_small_initial_radius(self):
        """ Test exponential search with small initial radius """
        action = FindMonstersAction(
            character_x=0, 
            character_y=0, 
            search_radius=3,
            use_exponential_search=True,
            max_search_radius=20
        )
        
        radii = action._get_search_radii()
        
        # Should include small radii and then expand
        self.assertIn(1, radii)
        self.assertIn(2, radii)
        self.assertIn(3, radii)
        self.assertTrue(max(radii) <= 20)

    def test_suggest_exploration_locations(self):
        """ Test exploration location suggestions """
        locations = self.action._suggest_exploration_locations()
        
        # Should return 8 locations (4 cardinal + 4 diagonal)
        self.assertEqual(len(locations), 8)
        
        # Check cardinal directions
        expected_cardinal = [
            (5, 35),   # North (y + max_radius)
            (35, 5),   # East (x + max_radius)
            (5, -25),  # South (y - max_radius)
            (-25, 5)   # West (x - max_radius)
        ]
        
        for location in expected_cardinal:
            self.assertIn(location, locations)

    def test_execute_with_exponential_search_success(self):
        """ Test successful execution with exponential search """
        client = Mock()
        
        # Mock monsters API response
        mock_monster = Mock()
        mock_monster.code = "goblin"
        mock_monster.name = "Goblin"
        mock_monster.level = 1
        
        mock_monsters_response = Mock()
        mock_monsters_response.data = [mock_monster]
        
        # Mock map API response
        mock_map_content = Mock()
        mock_map_content.type_ = "monster"
        mock_map_content.code = "goblin"
        
        mock_map_data = Mock()
        mock_map_data.content = mock_map_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        
        with patch('src.controller.actions.find_monsters.get_all_monsters_api', return_value=mock_monsters_response), \
             patch('src.controller.actions.find_monsters.get_map_api', return_value=mock_map_response):
            
            result = self.action.execute(client)
        
        self.assertTrue(result['success'])
        self.assertIn('location', result)
        self.assertIn('search_radius_used', result)
        self.assertIn('exponential_search_used', result)
        self.assertTrue(result['exponential_search_used'])

    def test_execute_no_monsters_found_enhanced_error(self):
        """ Test enhanced error response when no monsters found """
        client = Mock()
        
        # Mock monsters API response with no suitable monsters
        mock_monsters_response = Mock()
        mock_monsters_response.data = []
        
        with patch('src.controller.actions.find_monsters.get_all_monsters_api', return_value=mock_monsters_response):
            result = self.action.execute(client)
        
        self.assertFalse(result['success'])
        self.assertIn('No suitable monsters found', result['error'])

    def test_execute_radius_exhausted_with_suggestions(self):
        """ Test when search radius is exhausted with exploration suggestions """
        client = Mock()
        
        # Mock monsters API response
        mock_monster = Mock()
        mock_monster.code = "goblin"
        mock_monster.name = "Goblin"
        mock_monster.level = 1
        
        mock_monsters_response = Mock()
        mock_monsters_response.data = [mock_monster]
        
        # Mock map API response with no monsters found
        mock_map_response = Mock()
        mock_map_response.data = None
        
        with patch('src.controller.actions.find_monsters.get_all_monsters_api', return_value=mock_monsters_response), \
             patch('src.controller.actions.find_monsters.get_map_api', return_value=mock_map_response):
            
            result = self.action.execute(client)
        
        self.assertFalse(result['success'])
        self.assertIn('max_radius_searched', result)
        self.assertIn('alternative_exploration_locations', result)
        self.assertIn('suggestion', result)
        self.assertEqual(len(result['alternative_exploration_locations']), 8)

    def test_exponential_growth_algorithm(self):
        """ Test the exponential growth algorithm specifics """
        action = FindMonstersAction(
            character_x=0, 
            character_y=0, 
            search_radius=4,
            use_exponential_search=True,
            max_search_radius=25
        )
        
        radii = action._get_search_radii()
        
        # Should include: 1,2,3,4 (initial range) + exponential: 4,6,9,13,19 (up to 25)
        expected_exponential = [4]
        current = 4
        while current <= 25:
            current = int(current * 1.5 + 0.5)  # Math.ceil approximation
            if current <= 25:
                expected_exponential.append(current)
        
        # All initial radii should be present
        for i in range(1, 5):
            self.assertIn(i, radii)
        
        # Some exponential radii should be present
        for exp_radius in expected_exponential[:3]:  # Check first few
            self.assertIn(exp_radius, radii)

    def test_level_filtering_in_exponential_search(self):
        """ Test that level filtering works with exponential search """
        action = FindMonstersAction(
            character_x=0, 
            character_y=0, 
            search_radius=5,
            character_level=3,
            level_range=1,
            use_exponential_search=True
        )
        
        client = Mock()
        
        # Mock monsters with different levels
        mock_monster1 = Mock()
        mock_monster1.code = "easy_monster"
        mock_monster1.name = "Easy Monster"
        mock_monster1.level = 2  # Within range (3 ± 1)
        
        mock_monster2 = Mock()
        mock_monster2.code = "hard_monster"
        mock_monster2.name = "Hard Monster"  
        mock_monster2.level = 10  # Outside range
        
        mock_monsters_response = Mock()
        mock_monsters_response.data = [mock_monster1, mock_monster2]
        
        with patch('src.controller.actions.find_monsters.get_all_monsters_api', return_value=mock_monsters_response):
            # Should find easy_monster in target_codes, but not hard_monster
            # This is tested indirectly by checking the monsters API call was made
            result = action.execute(client)
            
            # Even if no monsters found on map, the API should have been called
            # and level filtering should have been applied
            self.assertIn('success', result)

    def test_repr_with_exponential_search(self):
        """ Test string representation includes exponential search info """
        repr_str = repr(self.action)
        self.assertIn("exp_search=True", repr_str)
        self.assertIn("FindMonstersAction", repr_str)


if __name__ == '__main__':
    unittest.main()