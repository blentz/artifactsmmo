"""Test module for AnalyzeCraftingChainAction."""

import unittest
from unittest.mock import Mock, patch, MagicMock

from src.controller.actions.analyze_crafting_chain import AnalyzeCraftingChainAction
from src.controller.actions.base import ActionResult
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from test.fixtures import MockActionContext, create_mock_client


class TestAnalyzeCraftingChainAction(unittest.TestCase):
    """Test cases for AnalyzeCraftingChainAction class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = AnalyzeCraftingChainAction()
        self.mock_client = create_mock_client()
        self.character_name = "TestCharacter"
        
    def test_init(self):
        """Test initialization."""
        action = AnalyzeCraftingChainAction()
        self.assertIsInstance(action, AnalyzeCraftingChainAction)
        
        # Check GOAP parameters
        self.assertEqual(action.conditions['character_status']['alive'], True)
        self.assertEqual(action.reactions['craft_plan_available'], True)
        self.assertEqual(action.reactions['crafting_opportunities_known'], True)
        self.assertEqual(action.weight, 20)
        
        # Check initialized attributes
        self.assertIsInstance(action.analyzed_items, set)
        self.assertIsInstance(action.resource_nodes, dict)
        self.assertIsInstance(action.workshops, dict)
        self.assertIsInstance(action.crafting_dependencies, dict)
        self.assertIsInstance(action.transformation_chains, list)
    
    def test_execute_no_character_name(self):
        """Test execution when no character name is provided."""
        context = MockActionContext()
        context.character_name = None
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "No character name provided")
    
    def test_execute_no_target_item(self):
        """Test execution when no target item is specified."""
        context = MockActionContext(character_name=self.character_name)
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "No target item specified for analysis")
    
    def test_execute_with_exception(self):
        """Test execution with exception handling."""
        context = MockActionContext(
            character_name=self.character_name,
            target_item='copper_dagger'
        )
        
        # Mock exception in _analyze_complete_chain
        with patch.object(self.action, '_analyze_complete_chain', side_effect=Exception("Analysis error")):
            result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Crafting chain analysis failed: Analysis error")
    
    def test_execute_chain_analysis_failed(self):
        """Test execution when chain analysis returns None."""
        context = MockActionContext(
            character_name=self.character_name,
            target_item='unknown_item'
        )
        
        # Mock _analyze_complete_chain to return None
        with patch.object(self.action, '_analyze_complete_chain', return_value=None):
            result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Could not analyze crafting chain for unknown_item")
    
    def test_execute_successful(self):
        """Test successful execution."""
        context = MockActionContext(
            character_name=self.character_name,
            target_item='copper_dagger'
        )
        
        mock_chain = {
            'item_code': 'copper_dagger',
            'type': 'craftable',
            'required_materials': []
        }
        
        mock_actions = [
            {'name': 'find_workshop', 'params': {}}
        ]
        
        # Mock the analysis methods
        with patch.object(self.action, '_analyze_complete_chain', return_value=mock_chain):
            with patch.object(self.action, '_build_action_sequence', return_value=mock_actions):
                with patch.object(self.action, '_extract_raw_materials', return_value=['copper_ore']):
                    result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.data['target_item'], 'copper_dagger')
        self.assertEqual(result.data['chain_analysis'], mock_chain)
        self.assertEqual(result.data['action_sequence'], mock_actions)
        self.assertEqual(result.data['total_steps'], 1)
        self.assertEqual(result.data['raw_materials_needed'], ['copper_ore'])
    
    def test_analyze_complete_chain_max_depth(self):
        """Test _analyze_complete_chain with max recursion depth."""
        mock_kb = Mock()
        
        result = self.action._analyze_complete_chain(self.mock_client, 'test_item', mock_kb, depth=11)
        
        self.assertIsNone(result)
    
    def test_analyze_complete_chain_already_analyzed(self):
        """Test _analyze_complete_chain with already analyzed item."""
        mock_kb = Mock()
        self.action.analyzed_items.add('test_item')
        
        result = self.action._analyze_complete_chain(self.mock_client, 'test_item', mock_kb)
        
        self.assertEqual(result, {"item_code": "test_item", "type": "already_analyzed"})
    
    def test_analyze_complete_chain_from_knowledge_base(self):
        """Test _analyze_complete_chain using knowledge base data."""
        mock_kb = Mock()
        mock_kb.data = {
            'items': {
                'copper_dagger': {
                    'name': 'Copper Dagger',
                    'level': 5,
                    'craft_data': {
                        'skill': 'weaponcrafting',
                        'items': [
                            {'code': 'copper_bar', 'quantity': 6}
                        ]
                    }
                },
                'copper_bar': {}
            }
        }
        
        # Mock _get_item_from_knowledge
        with patch.object(self.action, '_get_item_from_knowledge') as mock_get_item:
            mock_get_item.side_effect = lambda item, kb: kb.data['items'].get(item)
            with patch.object(self.action, '_skill_to_workshop_type', return_value='weaponcrafting'):
                with patch.object(self.action, '_analyze_resource_chain', return_value={'item_code': 'copper_bar', 'type': 'base_resource'}):
                    result = self.action._analyze_complete_chain(self.mock_client, 'copper_dagger', mock_kb)
        
        self.assertEqual(result['item_code'], 'copper_dagger')
        self.assertEqual(result['type'], 'craftable')
        self.assertEqual(result['craft_skill'], 'weaponcrafting')
    
    @patch('src.controller.actions.analyze_crafting_chain.get_item_api')
    def test_analyze_complete_chain_from_api(self, mock_get_item):
        """Test _analyze_complete_chain using API data."""
        mock_kb = Mock()
        mock_kb.data = {'items': {}}
        
        # Mock API response
        mock_item = Mock()
        mock_item.name = 'Copper Dagger'
        mock_item.level = 5
        mock_item.craft = Mock()
        mock_item.craft.skill = 'weaponcrafting'
        mock_item.craft.items = []
        
        mock_response = Mock()
        mock_response.data = mock_item
        mock_get_item.return_value = mock_response
        
        with patch.object(self.action, '_get_item_from_knowledge', return_value=None):
            with patch.object(self.action, '_skill_to_workshop_type', return_value='weaponcrafting'):
                result = self.action._analyze_complete_chain(self.mock_client, 'copper_dagger', mock_kb)
        
        self.assertEqual(result['item_code'], 'copper_dagger')
        self.assertEqual(result['type'], 'craftable')
        self.assertEqual(result['craft_skill'], 'weaponcrafting')
    
    @patch('src.controller.actions.analyze_crafting_chain.get_item_api')
    def test_analyze_complete_chain_api_no_data(self, mock_get_item):
        """Test _analyze_complete_chain when API returns no data."""
        mock_kb = Mock()
        
        mock_get_item.return_value = None
        
        with patch.object(self.action, '_get_item_from_knowledge', return_value=None):
            result = self.action._analyze_complete_chain(self.mock_client, 'unknown_item', mock_kb)
        
        self.assertIsNone(result)
    
    @patch('src.controller.actions.analyze_crafting_chain.get_item_api')
    def test_analyze_complete_chain_api_exception(self, mock_get_item):
        """Test _analyze_complete_chain when API raises exception."""
        mock_kb = Mock()
        
        mock_get_item.side_effect = Exception("API error")
        
        with patch.object(self.action, '_get_item_from_knowledge', return_value=None):
            result = self.action._analyze_complete_chain(self.mock_client, 'test_item', mock_kb)
        
        self.assertIsNone(result)
    
    def test_analyze_complete_chain_base_resource(self):
        """Test _analyze_complete_chain with base resource."""
        mock_kb = Mock()
        mock_item_data = {'name': 'Copper Ore'}
        
        with patch.object(self.action, '_get_item_from_knowledge', return_value=mock_item_data):
            with patch.object(self.action, '_analyze_resource_chain', return_value={'type': 'base_resource'}):
                result = self.action._analyze_complete_chain(self.mock_client, 'copper_ore', mock_kb)
        
        self.assertEqual(result['type'], 'base_resource')
    
    def test_analyze_resource_chain_transformable(self):
        """Test _analyze_resource_chain with transformable resource."""
        mock_kb = Mock()
        item_data = {'name': 'Copper Bar'}
        
        transformation = {
            'raw_material': 'copper_ore',
            'workshop_type': 'smelting'
        }
        
        gathering_info = {'resource_code': 'copper_ore'}
        
        with patch.object(self.action, '_check_transformation_needed', return_value=transformation):
            with patch.object(self.action, '_get_gathering_info', return_value=gathering_info):
                result = self.action._analyze_resource_chain('copper_bar', item_data, mock_kb)
        
        self.assertEqual(result['type'], 'transformable_resource')
        self.assertEqual(result['raw_material'], 'copper_ore')
        self.assertEqual(result['workshop_type'], 'smelting')
    
    def test_analyze_resource_chain_base(self):
        """Test _analyze_resource_chain with base resource."""
        mock_kb = Mock()
        item_data = Mock()
        item_data.name = 'Copper Ore'
        
        gathering_info = {'resource_code': 'copper_ore'}
        
        with patch.object(self.action, '_check_transformation_needed', return_value=None):
            with patch.object(self.action, '_get_gathering_info', return_value=gathering_info):
                result = self.action._analyze_resource_chain('copper_ore', item_data, mock_kb)
        
        self.assertEqual(result['type'], 'base_resource')
        self.assertEqual(result['item_code'], 'copper_ore')
    
    def test_check_transformation_needed_no_kb(self):
        """Test _check_transformation_needed with no knowledge base."""
        result = self.action._check_transformation_needed('copper_bar', None)
        self.assertIsNone(result)
    
    def test_check_transformation_needed_found(self):
        """Test _check_transformation_needed when transformation found."""
        mock_kb = Mock()
        mock_kb.data = {
            'items': {
                'copper_bar': {
                    'craft_data': {
                        'skill': 'smelting',
                        'items': [
                            {'code': 'copper_ore', 'quantity': 10}
                        ]
                    }
                }
            }
        }
        
        with patch.object(self.action, '_skill_to_workshop_type', return_value='smelting'):
            result = self.action._check_transformation_needed('copper_bar', mock_kb)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['raw_material'], 'copper_ore')
        self.assertEqual(result['workshop_type'], 'smelting')
    
    def test_check_transformation_needed_no_craft_data(self):
        """Test _check_transformation_needed when no craft data."""
        mock_kb = Mock()
        mock_kb.data = {
            'items': {
                'copper_ore': {}
            }
        }
        
        result = self.action._check_transformation_needed('copper_ore', mock_kb)
        self.assertIsNone(result)
    
    def test_get_gathering_info(self):
        """Test _get_gathering_info."""
        mock_kb = Mock()
        mock_kb.data = {
            'resources': {
                'copper_ore': {
                    'skill_required': 'mining',
                    'level_required': 5
                }
            }
        }
        
        result = self.action._get_gathering_info('copper_ore', mock_kb)
        
        self.assertEqual(result['resource_code'], 'copper_ore')
        self.assertEqual(result['skill_required'], 'mining')
        self.assertEqual(result['level_required'], 5)
    
    def test_get_gathering_info_no_data(self):
        """Test _get_gathering_info with no data."""
        mock_kb = Mock()
        mock_kb.data = {'resources': {}}
        
        result = self.action._get_gathering_info('unknown_resource', mock_kb)
        
        self.assertEqual(result['resource_code'], 'unknown_resource')
        self.assertEqual(result['skill_required'], 'unknown')
        self.assertEqual(result['level_required'], 1)
    
    def test_skill_to_workshop_type_no_skill(self):
        """Test _skill_to_workshop_type with no skill."""
        result = self.action._skill_to_workshop_type('', None)
        self.assertEqual(result, 'unknown')
    
    def test_skill_to_workshop_type_from_workshops(self):
        """Test _skill_to_workshop_type from workshops data."""
        mock_kb = Mock()
        mock_kb.data = {
            'workshops': {
                'weaponcrafting': {
                    'craft_skill': 'weaponcrafting',
                    'facility_type': 'workshop'
                }
            }
        }
        
        result = self.action._skill_to_workshop_type('weaponcrafting', mock_kb)
        self.assertEqual(result, 'weaponcrafting')
    
    def test_skill_to_workshop_type_from_facilities(self):
        """Test _skill_to_workshop_type from facilities data."""
        mock_kb = Mock()
        mock_kb.data = {
            'workshops': {},
            'facilities': {
                'jewelrycrafting': {
                    'craft_skill': 'jewelrycrafting',
                    'facility_type': 'workshop'
                }
            }
        }
        
        result = self.action._skill_to_workshop_type('jewelrycrafting', mock_kb)
        self.assertEqual(result, 'jewelrycrafting')
    
    def test_skill_to_workshop_type_not_found(self):
        """Test _skill_to_workshop_type when not found."""
        mock_kb = Mock()
        mock_kb.data = {'workshops': {}, 'facilities': {}}
        
        result = self.action._skill_to_workshop_type('unknown_skill', mock_kb)
        self.assertEqual(result, 'unknown_skill')
    
    def test_get_equipment_slot_no_item_code(self):
        """Test _get_equipment_slot with no item code."""
        result = self.action._get_equipment_slot('', 'workshop', None)
        self.assertIsNone(result)
    
    def test_get_equipment_slot_explicit_slot(self):
        """Test _get_equipment_slot with explicit slot."""
        mock_kb = Mock()
        mock_kb.get_item_data.return_value = {'slot': 'weapon'}
        
        result = self.action._get_equipment_slot('sword', 'weaponcrafting', mock_kb)
        self.assertEqual(result, 'weapon')
    
    def test_get_equipment_slot_by_type(self):
        """Test _get_equipment_slot by item type."""
        mock_kb = Mock()
        mock_kb.get_item_data.return_value = {'type': 'weapon'}
        
        result = self.action._get_equipment_slot('sword', 'weaponcrafting', mock_kb)
        self.assertEqual(result, 'weapon')
    
    def test_get_equipment_slot_all_types(self):
        """Test _get_equipment_slot for all equipment types."""
        mock_kb = Mock()
        
        test_cases = [
            ('shield', 'shield'),
            ('helmet', 'helmet'),
            ('body_armor', 'body_armor'),
            ('leg_armor', 'leg_armor'),
            ('boots', 'boots'),
            ('ring', 'ring1'),
            ('amulet', 'amulet'),
            ('artifact', 'artifact1')
        ]
        
        for item_type, expected_slot in test_cases:
            mock_kb.get_item_data.return_value = {'type': item_type}
            result = self.action._get_equipment_slot('test_item', 'workshop', mock_kb)
            self.assertEqual(result, expected_slot)
    
    def test_get_equipment_slot_no_slot(self):
        """Test _get_equipment_slot when no slot found."""
        mock_kb = Mock()
        mock_kb.get_item_data.return_value = {'type': 'consumable'}
        
        result = self.action._get_equipment_slot('potion', 'alchemy', mock_kb)
        self.assertIsNone(result)
    
    def test_calculate_total_materials_base_resources(self):
        """Test _calculate_total_materials with base resources."""
        materials = [
            {
                'material_code': 'copper_ore',
                'quantity_required': 10,
                'chain': {'type': 'base_resource'}
            },
            {
                'material_code': 'iron_ore',
                'quantity_required': 5,
                'chain': {'type': 'base_resource'}
            }
        ]
        
        result = self.action._calculate_total_materials(materials)
        
        self.assertEqual(result['copper_ore'], 10)
        self.assertEqual(result['iron_ore'], 5)
    
    def test_calculate_total_materials_craftable(self):
        """Test _calculate_total_materials with craftable items."""
        materials = [
            {
                'material_code': 'copper_bar',
                'quantity_required': 2,
                'chain': {
                    'type': 'craftable',
                    'total_materials_needed': {'copper_ore': 10}
                }
            }
        ]
        
        result = self.action._calculate_total_materials(materials)
        
        self.assertEqual(result['copper_ore'], 20)  # 2 bars * 10 ore each
    
    def test_build_action_sequence(self):
        """Test _build_action_sequence."""
        chain_analysis = {
            'item_code': 'copper_dagger',
            'workshop_type': 'weaponcrafting',
            'required_materials': [
                {
                    'material_code': 'copper_bar',
                    'quantity_required': 6,
                    'chain': {'type': 'base_resource'}
                }
            ]
        }
        
        self.action.character_inventory = {'copper_bar': 2}  # Have 2, need 6
        
        mock_kb = Mock()
        mock_map_state = Mock()
        
        actions = []
        
        with patch.object(self.action, '_resolve_material_shortage') as mock_resolve:
            with patch.object(self.action, '_add_crafting_sequence') as mock_add_craft:
                actions = self.action._build_action_sequence(chain_analysis, mock_kb, mock_map_state)
                
                # Should resolve shortage of 4 copper_bar
                mock_resolve.assert_called_once()
                call_args = mock_resolve.call_args[0]
                self.assertEqual(call_args[0], 'copper_bar')
                self.assertEqual(call_args[1], 4)  # shortage
                
                # Should add crafting sequence
                mock_add_craft.assert_called_once_with('copper_dagger', 'weaponcrafting', actions, mock_kb, None)
    
    def test_resolve_material_shortage_base_resource(self):
        """Test _resolve_material_shortage for base resource."""
        actions = []
        material_chain = {'type': 'base_resource'}
        mock_kb = Mock()
        mock_map_state = Mock()
        
        with patch.object(self.action, '_add_resource_gathering_sequence') as mock_add_gather:
            self.action._resolve_material_shortage('copper_ore', 10, material_chain, actions, mock_kb, mock_map_state)
            
            mock_add_gather.assert_called_once_with('copper_ore', 10, actions)
    
    def test_resolve_material_shortage_transformable(self):
        """Test _resolve_material_shortage for transformable resource."""
        actions = []
        material_chain = {
            'type': 'transformable_resource',
            'raw_material': 'copper_ore',
            'workshop_type': 'smelting'
        }
        mock_kb = Mock()
        mock_map_state = Mock()
        
        self.action.character_inventory = {'copper_ore': 0}
        
        with patch.object(self.action, '_get_transformation_ratio', return_value=10):
            with patch.object(self.action, '_add_resource_gathering_sequence') as mock_add_gather:
                with patch.object(self.action, '_add_transformation_sequence') as mock_add_transform:
                    self.action._resolve_material_shortage('copper_bar', 5, material_chain, actions, mock_kb, mock_map_state)
                    
                    # Should gather 50 copper_ore (5 bars * 10 ratio)
                    mock_add_gather.assert_called_once_with('copper_ore', 50, actions)
                    # Should transform to copper_bar
                    mock_add_transform.assert_called_once_with('copper_ore', 'copper_bar', 'smelting', 5, actions)
    
    def test_resolve_material_shortage_craftable(self):
        """Test _resolve_material_shortage for craftable item."""
        actions = []
        material_chain = {
            'type': 'craftable',
            'workshop_type': 'weaponcrafting',
            'required_materials': [
                {
                    'material_code': 'iron_ore',
                    'quantity_required': 2,
                    'chain': {'type': 'base_resource'}
                }
            ]
        }
        mock_kb = Mock()
        mock_map_state = Mock()
        
        self.action.character_inventory = {'iron_ore': 0}
        
        # Call the method and check its internal behavior
        with patch.object(self.action, '_add_resource_gathering_sequence') as mock_add_gather:
            with patch.object(self.action, '_add_crafting_sequence') as mock_add_craft:
                self.action._resolve_material_shortage('iron_sword', 3, material_chain, actions, mock_kb, mock_map_state)
                
                # Should add gathering for iron_ore (2 * 3 = 6 needed)
                mock_add_gather.assert_called_once_with('iron_ore', 6, actions)
                # Should add crafting sequence for iron_sword with correct params
                mock_add_craft.assert_called_once()
                call_args = mock_add_craft.call_args[0]
                self.assertEqual(call_args[0], 'iron_sword')
                self.assertEqual(call_args[1], 'weaponcrafting')
                self.assertEqual(call_args[2], actions)
                self.assertEqual(call_args[3], mock_kb)
    
    def test_add_resource_gathering_sequence(self):
        """Test _add_resource_gathering_sequence."""
        actions = []
        
        self.action._add_resource_gathering_sequence('copper_ore', 10, actions)
        
        self.assertEqual(len(actions), 3)
        self.assertEqual(actions[0]['name'], 'find_resources')
        self.assertEqual(actions[1]['name'], 'move')
        self.assertEqual(actions[2]['name'], 'gather_resources')
    
    def test_add_transformation_sequence(self):
        """Test _add_transformation_sequence."""
        actions = []
        
        self.action._add_transformation_sequence('copper_ore', 'copper_bar', 'smelting', 5, actions)
        
        self.assertEqual(len(actions), 3)
        self.assertEqual(actions[0]['name'], 'find_correct_workshop')
        self.assertEqual(actions[1]['name'], 'move')
        self.assertEqual(actions[2]['name'], 'transform_raw_materials')
    
    def test_add_crafting_sequence(self):
        """Test _add_crafting_sequence."""
        actions = []
        mock_kb = Mock()
        
        with patch.object(self.action, '_get_equipped_materials_for_item', return_value=[]):
            with patch.object(self.action, '_get_equipment_slot', return_value='weapon'):
                self.action._add_crafting_sequence('copper_dagger', 'weaponcrafting', actions, mock_kb)
        
        self.assertEqual(len(actions), 4)
        self.assertEqual(actions[0]['name'], 'find_correct_workshop')
        self.assertEqual(actions[1]['name'], 'move')
        self.assertEqual(actions[2]['name'], 'craft_item')
        self.assertEqual(actions[3]['name'], 'equip_item')
    
    def test_add_crafting_sequence_with_unequip(self):
        """Test _add_crafting_sequence with items to unequip."""
        actions = []
        mock_kb = Mock()
        
        equipped_materials = [('copper_bar', 'weapon')]
        
        with patch.object(self.action, '_get_equipped_materials_for_item', return_value=equipped_materials):
            with patch.object(self.action, '_get_equipment_slot', return_value=None):
                self.action._add_crafting_sequence('copper_dagger', 'weaponcrafting', actions, mock_kb)
        
        # Should have unequip action
        unequip_action = next(a for a in actions if a['name'] == 'unequip_item')
        self.assertEqual(unequip_action['params']['slot'], 'weapon')
    
    def test_get_transformation_ratio_found(self):
        """Test _get_transformation_ratio when found."""
        mock_kb = Mock()
        mock_kb.data = {
            'items': {
                'copper_bar': {
                    'craft_data': {
                        'items': [
                            {'code': 'copper_ore', 'quantity': 10}
                        ]
                    }
                }
            }
        }
        
        ratio = self.action._get_transformation_ratio('copper_ore', 'copper_bar', mock_kb)
        self.assertEqual(ratio, 10)
    
    def test_get_transformation_ratio_not_found(self):
        """Test _get_transformation_ratio when not found."""
        mock_kb = Mock()
        mock_kb.data = {'items': {}}
        
        ratio = self.action._get_transformation_ratio('unknown', 'unknown', mock_kb)
        self.assertEqual(ratio, 1)  # Default ratio
    
    def test_extract_raw_materials(self):
        """Test _extract_raw_materials."""
        chain_analysis = {
            'type': 'craftable',
            'required_materials': [
                {
                    'chain': {
                        'type': 'transformable_resource',
                        'raw_material': 'copper_ore'
                    }
                },
                {
                    'chain': {
                        'type': 'base_resource',
                        'item_code': 'iron_ore'
                    }
                },
                {
                    'chain': {
                        'type': 'craftable',
                        'required_materials': [
                            {
                                'chain': {
                                    'type': 'base_resource',
                                    'item_code': 'coal'
                                }
                            }
                        ]
                    }
                }
            ]
        }
        
        materials = self.action._extract_raw_materials(chain_analysis)
        
        self.assertIn('copper_ore', materials)
        self.assertIn('iron_ore', materials)
        self.assertIn('coal', materials)
    
    def test_get_item_from_knowledge(self):
        """Test _get_item_from_knowledge."""
        mock_kb = Mock()
        mock_kb.data = {
            'items': {
                'copper_dagger': {'name': 'Copper Dagger'}
            }
        }
        
        result = self.action._get_item_from_knowledge('copper_dagger', mock_kb)
        self.assertEqual(result['name'], 'Copper Dagger')
        
        result = self.action._get_item_from_knowledge('unknown', mock_kb)
        self.assertIsNone(result)
        
        result = self.action._get_item_from_knowledge('test', None)
        self.assertIsNone(result)
    
    def test_has_sufficient_resources(self):
        """Test _has_sufficient_resources."""
        self.action.character_inventory = {'copper_ore': 10}
        
        self.assertTrue(self.action._has_sufficient_resources('copper_ore', 5))
        self.assertTrue(self.action._has_sufficient_resources('copper_ore', 10))
        self.assertFalse(self.action._has_sufficient_resources('copper_ore', 15))
        self.assertFalse(self.action._has_sufficient_resources('iron_ore', 1))
    
    def test_has_sufficient_resources_no_inventory(self):
        """Test _has_sufficient_resources with no inventory."""
        # Don't set character_inventory
        self.assertFalse(self.action._has_sufficient_resources('copper_ore', 1))
    
    def test_get_equipped_materials_for_item(self):
        """Test _get_equipped_materials_for_item."""
        mock_kb = Mock()
        mock_kb.data = {
            'items': {
                'copper_dagger': {
                    'craft_data': {
                        'items': [
                            {'code': 'copper_bar'},
                            {'code': 'leather'}
                        ]
                    }
                }
            }
        }
        
        # Mock context with character state
        mock_context = Mock()
        mock_context.character_state = Mock()
        mock_context.character_state.data = {
            'weapon': 'copper_bar',
            'boots': 'leather_boots',
            'inventory': []
        }
        
        self.action.current_context = mock_context
        
        result = self.action._get_equipped_materials_for_item('copper_dagger', mock_kb, self.mock_client)
        
        # Should find copper_bar equipped as weapon
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], ('copper_bar', 'weapon'))
    
    def test_get_equipped_materials_no_context(self):
        """Test _get_equipped_materials_for_item with no context."""
        mock_kb = Mock()
        mock_kb.data = {'items': {}}
        
        result = self.action._get_equipped_materials_for_item('test', mock_kb, self.mock_client)
        self.assertEqual(result, [])
    
    def test_get_equipped_materials_no_kb_data(self):
        """Test _get_equipped_materials_for_item with no data attribute in kb."""
        mock_kb = Mock(spec=['other_method'])  # No data attribute
        
        result = self.action._get_equipped_materials_for_item('test', mock_kb, self.mock_client)
        self.assertEqual(result, [])
    
    def test_get_equipped_materials_exception(self):
        """Test _get_equipped_materials_for_item with exception."""
        mock_kb = Mock()
        mock_kb.data = {
            'items': {
                'test': {
                    'craft_data': {
                        'items': [{'code': 'material'}]
                    }
                }
            }
        }
        
        self.action.current_context = Mock()
        self.action.current_context.character_state = Mock(side_effect=Exception("Error"))
        
        result = self.action._get_equipped_materials_for_item('test', mock_kb, self.mock_client)
        self.assertEqual(result, [])
    
    def test_repr(self):
        """Test __repr__ method."""
        self.assertEqual(repr(self.action), "AnalyzeCraftingChainAction()")
    
    def test_analyze_complete_chain_craft_data_api_format(self):
        """Test _analyze_complete_chain with API format craft data."""
        mock_kb = Mock()
        
        # Mock item data with API format (object with attributes)
        mock_item = Mock()
        mock_item.name = 'Copper Dagger'
        mock_item.level = 5
        mock_item.craft = Mock()
        mock_item.craft.skill = 'weaponcrafting'
        mock_craft_item = Mock()
        mock_craft_item.code = 'copper_bar'
        mock_craft_item.quantity = 6
        mock_item.craft.items = [mock_craft_item]
        
        with patch.object(self.action, '_get_item_from_knowledge', return_value=None):
            with patch('src.controller.actions.analyze_crafting_chain.get_item_api') as mock_get_item:
                mock_response = Mock()
                mock_response.data = mock_item
                mock_get_item.return_value = mock_response
                
                with patch.object(self.action, '_skill_to_workshop_type', return_value='weaponcrafting'):
                    with patch.object(self.action, '_analyze_resource_chain', return_value={'type': 'base_resource'}):
                        result = self.action._analyze_complete_chain(self.mock_client, 'copper_dagger', mock_kb)
        
        self.assertEqual(result['item_code'], 'copper_dagger')
        self.assertEqual(result['type'], 'craftable')
        self.assertEqual(result['craft_skill'], 'weaponcrafting')
        self.assertEqual(result['item_name'], 'Copper Dagger')
        self.assertEqual(result['level_required'], 5)
    
    def test_analyze_resource_chain_dict_format(self):
        """Test _analyze_resource_chain with dict format item data."""
        mock_kb = Mock()
        item_data = {'name': 'Copper Ore'}
        
        gathering_info = {'resource_code': 'copper_ore'}
        
        with patch.object(self.action, '_check_transformation_needed', return_value=None):
            with patch.object(self.action, '_get_gathering_info', return_value=gathering_info):
                result = self.action._analyze_resource_chain('copper_ore', item_data, mock_kb)
        
        self.assertEqual(result['type'], 'base_resource')
        self.assertEqual(result['item_code'], 'copper_ore')
        self.assertEqual(result['item_name'], 'Copper Ore')
    
    def test_check_transformation_needed_no_craft_items(self):
        """Test _check_transformation_needed when craft_data has no items."""
        mock_kb = Mock()
        mock_kb.data = {
            'items': {
                 'test_item': {
                     'craft_data': {
                         'skill': 'crafting',
                         'items': []
                     }
                 }
            }
        }
        
        result = self.action._check_transformation_needed('test_item', mock_kb)
        self.assertIsNone(result)
    
    def test_skill_to_workshop_type_no_kb(self):
        """Test _skill_to_workshop_type with no knowledge base."""
        result = self.action._skill_to_workshop_type('weaponcrafting', None)
        self.assertEqual(result, 'weaponcrafting')
    
    def test_get_equipment_slot_dict_format(self):
        """Test _get_equipment_slot with dict format item data."""
        mock_kb = Mock()
        mock_kb.get_item_data.return_value = None
        
        mock_kb.get_item_data.return_value = {'type': 'helmet'}
        
        result = self.action._get_equipment_slot('test_helmet', 'gearcrafting', mock_kb)
        
        self.assertEqual(result, 'helmet')
    
    def test_get_equipment_slot_artifact_type(self):
        """Test _get_equipment_slot with artifact type."""
        mock_kb = Mock()
        mock_kb.get_item_data.return_value = None
        
        mock_kb.get_item_data.return_value = {'type': 'artifact'}
        
        result = self.action._get_equipment_slot('ancient_artifact', 'workshop', mock_kb)
        
        self.assertEqual(result, 'artifact1')
    
    def test_get_equipment_slot_kb_exception(self):
        """Test _get_equipment_slot when KB throws exception."""
        mock_kb = None  # No knowledge base
        
        result = self.action._get_equipment_slot('test_item', 'workshop', mock_kb)
        
        self.assertIsNone(result)
    
    def test_build_action_sequence_with_client(self):
        """Test _build_action_sequence with client parameter."""
        chain_analysis = {
            'item_code': 'copper_dagger',
            'workshop_type': 'weaponcrafting',
            'required_materials': []
        }
        
        mock_kb = Mock()
        mock_map_state = Mock()
        
        with patch.object(self.action, '_add_crafting_sequence') as mock_add_craft:
            actions = self.action._build_action_sequence(chain_analysis, mock_kb, mock_map_state, self.mock_client)
            
            mock_add_craft.assert_called_once_with('copper_dagger', 'weaponcrafting', actions, mock_kb, self.mock_client)
    
    def test_build_action_sequence_no_shortage(self):
        """Test _build_action_sequence when there's no material shortage."""
        chain_analysis = {
            'item_code': 'copper_dagger',
            'workshop_type': 'weaponcrafting',
            'required_materials': [
                {
                    'material_code': 'copper_bar',
                    'quantity_required': 6,
                    'chain': {'type': 'base_resource'}
                }
            ]
        }
        
        self.action.character_inventory = {'copper_bar': 10}  # Have more than enough
        
        mock_kb = Mock()
        mock_map_state = Mock()
        
        with patch.object(self.action, '_resolve_material_shortage') as mock_resolve:
            with patch.object(self.action, '_add_crafting_sequence') as mock_add_craft:
                actions = self.action._build_action_sequence(chain_analysis, mock_kb, mock_map_state)
                
                # Should not resolve shortage
                mock_resolve.assert_not_called()
                # Should add crafting sequence
                mock_add_craft.assert_called_once()
    
    def test_resolve_material_shortage_craftable_with_client(self):
        """Test _resolve_material_shortage for craftable item with client parameter."""
        actions = []
        material_chain = {
            'type': 'craftable',
            'workshop_type': 'weaponcrafting',
            'required_materials': [
                {
                    'material_code': 'iron_ore',
                    'quantity_required': 2,
                    'chain': {'type': 'base_resource'}
                }
            ]
        }
        mock_kb = Mock()
        mock_map_state = Mock()
        
        self.action.character_inventory = {'iron_ore': 0}
        
        # Test the recursive crafting case
        with patch.object(self.action, '_add_resource_gathering_sequence') as mock_add_gather:
            with patch.object(self.action, '_add_crafting_sequence') as mock_add_craft:
                with patch.object(self.action, '_get_equipment_slot', return_value='weapon'):
                    self.action._resolve_material_shortage('iron_sword', 3, material_chain, actions, mock_kb, mock_map_state, self.mock_client)
                
                # Should add gathering for iron_ore (2 * 3 = 6 needed)
                mock_add_gather.assert_called_once_with('iron_ore', 6, actions)
                # Should add crafting sequence for iron_sword with correct params
                mock_add_craft.assert_called_once_with('iron_sword', 'weaponcrafting', actions, mock_kb, self.mock_client)
    
    def test_get_equipped_materials_for_item_no_craft_data(self):
        """Test _get_equipped_materials_for_item when item has no craft data."""
        mock_kb = Mock()
        mock_kb.data = {
            'items': {
                'test_item': {}  # No craft_data
            }
        }
        
        result = self.action._get_equipped_materials_for_item('test_item', mock_kb, self.mock_client)
        self.assertEqual(result, [])
    
    def test_get_equipped_materials_for_item_inventory_item(self):
        """Test _get_equipped_materials_for_item with inventory items."""
        mock_kb = Mock()
        mock_kb.data = {
            'items': {
                'copper_dagger': {
                    'craft_data': {
                        'items': [
                            {'code': 'copper_bar'},
                            {'code': 'leather'}
                        ]
                    }
                }
            }
        }
        
        # Mock context with character state
        mock_context = Mock()
        mock_context.character_state = Mock()
        mock_context.character_state.data = {
            'weapon': 'iron_sword',
            'inventory': [
                {'code': 'copper_bar', 'quantity': 5},
                {'code': 'leather', 'quantity': 3}
            ]
        }
        
        self.action.current_context = mock_context
        
        result = self.action._get_equipped_materials_for_item('copper_dagger', mock_kb, self.mock_client)
        
        # Should not find any equipped materials since they're in inventory
        self.assertEqual(result, [])
    
    def test_add_crafting_sequence_no_slot(self):
        """Test _add_crafting_sequence when no equipment slot found."""
        actions = []
        mock_kb = Mock()
        
        with patch.object(self.action, '_get_equipped_materials_for_item', return_value=[]):
            with patch.object(self.action, '_get_equipment_slot', return_value=None):
                self.action._add_crafting_sequence('consumable_item', 'alchemy', actions, mock_kb)
        
        # Should still add crafting actions without equip
        self.assertEqual(len(actions), 3)  # find_workshop, move, craft
        self.assertEqual(actions[0]['name'], 'find_correct_workshop')
        self.assertEqual(actions[1]['name'], 'move')
        self.assertEqual(actions[2]['name'], 'craft_item')
        # No equip action
        equip_actions = [a for a in actions if a['name'] == 'equip_item']
        self.assertEqual(len(equip_actions), 0)
    
    def test_check_transformation_needed_no_kb_data(self):
        """Test _check_transformation_needed when kb has no data attribute."""
        mock_kb = Mock(spec=['other_method'])  # No data attribute
        result = self.action._check_transformation_needed('copper_bar', mock_kb)
        self.assertIsNone(result)
    
    def test_check_transformation_needed_item_not_in_kb(self):
        """Test _check_transformation_needed when item not in knowledge base."""
        mock_kb = Mock()
        mock_kb.data = {'items': {}}
        result = self.action._check_transformation_needed('unknown_item', mock_kb)
        self.assertIsNone(result)
    
    def test_check_transformation_needed_no_raw_material_code(self):
        """Test _check_transformation_needed when craft data has no material code."""
        mock_kb = Mock()
        mock_kb.data = {
            'items': {
                'test_item': {
                    'craft_data': {
                        'skill': 'crafting',
                        'items': [{'quantity': 10}]  # No code field
                    }
                }
            }
        }
        result = self.action._check_transformation_needed('test_item', mock_kb)
        self.assertIsNone(result)
    
    def test_get_equipment_slot_other_equipment_type(self):
        """Test _get_equipment_slot with non-standard equipment type."""
        mock_kb = Mock()
        mock_kb.get_item_data.return_value = {'type': 'gloves'}
        
        result = self.action._get_equipment_slot('magic_gloves', 'workshop', mock_kb)
        self.assertEqual(result, 'gloves')  # Returns the type as slot
    
    def test_add_gathering_actions_base_resource(self):
        """Test _add_gathering_actions for base resource."""
        actions = []
        chain = {
            'item_code': 'copper_ore',
            'type': 'base_resource'
        }
        mock_kb = Mock()
        mock_map_state = Mock()
        
        # Mock _has_sufficient_resources to return False
        with patch.object(self.action, '_has_sufficient_resources', return_value=False):
            self.action._add_gathering_actions(chain, actions, mock_kb, mock_map_state)
        
        self.assertEqual(len(actions), 3)
        self.assertEqual(actions[0]['name'], 'find_resources')
        self.assertEqual(actions[1]['name'], 'move')
        self.assertEqual(actions[2]['name'], 'gather_resources')
    
    def test_add_gathering_actions_already_have_resource(self):
        """Test _add_gathering_actions when already have sufficient resource."""
        actions = []
        chain = {
            'item_code': 'copper_ore',
            'type': 'base_resource'
        }
        mock_kb = Mock()
        mock_map_state = Mock()
        
        # Mock _has_sufficient_resources to return True
        with patch.object(self.action, '_has_sufficient_resources', return_value=True):
            self.action._add_gathering_actions(chain, actions, mock_kb, mock_map_state)
        
        self.assertEqual(len(actions), 0)  # No actions added
    
    def test_add_gathering_actions_transformable(self):
        """Test _add_gathering_actions for transformable resource."""
        actions = []
        chain = {
            'item_code': 'copper_bar',
            'type': 'transformable_resource',
            'raw_material': 'copper_ore',
            'workshop_type': 'smelting'
        }
        mock_kb = Mock()
        mock_map_state = Mock()
        
        # Mock _has_sufficient_resources
        with patch.object(self.action, '_has_sufficient_resources') as mock_has_sufficient:
            mock_has_sufficient.side_effect = [False, False]  # Don't have copper_bar or copper_ore
            self.action._add_gathering_actions(chain, actions, mock_kb, mock_map_state)
        
        # Should add gathering for raw material and transformation
        self.assertEqual(len(actions), 6)  # 3 for gathering + 3 for transformation
        self.assertEqual(actions[0]['name'], 'find_resources')
        self.assertEqual(actions[0]['params']['resource_type'], 'copper_ore')
        self.assertEqual(actions[3]['name'], 'find_correct_workshop')
        self.assertEqual(actions[5]['name'], 'transform_raw_materials')
    
    def test_add_gathering_actions_transformable_have_raw_material(self):
        """Test _add_gathering_actions for transformable when already have raw material."""
        actions = []
        chain = {
            'item_code': 'copper_bar',
            'type': 'transformable_resource',
            'raw_material': 'copper_ore',
            'workshop_type': 'smelting'
        }
        mock_kb = Mock()
        mock_map_state = Mock()
        
        # Mock _has_sufficient_resources
        with patch.object(self.action, '_has_sufficient_resources') as mock_has_sufficient:
            mock_has_sufficient.side_effect = [False, True]  # Don't have copper_bar but have copper_ore
            self.action._add_gathering_actions(chain, actions, mock_kb, mock_map_state)
        
        # Should only add transformation
        self.assertEqual(len(actions), 3)  # Only transformation actions
        self.assertEqual(actions[0]['name'], 'find_correct_workshop')
        self.assertEqual(actions[2]['name'], 'transform_raw_materials')
    
    def test_add_gathering_actions_craftable(self):
        """Test _add_gathering_actions for craftable item."""
        actions = []
        chain = {
            'item_code': 'copper_dagger',
            'type': 'craftable',
            'required_materials': [
                {
                    'chain': {
                        'item_code': 'copper_bar',
                        'type': 'base_resource'
                    }
                }
            ]
        }
        mock_kb = Mock()
        mock_map_state = Mock()
        
        # Mock _has_sufficient_resources to return False
        with patch.object(self.action, '_has_sufficient_resources', return_value=False):
            self.action._add_gathering_actions(chain, actions, mock_kb, mock_map_state)
        
        # Should recursively add gathering for copper_bar
        self.assertEqual(len(actions), 3)
        self.assertEqual(actions[0]['name'], 'find_resources')
        self.assertEqual(actions[0]['params']['resource_type'], 'copper_bar')
    
    def test_add_gathering_actions_circular_reference(self):
        """Test _add_gathering_actions with circular reference."""
        actions = []
        chain = {
            'item_code': 'item_a',
            'type': 'craftable',
            'required_materials': [
                {
                    'chain': {
                        'item_code': 'item_a',  # Circular reference
                        'type': 'craftable'
                    }
                }
            ]
        }
        mock_kb = Mock()
        mock_map_state = Mock()
        
        # Should handle circular reference gracefully
        self.action._add_gathering_actions(chain, actions, mock_kb, mock_map_state)
        
        # Should not add actions for circular reference
        self.assertEqual(len(actions), 0)
    
    def test_add_crafting_actions(self):
        """Test _add_crafting_actions."""
        actions = []
        chain = {
            'item_code': 'copper_dagger',
            'type': 'craftable',
            'workshop_type': 'weaponcrafting',
            'required_materials': []
        }
        mock_kb = Mock()
        
        # Mock _get_equipment_slot to return a weapon slot
        with patch.object(self.action, '_get_equipment_slot', return_value='weapon'):
            self.action._add_crafting_actions(chain, actions, mock_kb)
        
        # Should add crafting actions
        self.assertEqual(len(actions), 5)  # find_workshop, check_location, transform, craft, equip
        self.assertEqual(actions[0]['name'], 'find_correct_workshop')
        self.assertEqual(actions[1]['name'], 'check_location')
        self.assertEqual(actions[2]['name'], 'transform_raw_materials')
        self.assertEqual(actions[3]['name'], 'craft_item')
        self.assertEqual(actions[4]['name'], 'equip_item')
    
    def test_add_crafting_actions_with_dependencies(self):
        """Test _add_crafting_actions with craftable dependencies."""
        actions = []
        chain = {
            'item_code': 'iron_sword',
            'type': 'craftable',
            'workshop_type': 'weaponcrafting',
            'required_materials': [
                {
                    'chain': {
                        'item_code': 'iron_bar',
                        'type': 'craftable',
                        'workshop_type': 'smelting',
                        'required_materials': []
                    }
                }
            ]
        }
        mock_kb = Mock()
        
        # Mock _get_equipment_slot to return None (no equip)
        with patch.object(self.action, '_get_equipment_slot', return_value=None):
            self.action._add_crafting_actions(chain, actions, mock_kb)
        
        # Should add crafting for dependency first, then main item
        # iron_bar: 4 actions (no equip), iron_sword: 4 actions (no equip)
        self.assertEqual(len(actions), 8)
    
    def test_get_equipment_slot_consumable_type(self):
        """Test _get_equipment_slot with consumable type."""
        mock_kb = Mock()
        mock_kb.get_item_data.return_value = {'type': 'consumable'}
        
        result = self.action._get_equipment_slot('health_potion', 'alchemy', mock_kb)
        self.assertIsNone(result)
    
    def test_get_equipment_slot_resource_type(self):
        """Test _get_equipment_slot with resource type."""
        mock_kb = Mock()
        mock_kb.get_item_data.return_value = {'type': 'resource'}
        
        result = self.action._get_equipment_slot('copper_ore', 'workshop', mock_kb)
        self.assertIsNone(result)
    
    def test_get_equipped_materials_no_materials_needed(self):
        """Test _get_equipped_materials_for_item when craft has no items."""
        mock_kb = Mock()
        mock_kb.data = {
            'items': {
                'test_item': {
                    'craft_data': {
                        'items': []  # No materials needed
                    }
                }
            }
        }
        
        result = self.action._get_equipped_materials_for_item('test_item', mock_kb, self.mock_client)
        self.assertEqual(result, [])
    
    def test_execute_with_action_context(self):
        """Test execute with real ActionContext."""
        # Create a mock controller with dependencies
        mock_controller = Mock()
        mock_controller.knowledge_base = Mock()
        mock_controller.map_state = Mock()
        mock_controller.character_state = None
        
        context = ActionContext.from_controller(mock_controller)
        context.set(StateParameters.CHARACTER_NAME, self.character_name)
        context.set(StateParameters.MATERIALS_TARGET_ITEM, 'copper_dagger')
        
        mock_chain = {
            'item_code': 'copper_dagger',
            'type': 'craftable',
            'required_materials': []
        }
        
        # Mock the analysis methods
        with patch.object(self.action, '_analyze_complete_chain', return_value=mock_chain):
            with patch.object(self.action, '_build_action_sequence', return_value=[]):
                with patch.object(self.action, '_extract_raw_materials', return_value=[]):
                    result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
    
    def test_add_gathering_actions_transformable_already_have_refined(self):
        """Test _add_gathering_actions when already have refined material."""
        actions = []
        chain = {
            'item_code': 'copper_bar',
            'type': 'transformable_resource',
            'raw_material': 'copper_ore',
            'workshop_type': 'smelting'
        }
        mock_kb = Mock()
        mock_map_state = Mock()
        
        # Mock _has_sufficient_resources to return True for copper_bar
        with patch.object(self.action, '_has_sufficient_resources') as mock_has_sufficient:
            mock_has_sufficient.side_effect = [True]  # Have copper_bar
            self.action._add_gathering_actions(chain, actions, mock_kb, mock_map_state)
        
        self.assertEqual(len(actions), 0)  # No actions needed
    
    def test_get_character_inventory_with_controller(self):
        """Test _get_character_inventory with controller."""
        mock_controller = Mock()
        mock_context = Mock()
        mock_context.get_character_inventory.return_value = {'copper_ore': 10}
        
        self.action.kwargs = {'controller': mock_controller}
        
        with patch('src.controller.actions.analyze_crafting_chain.ActionContext.from_controller', return_value=mock_context):
            inventory = self.action._get_character_inventory(self.mock_client)
        
        self.assertEqual(inventory, {'copper_ore': 10})
    
    def test_get_character_inventory_with_character_state(self):
        """Test _get_character_inventory with character state."""
        mock_char_state = Mock()
        mock_char_state.data = {
            'inventory': [
                {'code': 'copper_ore', 'quantity': 5},
                {'code': 'iron_ore', 'quantity': 3}
            ],
            'weapon': 'iron_sword',
            'shield': 'wooden_shield',
            'name': 'TestChar',
            'skin': 'default',
            'account': 'test_account'
        }
        
        self.action.kwargs = {'character_state': mock_char_state}
        
        inventory = self.action._get_character_inventory(self.mock_client)
        
        # Should include inventory items and equipped items
        self.assertEqual(inventory['copper_ore'], 5)
        self.assertEqual(inventory['iron_ore'], 3)
        self.assertEqual(inventory['iron_sword'], 1)
        self.assertEqual(inventory['wooden_shield'], 1)
        # Should not include name, skin, account
        self.assertNotIn('TestChar', inventory)
        self.assertNotIn('default', inventory)
        self.assertNotIn('test_account', inventory)
    
    def test_get_character_inventory_exception(self):
        """Test _get_character_inventory with exception."""
        mock_controller = Mock()
        self.action.kwargs = {'controller': mock_controller}
        
        with patch('src.controller.actions.analyze_crafting_chain.ActionContext.from_controller', side_effect=Exception("Error")):
            inventory = self.action._get_character_inventory(self.mock_client)
        
        self.assertEqual(inventory, {})
    
    def test_get_character_inventory_no_data(self):
        """Test _get_character_inventory with no data."""
        self.action.kwargs = {}
        inventory = self.action._get_character_inventory(self.mock_client)
        self.assertEqual(inventory, {})
    
    def test_add_crafting_actions_non_craftable(self):
        """Test _add_crafting_actions with non-craftable item."""
        actions = []
        chain = {
            'item_code': 'copper_ore',
            'type': 'base_resource'
        }
        mock_kb = Mock()
        
        self.action._add_crafting_actions(chain, actions, mock_kb)
        
        # Should not add any actions for non-craftable
        self.assertEqual(len(actions), 0)
    
    def test_get_equipped_materials_inventory_with_dict_items(self):
        """Test _get_equipped_materials_for_item with dict inventory items."""
        mock_kb = Mock()
        mock_kb.data = {
            'items': {
                'copper_dagger': {
                    'craft_data': {
                        'items': [
                            {'code': 'copper_bar'},
                            {'code': 'leather'}
                        ]
                    }
                }
            }
        }
        
        # Mock context with character state having dict inventory items
        mock_context = Mock()
        mock_context.character_state = Mock()
        mock_context.character_state.data = {
            'weapon': 'iron_sword',
            'inventory': [
                Mock(code='copper_bar', quantity=5),  # Mock objects instead of dicts
                Mock(code='leather', quantity=3)
            ]
        }
        
        self.action.current_context = mock_context
        
        result = self.action._get_equipped_materials_for_item('copper_dagger', mock_kb, self.mock_client)
        
        # Should not find any equipped materials since they're in inventory
        self.assertEqual(result, [])
    
    def test_get_item_from_knowledge_edge_cases(self):
        """Test _get_item_from_knowledge edge cases."""
        # Test with items not being a dict
        mock_kb = Mock()
        mock_kb.data = {'items': []}
        
        result = self.action._get_item_from_knowledge('test_item', mock_kb)
        self.assertIsNone(result)
    
    def test_get_gathering_info_with_knowledge_base(self):
        """Test _get_gathering_info with knowledge base data."""
        mock_kb = Mock()
        mock_kb.data = {
            'resources': {
                'copper_ore': {
                    'skill_required': 'mining',
                    'level_required': 5
                }
            }
        }
        
        result = self.action._get_gathering_info('copper_ore', mock_kb)
        
        self.assertEqual(result['resource_code'], 'copper_ore')
        self.assertEqual(result['skill_required'], 'mining')
        self.assertEqual(result['level_required'], 5)


if __name__ == '__main__':
    unittest.main()