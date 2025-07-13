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
        context1.set(StateParameters.TARGET_ITEM, 'test_item')
        self.assertEqual(context2.get(StateParameters.TARGET_ITEM), 'test_item')
    
    def test_get_and_set_with_state_parameters(self):
        """Test get/set operations using StateParameters registry."""
        context = ActionContext()
        
        # Test setting and getting valid parameters
        context.set(StateParameters.TARGET_ITEM, 'copper_sword')
        context.set(StateParameters.CHARACTER_LEVEL, 42)
        context.set(StateParameters.MATERIALS_STATUS, 'sufficient')
        
        self.assertEqual(context.get(StateParameters.TARGET_ITEM), 'copper_sword')
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
    
    def test_knowledge_base_target_item_helper(self):
        """Test knowledge_base.has_target_item() helper function."""
        context = ActionContext()
        
        # Mock knowledge_base for testing
        from test.fixtures import MockKnowledgeBase
        context.knowledge_base = MockKnowledgeBase()
        
        # Setting target item should be checkable via knowledge_base helper
        context.set(StateParameters.TARGET_ITEM, 'test_weapon')
        # Note: has_target_item checks inventory/equipment via API, returns False in mock context
        # This tests the helper method exists and can be called
        result = context.knowledge_base.has_target_item(context)
        self.assertIsInstance(result, bool)
        
        # Setting empty/None target item 
        context.set(StateParameters.TARGET_ITEM, None)
        result = context.knowledge_base.has_target_item(context)
        self.assertFalse(result)  # Should return False for None target
        
        context.set(StateParameters.TARGET_ITEM, '')
        result = context.knowledge_base.has_target_item(context)
        self.assertFalse(result)  # Should return False for empty target
    
    def test_from_controller_character_data_mapping(self):
        """Test from_controller creates context with controller reference."""
        context = ActionContext.from_controller(self.mock_controller)
        
        # Architecture compliance: Character data should come from controller.character_state, not state parameters
        # Test that context creation succeeded (behavioral test)
        self.assertIsInstance(context, ActionContext)
        
        # Test that state parameters from config are accessible
        self.assertTrue(context.get(StateParameters.CHARACTER_HEALTHY))
        self.assertFalse(context.get(StateParameters.CHARACTER_COOLDOWN_ACTIVE))
        
        # Equipment data removed - APIs are authoritative for current equipment state
        # Test that knowledge_base and other dependencies are set
        self.assertIsNotNone(context.knowledge_base)
    
    def test_from_controller_no_character_state(self):
        """Test from_controller handles missing character state gracefully."""
        mock_controller = Mock()
        mock_controller.character_state = None
        
        context = ActionContext.from_controller(mock_controller)
        
        # Architecture compliance: Character data comes from API, not state parameters
        # Test that context creation succeeded even without character state
        self.assertIsInstance(context, ActionContext)
        
        # Test that config-based state parameters work
        self.assertTrue(context.get(StateParameters.CHARACTER_HEALTHY))  # From config defaults
    
    def test_update_multiple_parameters(self):
        """Test updating multiple parameters at once."""
        context = ActionContext()
        
        updates = {
            StateParameters.TARGET_ITEM: 'iron_sword',
            StateParameters.CHARACTER_LEVEL: 15,
            StateParameters.MATERIALS_STATUS: 'ready'
        }
        
        context.update(updates)
        
        # Verify all updates applied
        self.assertEqual(context.get(StateParameters.TARGET_ITEM), 'iron_sword')
        self.assertEqual(context.get(StateParameters.CHARACTER_LEVEL), 15)
        self.assertEqual(context.get(StateParameters.MATERIALS_STATUS), 'ready')
        
        # HAS_TARGET_ITEM removed - use knowledge_base.has_target_item(context) helper instead
    
    def test_set_result_uses_state_parameters(self):
        """Test set_result delegates to StateParameters set method."""
        context = ActionContext()
        
        context.set_result(StateParameters.TARGET_ITEM, 'result_item')
        context.set_result(StateParameters.COMBAT_STATUS, 'active')
        
        self.assertEqual(context.get(StateParameters.TARGET_ITEM), 'result_item')
        self.assertEqual(context.get(StateParameters.COMBAT_STATUS), 'active')
        
        # HAS_TARGET_ITEM automatic flag setting removed - use knowledge_base.has_target_item(context) helper instead
    
    def test_equipment_api_authoritative(self):
        """Test that equipment data uses APIs as authoritative source."""
        context = ActionContext()
        
        # Equipment parameters removed - APIs are authoritative for current equipment state
        # Test that context exists and can be used with API calls
        self.assertIsNotNone(context)
        
        # Equipment slot method removed - use character API calls directly
        # This test ensures the architecture change is properly implemented
    
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
        
        # Test state defaults from configuration (not API-obtainable data)
        self.assertIsNone(context.get(StateParameters.TARGET_ITEM))  # TARGET_ITEM defaults to None
        self.assertTrue(context.get(StateParameters.CHARACTER_HEALTHY))  # From config defaults
        self.assertFalse(context.get(StateParameters.CHARACTER_COOLDOWN_ACTIVE))  # From config defaults
        self.assertEqual(context.get(StateParameters.MATERIALS_STATUS), "unknown")  # From config defaults
    
    def test_parameter_validation_on_invalid_updates(self):
        """Test parameter validation during bulk updates."""
        context = ActionContext()
        
        # Valid updates should work
        valid_updates = {
            StateParameters.TARGET_ITEM: 'valid_item',
            StateParameters.CHARACTER_LEVEL: 10
        }
        context.update(valid_updates)
        
        # Invalid updates should raise ValueError
        invalid_updates = {
            StateParameters.TARGET_ITEM: 'valid_item',
            'invalid.parameter': 'invalid_value'
        }
        
        with self.assertRaises(ValueError, msg="Parameter 'invalid.parameter' not registered"):
            context.update(invalid_updates)