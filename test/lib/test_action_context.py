"""
Tests for the unified ActionContext system.
"""

import unittest
from unittest.mock import Mock

from src.lib.action_context import ActionContext


class TestActionContext(unittest.TestCase):
    """Test cases for ActionContext class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_controller = Mock()
        self.mock_controller.client = Mock()
        self.mock_controller.character_state = Mock()
        self.mock_controller.world_state = Mock()
        self.mock_controller.map_state = Mock()
        self.mock_controller.knowledge_base = Mock()
        self.mock_controller.action_context = {'previous_result': 'test'}
        
        # Set up character state mock
        self.mock_controller.character_state.name = 'TestChar'
        self.mock_controller.character_state.data = {
            'x': 10,
            'y': 20,
            'level': 5,
            'hp': 100,
            'max_hp': 125,
            'weapon': 'iron_sword',
            'shield': 'wooden_shield',
            'inventory': [
                {'code': 'copper_ore', 'quantity': 5},
                {'code': 'ash_wood', 'quantity': 10}
            ]
        }
    
    def test_context_creation_empty(self):
        """Test creating an empty ActionContext."""
        context = ActionContext()
        self.assertIsNone(context.controller)
        self.assertIsNone(context.client)
        self.assertEqual(context.character_name, "")
        self.assertEqual(context.character_x, 0)
        self.assertEqual(context.character_y, 0)
        self.assertEqual(context.character_level, 1)
        self.assertEqual(context.character_hp, 0)
        self.assertEqual(context.character_max_hp, 0)
        self.assertEqual(context.equipment, {})
        self.assertEqual(context.action_data, {})
        self.assertEqual(context.action_results, {})
    
    def test_from_controller(self):
        """Test creating ActionContext from controller."""
        context = ActionContext.from_controller(self.mock_controller)
        
        # Core dependencies
        self.assertEqual(context.controller, self.mock_controller)
        self.assertEqual(context.client, self.mock_controller.client)
        self.assertEqual(context.character_state, self.mock_controller.character_state)
        self.assertEqual(context.world_state, self.mock_controller.world_state)
        self.assertEqual(context.map_state, self.mock_controller.map_state)
        self.assertEqual(context.knowledge_base, self.mock_controller.knowledge_base)
        
        # Character information
        self.assertEqual(context.character_name, 'TestChar')
        self.assertEqual(context.character_x, 10)
        self.assertEqual(context.character_y, 20)
        self.assertEqual(context.character_level, 5)
        self.assertEqual(context.character_hp, 100)
        self.assertEqual(context.character_max_hp, 125)
        
        # Equipment should be the entire character data dict
        self.assertEqual(context.equipment, self.mock_controller.character_state.data)
        
        # Action results from controller context
        self.assertEqual(context.action_results, {'previous_result': 'test'})
    
    def test_from_controller_with_action_data(self):
        """Test creating ActionContext with action data."""
        action_data = {
            'name': 'test_action',
            'params': {
                'slot': 'weapon',
                'item_code': 'copper_sword'
            }
        }
        
        context = ActionContext.from_controller(self.mock_controller, action_data)
        
        # Action data should be merged
        self.assertEqual(context.action_data['name'], 'test_action')
        self.assertEqual(context.action_data['slot'], 'weapon')
        self.assertEqual(context.action_data['item_code'], 'copper_sword')
    
    def test_get_parameter(self):
        """Test parameter retrieval with fallback."""
        context = ActionContext()
        context.action_data = {'action_param': 'value1'}
        context.action_results = {'result_param': 'value2'}
        context.character_level = 10
        
        # From action_data
        self.assertEqual(context.get_parameter('action_param'), 'value1')
        
        # From action_results
        self.assertEqual(context.get_parameter('result_param'), 'value2')
        
        # From context attributes
        self.assertEqual(context.get_parameter('character_level'), 10)
        
        # Default value
        self.assertEqual(context.get_parameter('missing_param', 'default'), 'default')
        self.assertIsNone(context.get_parameter('missing_param'))
    
    def test_set_parameter_and_result(self):
        """Test setting parameters and results."""
        context = ActionContext()
        
        context.set_parameter('test_param', 'test_value')
        self.assertEqual(context.action_data['test_param'], 'test_value')
        
        context.set_result('test_result', 'result_value')
        self.assertEqual(context.action_results['test_result'], 'result_value')
    
    def test_get_character_inventory(self):
        """Test getting character inventory."""
        context = ActionContext.from_controller(self.mock_controller)
        
        inventory = context.get_character_inventory()
        
        # Should include inventory items
        self.assertEqual(inventory['copper_ore'], 5)
        self.assertEqual(inventory['ash_wood'], 10)
        
        # Should include equipped items
        self.assertEqual(inventory['iron_sword'], 1)
        self.assertEqual(inventory['wooden_shield'], 1)
    
    def test_get_character_inventory_caching(self):
        """Test inventory caching behavior."""
        context = ActionContext.from_controller(self.mock_controller)
        
        # First call
        inventory1 = context.get_character_inventory()
        
        # Modify character state
        context.character_state.data['inventory'].append({'code': 'new_item', 'quantity': 1})
        
        # Second call with cache should return same result
        inventory2 = context.get_character_inventory(use_cache=True)
        self.assertEqual(inventory1, inventory2)
        self.assertNotIn('new_item', inventory2)
        
        # Clear cache and get fresh data
        context.clear_inventory_cache()
        inventory3 = context.get_character_inventory()
        self.assertEqual(inventory3['new_item'], 1)
    
    def test_get_equipped_item_in_slot(self):
        """Test getting equipped item in slot."""
        context = ActionContext.from_controller(self.mock_controller)
        
        # Since equipment is the whole character data dict
        self.assertEqual(context.get_equipped_item_in_slot('weapon'), 'iron_sword')
        self.assertEqual(context.get_equipped_item_in_slot('shield'), 'wooden_shield')
        self.assertIsNone(context.get_equipped_item_in_slot('helmet'))
    
    def test_has_item(self):
        """Test checking if character has item."""
        context = ActionContext.from_controller(self.mock_controller)
        
        # Inventory items
        self.assertTrue(context.has_item('copper_ore', 5))
        self.assertTrue(context.has_item('copper_ore', 3))
        self.assertFalse(context.has_item('copper_ore', 10))
        
        # Equipped items
        self.assertTrue(context.has_item('iron_sword', 1))
        self.assertFalse(context.has_item('iron_sword', 2))
        
        # Non-existent items
        self.assertFalse(context.has_item('gold_ore', 1))
    
    def test_get_item_data(self):
        """Test getting item data from knowledge base."""
        context = ActionContext.from_controller(self.mock_controller)
        
        # Mock knowledge base method
        mock_item_data = {'code': 'iron_sword', 'type': 'weapon', 'level': 5}
        context.knowledge_base.get_item_data = Mock(return_value=mock_item_data)
        
        result = context.get_item_data('iron_sword')
        self.assertEqual(result, mock_item_data)
        context.knowledge_base.get_item_data.assert_called_once_with('iron_sword', client=context.client)
    
    def test_get_item_data_no_knowledge_base(self):
        """Test getting item data when knowledge base is not available."""
        context = ActionContext()
        self.assertIsNone(context.get_item_data('iron_sword'))
    
    def test_to_dict(self):
        """Test converting context to dictionary."""
        context = ActionContext.from_controller(self.mock_controller)
        context.set_parameter('test_param', 'test_value')
        context.set_result('test_result', 'result_value')
        
        result = dict(context)
        
        # Core dependencies
        self.assertEqual(result['controller'], self.mock_controller)
        self.assertEqual(result['character_state'], self.mock_controller.character_state)
        self.assertEqual(result['world_state'], self.mock_controller.world_state)
        self.assertEqual(result['map_state'], self.mock_controller.map_state)
        self.assertEqual(result['knowledge_base'], self.mock_controller.knowledge_base)
        
        # Character information
        self.assertEqual(result['character_name'], 'TestChar')
        self.assertEqual(result['character_x'], 10)
        self.assertEqual(result['character_y'], 20)
        self.assertEqual(result['character_level'], 5)
        # Check if pre_combat_hp exists or use character_hp
        if 'pre_combat_hp' in result:
            self.assertEqual(result['pre_combat_hp'], 100)
        else:
            self.assertEqual(result['character_hp'], 100)
        
        # Action data and results
        self.assertEqual(result['test_param'], 'test_value')
        self.assertEqual(result['test_result'], 'result_value')
        self.assertEqual(result['previous_result'], 'test')
    
    def test_edge_cases(self):
        """Test edge cases and error handling."""
        # Empty controller
        empty_controller = Mock()
        empty_controller.action_context = {}  # Ensure it's a dict, not a Mock
        empty_controller.character_state = None  # No character state
        context = ActionContext.from_controller(empty_controller)
        self.assertEqual(context.character_name, "")
        self.assertEqual(context.equipment, {})
        
        # No character state
        controller_no_char = Mock()
        controller_no_char.character_state = None
        context = ActionContext.from_controller(controller_no_char)
        self.assertEqual(context.character_name, "")
        self.assertEqual(context.get_character_inventory(), {})
        
        # Character state without name
        controller_no_name = Mock()
        controller_no_name.character_state = Mock()
        del controller_no_name.character_state.name
        context = ActionContext.from_controller(controller_no_name)
        self.assertEqual(context.character_name, "")
    
    def test_dynamic_equipment_detection(self):
        """Test that equipment is dynamically detected without hardcoded lists."""
        # Create character with non-standard equipment slots
        self.mock_controller.character_state.data = {
            'x': 10,
            'y': 20,
            'level': 5,
            'hp': 100,
            'max_hp': 125,
            'custom_slot': 'custom_item',
            'another_slot': 'another_item',
            'inventory': []
        }
        
        context = ActionContext.from_controller(self.mock_controller)
        inventory = context.get_character_inventory()
        
        # Should detect custom equipment slots dynamically
        self.assertEqual(inventory['custom_item'], 1)
        self.assertEqual(inventory['another_item'], 1)
    
    def test_non_equipment_fields_excluded(self):
        """Test that known non-equipment fields are excluded from inventory."""
        self.mock_controller.character_state.data = {
            'name': 'TestChar',
            'skin': 'default',
            'account': 'test_account',
            'task': 'some_task',
            'task_type': 'some_type',
            'weapon': 'iron_sword',
            'inventory': []
        }
        
        context = ActionContext.from_controller(self.mock_controller)
        inventory = context.get_character_inventory()
        
        # Should not include non-equipment fields
        self.assertNotIn('TestChar', inventory)
        self.assertNotIn('default', inventory)
        self.assertNotIn('test_account', inventory)
        self.assertNotIn('some_task', inventory)
        self.assertNotIn('some_type', inventory)
        
        # Should include actual equipment
        self.assertEqual(inventory['iron_sword'], 1)


if __name__ == '__main__':
    unittest.main()