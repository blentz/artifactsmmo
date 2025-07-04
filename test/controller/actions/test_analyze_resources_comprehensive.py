"""
Comprehensive tests for AnalyzeResourcesAction

Tests all methods and edge cases for the AnalyzeResourcesAction class.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock

from src.controller.actions.analyze_resources import AnalyzeResourcesAction
from src.controller.actions.base import ActionResult
from src.lib.action_context import ActionContext


class TestAnalyzeResourcesComprehensive(unittest.TestCase):
    """Comprehensive test cases for AnalyzeResourcesAction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = AnalyzeResourcesAction()
        self.client = Mock()
        self.context = ActionContext()
        self.context.character_name = "test_character"
        self.context.character_x = 0
        self.context.character_y = 0
        self.context.character_level = 5
        self.context.analysis_radius = 2
        self.context.equipment_types = ["weapon", "armor"]
        self.context.knowledge_base = Mock()
        self.context.config_data = Mock()
        
    def test_find_nearby_resources_success(self):
        """Test _find_nearby_resources finds resources correctly."""
        # Mock map API responses
        mock_map_response = Mock()
        mock_map_response.data = Mock()
        mock_map_response.data.content = Mock()
        mock_map_response.data.content.type_ = 'resource'
        mock_map_response.data.content.code = 'iron_ore'
        
        with patch('src.controller.actions.analyze_resources.get_map_api') as mock_get_map:
            # Return resource for one location, None for others
            def map_side_effect(x, y, client):
                if x == 0 and y == 1:
                    return mock_map_response
                return Mock(data=None)
            
            mock_get_map.side_effect = map_side_effect
            
            resources = self.action._find_nearby_resources(self.client, 0, 0, 2)
            
            self.assertEqual(len(resources), 1)
            self.assertEqual(resources[0]['resource_code'], 'iron_ore')
            self.assertEqual(resources[0]['x'], 0)
            self.assertEqual(resources[0]['y'], 1)
            self.assertEqual(resources[0]['distance'], 1)
    
    def test_find_nearby_resources_api_exception(self):
        """Test _find_nearby_resources handles API exceptions gracefully."""
        with patch('src.controller.actions.analyze_resources.get_map_api') as mock_get_map:
            mock_get_map.side_effect = Exception("API error")
            
            resources = self.action._find_nearby_resources(self.client, 0, 0, 2)
            
            # Should return empty list on API errors
            self.assertEqual(resources, [])
    
    def test_analyze_resource_crafting_potential_success(self):
        """Test _analyze_resource_crafting_potential analyzes resources correctly."""
        resource_location = {
            'x': 1,
            'y': 1,
            'resource_code': 'iron_ore',
            'distance': 2
        }
        
        # Mock resource API response
        mock_resource_response = Mock()
        mock_resource_response.data = Mock()
        mock_resource_response.data.name = 'Iron Ore'
        mock_resource_response.data.skill = 'mining'
        mock_resource_response.data.level = 1
        mock_resource_response.data.drops = [Mock(code='iron')]
        
        with patch('src.controller.actions.analyze_resources.get_resource_api') as mock_get_resource:
            mock_get_resource.return_value = mock_resource_response
            
            with patch.object(self.action, '_find_crafting_uses_for_item') as mock_find_uses:
                mock_find_uses.return_value = [
                    {
                        'item_code': 'iron_sword',
                        'item_name': 'Iron Sword',
                        'item_type': 'weapon',
                        'item_level': 5
                    }
                ]
                
                result = self.action._analyze_resource_crafting_potential(
                    self.client, resource_location, self.context.knowledge_base, 5, ['weapon']
                )
                
                self.assertIsNotNone(result)
                self.assertEqual(result['resource_code'], 'iron_ore')
                self.assertEqual(result['resource_name'], 'Iron Ore')
                self.assertEqual(result['skill_required'], 'mining')
                self.assertEqual(result['level_required'], 1)
                self.assertTrue(result['can_gather'])
                self.assertEqual(len(result['crafting_uses']), 1)
    
    def test_analyze_resource_crafting_potential_no_drops(self):
        """Test _analyze_resource_crafting_potential handles resources with no drops."""
        resource_location = {
            'x': 1,
            'y': 1,
            'resource_code': 'empty_rock',
            'distance': 2
        }
        
        # Mock resource with no drops
        mock_resource_response = Mock()
        mock_resource_response.data = Mock()
        mock_resource_response.data.name = 'Empty Rock'
        mock_resource_response.data.skill = 'mining'
        mock_resource_response.data.level = 1
        mock_resource_response.data.drops = []
        
        with patch('src.controller.actions.analyze_resources.get_resource_api') as mock_get_resource:
            mock_get_resource.return_value = mock_resource_response
            
            result = self.action._analyze_resource_crafting_potential(
                self.client, resource_location, self.context.knowledge_base, 5, ['weapon']
            )
            
            self.assertIsNotNone(result)
            self.assertEqual(result['resource_code'], 'empty_rock')
            self.assertEqual(len(result['crafting_uses']), 0)
    
    def test_analyze_resource_crafting_potential_api_error(self):
        """Test _analyze_resource_crafting_potential handles API errors."""
        resource_location = {
            'x': 1,
            'y': 1,
            'resource_code': 'error_resource',
            'distance': 2
        }
        
        with patch('src.controller.actions.analyze_resources.get_resource_api') as mock_get_resource:
            mock_get_resource.side_effect = Exception("API error")
            
            result = self.action._analyze_resource_crafting_potential(
                self.client, resource_location, self.context.knowledge_base, 5, ['weapon']
            )
            
            self.assertIsNone(result)
    
    def test_extract_all_materials(self):
        """Test _extract_all_materials extracts materials correctly."""
        # Mock craft data with materials
        craft_data = Mock()
        material1 = Mock()
        material1.code = 'iron'
        material1.quantity = 3
        material2 = Mock()
        material2.code = 'wood'
        material2.quantity = 1
        craft_data.items = [material1, material2]
        
        materials = self.action._extract_all_materials(craft_data)
        
        self.assertEqual(len(materials), 2)
        self.assertEqual(materials[0]['code'], 'iron')
        self.assertEqual(materials[0]['quantity'], 3)
        self.assertEqual(materials[1]['code'], 'wood')
        self.assertEqual(materials[1]['quantity'], 1)
    
    def test_extract_all_materials_no_items(self):
        """Test _extract_all_materials handles craft data with no items."""
        craft_data = Mock()
        craft_data.items = None
        
        materials = self.action._extract_all_materials(craft_data)
        
        self.assertEqual(materials, [])
    
    def test_get_equipment_items_from_knowledge_success(self):
        """Test _get_equipment_items_from_knowledge retrieves items from knowledge base."""
        # Mock knowledge base with items
        self.context.knowledge_base.data = {
            'items': {
                'iron_sword': {
                    'item_type': 'weapon',
                    'level': 5
                },
                'steel_sword': {
                    'item_type': 'weapon',
                    'level': 10
                },
                'iron_helmet': {
                    'item_type': 'helmet',
                    'level': 5
                },
                'cloth_shirt': {
                    'item_type': 'body_armor',
                    'level': 1
                }
            }
        }
        
        items = self.action._get_equipment_items_from_knowledge(
            self.context.knowledge_base, 5, ['weapon', 'armor']
        )
        
        # Should return items within level range (±5 levels)
        self.assertIn('iron_sword', items)
        self.assertIn('iron_helmet', items)
        self.assertIn('cloth_shirt', items)
        self.assertIn('steel_sword', items)  # Level 10 is within range of character level 5
    
    def test_get_equipment_items_from_knowledge_no_data(self):
        """Test _get_equipment_items_from_knowledge handles missing knowledge base."""
        items = self.action._get_equipment_items_from_knowledge(None, 5, ['weapon'])
        self.assertEqual(items, [])
    
    def test_get_equipment_items_from_knowledge_exception(self):
        """Test _get_equipment_items_from_knowledge handles exceptions."""
        # Mock knowledge base that raises exception
        kb = Mock()
        kb.data = Mock()
        kb.data.get.side_effect = Exception("Data error")
        
        items = self.action._get_equipment_items_from_knowledge(kb, 5, ['weapon'])
        self.assertEqual(items, [])
    
    def test_prioritize_crafting_opportunities(self):
        """Test _prioritize_crafting_opportunities sorts opportunities correctly."""
        opportunities = [
            {
                'item_code': 'iron_sword',
                'item_type': 'weapon',
                'level_appropriateness': 'good',
                'feasibility_score': 0.5
            },
            {
                'item_code': 'iron_helmet',
                'item_type': 'helmet',
                'level_appropriateness': 'good',
                'feasibility_score': 0.8
            },
            {
                'item_code': 'steel_sword',
                'item_type': 'weapon',
                'level_appropriateness': 'poor',
                'feasibility_score': 0.9
            }
        ]
        
        # Mock config data with priorities
        config_data = Mock()
        config_data.data = {
            'resource_analysis_priorities': {
                'equipment_type_priorities': {
                    'weapon': 3,
                    'helmet': 2
                },
                'level_appropriateness_priorities': {
                    'good': 3,
                    'poor': 1
                }
            }
        }
        
        prioritized = self.action._prioritize_crafting_opportunities(opportunities, config_data)
        
        # Should prioritize weapon with good level appropriateness first
        self.assertEqual(prioritized[0]['item_code'], 'iron_sword')
        self.assertEqual(prioritized[1]['item_code'], 'steel_sword')  # Weapon but poor level
        self.assertEqual(prioritized[2]['item_code'], 'iron_helmet')  # Lower priority type
    
    def test_get_equipment_type_priority_from_config(self):
        """Test _get_equipment_type_priority reads from config correctly."""
        config_data = Mock()
        config_data.data = {
            'resource_analysis_priorities': {
                'equipment_type_priorities': {
                    'weapon': 5,
                    'armor': 3
                }
            }
        }
        
        priority = self.action._get_equipment_type_priority('weapon', config_data)
        self.assertEqual(priority, 5)
        
        priority = self.action._get_equipment_type_priority('armor', config_data)
        self.assertEqual(priority, 3)
    
    def test_get_equipment_type_priority_fallback(self):
        """Test _get_equipment_type_priority uses fallback values."""
        # No config data
        priority = self.action._get_equipment_type_priority('weapon', None)
        self.assertEqual(priority, 3)  # Fallback value for weapon
        
        # Unknown type
        priority = self.action._get_equipment_type_priority('unknown_type', None)
        self.assertEqual(priority, 0)
    
    def test_get_level_appropriateness_priority_from_config(self):
        """Test _get_level_appropriateness_priority reads from config correctly."""
        config_data = Mock()
        config_data.data = {
            'resource_analysis_priorities': {
                'level_appropriateness_priorities': {
                    'good': 5,
                    'acceptable': 3,
                    'poor': 1
                }
            }
        }
        
        priority = self.action._get_level_appropriateness_priority('good', config_data)
        self.assertEqual(priority, 5)
        
        priority = self.action._get_level_appropriateness_priority('poor', config_data)
        self.assertEqual(priority, 1)
    
    def test_get_level_appropriateness_priority_fallback(self):
        """Test _get_level_appropriateness_priority uses fallback values."""
        # No config data
        priority = self.action._get_level_appropriateness_priority('good', None)
        self.assertEqual(priority, 3)  # Fallback value
        
        # Unknown rating
        priority = self.action._get_level_appropriateness_priority('unknown', None)
        self.assertEqual(priority, 0)
    
    def test_recommend_next_action_with_opportunities(self):
        """Test _recommend_next_action with viable opportunities."""
        opportunities = [
            {
                'item_code': 'iron_sword',
                'item_name': 'Iron Sword',
                'item_level': 5,
                'resource_code': 'iron_ore',
                'resource_location': (1, 1),
                'materials_needed': [{'code': 'iron', 'quantity': 3}],
                'workshop_skill': 'weaponsmithing'
            }
        ]
        
        recommendation = self.action._recommend_next_action(opportunities)
        
        self.assertEqual(recommendation['action'], 'gather_for_crafting')
        self.assertEqual(recommendation['priority'], 'high')
        self.assertEqual(recommendation['target_item'], 'iron_sword')
        self.assertEqual(recommendation['target_resource'], 'iron_ore')
        self.assertIn('Craft Iron Sword', recommendation['reason'])
    
    def test_recommend_next_action_no_opportunities(self):
        """Test _recommend_next_action with no opportunities."""
        recommendation = self.action._recommend_next_action([])
        
        self.assertEqual(recommendation['action'], 'continue_hunting')
        self.assertEqual(recommendation['priority'], 'low')
        self.assertIn('No viable equipment crafting opportunities', recommendation['reason'])
    
    def test_execute_success_with_opportunities(self):
        """Test successful execute with crafting opportunities found."""
        # Mock the helper methods
        with patch.object(self.action, '_find_nearby_resources') as mock_find:
            mock_find.return_value = [
                {'x': 1, 'y': 1, 'resource_code': 'iron_ore', 'distance': 1}
            ]
            
            with patch.object(self.action, '_analyze_resource_crafting_potential') as mock_analyze:
                mock_analyze.return_value = {
                    'resource_code': 'iron_ore',
                    'can_gather': True,
                    'crafting_uses': [{'item_code': 'iron_sword'}],
                    'location': (1, 1),
                    'distance': 1,
                    'resource_name': 'Iron Ore'
                }
                
                with patch.object(self.action, '_find_equipment_crafting_opportunities') as mock_find_equip:
                    mock_find_equip.return_value = [
                        {
                            'item_code': 'iron_sword',
                            'item_name': 'Iron Sword',
                            'item_type': 'weapon',
                            'item_level': 5,
                            'level_appropriateness': 'good',
                            'feasibility_score': 0.8
                        }
                    ]
                    
                    with patch.object(self.action, '_prioritize_crafting_opportunities') as mock_prioritize:
                        mock_prioritize.return_value = mock_find_equip.return_value
                        
                        with patch.object(self.action, '_recommend_next_action') as mock_recommend:
                            mock_recommend.return_value = {
                                'action': 'gather_for_crafting',
                                'priority': 'high'
                            }
                            
                            result = self.action.execute(self.client, self.context)
                            
                            self.assertIsInstance(result, ActionResult)
                            self.assertTrue(result.success)
                            self.assertEqual(result.data['nearby_resources_count'], 1)
                            self.assertIn('iron_ore', result.data['analyzed_resources'])
                            self.assertEqual(len(result.data['equipment_opportunities']), 1)
    
    def test_execute_no_resources_found(self):
        """Test execute when no resources are found."""
        with patch.object(self.action, '_find_nearby_resources') as mock_find:
            mock_find.return_value = []
            
            result = self.action.execute(self.client, self.context)
            
            self.assertIsInstance(result, ActionResult)
            self.assertFalse(result.success)
            self.assertIn('No resources found', result.error)
    
    def test_execute_with_exception(self):
        """Test execute handles exceptions properly."""
        with patch.object(self.action, '_find_nearby_resources') as mock_find:
            mock_find.side_effect = Exception("Test error")
            
            result = self.action.execute(self.client, self.context)
            
            self.assertIsInstance(result, ActionResult)
            self.assertFalse(result.success)
            self.assertIn('Resource analysis failed', result.error)
            self.assertIn('Test error', result.error)


    def test_find_crafting_uses_for_item_with_knowledge_base(self):
        """Test _find_crafting_uses_for_item using knowledge base data."""
        # Mock knowledge base with equipment items
        with patch.object(self.action, '_get_equipment_items_from_knowledge') as mock_get_kb:
            mock_get_kb.return_value = ['iron_sword', 'iron_helmet']
            
            # Mock item API responses
            sword_response = Mock()
            sword_response.data = Mock()
            sword_response.data.code = 'iron_sword'
            sword_response.data.name = 'Iron Sword'
            sword_response.data.type = 'weapon'
            sword_response.data.level = 5
            sword_response.data.craft = Mock()
            sword_response.data.craft.skill = 'weaponsmithing'
            sword_response.data.craft.items = [
                Mock(code='iron', quantity=3),
                Mock(code='wood', quantity=1)
            ]
            
            helmet_response = Mock()
            helmet_response.data = Mock()
            helmet_response.data.code = 'iron_helmet'
            helmet_response.data.craft = None  # No craft data
            
            with patch('src.controller.actions.analyze_resources.get_item_api') as mock_get_item:
                def item_side_effect(code, client):
                    if code == 'iron_sword':
                        return sword_response
                    elif code == 'iron_helmet':
                        return helmet_response
                    return None
                
                mock_get_item.side_effect = item_side_effect
                
                uses = self.action._find_crafting_uses_for_item(
                    self.client, 'iron', self.context.knowledge_base, 5, ['weapon']
                )
                
                self.assertEqual(len(uses), 1)
                self.assertEqual(uses[0]['item_code'], 'iron_sword')
                self.assertEqual(uses[0]['material_quantity_needed'], 3)
                self.assertEqual(uses[0]['workshop_required'], 'weaponsmithing')
    
    def test_find_crafting_uses_for_item_api_discovery(self):
        """Test _find_crafting_uses_for_item using API discovery."""
        # Mock no knowledge base data
        with patch.object(self.action, '_get_equipment_items_from_knowledge') as mock_get_kb:
            mock_get_kb.return_value = []
            
            # Mock API discovery
            with patch.object(self.action, '_discover_equipment_items_from_api') as mock_discover:
                mock_discover.return_value = ['bronze_sword']
                
                # Mock item API response
                item_response = Mock()
                item_response.data = Mock()
                item_response.data.code = 'bronze_sword'
                item_response.data.name = 'Bronze Sword'
                item_response.data.type = 'weapon'
                item_response.data.level = 3
                item_response.data.craft = Mock()
                item_response.data.craft.skill = 'weaponsmithing'
                item_response.data.craft.items = [Mock(code='bronze', quantity=2)]
                
                with patch('src.controller.actions.analyze_resources.get_item_api') as mock_get_item:
                    mock_get_item.return_value = item_response
                    
                    uses = self.action._find_crafting_uses_for_item(
                        self.client, 'bronze', self.context.knowledge_base, 5, ['weapon']
                    )
                    
                    self.assertEqual(len(uses), 1)
                    self.assertEqual(uses[0]['item_code'], 'bronze_sword')
    
    def test_find_crafting_uses_for_item_no_matching_materials(self):
        """Test _find_crafting_uses_for_item when no items use the material."""
        with patch.object(self.action, '_get_equipment_items_from_knowledge') as mock_get_kb:
            mock_get_kb.return_value = ['iron_sword']
            
            # Mock item that doesn't use our material
            item_response = Mock()
            item_response.data = Mock()
            item_response.data.code = 'iron_sword'
            item_response.data.craft = Mock()
            item_response.data.craft.items = [Mock(code='iron', quantity=3)]  # Uses iron, not copper
            
            with patch('src.controller.actions.analyze_resources.get_item_api') as mock_get_item:
                mock_get_item.return_value = item_response
                
                uses = self.action._find_crafting_uses_for_item(
                    self.client, 'copper', self.context.knowledge_base, 5, ['weapon']
                )
                
                self.assertEqual(len(uses), 0)
    
    def test_find_crafting_uses_for_item_exception_handling(self):
        """Test _find_crafting_uses_for_item handles exceptions gracefully."""
        with patch.object(self.action, '_get_equipment_items_from_knowledge') as mock_get_kb:
            mock_get_kb.return_value = ['error_item']
            
            with patch('src.controller.actions.analyze_resources.get_item_api') as mock_get_item:
                mock_get_item.side_effect = Exception("API error")
                
                uses = self.action._find_crafting_uses_for_item(
                    self.client, 'iron', self.context.knowledge_base, 5, ['weapon']
                )
                
                self.assertEqual(uses, [])
    
    def test_discover_equipment_items_from_api_success(self):
        """Test _discover_equipment_items_from_api retrieves items from API."""
        # Mock API response
        items_response = Mock()
        item1 = Mock()
        item1.code = 'iron_sword'
        item2 = Mock()
        item2.code = 'iron_helmet'
        items_response.data = [item1, item2]
        
        # Patch where it's imported
        with patch('artifactsmmo_api_client.api.items.get_all_items_items_get.sync') as mock_get_all:
            mock_get_all.return_value = items_response
            
            items = self.action._discover_equipment_items_from_api(self.client, 5, ['weapon'])
            
            # Should be called for each equipment type
            self.assertTrue(mock_get_all.called)
            self.assertIn('iron_sword', items)
            self.assertIn('iron_helmet', items)
    
    def test_discover_equipment_items_from_api_exception(self):
        """Test _discover_equipment_items_from_api handles API exceptions."""
        # The import happens inside the method, so we need to patch the actual exception
        with patch('artifactsmmo_api_client.api.items.get_all_items_items_get.sync') as mock_get_all:
            mock_get_all.side_effect = Exception("API error")
            
            items = self.action._discover_equipment_items_from_api(self.client, 5, ['weapon'])
            
            self.assertEqual(items, [])
    
    def test_find_equipment_crafting_opportunities(self):
        """Test _find_equipment_crafting_opportunities creates opportunities correctly."""
        resource_analysis = {
            'iron_ore': {
                'can_gather': True,
                'location': (1, 1),
                'distance': 2,
                'resource_name': 'Iron Ore',
                'crafting_uses': [
                    {
                        'item_code': 'iron_sword',
                        'item_name': 'Iron Sword',
                        'item_type': 'weapon',
                        'item_level': 5,
                        'all_materials_needed': [{'code': 'iron', 'quantity': 3}],
                        'workshop_required': 'weaponsmithing'
                    }
                ]
            },
            'copper_ore': {
                'can_gather': False,  # Can't gather this one
                'crafting_uses': []
            }
        }
        
        opportunities = self.action._find_equipment_crafting_opportunities(
            self.client, resource_analysis, 5, ['weapon']
        )
        
        self.assertEqual(len(opportunities), 1)
        self.assertEqual(opportunities[0]['item_code'], 'iron_sword')
        self.assertEqual(opportunities[0]['resource_code'], 'iron_ore')
        self.assertEqual(opportunities[0]['level_appropriateness'], 'good')  # Level 5 item for level 5 character
        self.assertGreater(opportunities[0]['feasibility_score'], 0)
    
    def test_repr(self):
        """Test string representation."""
        self.assertEqual(repr(self.action), "AnalyzeResourcesAction()")
    
    def test_analyze_resource_crafting_potential_no_resource_response(self):
        """Test _analyze_resource_crafting_potential handles no resource response."""
        resource_location = {
            'x': 1,
            'y': 1,
            'resource_code': 'missing_resource',
            'distance': 2
        }
        
        with patch('src.controller.actions.analyze_resources.get_resource_api') as mock_get_resource:
            # Return None response
            mock_get_resource.return_value = None
            
            result = self.action._analyze_resource_crafting_potential(
                self.client, resource_location, self.context.knowledge_base, 5, ['weapon']
            )
            
            self.assertIsNone(result)
    
    def test_find_crafting_uses_for_item_no_item_response(self):
        """Test _find_crafting_uses_for_item handles items with no API response."""
        with patch.object(self.action, '_get_equipment_items_from_knowledge') as mock_get_kb:
            mock_get_kb.return_value = ['missing_item']
            
            with patch('src.controller.actions.analyze_resources.get_item_api') as mock_get_item:
                # Return None for the item
                mock_get_item.return_value = None
                
                uses = self.action._find_crafting_uses_for_item(
                    self.client, 'iron', self.context.knowledge_base, 5, ['weapon']
                )
                
                self.assertEqual(uses, [])
    
    def test_find_crafting_uses_for_item_inner_exception(self):
        """Test _find_crafting_uses_for_item handles inner loop exceptions."""
        with patch.object(self.action, '_get_equipment_items_from_knowledge') as mock_get_kb:
            mock_get_kb.return_value = ['item1', 'item2']
            
            # Mock item responses - first throws exception, second works
            item_response = Mock()
            item_response.data = Mock()
            item_response.data.code = 'item2'
            item_response.data.name = 'Item 2'
            item_response.data.type = 'weapon'
            item_response.data.level = 5
            item_response.data.craft = Mock()
            item_response.data.craft.skill = 'weaponsmithing'
            item_response.data.craft.items = [Mock(code='iron', quantity=1)]
            
            with patch('src.controller.actions.analyze_resources.get_item_api') as mock_get_item:
                def item_side_effect(code, client):
                    if code == 'item1':
                        raise Exception("Item 1 error")
                    return item_response
                
                mock_get_item.side_effect = item_side_effect
                
                uses = self.action._find_crafting_uses_for_item(
                    self.client, 'iron', self.context.knowledge_base, 5, ['weapon']
                )
                
                # Should still process item2 despite item1 error
                self.assertEqual(len(uses), 1)
                self.assertEqual(uses[0]['item_code'], 'item2')
    
    def test_discover_equipment_items_from_api_import_error(self):
        """Test _discover_equipment_items_from_api handles import errors."""
        # Mock the import to fail
        import sys
        original_modules = sys.modules.copy()
        
        # Remove the module if it exists
        if 'artifactsmmo_api_client.api.items.get_all_items_items_get' in sys.modules:
            del sys.modules['artifactsmmo_api_client.api.items.get_all_items_items_get']
        
        # Make the import fail
        with patch.dict('sys.modules', {'artifactsmmo_api_client.api.items.get_all_items_items_get': None}):
            items = self.action._discover_equipment_items_from_api(self.client, 5, ['weapon'])
            self.assertEqual(items, [])
        
        # Restore original modules
        sys.modules.update(original_modules)
    
    def test_find_crafting_uses_for_item_outer_exception(self):
        """Test _find_crafting_uses_for_item handles outer try block exceptions."""
        # Mock equipment items to return values
        with patch.object(self.action, '_get_equipment_items_from_knowledge') as mock_get_kb:
            mock_get_kb.return_value = ['test_item']
            
            # Mock the loop to raise an exception that's not caught by inner try
            with patch.object(self.action, '_extract_all_materials') as mock_extract:
                mock_extract.side_effect = Exception("Unexpected error in outer try")
                
                # Mock get_item_api to return a valid item with craft data
                item_response = Mock()
                item_response.data = Mock()
                item_response.data.code = 'test_item'
                item_response.data.type = 'weapon'
                item_response.data.level = 5
                item_response.data.craft = Mock()
                item_response.data.craft.items = [Mock(code='iron', quantity=1)]
                
                with patch('src.controller.actions.analyze_resources.get_item_api') as mock_get_item:
                    mock_get_item.return_value = item_response
                    
                    # This should trigger the outer exception handler at line 251-252
                    uses = self.action._find_crafting_uses_for_item(
                        self.client, 'iron', self.context.knowledge_base, 5, ['weapon']
                    )
                    
                    self.assertEqual(uses, [])


if __name__ == '__main__':
    unittest.main()