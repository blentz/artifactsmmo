"""
Comprehensive tests for resource analysis base classes and mixins.

These tests ensure 100% coverage of the new base class system that extracts
common API discovery patterns from complex action files.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List

from src.controller.actions.base.resource_analysis import (
    ResourceDiscoveryMixin,
    EquipmentDiscoveryMixin, 
    CraftingAnalysisMixin,
    WorkshopDiscoveryMixin,
    ResourceAnalysisBase,
    ComprehensiveDiscoveryBase
)
from src.lib.action_context import ActionContext


class TestResourceDiscoveryMixin(unittest.TestCase):
    """Test ResourceDiscoveryMixin functionality."""
    
    def setUp(self):
        self.mixin = ResourceDiscoveryMixin()
        self.mock_client = Mock()
    
    @patch('src.controller.actions.base.resource_analysis.get_map_api')
    def test_find_nearby_resources_success(self, mock_get_map_api):
        """Test successful resource discovery."""
        # Mock map response with resource
        mock_content = Mock()
        mock_content.type_ = 'resource'
        mock_content.code = 'copper_rocks'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_response = Mock()
        mock_response.data = mock_map_data
        mock_get_map_api.return_value = mock_response
        
        # Mock context
        mock_context = Mock()
        mock_context.get.side_effect = lambda key: {'character_x': 0, 'character_y': 0, 'analysis_radius': 1}[key]
        
        # Test finding resources
        result = self.mixin.find_nearby_resources(self.mock_client, mock_context)
        
        # Should find resources (grid search with radius 1 = 9 positions)
        # But since we mock the same response for all positions, we get 9 identical resources
        self.assertEqual(len(result), 9)  # 3x3 grid = 9 positions
        # All should have the same resource code since we mock the same response
        for resource in result:
            self.assertEqual(resource['resource_code'], 'copper_rocks')
        # The center resource (0,0) should have distance 0
        center_resource = [r for r in result if r['x'] == 0 and r['y'] == 0][0]
        self.assertEqual(center_resource['distance'], 0)
    
    @patch('src.controller.actions.base.resource_analysis.get_map_api')
    def test_find_nearby_resources_no_content(self, mock_get_map_api):
        """Test resource discovery with no map content."""
        mock_map_data = Mock()
        mock_map_data.content = None
        
        mock_response = Mock()
        mock_response.data = mock_map_data
        mock_get_map_api.return_value = mock_response
        
        # Mock context
        mock_context = Mock()
        mock_context.get.side_effect = lambda key: {'character_x': 0, 'character_y': 0, 'analysis_radius': 1}[key]
        
        result = self.mixin.find_nearby_resources(self.mock_client, mock_context)
        self.assertEqual(len(result), 0)
    
    @patch('src.controller.actions.base.resource_analysis.get_map_api')
    def test_find_nearby_resources_api_error(self, mock_get_map_api):
        """Test resource discovery with API errors."""
        mock_get_map_api.side_effect = Exception("API Error")
        
        # Mock context
        mock_context = Mock()
        mock_context.get.side_effect = lambda key: {'character_x': 0, 'character_y': 0, 'analysis_radius': 1}[key]
        
        result = self.mixin.find_nearby_resources(self.mock_client, mock_context)
        self.assertEqual(len(result), 0)
    
    @patch('src.controller.actions.base.resource_analysis.get_resource_api')
    def test_get_resource_details_success(self, mock_get_resource_api):
        """Test successful resource details retrieval."""
        mock_resource_data = Mock()
        mock_resource_data.name = 'Copper Rocks'
        mock_resource_data.skill = 'mining'
        mock_resource_data.level = 1
        
        mock_response = Mock()
        mock_response.data = mock_resource_data
        mock_get_resource_api.return_value = mock_response
        
        # Mock context
        mock_context = Mock()
        mock_context.knowledge_base = None
        
        result = self.mixin.get_resource_details(self.mock_client, 'copper_rocks', mock_context)
        
        self.assertEqual(result, mock_resource_data)
        mock_get_resource_api.assert_called_once_with(code='copper_rocks', client=self.mock_client)
    
    @patch('src.controller.actions.base.resource_analysis.get_resource_api')
    def test_get_resource_details_no_data(self, mock_get_resource_api):
        """Test resource details with no data."""
        mock_response = Mock()
        mock_response.data = None
        mock_get_resource_api.return_value = mock_response
        
        # Mock context
        mock_context = Mock()
        mock_context.knowledge_base = None
        
        result = self.mixin.get_resource_details(self.mock_client, 'copper_rocks', mock_context)
        self.assertIsNone(result)
    
    @patch('src.controller.actions.base.resource_analysis.get_resource_api')
    def test_get_resource_details_api_error(self, mock_get_resource_api):
        """Test resource details with API error."""
        self.mixin.logger = Mock()  # Add logger for error handling
        mock_get_resource_api.side_effect = Exception("API Error")
        
        # Mock context
        mock_context = Mock()
        mock_context.knowledge_base = None
        
        result = self.mixin.get_resource_details(self.mock_client, 'copper_rocks', mock_context)
        self.assertIsNone(result)
        self.mixin.logger.warning.assert_called_once()


class TestEquipmentDiscoveryMixin(unittest.TestCase):
    """Test EquipmentDiscoveryMixin functionality."""
    
    def setUp(self):
        self.mixin = EquipmentDiscoveryMixin()
        self.mixin.logger = Mock()  # Add logger for testing
        self.mock_client = Mock()
    
    def test_get_equipment_items_from_knowledge_success(self):
        """Test successful equipment retrieval from knowledge base."""
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'items': {
                'copper_dagger': {
                    'item_type': 'weapon',
                    'level': 1,
                    'attack_fire': 10  # Equipment stat
                },
                'leather_helmet': {
                    'item_type': 'helmet', 
                    'level': 2,
                    'def_air': 5  # Equipment stat
                },
                'raw_chicken': {  # Non-equipment item
                    'item_type': 'consumable',
                    'level': 1
                    # No equipment stats
                }
            }
        }
        
        # Mock context
        mock_context = Mock()
        mock_context.knowledge_base = mock_knowledge_base
        mock_context.get.side_effect = lambda key: {'character_level': 2, 'level_range': 5}[key]
        
        # Ensure the knowledge base doesn't have is_equipment_item method
        # so it falls back to pattern discovery
        del mock_knowledge_base.is_equipment_item
        
        result = self.mixin.get_equipment_items_from_knowledge(mock_context)
        
        # Should return both equipment items since they're level-appropriate (within 5 levels)
        self.assertEqual(len(result), 2)
        self.assertIn('copper_dagger', result)
        self.assertIn('leather_helmet', result)
    
    def test_get_equipment_items_from_knowledge_no_knowledge_base(self):
        """Test equipment retrieval with no knowledge base."""
        # Mock context with no knowledge base
        mock_context = Mock()
        mock_context.knowledge_base = None
        mock_context.get.side_effect = lambda key: {'character_level': 1, 'level_range': 5}[key]
        
        result = self.mixin.get_equipment_items_from_knowledge(mock_context)
        self.assertEqual(len(result), 0)
    
    def test_get_equipment_items_from_knowledge_no_data(self):
        """Test equipment retrieval with knowledge base but no data."""
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {}
        
        # Mock context
        mock_context = Mock()
        mock_context.knowledge_base = mock_knowledge_base
        mock_context.get.side_effect = lambda key: {'character_level': 1, 'level_range': 5}[key]
        
        result = self.mixin.get_equipment_items_from_knowledge(mock_context)
        self.assertEqual(len(result), 0)
    
    def test_get_equipment_items_from_knowledge_exception(self):
        """Test equipment retrieval with exception."""
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = None  # Will cause exception
        
        # Mock context
        mock_context = Mock()
        mock_context.knowledge_base = mock_knowledge_base
        mock_context.get.side_effect = lambda key: {'character_level': 1, 'level_range': 5}[key]
        
        result = self.mixin.get_equipment_items_from_knowledge(mock_context)
        self.assertEqual(len(result), 0)
        self.mixin.logger.warning.assert_called_once()
    
    @patch('src.controller.actions.base.resource_analysis.get_all_items_api')
    def test_discover_equipment_items_from_api_success(self, mock_get_all_items_api):
        """Test successful equipment discovery from API."""
        # Mock API response
        mock_item = Mock()
        mock_item.code = 'iron_sword'
        
        mock_response = Mock()
        mock_response.data = [mock_item]
        mock_get_all_items_api.return_value = mock_response
        
        # Mock knowledge base with equipment types
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'items': {
                'test_weapon': {
                    'item_type': 'weapon',
                    'level': 1,
                    'attack_fire': 10  # Equipment stat
                }
            }
        }
        
        # Mock context
        mock_context = Mock()
        mock_context.knowledge_base = mock_knowledge_base
        mock_context.get.side_effect = lambda key: {'character_level': 5, 'level_range': 10}[key]
        
        result = self.mixin.discover_equipment_items_from_api(self.mock_client, mock_context)
        
        # Should find equipment items for all equipment types
        self.assertGreater(len(result), 0)
        self.assertIn('iron_sword', result)
    
    @patch('src.controller.actions.base.resource_analysis.get_all_items_api')
    def test_discover_equipment_items_from_api_no_data(self, mock_get_all_items_api):
        """Test equipment discovery with no API data."""
        mock_response = Mock()
        mock_response.data = None
        mock_get_all_items_api.return_value = mock_response
        
        # Mock knowledge base with equipment types
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'items': {
                'test_weapon': {
                    'item_type': 'weapon',
                    'level': 1,
                    'attack_fire': 10  # Equipment stat
                }
            }
        }
        
        # Mock context
        mock_context = Mock()
        mock_context.knowledge_base = mock_knowledge_base
        mock_context.get.side_effect = lambda key: {'character_level': 5, 'level_range': 10}[key]
        
        result = self.mixin.discover_equipment_items_from_api(self.mock_client, mock_context)
        self.assertEqual(len(result), 0)
    
    @patch('src.controller.actions.base.resource_analysis.get_all_items_api')
    def test_discover_equipment_items_from_api_exception(self, mock_get_all_items_api):
        """Test equipment discovery with API exception."""
        mock_get_all_items_api.side_effect = Exception("API Error")
        
        # Mock knowledge base with equipment types
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'items': {
                'test_weapon': {
                    'item_type': 'weapon',
                    'level': 1,
                    'attack_fire': 10  # Equipment stat
                }
            }
        }
        
        # Mock context
        mock_context = Mock()
        mock_context.knowledge_base = mock_knowledge_base
        mock_context.get.side_effect = lambda key: {'character_level': 5, 'level_range': 10}[key]
        
        result = self.mixin.discover_equipment_items_from_api(self.mock_client, mock_context)
        self.assertEqual(len(result), 0)
        # Should have called warning for each of the 1 equipment type that failed
        self.assertEqual(self.mixin.logger.warning.call_count, 1)


class TestCraftingAnalysisMixin(unittest.TestCase):
    """Test CraftingAnalysisMixin functionality."""
    
    def setUp(self):
        self.mixin = CraftingAnalysisMixin()
        self.mixin.logger = Mock()
        self.mock_client = Mock()
    
    def test_extract_all_materials_success(self):
        """Test successful material extraction from craft data."""
        # Mock craft data
        mock_material1 = Mock()
        mock_material1.code = 'copper_ore'
        mock_material1.quantity = 3
        
        mock_material2 = Mock()
        mock_material2.code = 'ash_wood'
        mock_material2.quantity = 2
        
        mock_craft_data = Mock()
        mock_craft_data.items = [mock_material1, mock_material2]
        
        result = self.mixin.extract_all_materials(mock_craft_data)
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['code'], 'copper_ore')
        self.assertEqual(result[0]['quantity'], 3)
        self.assertEqual(result[1]['code'], 'ash_wood')
        self.assertEqual(result[1]['quantity'], 2)
    
    def test_extract_all_materials_no_items(self):
        """Test material extraction with no items."""
        mock_craft_data = Mock()
        mock_craft_data.items = None
        
        result = self.mixin.extract_all_materials(mock_craft_data)
        self.assertEqual(len(result), 0)
    
    @patch('src.controller.actions.base.resource_analysis.get_item_api')
    def test_find_crafting_uses_for_item_success(self, mock_get_item_api):
        """Test successful crafting uses discovery."""
        # Mock equipment discovery methods
        self.mixin.get_equipment_items_from_knowledge = Mock(return_value=['copper_dagger'])
        self.mixin.discover_equipment_items_from_api = Mock(return_value=[])
        
        # Mock material for craft recipe
        mock_material = Mock()
        mock_material.code = 'copper_ore'
        mock_material.quantity = 2
        
        # Mock craft data
        mock_craft_data = Mock()
        mock_craft_data.items = [mock_material]
        mock_craft_data.skill = 'weaponcrafting'
        
        # Mock item data
        mock_item = Mock()
        mock_item.code = 'copper_dagger'
        mock_item.name = 'Copper Dagger'
        mock_item.type = 'weapon'
        mock_item.level = 1
        mock_item.craft = mock_craft_data
        
        mock_response = Mock()
        mock_response.data = mock_item
        mock_get_item_api.return_value = mock_response
        
        # Mock knowledge base
        mock_knowledge_base = Mock()
        
        # Mock context
        mock_context = Mock()
        mock_context.knowledge_base = mock_knowledge_base
        mock_context.get.side_effect = lambda key: {'character_level': 1, 'level_range': 5}[key]
        
        # Mock the _is_equipment_from_knowledge_base method to return True for the test item
        self.mixin._is_equipment_from_knowledge_base = Mock(return_value=True)
        
        result = self.mixin.find_crafting_uses_for_item(
            self.mock_client, 'copper_ore', mock_context
        )
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['item_code'], 'copper_dagger')
        self.assertEqual(result[0]['item_name'], 'Copper Dagger')
        self.assertEqual(result[0]['workshop_required'], 'weaponcrafting')
    
    def test_find_crafting_uses_for_item_no_equipment_items(self):
        """Test crafting uses with no equipment items found."""
        self.mixin.get_equipment_items_from_knowledge = Mock(return_value=[])
        self.mixin.discover_equipment_items_from_api = Mock(return_value=[])
        
        mock_knowledge_base = Mock()
        
        # Mock context
        mock_context = Mock()
        mock_context.knowledge_base = mock_knowledge_base
        mock_context.get.side_effect = lambda key: {'character_level': 1, 'level_range': 5}[key]
        
        result = self.mixin.find_crafting_uses_for_item(
            self.mock_client, 'copper_ore', mock_context
        )
        
        self.assertEqual(len(result), 0)


class TestWorkshopDiscoveryMixin(unittest.TestCase):
    """Test WorkshopDiscoveryMixin functionality."""
    
    def setUp(self):
        self.mixin = WorkshopDiscoveryMixin()
        self.mixin.logger = Mock()
        self.mock_client = Mock()
    
    @patch('src.controller.actions.base.resource_analysis.get_map_api')
    def test_find_nearby_workshops_success(self, mock_get_map_api):
        """Test successful workshop discovery."""
        # Mock map response with workshop
        mock_content = Mock()
        mock_content.type_ = 'workshop'
        mock_content.code = 'weaponcrafting_workshop'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_response = Mock()
        mock_response.data = mock_map_data
        mock_get_map_api.return_value = mock_response
        
        # Mock context
        mock_context = Mock()
        mock_context.get.side_effect = lambda key: {'character_x': 0, 'character_y': 0, 'search_radius': 1}[key]
        
        result = self.mixin.find_nearby_workshops(self.mock_client, mock_context)
        
        # Should find workshops (grid search with radius 1 = 9 positions)
        self.assertEqual(len(result), 9)  # 3x3 grid = 9 positions
        # All should have the same workshop code since we mock the same response
        for workshop in result:
            self.assertEqual(workshop['workshop_code'], 'weaponcrafting_workshop')
        # The center workshop (0,0) should have distance 0
        center_workshop = [w for w in result if w['x'] == 0 and w['y'] == 0][0]
        self.assertEqual(center_workshop['distance'], 0)
    
    @patch('src.controller.actions.base.resource_analysis.get_map_api')
    def test_find_nearby_workshops_filtered(self, mock_get_map_api):
        """Test workshop discovery with type filtering."""
        # Mock map response with different workshop
        mock_content = Mock()
        mock_content.type_ = 'workshop'
        mock_content.code = 'gearcrafting_workshop'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_response = Mock()
        mock_response.data = mock_map_data
        mock_get_map_api.return_value = mock_response
        
        # Mock context
        mock_context = Mock()
        mock_context.get.side_effect = lambda key: {'character_x': 0, 'character_y': 0, 'search_radius': 1}[key]
        
        # Search for weaponcrafting workshop specifically
        result = self.mixin.find_nearby_workshops(
            self.mock_client, mock_context, workshop_type='weaponcrafting_workshop'
        )
        
        # Should find no workshops since we filtered for different type
        self.assertEqual(len(result), 0)
    
    def test_get_workshop_details_success(self):
        """Test successful workshop details retrieval."""
        # Mock knowledge base with workshop skill mapping
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'items': {
                'test_weapon': {
                    'craft_data': {
                        'skill': 'weaponcrafting'
                    }
                }
            }
        }
        mock_knowledge_base.get_workshop_data = Mock(return_value=None)  # No cached data
        
        # Mock context
        mock_context = Mock()
        mock_context.knowledge_base = mock_knowledge_base
        
        result = self.mixin.get_workshop_details(self.mock_client, 'weaponcrafting_workshop', mock_context)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['code'], 'weaponcrafting_workshop')
        self.assertEqual(result['type'], 'workshop')
        self.assertEqual(result['skill'], 'weaponcrafting')
    
    def test_get_workshop_details_exception(self):
        """Test workshop details with exception."""
        # Mock context
        mock_context = Mock()
        mock_context.knowledge_base = None
        
        # Force an exception by making the method fail
        with patch.object(self.mixin, '_discover_workshop_skill_from_knowledge_base', side_effect=Exception("Error")):
            result = self.mixin.get_workshop_details(self.mock_client, 'test_workshop', mock_context)
            self.assertIsNone(result)
            self.mixin.logger.warning.assert_called_once()
    
    def test_discover_workshop_skill_from_knowledge_base(self):
        """Test workshop skill discovery from knowledge base patterns."""
        # Mock knowledge base with crafting patterns
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'items': {
                'test_weapon': {
                    'craft_data': {
                        'skill': 'weaponcrafting'
                    }
                },
                'test_gear': {
                    'craft': {
                        'skill': 'gearcrafting'
                    }
                }
            }
        }
        
        # Test known patterns
        test_cases = [
            ('weaponcrafting_workshop', 'weaponcrafting'),
            ('gearcrafting_workshop', 'gearcrafting'),
            ('unknown_workshop', 'unknown')
        ]
        
        for workshop_code, expected_skill in test_cases:
            result = self.mixin._discover_workshop_skill_from_knowledge_base(workshop_code, mock_knowledge_base)
            self.assertEqual(result, expected_skill)
    
    def test_find_workshops_by_skill_success(self):
        """Test finding workshops by skill."""
        # Mock find_nearby_workshops to return some workshops
        mock_workshop = {
            'x': 1,
            'y': 1, 
            'workshop_code': 'weaponcrafting_workshop',
            'distance': 1
        }
        self.mixin.find_nearby_workshops = Mock(return_value=[mock_workshop])
        
        # Mock get_workshop_details to return matching skill
        self.mixin.get_workshop_details = Mock(return_value={'skill': 'weaponcrafting'})
        
        # Mock context
        mock_context = Mock()
        mock_context.get.side_effect = lambda key: {'character_x': 0, 'character_y': 0, 'search_radius': 2}[key]
        
        result = self.mixin.find_workshops_by_skill(self.mock_client, mock_context, 'weaponcrafting')
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['skill'], 'weaponcrafting')


class TestResourceAnalysisBase(unittest.TestCase):
    """Test ResourceAnalysisBase functionality."""
    
    def setUp(self):
        # Create a concrete test class
        class TestResourceAnalysisAction(ResourceAnalysisBase):
            conditions = {'character_status': {'alive': True}}
            reactions = {'test': True}
            weight = 1.0
            
            def execute(self, client, context):
                return self.create_success_result('Test')
        
        self.action = TestResourceAnalysisAction()
    
    def test_inheritance(self):
        """Test that ResourceAnalysisBase properly inherits from all mixins."""
        # Check that all mixin methods are available
        self.assertTrue(hasattr(self.action, 'find_nearby_resources'))
        self.assertTrue(hasattr(self.action, 'get_equipment_items_from_knowledge'))
        self.assertTrue(hasattr(self.action, 'extract_all_materials'))
        self.assertTrue(hasattr(self.action, 'calculate_distance'))
    
    def test_calculate_distance(self):
        """Test distance calculation method."""
        # Test Manhattan distance calculation
        self.assertEqual(self.action.calculate_distance(0, 0, 0, 0), 0)
        self.assertEqual(self.action.calculate_distance(1, 1, 0, 0), 2)
        self.assertEqual(self.action.calculate_distance(-1, -1, 0, 0), 2)
        self.assertEqual(self.action.calculate_distance(3, 4, 0, 0), 7)


class TestComprehensiveDiscoveryBase(unittest.TestCase):
    """Test ComprehensiveDiscoveryBase functionality."""
    
    def setUp(self):
        # Create a concrete test class
        class TestComprehensiveAction(ComprehensiveDiscoveryBase):
            conditions = {'character_status': {'alive': True}}
            reactions = {'test': True}
            weight = 1.0
            
            def execute(self, client, context):
                return self.create_success_result('Test')
        
        self.action = TestComprehensiveAction()
    
    def test_comprehensive_inheritance(self):
        """Test that ComprehensiveDiscoveryBase inherits from all mixins."""
        # Check that all mixin methods are available
        self.assertTrue(hasattr(self.action, 'find_nearby_resources'))
        self.assertTrue(hasattr(self.action, 'get_equipment_items_from_knowledge'))
        self.assertTrue(hasattr(self.action, 'extract_all_materials'))
        self.assertTrue(hasattr(self.action, 'find_nearby_workshops'))
        self.assertTrue(hasattr(self.action, 'calculate_distance'))
    
    def test_action_base_methods(self):
        """Test that ActionBase methods are still available."""
        self.assertTrue(hasattr(self.action, 'create_success_result'))
        self.assertTrue(hasattr(self.action, 'create_error_result'))
        self.assertTrue(hasattr(self.action, 'create_result_with_state_changes'))


if __name__ == '__main__':
    unittest.main()