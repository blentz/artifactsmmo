""" Test module for ExploreMapAction """

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.explore_map import ExploreMapAction

from test.fixtures import create_mock_client


class TestExploreMapAction(unittest.TestCase):
    """ Test cases for ExploreMapAction """

    def setUp(self):
        """ Set up test fixtures """
        self.action = ExploreMapAction()

    def test_init_basic(self):
        """ Test basic initialization """
        # Action should have no parameters stored as instance variables
        self.assertIsInstance(self.action, ExploreMapAction)
        self.assertFalse(hasattr(self.action, 'character_x'))
        self.assertFalse(hasattr(self.action, 'character_y'))
        self.assertFalse(hasattr(self.action, 'exploration_radius'))
        self.assertFalse(hasattr(self.action, 'exploration_strategy'))
        self.assertFalse(hasattr(self.action, 'target_content_types'))

    def test_init_custom_content_types(self):
        """ Test initialization with custom content types """
        action = ExploreMapAction()
        self.assertIsInstance(action, ExploreMapAction)
        self.assertFalse(hasattr(action, 'target_content_types'))

    def test_generate_spiral_coordinates(self):
        """ Test spiral coordinate generation """
        coords = self.action._generate_spiral_coordinates(10, 10, 5)
        
        # Should generate coordinates in spiral pattern
        self.assertTrue(len(coords) > 0)
        
        # All coordinates should be within exploration radius
        for x, y in coords:
            distance = max(abs(x - 10), abs(y - 10))
            self.assertLessEqual(distance, 5)

    def test_generate_random_coordinates(self):
        """ Test random coordinate generation """
        coords = self.action._generate_random_coordinates(10, 10, 5)
        
        # Should generate some coordinates
        self.assertTrue(len(coords) > 0)
        
        # Coordinates should be within radius (approximately)
        for x, y in coords:
            distance = max(abs(x - 10), abs(y - 10))
            self.assertLessEqual(distance, 5)

    def test_generate_cardinal_coordinates(self):
        """ Test cardinal direction coordinate generation """
        coords = self.action._generate_cardinal_coordinates(10, 10, 5)
        
        # Should generate coordinates in N, S, E, W directions
        self.assertTrue(len(coords) > 0)
        
        # Check some expected cardinal coordinates
        expected_coords = [
            (10, 11), (10, 9),   # North, South at distance 1
            (11, 10), (9, 10),   # East, West at distance 1
            (10, 15), (10, 5),   # North, South at distance 5
            (15, 10), (5, 10)    # East, West at distance 5
        ]
        
        for expected in expected_coords:
            self.assertIn(expected, coords)

    def test_generate_grid_coordinates(self):
        """ Test grid coordinate generation """
        coords = self.action._generate_grid_coordinates(10, 10, 5)
        
        # Should generate coordinates in grid pattern
        self.assertTrue(len(coords) > 0)
        
        # All coordinates should be within radius
        for x, y in coords:
            distance = max(abs(x - 10), abs(y - 10))
            self.assertLessEqual(distance, 5)

    def test_generate_exploration_coordinates_strategies(self):
        """ Test different exploration strategies """
        strategies = ["spiral", "random", "cardinal", "grid", "unknown"]
        
        for strategy in strategies:
            action = ExploreMapAction()
            coords = action._generate_exploration_coordinates(0, 0, 3, strategy)
            self.assertTrue(len(coords) > 0, f"Strategy {strategy} should generate coordinates")

    def test_analyze_location_monster(self):
        """ Test location analysis for monster content """
        mock_content = Mock()
        mock_content.type_ = "monster"
        mock_content.code = "goblin"
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        result = self.action._analyze_location(mock_map_data, 12, 8, 10, 10, ['monster', 'resource'])
        
        self.assertIsNotNone(result)
        self.assertEqual(result['content_type'], 'monster')
        self.assertEqual(result['monster_code'], 'goblin')
        self.assertEqual(result['x'], 12)
        self.assertEqual(result['y'], 8)
        self.assertEqual(result['distance_from_character'], 4)  # |12-10| + |8-10|

    def test_analyze_location_resource(self):
        """ Test location analysis for resource content """
        mock_content = Mock()
        mock_content.type_ = "resource"
        mock_content.code = "copper_rock"
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        result = self.action._analyze_location(mock_map_data, 10, 15, 10, 10, ['monster', 'resource'])
        
        self.assertIsNotNone(result)
        self.assertEqual(result['content_type'], 'resource')
        self.assertEqual(result['resource_code'], 'copper_rock')
        self.assertEqual(result['distance_from_character'], 5)

    def test_analyze_location_no_content(self):
        """ Test location analysis with no content """
        mock_map_data = Mock()
        mock_map_data.content = None
        
        result = self.action._analyze_location(mock_map_data, 10, 10, 10, 10, ["monster", "resource"])
        self.assertIsNone(result)

    def test_analyze_location_irrelevant_content(self):
        """ Test location analysis with irrelevant content type """
        mock_content = Mock()
        mock_content.type_ = "bank"  # Not in target_content_types
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        result = self.action._analyze_location(mock_map_data, 10, 10, 10, 10, ["monster", "resource"])
        self.assertIsNone(result)

    def test_suggest_next_action_monster_found(self):
        """ Test action suggestion when monster is found """
        discoveries = {
            "monsters": [
                {'x': 12, 'y': 10, 'distance_from_character': 2, 'monster_code': 'goblin'},
                {'x': 8, 'y': 10, 'distance_from_character': 2, 'monster_code': 'orc'}
            ],
            "resources": [],
            "workshops": [],
            "other": []
        }
        
        suggestion = self.action._suggest_next_action(discoveries, 10, 10, 5)
        
        self.assertEqual(suggestion['action'], 'move_to_monster')
        self.assertEqual(suggestion['priority'], 'high')
        self.assertIn('target_location', suggestion)
        self.assertIn('monster_code', suggestion)

    def test_suggest_next_action_resource_found(self):
        """ Test action suggestion when resource is found """
        discoveries = {
            "monsters": [],
            "resources": [
                {'x': 13, 'y': 10, 'distance_from_character': 3, 'resource_code': 'copper_rock'}
            ],
            "workshops": [],
            "other": []
        }
        
        suggestion = self.action._suggest_next_action(discoveries, 10, 10, 5)
        
        self.assertEqual(suggestion['action'], 'investigate_resource')
        self.assertEqual(suggestion['priority'], 'medium')
        self.assertIn('target_location', suggestion)
        self.assertIn('resource_code', suggestion)

    def test_suggest_next_action_workshop_found(self):
        """ Test action suggestion when workshop is found """
        discoveries = {
            "monsters": [],
            "resources": [],
            "workshops": [
                {'x': 15, 'y': 10, 'distance_from_character': 5, 'workshop_code': 'weaponcrafting'}
            ],
            "other": []
        }
        
        suggestion = self.action._suggest_next_action(discoveries, 10, 10, 5)
        
        self.assertEqual(suggestion['action'], 'visit_workshop')
        self.assertEqual(suggestion['priority'], 'medium')

    def test_suggest_next_action_nothing_found(self):
        """ Test action suggestion when nothing is found """
        discoveries = {
            "monsters": [],
            "resources": [],
            "workshops": [],
            "other": []
        }
        
        suggestion = self.action._suggest_next_action(discoveries, 10, 10, 5)
        
        self.assertEqual(suggestion['action'], 'relocate')
        self.assertEqual(suggestion['priority'], 'medium')
        self.assertIn('target_location', suggestion)

    def test_suggest_relocation_target(self):
        """ Test relocation target suggestion """
        target = self.action._suggest_relocation_target(10, 10, 5)
        
        # Should be a tuple of (x, y)
        self.assertIsInstance(target, tuple)
        self.assertEqual(len(target), 2)
        
        x, y = target
        # Should be farther away than exploration radius
        distance = max(abs(x - 10), abs(y - 10))
        self.assertGreater(distance, 5)

    def test_execute_success(self):
        """ Test successful exploration execution """
        client = create_mock_client()
        
        # Mock map API responses
        mock_content = Mock()
        mock_content.type_ = "monster"
        mock_content.code = "goblin"
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        
        from test.fixtures import MockActionContext
        context = MockActionContext(
            character_x=10,
            character_y=10,
            exploration_radius=5,
            exploration_strategy="spiral"
        )
        
        with patch('src.controller.actions.explore_map.get_map_api', return_value=mock_map_response):
            result = self.action.execute(client, context)
        
        self.assertTrue(result.success)
        self.assertIn('explored_locations', result.data)
        self.assertIn('discovered_monsters', result.data)
        self.assertIn('discoveries', result.data)
        self.assertIn('next_action_suggestion', result.data)
        self.assertIn('exploration_strategy_used', result.data)

    def test_execute_no_client(self):
        """ Test execution with no API client """
        from test.fixtures import MockActionContext
        context = MockActionContext(
            character_x=10,
            character_y=10,
            exploration_radius=5,
            exploration_strategy="spiral"
        )
        # ExploreMapAction returns success with 0 explored locations when client is None
        result = self.action.execute(None, context)
        self.assertTrue(result.success)  # Returns success
        self.assertEqual(result.data['explored_locations'], 0)  # But explores 0 locations

    def test_execute_api_failure(self):
        """ Test execution when API calls fail """
        client = create_mock_client()
        
        from test.fixtures import MockActionContext
        context = MockActionContext(
            character_x=10,
            character_y=10,
            exploration_radius=5,
            exploration_strategy="spiral"
        )
        
        with patch('src.controller.actions.explore_map.get_map_api', side_effect=Exception("API Error")):
            result = self.action.execute(client, context)
        
        # Should still succeed even if some API calls fail
        self.assertTrue(result.success)
        self.assertEqual(result.data['discovered_monsters'], 0)

    def test_repr(self):
        """ Test string representation """
        expected = "ExploreMapAction()"
        self.assertEqual(repr(self.action), expected)

    def test_cos_sin_approximations(self):
        """ Test trigonometric approximation functions """
        from src.controller.actions.explore_map import cos_approximation, sin_approximation
        
        # Test known values
        self.assertAlmostEqual(cos_approximation(0), 1.0, places=2)
        self.assertAlmostEqual(sin_approximation(0), 0.0, places=2)
        self.assertAlmostEqual(cos_approximation(3.14159/2), 0.0, places=2)  # 90 degrees
        self.assertAlmostEqual(sin_approximation(3.14159/2), 1.0, places=2)  # 90 degrees

    def test_multiple_discovery_types(self):
        """ Test handling multiple types of discoveries """
        discoveries = {
            "monsters": [
                {'x': 12, 'y': 10, 'distance_from_character': 2, 'monster_code': 'goblin'}
            ],
            "resources": [
                {'x': 8, 'y': 10, 'distance_from_character': 2, 'resource_code': 'copper'}
            ],
            "workshops": [
                {'x': 10, 'y': 12, 'distance_from_character': 2, 'workshop_code': 'forge'}
            ],
            "other": []
        }
        
        # Monsters should have priority
        suggestion = self.action._suggest_next_action(discoveries, 10, 10, 5)
        self.assertEqual(suggestion['action'], 'move_to_monster')


if __name__ == '__main__':
    unittest.main()