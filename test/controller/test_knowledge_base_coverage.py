"""Additional tests to improve KnowledgeBase coverage."""

import json
import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, PropertyMock

from src.controller.knowledge.base import KnowledgeBase


class TestKnowledgeBaseCoverage(unittest.TestCase):
    """Additional test cases to improve KnowledgeBase coverage."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, 'test_knowledge.yaml')
        self.knowledge_base = KnowledgeBase(self.test_file)
        
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
        
    def test_learn_from_content_discovery_npc(self):
        """Test learning from NPC discovery."""
        content_data = {
            'name': 'Merchant Bob',
            'type_': 'merchant',
            'description': 'A friendly merchant',
            'services': ['trade', 'quest']
        }
        
        self.knowledge_base.learn_from_content_discovery('npc', 'merchant_bob', 10, 20, content_data)
        
        # Check NPC was added
        self.assertIn('merchant_bob', self.knowledge_base.data['npcs'])
        npc_info = self.knowledge_base.data['npcs']['merchant_bob']
        self.assertEqual(npc_info['name'], 'Merchant Bob')
        self.assertEqual(npc_info['type'], 'merchant')
        self.assertEqual(npc_info['services'], ['trade', 'quest'])
        self.assertEqual(self.knowledge_base.data['learning_stats']['unique_npcs_met'], 1)
        
    def test_learn_from_content_discovery_workshop(self):
        """Test learning from workshop discovery."""
        content_data = {
            'name': 'Blacksmith',
            'skill': 'weaponcrafting',
            'recipes': ['wooden_sword', 'iron_sword'],
            'level': 5
        }
        
        self.knowledge_base.learn_from_content_discovery('workshop', 'blacksmith_shop', 30, 40, content_data)
        
        # Check workshop was added
        self.assertIn('blacksmith_shop', self.knowledge_base.data['workshops'])
        workshop_info = self.knowledge_base.data['workshops']['blacksmith_shop']
        self.assertEqual(workshop_info['name'], 'Blacksmith')
        self.assertEqual(workshop_info['craft_skill'], 'weaponcrafting')
        self.assertEqual(workshop_info['available_recipes'], ['wooden_sword', 'iron_sword'])
        self.assertEqual(workshop_info['skill_requirements'], 5)
        self.assertEqual(self.knowledge_base.data['learning_stats']['unique_workshops_found'], 1)
        
    def test_learn_from_content_discovery_skill_station(self):
        """Test learning from skill station discovery (treated as workshop)."""
        content_data = {
            'name': 'Mining Station',
            'craft_skill': 'mining',
            'level': 1
        }
        
        self.knowledge_base.learn_from_content_discovery('skill_station', 'mining_station', 15, 25, content_data)
        
        # Should be stored as workshop
        self.assertIn('mining_station', self.knowledge_base.data['workshops'])
        workshop_info = self.knowledge_base.data['workshops']['mining_station']
        self.assertEqual(workshop_info['craft_skill'], 'mining')
        
    def test_learn_from_content_discovery_facility(self):
        """Test learning from facility discovery."""
        content_data = {
            'name': 'City Bank',
            'type_': 'bank',
            'services': ['deposit', 'withdraw']
        }
        
        self.knowledge_base.learn_from_content_discovery('facility', 'bank_main', 50, 50, content_data)
        
        # Check facility was added
        self.assertIn('bank_main', self.knowledge_base.data['facilities'])
        facility_info = self.knowledge_base.data['facilities']['bank_main']
        self.assertEqual(facility_info['name'], 'City Bank')
        self.assertEqual(facility_info['facility_type'], 'bank')
        self.assertEqual(facility_info['services'], ['deposit', 'withdraw'])
        self.assertEqual(self.knowledge_base.data['learning_stats']['unique_facilities_found'], 1)
        
    def test_learn_from_content_discovery_item(self):
        """Test learning from item discovery."""
        content_data = {
            'name': 'Health Potion',
            'type_': 'consumable',
            'subtype': 'potion',
            'tradeable': True,
            'description': 'Restores health',
            'effects': [{'type': 'heal', 'amount': 50}]
        }
        
        self.knowledge_base.learn_from_content_discovery('item', 'health_potion', 60, 70, content_data)
        
        # Check item was added
        self.assertIn('health_potion', self.knowledge_base.data['items'])
        item_info = self.knowledge_base.data['items']['health_potion']
        self.assertEqual(item_info['name'], 'Health Potion')
        self.assertEqual(item_info['item_type'], 'consumable')
        self.assertEqual(item_info['tradeable'], True)
        self.assertEqual(self.knowledge_base.data['learning_stats']['unique_items_discovered'], 1)
        
    def test_learn_from_content_discovery_unknown_type(self):
        """Test learning from unknown content type."""
        content_data = {'name': 'Mystery Object'}
        
        # Should log warning but not crash
        self.knowledge_base.learn_from_content_discovery('unknown_type', 'mystery', 0, 0, content_data)
        
        # Should not be in any category
        self.assertNotIn('mystery', self.knowledge_base.data['monsters'])
        self.assertNotIn('mystery', self.knowledge_base.data['resources'])
        self.assertNotIn('mystery', self.knowledge_base.data['npcs'])
        
    def test_record_combat_result_with_no_data(self):
        """Test recording combat result when monster has no prior data."""
        # Monster not in knowledge base yet
        character_data = {
            'name': 'test_char',
            'level': 5,
            'hp': 80,
            'max_hp': 100
        }
        
        fight_data = {
            'xp': 100,
            'gold': 25,
            'drops': []
        }
        
        self.knowledge_base.record_combat_result('new_monster', 'win', character_data, fight_data)
        
        # Should create monster entry
        self.assertIn('new_monster', self.knowledge_base.data['monsters'])
        monster_info = self.knowledge_base.data['monsters']['new_monster']
        self.assertEqual(len(monster_info['combat_results']), 1)
        
    def test_learn_effect(self):
        """Test learning about effects."""
        effect_data = {
            'name': 'Healing',
            'type': 'heal',
            'amount': 50,
            'duration': 0
        }
        
        self.knowledge_base.learn_effect('heal_50', effect_data)
        
        # Check effect was stored
        self.assertIn('effects', self.knowledge_base.data)
        self.assertIn('heal_50', self.knowledge_base.data['effects'])
        effect_info = self.knowledge_base.data['effects']['heal_50']
        self.assertEqual(effect_info['type'], 'heal')
        self.assertEqual(effect_info['amount'], 50)
        
    def test_learn_xp_effects_analysis(self):
        """Test storing XP effects analysis."""
        xp_effects = {
            'mining': ['copper_ore', 'iron_ore', 'gold_ore'],
            'fishing': ['bass', 'trout', 'salmon']
        }
        
        self.knowledge_base.learn_xp_effects_analysis(xp_effects)
        
        # Check XP effects were stored
        self.assertIn('xp_effects_analysis', self.knowledge_base.data)
        self.assertEqual(len(self.knowledge_base.data['xp_effects_analysis']['mining']), 3)
        self.assertIn('copper_ore', self.knowledge_base.data['xp_effects_analysis']['mining'])
        
        # Check learning stats updated
        self.assertEqual(self.knowledge_base.data['learning_stats']['total_xp_effects_learned'], 6)
        self.assertEqual(self.knowledge_base.data['learning_stats']['skills_with_xp_effects'], 2)
        
    def test_get_combat_statistics(self):
        """Test generating combat statistics."""
        # Add combat data
        self.knowledge_base.data['monsters'] = {
            'chicken': {
                'combat_results': [
                    {'result': 'win'},
                    {'result': 'win'},
                    {'result': 'loss'}
                ]
            },
            'wolf': {
                'combat_results': [
                    {'result': 'win'},
                    {'result': 'loss'},
                    {'result': 'loss'}
                ]
            }
        }
        
        stats = self.knowledge_base.get_combat_statistics()
        
        self.assertIn('chicken', stats)
        self.assertEqual(stats['chicken']['total_combats'], 3)
        self.assertEqual(stats['chicken']['wins'], 2)
        self.assertEqual(stats['chicken']['losses'], 1)
        self.assertAlmostEqual(stats['chicken']['win_rate'], 0.667, places=2)
        
        self.assertIn('wolf', stats)
        self.assertEqual(stats['wolf']['wins'], 1)
        self.assertEqual(stats['wolf']['losses'], 2)
        
    def test_get_resource_data(self):
        """Test getting resource data with API fallback."""
        # Test with cached data
        self.knowledge_base.data['resources']['iron_ore'] = {
            'name': 'Iron Ore',
            'type': 'resource'
        }
        
        data = self.knowledge_base.get_resource_data('iron_ore')
        self.assertIsNotNone(data)
        self.assertEqual(data['name'], 'Iron Ore')
        
        # Test with no data and no client
        data = self.knowledge_base.get_resource_data('unknown_resource')
        self.assertIsNone(data)
        
    def test_get_learning_stats(self):
        """Test getting learning statistics."""
        # Add some stats
        self.knowledge_base.data['learning_stats'] = {
            'unique_monsters_fought': 5,
            'total_combats': 25,
            'resources_discovered': 10
        }
        
        stats = self.knowledge_base.get_learning_stats()
        
        self.assertEqual(stats['unique_monsters_fought'], 5)
        self.assertEqual(stats['total_combats'], 25)
        self.assertEqual(stats['resources_discovered'], 10)
        
    def test_learn_resource_with_sanitization(self):
        """Test learning resource with data sanitization."""
        resource_data = {
            'name': 'Iron Ore',
            'type': 'resource',
            'skill': 'mining',
            'level': 1
        }
        
        self.knowledge_base.learn_resource('iron_ore', resource_data)
        
        # Check resource was stored
        self.assertIn('iron_ore', self.knowledge_base.data['resources'])
        resource_info = self.knowledge_base.data['resources']['iron_ore']
        self.assertEqual(resource_info['name'], 'Iron Ore')
        self.assertEqual(resource_info['code'], 'iron_ore')
        # The API data is stored in a sanitized form
        self.assertIn('api_data', resource_info)
        self.assertEqual(resource_info['api_data']['skill'], 'mining')
        
    def test_get_all_known_resource_codes(self):
        """Test getting all known resource codes."""
        # Add some resources
        self.knowledge_base.data['resources'] = {
            'iron_ore': {'name': 'Iron Ore'},
            'copper_ore': {'name': 'Copper Ore'},
            'gold_ore': {'name': 'Gold Ore'}
        }
        
        codes = self.knowledge_base.get_all_known_resource_codes()
        
        self.assertEqual(len(codes), 3)
        self.assertIn('iron_ore', codes)
        self.assertIn('copper_ore', codes)
        self.assertIn('gold_ore', codes)


if __name__ == '__main__':
    unittest.main()