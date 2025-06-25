"""Unit tests for KnowledgeBase class."""

import unittest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.controller.knowledge.base import KnowledgeBase
from src.game.map.state import MapState


class TestKnowledgeBase(unittest.TestCase):
    """Test cases for KnowledgeBase class."""

    def setUp(self) -> None:
        """Set up test fixtures before each test method."""
        # Create a temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        self.temp_file.close()
        
        # Create KnowledgeBase instance with temporary file
        self.knowledge_base = KnowledgeBase(filename=self.temp_file.name)
        
        # Mock MapState
        self.mock_map_state = Mock(spec=MapState)
        self.mock_map_state.data = {}

    def tearDown(self) -> None:
        """Clean up after each test method."""
        try:
            os.unlink(self.temp_file.name)
        except FileNotFoundError:
            pass

    def test_init(self) -> None:
        """Test KnowledgeBase initialization."""
        # Verify initial structure
        self.assertIsInstance(self.knowledge_base.data, dict)
        self.assertIn('monsters', self.knowledge_base.data)
        self.assertIn('combat_insights', self.knowledge_base.data)
        self.assertIn('resources', self.knowledge_base.data)
        self.assertIn('character_insights', self.knowledge_base.data)
        self.assertIn('learning_stats', self.knowledge_base.data)
        
        # Verify learning stats structure
        learning_stats = self.knowledge_base.data['learning_stats']
        self.assertEqual(learning_stats['total_combats'], 0)
        self.assertEqual(learning_stats['unique_monsters_fought'], 0)
        self.assertIsNone(learning_stats['last_learning_session'])
        self.assertEqual(learning_stats['learning_version'], '1.0')

    def test_learn_from_content_discovery_monster(self) -> None:
        """Test learning from monster discovery."""
        content_data = {
            'name': 'Green Slime',
            'type_': 'monster',
            'code': 'green_slime'
        }
        
        self.knowledge_base.learn_from_content_discovery(
            'monster', 'green_slime', 5, 5, content_data
        )
        
        # Verify monster was recorded
        self.assertIn('green_slime', self.knowledge_base.data['monsters'])
        monster_info = self.knowledge_base.data['monsters']['green_slime']
        
        self.assertEqual(monster_info['code'], 'green_slime')
        self.assertEqual(monster_info['name'], 'Green Slime')
        self.assertEqual(monster_info['encounter_count'], 1)
        self.assertIsNotNone(monster_info['first_discovered'])
        self.assertIsNotNone(monster_info['last_seen'])
        self.assertEqual(monster_info['combat_results'], [])
        
        # Verify learning stats updated
        self.assertEqual(self.knowledge_base.data['learning_stats']['unique_monsters_fought'], 1)

    def test_learn_from_content_discovery_resource(self) -> None:
        """Test learning from resource discovery."""
        content_data = {
            'name': 'Copper Rock',
            'type_': 'resource',
            'code': 'copper_rock'
        }
        
        self.knowledge_base.learn_from_content_discovery(
            'resource', 'copper_rock', 10, 10, content_data
        )
        
        # Verify resource was recorded
        self.assertIn('copper_rock', self.knowledge_base.data['resources'])
        resource_info = self.knowledge_base.data['resources']['copper_rock']
        
        self.assertEqual(resource_info['code'], 'copper_rock')
        self.assertEqual(resource_info['name'], 'Copper Rock')
        self.assertEqual(resource_info['harvest_attempts'], 0)
        self.assertEqual(resource_info['successful_harvests'], 0)
        self.assertIsNotNone(resource_info['first_discovered'])
        self.assertIsNotNone(resource_info['last_seen'])

    def test_record_combat_result_new_monster(self) -> None:
        """Test recording combat result for new monster."""
        character_data = {
            'level': 5,
            'hp': 80,
            'hp_before': 100
        }
        
        fight_data = {
            'xp': 25,
            'turns': 3,
            'drops': ['slime_goo'],
            'gold': 10
        }
        
        self.knowledge_base.record_combat_result(
            'green_slime', 'win', character_data, fight_data
        )
        
        # Verify monster was created and combat recorded
        self.assertIn('green_slime', self.knowledge_base.data['monsters'])
        monster_info = self.knowledge_base.data['monsters']['green_slime']
        
        self.assertEqual(len(monster_info['combat_results']), 1)
        combat_result = monster_info['combat_results'][0]
        
        self.assertEqual(combat_result['result'], 'win')
        self.assertEqual(combat_result['character_level'], 5)
        self.assertEqual(combat_result['character_hp_before'], 100)
        self.assertEqual(combat_result['character_hp_after'], 80)
        self.assertEqual(combat_result['damage_taken'], 20)
        self.assertEqual(combat_result['xp_gained'], 25)
        self.assertEqual(combat_result['turns'], 3)
        self.assertEqual(combat_result['drops'], ['slime_goo'])
        self.assertEqual(combat_result['gold_gained'], 10)
        
        # Verify learning stats updated
        self.assertEqual(self.knowledge_base.data['learning_stats']['total_combats'], 1)
        self.assertIsNotNone(self.knowledge_base.data['learning_stats']['last_learning_session'])

    def test_record_multiple_combat_results(self) -> None:
        """Test recording multiple combat results for same monster."""
        character_data_1 = {'level': 3, 'hp': 90, 'hp_before': 100}
        character_data_2 = {'level': 3, 'hp': 70, 'hp_before': 100}
        
        # Record two combat results
        self.knowledge_base.record_combat_result('green_slime', 'win', character_data_1)
        self.knowledge_base.record_combat_result('green_slime', 'loss', character_data_2)
        
        monster_info = self.knowledge_base.data['monsters']['green_slime']
        self.assertEqual(len(monster_info['combat_results']), 2)
        self.assertEqual(self.knowledge_base.data['learning_stats']['total_combats'], 2)

    def test_get_monster_combat_success_rate(self) -> None:
        """Test calculating monster combat success rate."""
        # No data available
        success_rate = self.knowledge_base.get_monster_combat_success_rate('unknown_monster', 5)
        self.assertEqual(success_rate, -1.0)
        
        # Add combat data for level 5 character
        character_data_win = {'level': 5, 'hp': 80}
        character_data_loss = {'level': 5, 'hp': 40}
        
        self.knowledge_base.record_combat_result('test_monster', 'win', character_data_win)
        self.knowledge_base.record_combat_result('test_monster', 'win', character_data_win)
        self.knowledge_base.record_combat_result('test_monster', 'loss', character_data_loss)
        
        # Test success rate calculation (2 wins out of 3 = 0.67)
        success_rate = self.knowledge_base.get_monster_combat_success_rate('test_monster', 5)
        self.assertAlmostEqual(success_rate, 2/3, places=2)
        
        # Test with different level (should return -1 if no relevant data)
        success_rate = self.knowledge_base.get_monster_combat_success_rate('test_monster', 10)
        self.assertEqual(success_rate, -1.0)

    def test_find_suitable_monsters_empty_map(self) -> None:
        """Test finding suitable monsters with empty map state."""
        # Empty map state
        result = self.knowledge_base.find_suitable_monsters(
            self.mock_map_state, character_level=5, current_x=0, current_y=0
        )
        self.assertEqual(result, [])

    def test_find_suitable_monsters_with_data(self) -> None:
        """Test finding suitable monsters with map data."""
        # Set up map data with monsters
        self.mock_map_state.data = {
            '5,5': {
                'content': {
                    'type_': 'monster',
                    'code': 'green_slime',
                    'name': 'Green Slime'
                }
            },
            '10,10': {
                'content': {
                    'type_': 'monster',
                    'code': 'red_slime', 
                    'name': 'Red Slime'
                }
            },
            '15,15': {
                'content': {
                    'type_': 'resource',
                    'code': 'copper_rock',
                    'name': 'Copper Rock'
                }
            }
        }
        
        # Add combat learning data for green_slime
        character_data = {'level': 5, 'hp': 80}
        self.knowledge_base.record_combat_result('green_slime', 'win', character_data)
        self.knowledge_base.record_combat_result('green_slime', 'win', character_data)
        
        # Find suitable monsters
        result = self.knowledge_base.find_suitable_monsters(
            self.mock_map_state, character_level=5, max_distance=20, current_x=0, current_y=0
        )
        
        # Should find both monsters, sorted by success rate and distance
        self.assertEqual(len(result), 2)
        
        # First result should be green_slime (has learning data)
        first_monster = result[0]
        self.assertEqual(first_monster['monster_code'], 'green_slime')
        self.assertEqual(first_monster['location'], (5, 5))
        self.assertAlmostEqual(first_monster['distance'], 7.07, places=1)
        self.assertEqual(first_monster['success_rate'], 1.0)  # 2 wins out of 2
        
        # Second result should be red_slime (no learning data)
        second_monster = result[1]
        self.assertEqual(second_monster['monster_code'], 'red_slime')
        self.assertEqual(second_monster['location'], (10, 10))

    def test_find_suitable_monsters_distance_filter(self) -> None:
        """Test distance filtering in monster search."""
        # Set up map data with distant monster
        self.mock_map_state.data = {
            '100,100': {
                'content': {
                    'type_': 'monster',
                    'code': 'distant_monster',
                    'name': 'Distant Monster'
                }
            }
        }
        
        # Search with small radius
        result = self.knowledge_base.find_suitable_monsters(
            self.mock_map_state, max_distance=10, current_x=0, current_y=0
        )
        
        # Should find no monsters within range
        self.assertEqual(len(result), 0)

    def test_get_knowledge_summary_with_map_state(self) -> None:
        """Test getting knowledge summary with map state."""
        # Add some learning data
        self.knowledge_base.record_combat_result('monster1', 'win', {'level': 5})
        self.knowledge_base.record_combat_result('monster2', 'loss', {'level': 5})
        self.knowledge_base.learn_from_content_discovery('resource', 'resource1', 5, 5)
        
        # Mock map state with locations
        self.mock_map_state.data = {'1,1': {}, '2,2': {}, '3,3': {}}
        
        summary = self.knowledge_base.get_knowledge_summary(self.mock_map_state)
        
        self.assertEqual(summary['monsters_discovered'], 2)
        self.assertEqual(summary['resources_discovered'], 1)
        self.assertEqual(summary['total_combats'], 2)
        self.assertEqual(summary['total_locations_discovered'], 3)

    def test_get_knowledge_summary_without_map_state(self) -> None:
        """Test getting knowledge summary without map state."""
        summary = self.knowledge_base.get_knowledge_summary()
        
        self.assertEqual(summary['monsters_discovered'], 0)
        self.assertEqual(summary['resources_discovered'], 0)
        self.assertEqual(summary['total_combats'], 0)
        self.assertEqual(summary['total_locations_discovered'], 0)

    def test_is_location_known(self) -> None:
        """Test checking if location is known."""
        # Set up map state
        self.mock_map_state.data = {'5,5': {}}
        
        # Test known location
        self.assertTrue(self.knowledge_base.is_location_known(self.mock_map_state, 5, 5))
        
        # Test unknown location
        self.assertFalse(self.knowledge_base.is_location_known(self.mock_map_state, 10, 10))
        
        # Test with no map state
        self.assertFalse(self.knowledge_base.is_location_known(None, 5, 5))

    def test_get_location_info(self) -> None:
        """Test getting location information."""
        location_data = {'content': {'type_': 'monster', 'code': 'test_monster'}}
        self.mock_map_state.data = {'5,5': location_data}
        
        # Test getting known location
        result = self.knowledge_base.get_location_info(self.mock_map_state, 5, 5)
        self.assertEqual(result, location_data)
        
        # Test getting unknown location
        result = self.knowledge_base.get_location_info(self.mock_map_state, 10, 10)
        self.assertIsNone(result)
        
        # Test with no map state
        result = self.knowledge_base.get_location_info(None, 5, 5)
        self.assertIsNone(result)

    def test_find_nearest_known_content(self) -> None:
        """Test finding nearest known content."""
        # Set up map data
        self.mock_map_state.data = {
            '5,5': {'content': {'type_': 'monster', 'code': 'close_monster'}},
            '10,10': {'content': {'type_': 'monster', 'code': 'far_monster'}},
            '3,3': {'content': {'type_': 'resource', 'code': 'resource1'}}
        }
        
        # Find nearest monster from (0,0)
        result = self.knowledge_base.find_nearest_known_content(
            self.mock_map_state, 0, 0, 'monster', max_distance=20
        )
        
        self.assertIsNotNone(result)
        x, y, distance = result
        self.assertEqual((x, y), (5, 5))  # Should find the closer monster
        self.assertAlmostEqual(distance, 7.07, places=1)
        
        # Find nearest resource
        result = self.knowledge_base.find_nearest_known_content(
            self.mock_map_state, 0, 0, 'resource', max_distance=20
        )
        
        self.assertIsNotNone(result)
        x, y, distance = result
        self.assertEqual((x, y), (3, 3))
        
        # Test with no matching content
        result = self.knowledge_base.find_nearest_known_content(
            self.mock_map_state, 0, 0, 'treasure', max_distance=20
        )
        self.assertIsNone(result)

    def test_monster_level_estimation(self) -> None:
        """Test monster level estimation from combat data."""
        # Add combat data for different character levels
        self.knowledge_base.record_combat_result('test_monster', 'win', {'level': 5, 'hp': 80})
        self.knowledge_base.record_combat_result('test_monster', 'win', {'level': 6, 'hp': 75})
        self.knowledge_base.record_combat_result('test_monster', 'loss', {'level': 4, 'hp': 20})
        
        monster_info = self.knowledge_base.data['monsters']['test_monster']
        
        # Level should be estimated based on winning character levels
        self.assertIsNotNone(monster_info['estimated_level'])
        self.assertGreaterEqual(monster_info['estimated_level'], 5)  # Average of 5 and 6

    def test_monster_damage_estimation(self) -> None:
        """Test monster damage estimation from combat data."""
        # Add combat data with damage
        character_data_1 = {'level': 5, 'hp': 70, 'hp_before': 100}  # 30 damage
        character_data_2 = {'level': 5, 'hp': 80, 'hp_before': 100}  # 20 damage
        
        self.knowledge_base.record_combat_result('damage_monster', 'win', character_data_1)
        self.knowledge_base.record_combat_result('damage_monster', 'win', character_data_2)
        
        monster_info = self.knowledge_base.data['monsters']['damage_monster']
        
        # Damage should be estimated as average: (30 + 20) / 2 = 25
        self.assertEqual(monster_info['estimated_damage'], 25)

    def test_persistence(self) -> None:
        """Test that knowledge base persists data correctly."""
        # Add some data
        self.knowledge_base.record_combat_result('persist_monster', 'win', {'level': 5})
        self.knowledge_base.save()
        
        # Create new instance with same file
        new_kb = KnowledgeBase(filename=self.temp_file.name)
        
        # Verify data was loaded
        self.assertIn('persist_monster', new_kb.data['monsters'])
        self.assertEqual(new_kb.data['learning_stats']['total_combats'], 1)


if __name__ == '__main__':
    unittest.main()