"""
Tests for the unified ActionContext system - Zero Backward Compatibility

Tests the new StateParameters-only ActionContext implementation.
No legacy attribute testing - only StateParameters validation.
"""

import unittest
from unittest.mock import Mock
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters


class TestActionContext(unittest.TestCase):
    """Test cases for new StateParameters-only ActionContext."""
    
    def setUp(self):
        """Set up test fixtures with singleton reset."""
        # Reset singleton state before each test
        import src.lib.unified_state_context
        src.lib.unified_state_context._unified_instance = None
        
        self.mock_controller = Mock()
        self.mock_controller.character_state = Mock()
        self.mock_controller.character_state.data = {
            'x': 10,
            'y': 20,
            'level': 5,
            'hp': 100,
            'max_hp': 125,
            'weapon': 'iron_sword',
            'armor': 'leather_armor',
            'helmet': 'iron_helmet',
            'boots': '',
            'shield': 'wooden_shield'
        }
    
    def test_context_creation_uses_singleton(self):
        """Test ActionContext uses unified singleton context."""
        context1 = ActionContext()
        context2 = ActionContext()
        
        # Both contexts should use the same singleton
        self.assertIs(context1._state, context2._state)
        
        # Setting value in one should appear in other
        context1.set(StateParameters.EQUIPMENT_SELECTED_ITEM, 'test_item')
        self.assertEqual(context2.get(StateParameters.EQUIPMENT_SELECTED_ITEM), 'test_item')
    
    def test_get_and_set_with_state_parameters(self):
        """Test get/set operations using StateParameters registry."""
        context = ActionContext()
        
        # Test setting and getting valid parameters
        context.set(StateParameters.EQUIPMENT_SELECTED_ITEM, 'copper_sword')
        context.set(StateParameters.CHARACTER_LEVEL, 42)
        context.set(StateParameters.MATERIALS_STATUS, 'sufficient')
        
        self.assertEqual(context.get(StateParameters.EQUIPMENT_SELECTED_ITEM), 'copper_sword')
        self.assertEqual(context.get(StateParameters.CHARACTER_LEVEL), 42)
        self.assertEqual(context.get(StateParameters.MATERIALS_STATUS), 'sufficient')
    
    def test_parameter_validation_enforcement(self):
        """Test that invalid parameters raise ValueError."""
        context = ActionContext()
        
        # Invalid parameters should raise ValueError
        with self.assertRaises(ValueError, msg="Parameter 'invalid.parameter' not registered"):
            context.get('invalid.parameter')
        
        with self.assertRaises(ValueError, msg="Parameter 'another.invalid' not registered"):
            context.set('another.invalid', 'value')
    
    def test_automatic_flag_setting(self):
        """Test automatic related flag setting."""
        context = ActionContext()
        
        # Setting selected item should automatically set has_selected_item flag
        context.set(StateParameters.EQUIPMENT_SELECTED_ITEM, 'test_weapon')
        self.assertTrue(context.get(StateParameters.EQUIPMENT_HAS_SELECTED_ITEM))
        
        # Setting empty/None selected item should set flag to False
        context.set(StateParameters.EQUIPMENT_SELECTED_ITEM, None)
        self.assertFalse(context.get(StateParameters.EQUIPMENT_HAS_SELECTED_ITEM))
        
        context.set(StateParameters.EQUIPMENT_SELECTED_ITEM, '')
        self.assertFalse(context.get(StateParameters.EQUIPMENT_HAS_SELECTED_ITEM))
    
    def test_from_controller_character_data_mapping(self):
        """Test from_controller maps character data to StateParameters."""
        context = ActionContext.from_controller(self.mock_controller)
        
        # Verify character data mapped to StateParameters
        self.assertEqual(context.get(StateParameters.CHARACTER_X), 10)
        self.assertEqual(context.get(StateParameters.CHARACTER_Y), 20)
        self.assertEqual(context.get(StateParameters.CHARACTER_LEVEL), 5)
        self.assertEqual(context.get(StateParameters.CHARACTER_HP), 100)
        self.assertEqual(context.get(StateParameters.CHARACTER_MAX_HP), 125)
        self.assertTrue(context.get(StateParameters.CHARACTER_ALIVE))  # hp > 0
        
        # Verify equipment mapped to StateParameters
        self.assertEqual(context.get(StateParameters.EQUIPMENT_WEAPON), 'iron_sword')
        self.assertEqual(context.get(StateParameters.EQUIPMENT_ARMOR), 'leather_armor')
        self.assertEqual(context.get(StateParameters.EQUIPMENT_HELMET), 'iron_helmet')
        self.assertEqual(context.get(StateParameters.EQUIPMENT_BOOTS), '')
        self.assertEqual(context.get(StateParameters.EQUIPMENT_SHIELD), 'wooden_shield')
    
    def test_from_controller_no_character_state(self):
        """Test from_controller handles missing character state gracefully."""
        mock_controller = Mock()
        mock_controller.character_state = None
        
        context = ActionContext.from_controller(mock_controller)
        
        # Should still work with defaults
        self.assertEqual(context.get(StateParameters.CHARACTER_LEVEL), 1)  # Default
        self.assertTrue(context.get(StateParameters.CHARACTER_ALIVE))  # Default
    
    def test_update_multiple_parameters(self):
        """Test updating multiple parameters at once."""
        context = ActionContext()
        
        updates = {
            StateParameters.EQUIPMENT_SELECTED_ITEM: 'iron_sword',
            StateParameters.CHARACTER_LEVEL: 15,
            StateParameters.MATERIALS_STATUS: 'ready'
        }
        
        context.update(updates)
        
        # Verify all updates applied
        self.assertEqual(context.get(StateParameters.EQUIPMENT_SELECTED_ITEM), 'iron_sword')
        self.assertEqual(context.get(StateParameters.CHARACTER_LEVEL), 15)
        self.assertEqual(context.get(StateParameters.MATERIALS_STATUS), 'ready')
        
        # Verify automatic flag setting worked
        self.assertTrue(context.get(StateParameters.EQUIPMENT_HAS_SELECTED_ITEM))
    
    def test_set_result_uses_state_parameters(self):
        """Test set_result delegates to StateParameters set method."""
        context = ActionContext()
        
        context.set_result(StateParameters.EQUIPMENT_SELECTED_ITEM, 'result_item')
        context.set_result(StateParameters.COMBAT_STATUS, 'active')
        
        self.assertEqual(context.get(StateParameters.EQUIPMENT_SELECTED_ITEM), 'result_item')
        self.assertEqual(context.get(StateParameters.COMBAT_STATUS), 'active')
        
        # Should trigger automatic flag setting
        self.assertTrue(context.get(StateParameters.EQUIPMENT_HAS_SELECTED_ITEM))
    
    def test_get_equipped_item_in_slot(self):
        """Test equipment slot retrieval using StateParameters."""
        context = ActionContext()
        
        # Set equipment in various slots
        context.set(StateParameters.EQUIPMENT_WEAPON, 'test_sword')
        context.set(StateParameters.EQUIPMENT_ARMOR, 'test_armor')
        context.set(StateParameters.EQUIPMENT_HELMET, 'test_helmet')
        context.set(StateParameters.EQUIPMENT_BOOTS, '')  # Empty slot
        
        # Test slot retrieval
        self.assertEqual(context.get_equipped_item_in_slot('weapon'), 'test_sword')
        self.assertEqual(context.get_equipped_item_in_slot('armor'), 'test_armor')
        self.assertEqual(context.get_equipped_item_in_slot('helmet'), 'test_helmet')
        self.assertIsNone(context.get_equipped_item_in_slot('boots'))  # Empty returns None
        self.assertIsNone(context.get_equipped_item_in_slot('invalid_slot'))  # Invalid slot
    
    def test_get_character_inventory_returns_empty(self):
        """Test get_character_inventory returns empty dict (legacy method)."""
        context = ActionContext()
        
        # This method is marked for elimination - should return empty dict
        inventory = context.get_character_inventory()
        self.assertEqual(inventory, {})
        self.assertIsInstance(inventory, dict)
    
    def test_default_values_from_unified_context(self):
        """Test that ActionContext gets default values from UnifiedStateContext."""
        context = ActionContext()
        
        # Test some key default values
        self.assertTrue(context.get(StateParameters.CHARACTER_ALIVE))
        self.assertEqual(context.get(StateParameters.CHARACTER_LEVEL), 1)
        self.assertFalse(context.get(StateParameters.EQUIPMENT_HAS_SELECTED_ITEM))
        self.assertFalse(context.get(StateParameters.CHARACTER_COOLDOWN_ACTIVE))
        self.assertEqual(context.get(StateParameters.MATERIALS_STATUS), "unknown")
    
    def test_parameter_validation_on_invalid_updates(self):
        """Test parameter validation during bulk updates."""
        context = ActionContext()
        
        # Valid updates should work
        valid_updates = {
            StateParameters.EQUIPMENT_SELECTED_ITEM: 'valid_item',
            StateParameters.CHARACTER_LEVEL: 10
        }
        context.update(valid_updates)
        
        # Invalid updates should raise ValueError
        invalid_updates = {
            StateParameters.EQUIPMENT_SELECTED_ITEM: 'valid_item',
            'invalid.parameter': 'invalid_value'
        }
        
        with self.assertRaises(ValueError, msg="Parameter 'invalid.parameter' not registered"):
            context.update(invalid_updates)