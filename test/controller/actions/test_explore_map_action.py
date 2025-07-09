""" Test module for ExploreMapAction """

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.explore_map import ExploreMapAction

from test.fixtures import create_mock_client, MockActionContext


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
    
    def test_execute_explores_multiple_locations_with_different_content_types(self):
        """Test execute method finds different content types including resource, workshop, and other."""
        context = MockActionContext(
            character_name="TestCharacter",
            character_x=10,
            character_y=10,
            exploration_radius=1,
            exploration_strategy='cardinal',
            target_content_types=['monster', 'resource', 'workshop', 'other', 'town']  # Include all types we'll test
        )
        
        # Create a sequence of map responses for different locations
        # Cardinal with radius 1 explores: center(10,10), north(10,11), south(10,9), east(11,10), west(9,10)
        map_responses = []
        
        # Center location (10,10) - no content
        center_response = Mock()
        center_response.data = Mock()
        center_response.data.content = None
        map_responses.append(center_response)
        
        # North location (10,11) - resource
        north_response = Mock()
        north_response.data = Mock()
        north_response.data.content = Mock()
        north_response.data.content.type_ = 'resource'
        north_response.data.content.code = 'copper_ore'
        map_responses.append(north_response)
        
        # South location (10,9) - workshop
        south_response = Mock()
        south_response.data = Mock()
        south_response.data.content = Mock()
        south_response.data.content.type_ = 'workshop'
        south_response.data.content.code = 'weaponcrafting'
        map_responses.append(south_response)
        
        # East location (11,10) - other content
        east_response = Mock()
        east_response.data = Mock()
        east_response.data.content = Mock()
        east_response.data.content.type_ = 'town'  # Not monster/resource/workshop
        east_response.data.content.code = 'spawn_town'
        map_responses.append(east_response)
        
        # West location (9,10) - no map response
        map_responses.append(None)
        
        with patch('src.controller.actions.explore_map.get_map_api', side_effect=map_responses):
            result = self.action.execute(create_mock_client(), context)
        
        self.assertTrue(result.success)
        discoveries = result.data['discoveries']
        
        # Check that resource was discovered
        self.assertEqual(len(discoveries['resources']), 1)
        self.assertEqual(discoveries['resources'][0]['resource_code'], 'copper_ore')
        
        # Check that workshop was discovered
        self.assertEqual(len(discoveries['workshops']), 1)
        self.assertEqual(discoveries['workshops'][0]['workshop_code'], 'weaponcrafting')
        
        # Check that other content was discovered (town type)
        self.assertEqual(len(discoveries['other']), 1)
        self.assertEqual(discoveries['other'][0]['content_type'], 'town')
    
    def test_execute_exception_handling(self):
        """Test execute method handles exceptions gracefully."""
        context = MockActionContext(
            character_name="TestCharacter", 
            character_x=10,
            character_y=10,
            exploration_radius=2
        )
        
        # First mock call will work, subsequent calls will raise exception to trigger the overall exception handler
        def side_effect_func(*args, **kwargs):
            # Raise exception on the first call to trigger the overall exception handler
            raise Exception("API error")
            
        # Mock generate_exploration_coordinates to raise exception
        with patch.object(self.action, '_generate_exploration_coordinates', side_effect=Exception("API error")):
            result = self.action.execute(create_mock_client(), context)
        
        self.assertFalse(result.success)
        self.assertIn("Map exploration failed: API error", result.error)
    
    def test_analyze_location_workshop_with_code(self):
        """Test analyze_location correctly extracts workshop code."""
        # Create map data with workshop content
        map_data = Mock()
        map_data.content = Mock()
        map_data.content.type_ = 'workshop'
        map_data.content.code = 'smithing_workshop'
        
        location_info = self.action._analyze_location(map_data, 10, 15, 5, 5, ['workshop'])
        
        self.assertEqual(location_info['content_type'], 'workshop')
        self.assertEqual(location_info['workshop_code'], 'smithing_workshop')
        self.assertEqual(location_info['x'], 10)
        self.assertEqual(location_info['y'], 15)
    
    def test_execute_simple_workshop_and_other_discovery(self):
        """Simple test to ensure workshop and other categorization branches are covered."""
        context = MockActionContext(
            character_name="TestCharacter",
            character_x=0,
            character_y=0,
            exploration_radius=1,
            exploration_strategy='cardinal',
            target_content_types=['workshop', 'other']
        )
        
        # Mock only two locations - one workshop, one other
        workshop_response = Mock()
        workshop_response.data = Mock()
        workshop_response.data.content = Mock()
        workshop_response.data.content.type_ = 'workshop'
        workshop_response.data.content.code = 'test_workshop'
        
        other_response = Mock()
        other_response.data = Mock()
        other_response.data.content = Mock()
        other_response.data.content.type_ = 'other'
        other_response.data.content.code = 'test_other'
        
        responses = [
            Mock(data=Mock(content=None)),  # Center - no content
            workshop_response,  # First cardinal direction
            other_response,     # Second cardinal direction
            None,              # Third location fails
            None               # Fourth location fails  
        ]
        
        with patch('src.controller.actions.explore_map.get_map_api', side_effect=responses):
            result = self.action.execute(create_mock_client(), context)
        
        self.assertTrue(result.success)
        discoveries = result.data['discoveries']
        
        # Verify workshop was categorized correctly (line 65-66)
        self.assertEqual(len(discoveries['workshops']), 1)
        self.assertEqual(discoveries['workshops'][0]['workshop_code'], 'test_workshop')
        
        # Verify other was categorized correctly (line 67-68)
        self.assertEqual(len(discoveries['other']), 1)
        self.assertEqual(discoveries['other'][0]['content_type'], 'other')


if __name__ == '__main__':
    unittest.main()