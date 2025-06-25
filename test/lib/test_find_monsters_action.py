import unittest
from unittest.mock import Mock, patch
import math

from artifactsmmo_api_client.client import AuthenticatedClient
from artifactsmmo_api_client.models.data_page_monster_schema import DataPageMonsterSchema
from artifactsmmo_api_client.models.monster_schema import MonsterSchema
from artifactsmmo_api_client.models.map_response_schema import MapResponseSchema
from artifactsmmo_api_client.models.map_schema import MapSchema
from artifactsmmo_api_client.models.map_content_schema import MapContentSchema
from artifactsmmo_api_client.models.map_content_type import MapContentType
from src.controller.actions.find_monsters import FindMonstersAction


class TestFindMonstersAction(unittest.TestCase):
    def setUp(self):
        self.client = AuthenticatedClient(base_url="https://api.artifactsmmo.com", token="test_token")
        self.character_x = 5
        self.character_y = 5
        self.search_radius = 10

    def test_find_monsters_action_initialization_default(self):
        action = FindMonstersAction()
        self.assertEqual(action.character_x, 0)
        self.assertEqual(action.character_y, 0)
        self.assertEqual(action.search_radius, 10)
        self.assertEqual(action.monster_types, [])

    def test_find_monsters_action_initialization_with_params(self):
        monster_types = ["slime", "goblin"]
        action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius,
            monster_types=monster_types
        )
        self.assertEqual(action.character_x, self.character_x)
        self.assertEqual(action.character_y, self.character_y)
        self.assertEqual(action.search_radius, self.search_radius)
        self.assertEqual(action.monster_types, monster_types)

    def test_find_monsters_action_repr_no_filter(self):
        action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius
        )
        expected_repr = f"FindMonstersAction({self.character_x}, {self.character_y}, radius={self.search_radius})"
        self.assertEqual(repr(action), expected_repr)

    def test_find_monsters_action_repr_with_filter(self):
        monster_types = ["slime", "goblin"]
        action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius,
            monster_types=monster_types
        )
        expected_repr = f"FindMonstersAction({self.character_x}, {self.character_y}, radius={self.search_radius}, types={monster_types})"
        self.assertEqual(repr(action), expected_repr)

    def test_find_monsters_action_class_attributes(self):
        action = FindMonstersAction()
        self.assertIsInstance(action.conditions, dict)
        self.assertIsInstance(action.reactions, dict)
        self.assertIsInstance(action.weights, dict)
        self.assertIsNone(action.g)

    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_no_monsters_response(self, mock_get_monsters):
        mock_get_monsters.return_value = None
        
        action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius
        )
        result = action.execute(client=self.client)
        
        self.assertIsNotNone(result)
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'No monsters data available from API')
        mock_get_monsters.assert_called_once_with(client=self.client, size=100)

    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_empty_monsters_data(self, mock_get_monsters):
        mock_response = Mock()
        mock_response.data = []
        mock_get_monsters.return_value = mock_response
        
        action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius
        )
        result = action.execute(client=self.client)
        
        self.assertIsNotNone(result)
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'No suitable monsters found matching criteria')

    @patch('src.controller.actions.find_monsters.get_map_api')
    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_no_matching_monsters(self, mock_get_monsters, mock_get_map):
        # Setup monster data
        mock_slime = Mock()
        mock_slime.name = "Green Slime"
        mock_slime.code = "green_slime"
        
        mock_response = Mock()
        mock_response.data = [mock_slime]
        mock_get_monsters.return_value = mock_response
        
        # Setup map responses with no monsters
        mock_map_data = Mock()
        mock_map_data.content = None
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map.return_value = mock_map_response
        
        action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=2,
            monster_types=["slime"]
        )
        result = action.execute(client=self.client)
        
        self.assertIsNotNone(result)
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'No monsters found within radius 2')

    @patch('src.controller.actions.find_monsters.get_map_api')
    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_find_monster_success(self, mock_get_monsters, mock_get_map):
        # Setup monster data
        mock_slime = Mock()
        mock_slime.name = "Green Slime"
        mock_slime.code = "green_slime"
        
        mock_response = Mock()
        mock_response.data = [mock_slime]
        mock_get_monsters.return_value = mock_response
        
        # Setup map responses
        def map_side_effect(x, y, client):
            if x == 3 and y == 3:
                # Monster at (3, 3)
                mock_content = Mock()
                mock_content.type_ = 'monster'
                mock_content.code = 'green_slime'
                
                mock_map_data = Mock()
                mock_map_data.content = mock_content
                
                mock_map_response = Mock()
                mock_map_response.data = mock_map_data
                return mock_map_response
            else:
                # Empty locations
                mock_map_data = Mock()
                mock_map_data.content = None
                mock_map_response = Mock()
                mock_map_response.data = mock_map_data
                return mock_map_response
        
        mock_get_map.side_effect = map_side_effect
        
        action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=3,
            monster_types=["slime"]
        )
        result = action.execute(client=self.client)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['location'], (3, 3))
        self.assertEqual(result['monster_code'], 'green_slime')
        self.assertEqual(result['target_codes'], ['green_slime'])
        
        expected_distance = math.sqrt((3 - 5) ** 2 + (3 - 5) ** 2)
        self.assertAlmostEqual(result['distance'], expected_distance, places=5)

    @patch('src.controller.actions.find_monsters.get_map_api')
    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_find_closest_monster(self, mock_get_monsters, mock_get_map):
        # Setup monster data
        mock_slime = Mock()
        mock_slime.name = "Green Slime"
        mock_slime.code = "green_slime"
        
        mock_response = Mock()
        mock_response.data = [mock_slime]
        mock_get_monsters.return_value = mock_response
        
        # Setup map responses with monsters at different distances
        def map_side_effect(x, y, client):
            if (x == 3 and y == 3) or (x == 7 and y == 7):
                # Monsters at (3, 3) and (7, 7)
                mock_content = Mock()
                mock_content.type_ = 'monster'
                mock_content.code = 'green_slime'
                
                mock_map_data = Mock()
                mock_map_data.content = mock_content
                
                mock_map_response = Mock()
                mock_map_response.data = mock_map_data
                return mock_map_response
            else:
                # Empty locations
                mock_map_data = Mock()
                mock_map_data.content = None
                mock_map_response = Mock()
                mock_map_response.data = mock_map_data
                return mock_map_response
        
        mock_get_map.side_effect = map_side_effect
        
        action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=5
        )
        result = action.execute(client=self.client)
        
        self.assertIsNotNone(result)
        # Should find the closer monster at (3, 3)
        self.assertEqual(result['location'], (3, 3))

    @patch('src.controller.actions.find_monsters.get_map_api')
    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_filter_by_monster_types_name_match(self, mock_get_monsters, mock_get_map):
        # Setup monster data with different types
        mock_slime = Mock()
        mock_slime.name = "Green Slime"
        mock_slime.code = "green_slime"
        
        mock_goblin = Mock()
        mock_goblin.name = "Forest Goblin"
        mock_goblin.code = "forest_goblin"
        
        mock_response = Mock()
        mock_response.data = [mock_slime, mock_goblin]
        mock_get_monsters.return_value = mock_response
        
        # Setup map response with slime
        mock_content = Mock()
        mock_content.type_ = 'monster'
        mock_content.code = 'green_slime'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map.return_value = mock_map_response
        
        action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=2,
            monster_types=["slime"]  # Only looking for slimes
        )
        result = action.execute(client=self.client)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['monster_code'], 'green_slime')
        self.assertEqual(result['target_codes'], ['green_slime'])

    @patch('src.controller.actions.find_monsters.get_map_api')
    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_filter_by_monster_types_code_match(self, mock_get_monsters, mock_get_map):
        # Setup monster data
        mock_monster = Mock()
        mock_monster.name = "Test Monster"
        mock_monster.code = "test_slime_monster"
        
        mock_response = Mock()
        mock_response.data = [mock_monster]
        mock_get_monsters.return_value = mock_response
        
        # Setup map response
        mock_content = Mock()
        mock_content.type_ = 'monster'
        mock_content.code = 'test_slime_monster'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map.return_value = mock_map_response
        
        action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=2,
            monster_types=["slime"]  # Should match "slime" in code
        )
        result = action.execute(client=self.client)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['monster_code'], 'test_slime_monster')

    @patch('src.controller.actions.find_monsters.get_map_api')
    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_no_filter_finds_all_monsters(self, mock_get_monsters, mock_get_map):
        # Setup monster data
        mock_slime = Mock()
        mock_slime.name = "Green Slime"
        mock_slime.code = "green_slime"
        
        mock_goblin = Mock()
        mock_goblin.name = "Forest Goblin"
        mock_goblin.code = "forest_goblin"
        
        mock_response = Mock()
        mock_response.data = [mock_slime, mock_goblin]
        mock_get_monsters.return_value = mock_response
        
        # Setup map response with slime
        mock_content = Mock()
        mock_content.type_ = 'monster'
        mock_content.code = 'green_slime'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map.return_value = mock_map_response
        
        action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=2
            # No monster_types filter - should find all
        )
        result = action.execute(client=self.client)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['monster_code'], 'green_slime')
        self.assertEqual(set(result['target_codes']), {'green_slime', 'forest_goblin'})

    @patch('src.controller.actions.find_monsters.get_map_api')
    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_handles_map_api_exceptions(self, mock_get_monsters, mock_get_map):
        # Setup monster data
        mock_slime = Mock()
        mock_slime.name = "Green Slime"
        mock_slime.code = "green_slime"
        
        mock_response = Mock()
        mock_response.data = [mock_slime]
        mock_get_monsters.return_value = mock_response
        
        # Make map API raise exception
        mock_get_map.side_effect = Exception("API Error")
        
        action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=2
        )
        result = action.execute(client=self.client)
        
        # Should handle exception gracefully and return error response
        self.assertIsNotNone(result)
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'No monsters found within radius 2')

    @patch('src.controller.actions.find_monsters.get_map_api')
    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_handles_partial_map_failures(self, mock_get_monsters, mock_get_map):
        # Setup monster data
        mock_slime = Mock()
        mock_slime.name = "Green Slime"
        mock_slime.code = "green_slime"
        
        mock_response = Mock()
        mock_response.data = [mock_slime]
        mock_get_monsters.return_value = mock_response
        
        # Setup map responses - some fail, one succeeds
        def map_side_effect(x, y, client):
            if x == 3 and y == 3:
                # Success case
                mock_content = Mock()
                mock_content.type_ = 'monster'
                mock_content.code = 'green_slime'
                
                mock_map_data = Mock()
                mock_map_data.content = mock_content
                
                mock_map_response = Mock()
                mock_map_response.data = mock_map_data
                return mock_map_response
            else:
                # Failure case
                raise Exception("API Error")
        
        mock_get_map.side_effect = map_side_effect
        
        action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=3
        )
        result = action.execute(client=self.client)
        
        # Should still find the successful one
        self.assertIsNotNone(result)
        self.assertEqual(result['location'], (3, 3))

    @patch('src.controller.actions.find_monsters.get_map_api')
    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_search_radius_optimization(self, mock_get_monsters, mock_get_map):
        # Setup monster data
        mock_slime = Mock()
        mock_slime.name = "Green Slime"
        mock_slime.code = "green_slime"
        
        mock_response = Mock()
        mock_response.data = [mock_slime]
        mock_get_monsters.return_value = mock_response
        
        # Track API calls
        api_calls = []
        
        def map_side_effect(x, y, client):
            api_calls.append((x, y))
            if x == 4 and y == 5:  # Distance 1 from (5,5)
                mock_content = Mock()
                mock_content.type_ = 'monster'
                mock_content.code = 'green_slime'
                
                mock_map_data = Mock()
                mock_map_data.content = mock_content
                
                mock_map_response = Mock()
                mock_map_response.data = mock_map_data
                return mock_map_response
            else:
                mock_map_data = Mock()
                mock_map_data.content = None
                mock_map_response = Mock()
                mock_map_response.data = mock_map_data
                return mock_map_response
        
        mock_get_map.side_effect = map_side_effect
        
        action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=5
        )
        result = action.execute(client=self.client)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['location'], (4, 5))
        
        # Should stop searching after finding monster at radius 1
        # Only radius 1 coordinates should be checked
        expected_radius_1_coords = {(4, 5), (6, 5), (5, 4), (5, 6)}
        actual_coords = set(api_calls)
        self.assertTrue(expected_radius_1_coords.issubset(actual_coords))

    def test_execute_monster_types_none_becomes_empty_list(self):
        action = FindMonstersAction(monster_types=None)
        self.assertEqual(action.monster_types, [])

    @patch('src.controller.actions.find_monsters.get_map_api')
    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_no_target_codes_after_filtering(self, mock_get_monsters, mock_get_map):
        # Setup monster data that doesn't match filter
        mock_dragon = Mock()
        mock_dragon.name = "Fire Dragon"
        mock_dragon.code = "fire_dragon"
        
        mock_response = Mock()
        mock_response.data = [mock_dragon]
        mock_get_monsters.return_value = mock_response
        
        action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=2,
            monster_types=["slime"]  # Won't match dragon
        )
        result = action.execute(client=self.client)
        
        self.assertIsNotNone(result)
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'No suitable monsters found matching criteria')
        # Map API should not be called if no target codes
        mock_get_map.assert_not_called()


    @patch('src.controller.actions.find_monsters.get_map_api')
    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_level_filtering_within_range(self, mock_get_monsters, mock_get_map):
        # Setup monster data with different levels
        mock_weak_slime = Mock()
        mock_weak_slime.name = "Weak Slime"
        mock_weak_slime.code = "weak_slime"
        mock_weak_slime.level = 7  # Too weak (character level 10, range 2, so 7 is level_diff=3 > 2)
        
        mock_normal_slime = Mock()
        mock_normal_slime.name = "Green Slime"
        mock_normal_slime.code = "green_slime"
        mock_normal_slime.level = 9  # Within range (level_diff=1 <= 2)
        
        mock_strong_slime = Mock()
        mock_strong_slime.name = "Strong Slime"
        mock_strong_slime.code = "strong_slime"
        mock_strong_slime.level = 13  # Too strong (level_diff=3 > 2)
        
        mock_response = Mock()
        mock_response.data = [mock_weak_slime, mock_normal_slime, mock_strong_slime]
        mock_get_monsters.return_value = mock_response
        
        # Setup map response with normal slime
        mock_content = Mock()
        mock_content.type_ = 'monster'
        mock_content.code = 'green_slime'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map.return_value = mock_map_response
        
        action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=2,
            character_level=10,
            level_range=2
        )
        result = action.execute(client=self.client)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['monster_code'], 'green_slime')
        # Should only include level-appropriate monsters in target codes
        self.assertEqual(result['target_codes'], ['green_slime'])

    @patch('src.controller.actions.find_monsters.get_map_api')
    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_level_filtering_no_matches_returns_none(self, mock_get_monsters, mock_get_map):
        # Setup monster data where none are in level range
        mock_weak_slime = Mock()
        mock_weak_slime.name = "Weak Slime"
        mock_weak_slime.code = "weak_slime"
        mock_weak_slime.level = 5  # Too weak (level_diff=5 > 2)
        
        mock_strong_slime = Mock()
        mock_strong_slime.name = "Strong Slime"
        mock_strong_slime.code = "strong_slime"
        mock_strong_slime.level = 25  # Too strong (level_diff=15 > 2)
        
        mock_response = Mock()
        mock_response.data = [mock_weak_slime, mock_strong_slime]
        mock_get_monsters.return_value = mock_response
        
        action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=2,
            character_level=10,
            level_range=2
        )
        result = action.execute(client=self.client)
        
        # Should return error response when no monsters match level criteria
        self.assertIsNotNone(result)
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'No suitable monsters found matching criteria')
        # Map API should not be called if no target codes
        mock_get_map.assert_not_called()

    @patch('src.controller.actions.find_monsters.get_map_api')
    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_level_filtering_boundary_cases(self, mock_get_monsters, mock_get_map):
        # Setup monster data at exact boundaries (level_range = 2)
        mock_min_level = Mock()
        mock_min_level.name = "Min Level Monster"
        mock_min_level.code = "min_monster"
        mock_min_level.level = 8  # Exactly at min level (10 - 2, level_diff=2)
        
        mock_max_level = Mock()
        mock_max_level.name = "Max Level Monster"
        mock_max_level.code = "max_monster"
        mock_max_level.level = 12  # Exactly at max level (10 + 2, level_diff=2)
        
        mock_below_min = Mock()
        mock_below_min.name = "Below Min Monster"
        mock_below_min.code = "below_min"
        mock_below_min.level = 7  # Just below min (level_diff=3 > 2)
        
        mock_above_max = Mock()
        mock_above_max.name = "Above Max Monster"
        mock_above_max.code = "above_max"
        mock_above_max.level = 13  # Just above max (level_diff=3 > 2)
        
        mock_response = Mock()
        mock_response.data = [mock_min_level, mock_max_level, mock_below_min, mock_above_max]
        mock_get_monsters.return_value = mock_response
        
        # Setup map response with min level monster
        mock_content = Mock()
        mock_content.type_ = 'monster'
        mock_content.code = 'min_monster'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map.return_value = mock_map_response
        
        action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=2,
            character_level=10,
            level_range=2
        )
        result = action.execute(client=self.client)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['monster_code'], 'min_monster')
        # Should only include monsters exactly at or within boundaries
        self.assertEqual(set(result['target_codes']), {'min_monster', 'max_monster'})

    @patch('src.controller.actions.find_monsters.get_map_api')
    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_no_character_level_uses_all_monsters(self, mock_get_monsters, mock_get_map):
        # Setup monster data with different levels
        mock_low_monster = Mock()
        mock_low_monster.name = "Low Level Monster"
        mock_low_monster.code = "low_monster"
        mock_low_monster.level = 1
        
        mock_high_monster = Mock()
        mock_high_monster.name = "High Level Monster"
        mock_high_monster.code = "high_monster"
        mock_high_monster.level = 50
        
        mock_response = Mock()
        mock_response.data = [mock_low_monster, mock_high_monster]
        mock_get_monsters.return_value = mock_response
        
        # Setup map response
        mock_content = Mock()
        mock_content.type_ = 'monster'
        mock_content.code = 'low_monster'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map.return_value = mock_map_response
        
        action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=2
            # No character_level provided
        )
        result = action.execute(client=self.client)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['monster_code'], 'low_monster')
        # Should include all monsters when no character level is provided
        self.assertEqual(set(result['target_codes']), {'low_monster', 'high_monster'})

    @patch('src.controller.actions.find_monsters.get_map_api')
    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_monsters_without_level_attribute(self, mock_get_monsters, mock_get_map):
        # Setup monster data where some monsters don't have level
        mock_monster_no_level = Mock(spec=['name', 'code'])  # Specify only name and code, no level
        mock_monster_no_level.name = "No Level Monster"
        mock_monster_no_level.code = "no_level_monster"
        # No level attribute - getattr will return 1 as default
        
        mock_monster_with_level = Mock()
        mock_monster_with_level.name = "Level Monster"
        mock_monster_with_level.code = "level_monster"
        mock_monster_with_level.level = 10
        
        mock_response = Mock()
        mock_response.data = [mock_monster_no_level, mock_monster_with_level]
        mock_get_monsters.return_value = mock_response
        
        # Setup map response with level monster
        mock_content = Mock()
        mock_content.type_ = 'monster'
        mock_content.code = 'level_monster'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map.return_value = mock_map_response
        
        action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=2,
            character_level=10,
            level_range=2
        )
        result = action.execute(client=self.client)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['monster_code'], 'level_monster')
        # Should include both monsters: no_level_monster (defaults to level 1, level_diff=9 > 2, filtered out)
        # and level_monster (level 10, level_diff=0 <= 2, included)
        self.assertEqual(result['target_codes'], ['level_monster'])

    def test_find_monsters_action_initialization_with_character_level(self):
        action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=self.search_radius,
            character_level=15,
            level_range=3
        )
        self.assertEqual(action.character_level, 15)
        self.assertEqual(action.level_range, 3)

    def test_find_monsters_action_initialization_default_character_level(self):
        action = FindMonstersAction()
        self.assertIsNone(action.character_level)
        self.assertEqual(action.level_range, 2)  # Default level range

    @patch('src.controller.actions.find_monsters.get_map_api')
    @patch('src.controller.actions.find_monsters.get_all_monsters_api')
    def test_execute_custom_level_range(self, mock_get_monsters, mock_get_map):
        # Test with custom level range of 5
        mock_monster = Mock()
        mock_monster.name = "Test Monster"
        mock_monster.code = "test_monster"
        mock_monster.level = 15  # level_diff = 5 from character level 10
        
        mock_response = Mock()
        mock_response.data = [mock_monster]
        mock_get_monsters.return_value = mock_response
        
        # Setup map response
        mock_content = Mock()
        mock_content.type_ = 'monster'
        mock_content.code = 'test_monster'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map.return_value = mock_map_response
        
        action = FindMonstersAction(
            character_x=self.character_x,
            character_y=self.character_y,
            search_radius=2,
            character_level=10,
            level_range=5  # Custom range allowing level_diff=5
        )
        result = action.execute(client=self.client)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['monster_code'], 'test_monster')
        self.assertEqual(result['target_codes'], ['test_monster'])


if __name__ == '__main__':
    unittest.main()
