"""Comprehensive unit tests for BulkDataLoader"""

import unittest
from unittest.mock import Mock, patch

from src.controller.bulk_data_loader import BulkDataLoader


class TestBulkDataLoader(unittest.TestCase):
    """Test cases for BulkDataLoader class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.loader = BulkDataLoader()
        self.mock_client = Mock()
        self.mock_map_state = Mock()
        self.mock_map_state.data = {}
        self.mock_map_state.save = Mock()
        
        self.mock_knowledge_base = Mock()
        self.mock_knowledge_base.data = {
            'npcs': {},
            'resources': {},
            'monsters': {},
            'items': {},
            'workshops': {},
            'facilities': {},
            'learning_stats': {
                'unique_workshops_found': 0,
                'unique_facilities_found': 0
            }
        }
        self.mock_knowledge_base.save = Mock()
    
    def test_initialization(self):
        """Test BulkDataLoader initialization."""
        loader = BulkDataLoader()
        self.assertIsNotNone(loader.logger)
    
    @patch('src.controller.bulk_data_loader.get_all_maps_api')
    @patch('src.controller.bulk_data_loader.get_all_npcs_api')
    @patch('src.controller.bulk_data_loader.get_all_resources_api')
    @patch('src.controller.bulk_data_loader.get_all_monsters_api')
    @patch('src.controller.bulk_data_loader.get_all_items_api')
    def test_load_all_game_data_success(self, mock_items, mock_monsters, 
                                       mock_resources, mock_npcs, mock_maps):
        """Test successful loading of all game data."""
        # Create proper mock location without content
        mock_location = Mock()
        mock_location.x = 0
        mock_location.y = 0
        mock_location.content = None
        
        # Mock all API responses to return valid data
        mock_maps.return_value = Mock(data=[mock_location])
        mock_npcs.return_value = Mock(data=[Mock(code='npc1')])
        mock_resources.return_value = Mock(data=[Mock(code='resource1')])
        mock_monsters.return_value = Mock(data=[Mock(code='monster1')])
        mock_items.return_value = Mock(data=[Mock(code='item1')])
        
        result = self.loader.load_all_game_data(
            self.mock_client, self.mock_map_state, self.mock_knowledge_base
        )
        
        self.assertTrue(result)
        self.assertTrue(mock_maps.called)
        self.assertTrue(mock_npcs.called)
        self.assertTrue(mock_resources.called)
        self.assertTrue(mock_monsters.called)
        self.assertTrue(mock_items.called)
    
    @patch('src.controller.bulk_data_loader.get_all_maps_api')
    def test_load_all_game_data_maps_failure(self, mock_maps):
        """Test failure when maps loading fails."""
        # Make maps loading fail
        mock_maps.side_effect = Exception("API Error")
        
        result = self.loader.load_all_game_data(
            self.mock_client, self.mock_map_state, self.mock_knowledge_base
        )
        
        self.assertFalse(result)
    
    @patch('src.controller.bulk_data_loader.get_all_maps_api')
    @patch('src.controller.bulk_data_loader.get_all_npcs_api')
    def test_load_all_game_data_npcs_failure(self, mock_npcs, mock_maps):
        """Test failure when NPCs loading fails."""
        # Maps succeed, NPCs fail
        mock_maps.return_value = Mock(data=[Mock(x=0, y=0)])
        mock_npcs.side_effect = Exception("NPC API Error")
        
        result = self.loader.load_all_game_data(
            self.mock_client, self.mock_map_state, self.mock_knowledge_base
        )
        
        self.assertFalse(result)
    
    @patch('src.controller.bulk_data_loader.get_all_maps_api')
    @patch('src.controller.bulk_data_loader.time.sleep')
    def test_load_all_maps_single_page(self, mock_sleep, mock_api):
        """Test loading maps with single page response."""
        # Create mock location
        mock_location = Mock()
        mock_location.x = 10
        mock_location.y = 20
        mock_location.content = None
        
        mock_response = Mock()
        mock_response.data = [mock_location]
        mock_api.return_value = mock_response
        
        result = self.loader._load_all_maps(
            self.mock_client, self.mock_map_state, self.mock_knowledge_base
        )
        
        self.assertTrue(result)
        self.assertEqual(len(self.mock_map_state.data), 1)
        self.assertIn('10,20', self.mock_map_state.data)
        self.mock_map_state.save.assert_called_once()
    
    @patch('src.controller.bulk_data_loader.get_all_maps_api')
    @patch('src.controller.bulk_data_loader.time.sleep')
    def test_load_all_maps_with_content(self, mock_sleep, mock_api):
        """Test loading maps with content (workshop)."""
        # Create mock location with workshop content
        mock_content = Mock()
        mock_content.code = 'weaponcrafting_workshop'
        mock_content.type_ = 'workshop'  # Use type_ for proper attribute access
        
        mock_location = Mock()
        mock_location.x = 5
        mock_location.y = 15
        mock_location.content = mock_content
        
        mock_response = Mock()
        mock_response.data = [mock_location]
        mock_api.return_value = mock_response
        
        result = self.loader._load_all_maps(
            self.mock_client, self.mock_map_state, self.mock_knowledge_base
        )
        
        self.assertTrue(result)
        location_data = self.mock_map_state.data['5,15']
        self.assertIsNotNone(location_data['content'])
        self.assertEqual(location_data['content']['code'], 'weaponcrafting_workshop')
    
    @patch('src.controller.bulk_data_loader.get_all_maps_api')
    @patch('src.controller.bulk_data_loader.time.sleep')
    def test_load_all_maps_pagination(self, mock_sleep, mock_api):
        """Test loading maps with pagination."""
        # First page - full (100 items)
        mock_locations_page1 = [Mock(x=i, y=0, content=None) for i in range(100)]
        mock_response_page1 = Mock(data=mock_locations_page1)
        
        # Second page - partial (50 items)
        mock_locations_page2 = [Mock(x=i, y=1, content=None) for i in range(50)]
        mock_response_page2 = Mock(data=mock_locations_page2)
        
        mock_api.side_effect = [mock_response_page1, mock_response_page2]
        
        result = self.loader._load_all_maps(
            self.mock_client, self.mock_map_state, self.mock_knowledge_base
        )
        
        self.assertTrue(result)
        self.assertEqual(len(self.mock_map_state.data), 150)  # 100 + 50
        self.assertEqual(mock_api.call_count, 2)  # Two pages
    
    @patch('src.controller.bulk_data_loader.get_all_npcs_api')
    @patch('src.controller.bulk_data_loader.time.sleep')
    def test_load_all_npcs(self, mock_sleep, mock_api):
        """Test loading NPCs."""
        # Create mock NPC
        mock_npc = Mock()
        mock_npc.code = 'test_npc'
        mock_npc.name = 'Test NPC'
        mock_npc.type = 'shopkeeper'
        mock_npc.services = ['buy', 'sell']
        mock_npc.trades = []
        
        mock_response = Mock()
        mock_response.data = [mock_npc]
        mock_api.return_value = mock_response
        
        result = self.loader._load_all_npcs(self.mock_client, self.mock_knowledge_base)
        
        self.assertTrue(result)
        self.assertIn('test_npc', self.mock_knowledge_base.data['npcs'])
        npc_data = self.mock_knowledge_base.data['npcs']['test_npc']
        self.assertEqual(npc_data['name'], 'Test NPC')
        self.assertEqual(npc_data['npc_type'], 'shopkeeper')
    
    @patch('src.controller.bulk_data_loader.get_all_resources_api')
    @patch('src.controller.bulk_data_loader.time.sleep')
    def test_load_all_resources(self, mock_sleep, mock_api):
        """Test loading resources."""
        # Create mock resource
        mock_resource = Mock()
        mock_resource.code = 'iron_ore'
        mock_resource.name = 'Iron Ore'
        mock_resource.type = 'ore'
        mock_resource.skill = 'mining'
        mock_resource.level = 5
        
        mock_response = Mock()
        mock_response.data = [mock_resource]
        mock_api.return_value = mock_response
        
        result = self.loader._load_all_resources(self.mock_client, self.mock_knowledge_base)
        
        self.assertTrue(result)
        self.assertIn('iron_ore', self.mock_knowledge_base.data['resources'])
        resource_data = self.mock_knowledge_base.data['resources']['iron_ore']
        self.assertEqual(resource_data['name'], 'Iron Ore')
        self.assertEqual(resource_data['skill_required'], 'mining')
        self.assertEqual(resource_data['level_required'], 5)
    
    @patch('src.controller.bulk_data_loader.get_all_monsters_api')
    @patch('src.controller.bulk_data_loader.time.sleep')
    def test_load_all_monsters(self, mock_sleep, mock_api):
        """Test loading monsters."""
        # Create mock monster
        mock_monster = Mock()
        mock_monster.code = 'goblin'
        mock_monster.name = 'Goblin'
        mock_monster.level = 3
        mock_monster.hp = 50
        mock_monster.attack_fire = 10
        mock_monster.attack_earth = 5
        mock_monster.attack_water = 0
        mock_monster.attack_air = 0
        mock_monster.res_fire = 5
        mock_monster.res_earth = 10
        mock_monster.res_water = 0
        mock_monster.res_air = 0
        mock_monster.drops = ['copper_coin']
        
        mock_response = Mock()
        mock_response.data = [mock_monster]
        mock_api.return_value = mock_response
        
        result = self.loader._load_all_monsters(self.mock_client, self.mock_knowledge_base)
        
        self.assertTrue(result)
        self.assertIn('goblin', self.mock_knowledge_base.data['monsters'])
        monster_data = self.mock_knowledge_base.data['monsters']['goblin']
        self.assertEqual(monster_data['name'], 'Goblin')
        self.assertEqual(monster_data['level'], 3)
        self.assertEqual(monster_data['hp'], 50)
        self.assertEqual(monster_data['attack_stats']['attack_fire'], 10)
        self.assertEqual(monster_data['resistance_stats']['res_fire'], 5)
    
    @patch('src.controller.bulk_data_loader.get_all_items_api')
    @patch('src.controller.bulk_data_loader.time.sleep')
    def test_load_all_items(self, mock_sleep, mock_api):
        """Test loading items."""
        # Create mock item
        mock_item = Mock()
        mock_item.code = 'iron_sword'
        mock_item.name = 'Iron Sword'
        mock_item.type = 'weapon'
        mock_item.level = 10
        mock_item.tradeable = True
        mock_item.craft = {'skill': 'weaponcrafting', 'level': 8}
        mock_item.effects = [{'stat': 'attack', 'value': 25}]
        
        mock_response = Mock()
        mock_response.data = [mock_item]
        mock_api.return_value = mock_response
        
        result = self.loader._load_all_items(self.mock_client, self.mock_knowledge_base)
        
        self.assertTrue(result)
        self.assertIn('iron_sword', self.mock_knowledge_base.data['items'])
        item_data = self.mock_knowledge_base.data['items']['iron_sword']
        self.assertEqual(item_data['name'], 'Iron Sword')
        self.assertEqual(item_data['item_type'], 'weapon')
        self.assertEqual(item_data['level'], 10)
        self.assertTrue(item_data['tradeable'])
    
    def test_is_workshop_or_facility_workshop_type(self):
        """Test workshop detection by type."""
        mock_content = Mock()
        mock_content.code = 'test'
        # Use type_ as that's what the method checks first
        mock_content.type_ = 'workshop'
        
        result = self.loader._is_workshop_or_facility(mock_content)
        self.assertTrue(result)
    
    def test_is_workshop_or_facility_facility_type(self):
        """Test facility detection by type."""
        mock_content = Mock()
        mock_content.code = 'test'
        # Use type_ as that's what the method checks first
        mock_content.type_ = 'facility'
        
        result = self.loader._is_workshop_or_facility(mock_content)
        self.assertTrue(result)
    
    def test_is_workshop_or_facility_workshop_code(self):
        """Test workshop detection by code patterns."""
        workshop_codes = ['weaponcrafting', 'gearcrafting', 'jewelrycrafting', 
                         'cooking', 'alchemy', 'mining', 'woodcutting']
        
        for code in workshop_codes:
            mock_content = Mock()
            mock_content.code = code
            mock_content.type = 'unknown'
            
            result = self.loader._is_workshop_or_facility(mock_content)
            self.assertTrue(result, f"Failed to detect workshop: {code}")
    
    def test_is_workshop_or_facility_workshop_patterns(self):
        """Test workshop detection by name patterns."""
        workshop_patterns = ['smithy', 'forge', 'anvil', 'crafting_table']
        
        for pattern in workshop_patterns:
            mock_content = Mock()
            mock_content.code = f"test_{pattern}"
            mock_content.type = 'unknown'
            
            result = self.loader._is_workshop_or_facility(mock_content)
            self.assertTrue(result, f"Failed to detect workshop pattern: {pattern}")
    
    def test_is_workshop_or_facility_facility_patterns(self):
        """Test facility detection by name patterns."""
        facility_patterns = ['bank', 'exchange', 'market', 'shop', 'store']
        
        for pattern in facility_patterns:
            mock_content = Mock()
            mock_content.code = f"test_{pattern}"
            mock_content.type = 'unknown'
            
            result = self.loader._is_workshop_or_facility(mock_content)
            self.assertTrue(result, f"Failed to detect facility pattern: {pattern}")
    
    def test_is_workshop_or_facility_negative(self):
        """Test that non-workshop/facility content is not detected."""
        mock_content = Mock()
        mock_content.code = 'random_content'
        mock_content.type_ = 'resource'
        
        result = self.loader._is_workshop_or_facility(mock_content)
        self.assertFalse(result)
    
    def test_add_workshop_to_knowledge_workshop(self):
        """Test adding workshop to knowledge base."""
        mock_content = Mock()
        mock_content.code = 'weaponcrafting_workshop'
        mock_content.type_ = 'workshop'
        mock_content.name = 'Weapon Crafting Workshop'
        
        self.loader._add_workshop_to_knowledge(
            self.mock_knowledge_base, mock_content, 10, 20
        )
        
        self.assertIn('weaponcrafting_workshop', self.mock_knowledge_base.data['workshops'])
        workshop_data = self.mock_knowledge_base.data['workshops']['weaponcrafting_workshop']
        self.assertEqual(workshop_data['name'], 'Weapon Crafting Workshop')
        self.assertEqual(workshop_data['x'], 10)
        self.assertEqual(workshop_data['y'], 20)
        self.assertEqual(workshop_data['craft_skill'], 'weaponcrafting')
        self.assertEqual(self.mock_knowledge_base.data['learning_stats']['unique_workshops_found'], 1)
    
    def test_add_workshop_to_knowledge_facility(self):
        """Test adding facility to knowledge base."""
        mock_content = Mock()
        mock_content.code = 'grand_exchange'
        mock_content.type_ = 'facility'
        mock_content.name = 'Grand Exchange'
        
        self.loader._add_workshop_to_knowledge(
            self.mock_knowledge_base, mock_content, 5, 15
        )
        
        self.assertIn('grand_exchange', self.mock_knowledge_base.data['facilities'])
        facility_data = self.mock_knowledge_base.data['facilities']['grand_exchange']
        self.assertEqual(facility_data['name'], 'Grand Exchange')
        self.assertEqual(facility_data['x'], 5)
        self.assertEqual(facility_data['y'], 15)
        self.assertEqual(self.mock_knowledge_base.data['learning_stats']['unique_facilities_found'], 1)
    
    def test_determine_craft_skill_weapon(self):
        """Test craft skill determination for weapon workshop."""
        result = self.loader._determine_craft_skill('weaponcrafting_workshop')
        self.assertEqual(result, 'weaponcrafting')
    
    def test_determine_craft_skill_gear(self):
        """Test craft skill determination for gear workshop."""
        result = self.loader._determine_craft_skill('gearcrafting_station')
        self.assertEqual(result, 'gearcrafting')
    
    def test_determine_craft_skill_jewelry(self):
        """Test craft skill determination for jewelry workshop."""
        result = self.loader._determine_craft_skill('jewelry_bench')
        self.assertEqual(result, 'jewelrycrafting')
    
    def test_determine_craft_skill_cooking(self):
        """Test craft skill determination for cooking workshop."""
        result = self.loader._determine_craft_skill('cooking_fire')
        self.assertEqual(result, 'cooking')
    
    def test_determine_craft_skill_alchemy(self):
        """Test craft skill determination for alchemy workshop."""
        result = self.loader._determine_craft_skill('alchemy_station')
        self.assertEqual(result, 'alchemy')
    
    def test_determine_craft_skill_mining(self):
        """Test craft skill determination for mining workshop."""
        result = self.loader._determine_craft_skill('mining_rock')
        self.assertEqual(result, 'mining')
    
    def test_determine_craft_skill_woodcutting(self):
        """Test craft skill determination for woodcutting workshop."""
        result = self.loader._determine_craft_skill('woodcutting_tree')
        self.assertEqual(result, 'woodcutting')
    
    def test_determine_craft_skill_unknown(self):
        """Test craft skill determination for unknown workshop."""
        result = self.loader._determine_craft_skill('unknown_workshop')
        self.assertEqual(result, 'unknown')
    
    @patch('src.controller.bulk_data_loader.get_all_maps_api')
    def test_load_all_maps_api_error(self, mock_api):
        """Test maps loading with API error."""
        mock_api.side_effect = Exception("API Connection Error")
        
        result = self.loader._load_all_maps(
            self.mock_client, self.mock_map_state, self.mock_knowledge_base
        )
        
        self.assertFalse(result)
    
    @patch('src.controller.bulk_data_loader.get_all_maps_api')
    def test_load_all_maps_no_response(self, mock_api):
        """Test maps loading with no response."""
        mock_api.return_value = None
        
        result = self.loader._load_all_maps(
            self.mock_client, self.mock_map_state, self.mock_knowledge_base
        )
        
        self.assertTrue(result)  # Should complete successfully with no data
        self.assertEqual(len(self.mock_map_state.data), 0)
    
    @patch('src.controller.bulk_data_loader.get_all_maps_api')
    def test_load_all_maps_empty_data(self, mock_api):
        """Test maps loading with empty data."""
        mock_response = Mock()
        mock_response.data = []
        mock_api.return_value = mock_response
        
        result = self.loader._load_all_maps(
            self.mock_client, self.mock_map_state, self.mock_knowledge_base
        )
        
        self.assertTrue(result)  # Should complete successfully with no data
        self.assertEqual(len(self.mock_map_state.data), 0)


if __name__ == '__main__':
    unittest.main()