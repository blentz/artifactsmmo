"""Test module for CheckGatheringCompleteAction."""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.check_gathering_complete import CheckGatheringCompleteAction
from src.controller.actions.base import ActionResult
from src.lib.action_context import ActionContext
from test.fixtures import MockActionContext, create_mock_client


class TestCheckGatheringCompleteAction(unittest.TestCase):
    """Test cases for CheckGatheringCompleteAction class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = CheckGatheringCompleteAction()
        self.mock_client = create_mock_client()
        self.character_name = "TestCharacter"
        
    def test_init(self):
        """Test initialization."""
        action = CheckGatheringCompleteAction()
        self.assertIsInstance(action, CheckGatheringCompleteAction)
        
        # Check GOAP parameters
        self.assertEqual(action.conditions['materials']['status'], 'gathering')
        self.assertEqual(action.conditions['materials']['gathering_initiated'], True)
        self.assertEqual(action.reactions['materials']['status'], ['sufficient', 'insufficient'])
        self.assertEqual(action.reactions['materials']['availability_checked'], False)
        self.assertEqual(action.weight, 1.0)
    
    def test_execute_gathering_complete(self):
        """Test execution when gathering is complete."""
        context = MockActionContext(
            character_name=self.character_name,
            gathering_complete=True,
            materials_gathered={'iron_ore': 10},
            quantity_gathered=10,
            quantity_needed=10,
            target_material='iron_ore'
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Gathering complete: 10 iron_ore gathered")
        self.assertTrue(result.data['gathering_complete'])
        self.assertEqual(result.data['materials_gathered'], {'iron_ore': 10})
        
        # Check state changes
        self.assertEqual(result.state_changes['materials']['status'], 'sufficient')
        self.assertTrue(result.state_changes['materials']['gathered'])
        self.assertEqual(result.state_changes['materials']['last_gathered'], 'iron_ore')
        self.assertTrue(result.state_changes['materials']['gathering_complete'])
    
    def test_execute_gathering_incomplete(self):
        """Test execution when gathering is incomplete."""
        context = MockActionContext(
            character_name=self.character_name,
            gathering_complete=False,
            materials_gathered={'copper_ore': 5},
            quantity_gathered=5,
            quantity_needed=10,
            target_material='copper_ore'
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Gathering incomplete: 5/10 copper_ore")
        self.assertFalse(result.data['gathering_complete'])
        self.assertEqual(result.data['materials_gathered'], {'copper_ore': 5})
        
        # Check state changes
        self.assertEqual(result.state_changes['materials']['status'], 'insufficient')
        self.assertFalse(result.state_changes['materials']['gathered'])
        self.assertFalse(result.state_changes['materials']['availability_checked'])
        self.assertEqual(result.state_changes['materials']['last_gathered'], 'copper_ore')
        self.assertFalse(result.state_changes['materials']['gathering_complete'])
    
    def test_execute_with_default_values(self):
        """Test execution with default/missing values in context."""
        # Minimal context with most values missing
        context = MockActionContext(character_name=self.character_name)
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Gathering incomplete: 0/0 unknown")
        self.assertFalse(result.data['gathering_complete'])
        self.assertEqual(result.data['materials_gathered'], {})
        
        # Check state changes
        self.assertEqual(result.state_changes['materials']['status'], 'insufficient')
        self.assertFalse(result.state_changes['materials']['gathered'])
        self.assertFalse(result.state_changes['materials']['availability_checked'])
        self.assertEqual(result.state_changes['materials']['last_gathered'], 'unknown')
        self.assertFalse(result.state_changes['materials']['gathering_complete'])
    
    def test_execute_partial_context(self):
        """Test execution with partial context values."""
        context = MockActionContext(
            character_name=self.character_name,
            gathering_complete=True,
            target_material='gold_ore'
            # Missing quantity_gathered, quantity_needed, materials_gathered
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Gathering complete: 0 gold_ore gathered")
        self.assertTrue(result.data['gathering_complete'])
        self.assertEqual(result.data['materials_gathered'], {})
        
        # Check state changes
        self.assertEqual(result.state_changes['materials']['last_gathered'], 'gold_ore')
        self.assertTrue(result.state_changes['materials']['gathering_complete'])
    
    def test_execute_with_exception(self):
        """Test execution with exception handling."""
        context = MockActionContext(character_name=self.character_name)
        
        # Mock exception during execution
        with patch.object(context, 'get', side_effect=Exception("Context error")):
            result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Failed to check gathering status: Context error")
    
    def test_execute_zero_quantity_needed(self):
        """Test execution when quantity needed is zero."""
        context = MockActionContext(
            character_name=self.character_name,
            gathering_complete=False,
            quantity_gathered=5,
            quantity_needed=0,
            target_material='ash_wood'
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Gathering incomplete: 5/0 ash_wood")
    
    def test_execute_overcollected(self):
        """Test execution when more was gathered than needed."""
        context = MockActionContext(
            character_name=self.character_name,
            gathering_complete=True,
            materials_gathered={'diamond': 15},
            quantity_gathered=15,
            quantity_needed=10,
            target_material='diamond'
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Gathering complete: 15 diamond gathered")
        self.assertTrue(result.data['gathering_complete'])
        self.assertEqual(result.data['materials_gathered'], {'diamond': 15})
    
    def test_execute_multiple_materials_gathered(self):
        """Test execution when multiple materials were gathered."""
        context = MockActionContext(
            character_name=self.character_name,
            gathering_complete=True,
            materials_gathered={
                'iron_ore': 5,
                'copper_ore': 3,
                'gold_ore': 2
            },
            quantity_gathered=10,
            quantity_needed=10,
            target_material='mixed_materials'
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Gathering complete: 10 mixed_materials gathered")
        self.assertTrue(result.data['gathering_complete'])
        self.assertEqual(len(result.data['materials_gathered']), 3)
        self.assertEqual(result.data['materials_gathered']['iron_ore'], 5)
        self.assertEqual(result.data['materials_gathered']['copper_ore'], 3)
        self.assertEqual(result.data['materials_gathered']['gold_ore'], 2)
    
    def test_repr(self):
        """Test __repr__ method."""
        self.assertEqual(repr(self.action), "CheckGatheringCompleteAction()")
    
    def test_goap_conditions(self):
        """Test GOAP conditions are properly set."""
        action = CheckGatheringCompleteAction()
        
        # Verify conditions
        self.assertIn('materials', action.conditions)
        self.assertEqual(action.conditions['materials']['status'], 'gathering')
        self.assertEqual(action.conditions['materials']['gathering_initiated'], True)
        
        self.assertIn('character_status', action.conditions)
        self.assertEqual(action.conditions['character_status']['alive'], True)
    
    def test_goap_reactions(self):
        """Test GOAP reactions are properly set."""
        action = CheckGatheringCompleteAction()
        
        # Verify reactions
        self.assertIn('materials', action.reactions)
        self.assertEqual(action.reactions['materials']['status'], ['sufficient', 'insufficient'])
        self.assertEqual(action.reactions['materials']['availability_checked'], False)


if __name__ == '__main__':
    unittest.main()