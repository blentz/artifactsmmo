"""
Test Execute Crafting Plan Action

Streamlined tests focusing on the public interface and integration behavior.
"""

import unittest
from unittest.mock import Mock

from src.controller.actions.execute_crafting_plan import ExecuteCraftingPlanAction
from src.controller.actions.base import ActionResult
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from test.test_base import UnifiedContextTestBase


class TestExecuteCraftingPlanAction(UnifiedContextTestBase):
    """Test the ExecuteCraftingPlanAction class public interface."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.action = ExecuteCraftingPlanAction()
        self.client = Mock()
        self.context.set(StateParameters.CHARACTER_NAME, "test_character")
        self.context.set(StateParameters.TARGET_ITEM, "iron_sword")
        
        # Mock knowledge base
        self.mock_kb = Mock()
        self.context.knowledge_base = self.mock_kb
        
    def test_init(self):
        """Test action initialization."""
        action = ExecuteCraftingPlanAction()
        self.assertIsNotNone(action)
        
    def test_repr(self):
        """Test string representation."""
        result = repr(self.action)
        self.assertIn("ExecuteCraftingPlanAction", result)
        
    def test_goap_parameters(self):
        """Test GOAP parameters are properly defined."""
        # Test conditions exist
        self.assertIn('character_status', self.action.conditions)
        self.assertIn('materials_sufficient', self.action.conditions)
        
        # Test reactions exist  
        self.assertIn('has_equipment', self.action.reactions)
        self.assertIn('inventory_updated', self.action.reactions)
        
        # Test weight is defined
        self.assertIsInstance(self.action.weight, (int, float))
        self.assertGreater(self.action.weight, 0)

    def test_execute_no_knowledge_base(self):
        """Test execute with no knowledge base."""
        self.context.knowledge_base = None
        
        result = self.action.execute(self.client, self.context)
        
        self.assertIsInstance(result, ActionResult)
        self.assertFalse(result.success)
        self.assertIn("No knowledge base", result.error)

    def test_execute_no_target_item(self):
        """Test execute with no target item."""
        self.context.set(StateParameters.TARGET_ITEM, None)
        
        result = self.action.execute(self.client, self.context)
        
        self.assertIsInstance(result, ActionResult)
        self.assertFalse(result.success)
        self.assertIn("No target item", result.error)

    def test_execute_item_not_found(self):
        """Test execute with item not found in knowledge base."""
        self.mock_kb.get_item_data.return_value = None
        
        result = self.action.execute(self.client, self.context)
        
        self.assertIsInstance(result, ActionResult)
        self.assertFalse(result.success)

    def test_execute_item_not_craftable(self):
        """Test execute with item that cannot be crafted."""
        self.mock_kb.get_item_data.return_value = {
            'name': 'Iron Sword',
            'craft_data': None  # Not craftable
        }
        
        result = self.action.execute(self.client, self.context)
        
        self.assertIsInstance(result, ActionResult)
        self.assertFalse(result.success)

    def test_execute_with_exception(self):
        """Test execute handles exceptions gracefully."""
        self.mock_kb.get_item_data.side_effect = Exception("Test error")
        
        result = self.action.execute(self.client, self.context)
        
        self.assertIsInstance(result, ActionResult)
        self.assertFalse(result.success)
        self.assertIn("Crafting execution failed", result.error)

    def test_determine_target_item_with_target_item(self):
        """Test _determine_target_item with TARGET_ITEM."""
        self.context.set(StateParameters.TARGET_ITEM, "iron_sword")
        
        result = self.action._determine_target_item(self.context)
        
        self.assertEqual(result, "iron_sword")

    def test_determine_target_item_none(self):
        """Test _determine_target_item with no item specified."""
        self.context.set(StateParameters.TARGET_ITEM, None)
        
        result = self.action._determine_target_item(self.context)
        
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()