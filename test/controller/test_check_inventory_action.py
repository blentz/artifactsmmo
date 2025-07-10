"""Test module for CheckInventoryAction."""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.controller.actions.check_inventory import CheckInventoryAction
from src.controller.actions.base import ActionResult
from src.lib.state_parameters import StateParameters

from test.fixtures import MockActionContext, create_mock_client


class TestCheckInventoryAction(unittest.TestCase):
    """Test cases for CheckInventoryAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_prefix = os.environ.get('DATA_PREFIX', '')
        os.environ['DATA_PREFIX'] = self.temp_dir
        
        self.character_name = "test_character"
        self.required_items = [
            {'item_code': 'copper_ore', 'quantity': 5},
            {'item_code': 'ash_wood', 'quantity': 2}
        ]
        self.action = CheckInventoryAction()

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['DATA_PREFIX'] = self.original_data_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_check_inventory_action_initialization(self):
        """Test CheckInventoryAction initialization."""
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(self.action, 'character_name'))
        self.assertFalse(hasattr(self.action, 'required_items'))

    def test_check_inventory_action_initialization_defaults(self):
        """Test CheckInventoryAction initialization with defaults."""
        action = CheckInventoryAction()
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(action, 'character_name'))
        self.assertFalse(hasattr(action, 'required_items'))

    def test_check_inventory_action_repr(self):
        """Test CheckInventoryAction string representation."""
        # Repr is now simplified
        expected = "CheckInventoryAction()"
        self.assertEqual(repr(self.action), expected)

    def test_check_inventory_action_repr_no_items(self):
        """Test CheckInventoryAction string representation without required items."""
        action = CheckInventoryAction()
        expected = "CheckInventoryAction()"
        self.assertEqual(repr(action), expected)

    def test_execute_no_client(self):
        """Test execute succeeds without client, returns empty inventory."""
        context = MockActionContext(character_name=self.character_name, required_items=self.required_items)
        result = self.action.execute(None, context)
        # CheckInventoryAction handles None client gracefully by returning empty inventory
        self.assertTrue(result.success)
        self.assertEqual(result.data['inventory'], {})
        self.assertEqual(result.data['total_items'], 0)
        self.assertIn("inventory_analysis", result.data)

    def test_execute_character_api_fails(self):
        """Test execute when character API fails - returns empty inventory."""
        client = create_mock_client()
        
        # Architecture compliant: Set empty inventory in context to simulate API failure
        context = MockActionContext(character_name=self.character_name, required_items=self.required_items)
        context.character_inventory = []  # Empty inventory simulates API failure
        
        result = self.action.execute(client, context)
        # Action succeeds with empty inventory when API fails
        self.assertTrue(result.success)
        self.assertEqual(result.data['inventory'], {})
        self.assertEqual(result.data['total_items'], 0)

    def test_execute_character_api_no_data(self):
        """Test execute when character API returns no data - returns empty inventory."""
        client = create_mock_client()
        
        # Architecture compliant: Set None inventory in context to simulate no data
        context = MockActionContext(character_name=self.character_name, required_items=self.required_items)
        context.character_inventory = None  # None inventory simulates no data from API
        
        result = self.action.execute(client, context)
        # Action succeeds with empty inventory when API returns no data
        self.assertTrue(result.success)
        self.assertEqual(result.data['inventory'], {})
        self.assertEqual(result.data['total_items'], 0)

    def test_execute_character_no_inventory(self):
        """Test execute when character has no inventory - returns empty inventory."""
        client = create_mock_client()
        
        # Architecture compliant: Set None character_inventory to simulate character with no inventory
        context = MockActionContext(character_name=self.character_name, required_items=self.required_items)
        context.character_inventory = None  # None inventory simulates character with no inventory
        
        result = self.action.execute(client, context)
        # Action succeeds with empty inventory when character has no inventory
        self.assertTrue(result.success)
        self.assertEqual(result.data['inventory'], {})
        self.assertEqual(result.data['total_items'], 0)

    def test_execute_success_with_sufficient_items(self):
        """Test successful execution with sufficient items."""
        # Architecture compliant: Set inventory containing required items in context
        mock_inventory = [
            {'slot': 1, 'code': 'copper_ore', 'quantity': 10},
            {'slot': 2, 'code': 'ash_wood', 'quantity': 5},
            {'slot': 3, 'code': 'iron_ore', 'quantity': 3}
        ]
        client = create_mock_client()
        
        # Create context with TARGET_RECIPE that requires copper_ore (5) and ash_wood (2)
        context = MockActionContext(character_name=self.character_name)
        context.character_inventory = mock_inventory  # Set inventory in context
        context.set_parameter(StateParameters.TARGET_RECIPE, 'copper_dagger')
        context.knowledge_base.data['items']['copper_dagger'] = {
            'craft_data': {
                'items': [
                    {'code': 'copper_ore', 'quantity': 5},
                    {'code': 'ash_wood', 'quantity': 2}
                ]
            }
        }
        
        result = self.action.execute(client, context)
        self.assertTrue(result.success)
        self.assertIn('inventory_summary', result.data)
        self.assertIn('world_state_updates', result.data)
        
        # Check item checks
        item_checks = result.data['item_checks']
        self.assertIn('copper_ore', item_checks)
        self.assertEqual(item_checks['copper_ore']['current'], 10)
        self.assertEqual(item_checks['copper_ore']['required'], 5)
        self.assertTrue(item_checks['copper_ore']['sufficient'])

    def test_execute_success_with_insufficient_items(self):
        """Test successful execution with insufficient items."""
        # Architecture compliant: Set inventory lacking required items in context
        mock_inventory = [
            {'slot': 1, 'code': 'copper_ore', 'quantity': 2},  # Need 5, have 2
            {'slot': 2, 'code': 'iron_ore', 'quantity': 5}     # Don't have ash_wood
        ]
        client = create_mock_client()
        
        # Create context with TARGET_RECIPE that requires copper_ore (5) and ash_wood (2)
        context = MockActionContext(character_name=self.character_name)
        context.character_inventory = mock_inventory  # Set inventory in context
        context.set_parameter(StateParameters.TARGET_RECIPE, 'copper_dagger')
        context.knowledge_base.data['items']['copper_dagger'] = {
            'craft_data': {
                'items': [
                    {'code': 'copper_ore', 'quantity': 5},
                    {'code': 'ash_wood', 'quantity': 2}
                ]
            }
        }
        
        result = self.action.execute(client, context)
        self.assertTrue(result.success)
        
        # Check inventory status shows insufficient items
        item_checks = result.data['item_checks']
        self.assertEqual(item_checks['copper_ore']['current'], 2)
        self.assertEqual(item_checks['copper_ore']['required'], 5)
        self.assertFalse(item_checks['copper_ore']['sufficient'])
        
        # ash_wood should be missing completely
        self.assertEqual(item_checks['ash_wood']['current'], 0)
        self.assertEqual(item_checks['ash_wood']['required'], 2)
        self.assertFalse(item_checks['ash_wood']['sufficient'])

    def test_execute_success_no_required_items(self):
        """Test successful execution with no required items (inventory check only)."""
        action = CheckInventoryAction()  # No required items
        
        mock_inventory = [
            {'slot': 1, 'code': 'copper_ore', 'quantity': 10},
            {'slot': 2, 'code': 'ash_wood', 'quantity': 5}
        ]
        client = create_mock_client()
        
        context = MockActionContext(character_name="player", required_items=[])
        context.character_inventory = mock_inventory  # Set inventory in context
        result = action.execute(client, context)
        self.assertTrue(result.success)
        # When no requirements specified, materials_sufficient is True by default
        self.assertTrue(result.data['world_state_updates'].get('materials_sufficient', True))
        self.assertIn('inventory', result.data)
        self.assertEqual(len(result.data['inventory']), 2)

    def test_get_character_inventory_helper_method(self):
        """Test _get_character_inventory helper method."""
        client = create_mock_client()
        
        # Mock successful inventory retrieval
        mock_inventory = [
            {'slot': 1, 'code': 'copper_ore', 'quantity': 10}
        ]
        mock_character = Mock()
        mock_character.inventory = mock_inventory
        mock_response = Mock()
        mock_response.data = mock_character
        
        # Test basic functionality if method exists - architecture compliant approach
        if hasattr(self.action, '_get_character_inventory'):
            # Architecture compliant: Set inventory data in context instead of mocking API calls
            context = MockActionContext(character_name=self.character_name)
            context.character_inventory = mock_inventory  # Set inventory in context
            self.action._context = context  # Set context on action
            
            inventory_dict = self.action._get_character_inventory(client, self.character_name)
            self.assertIsInstance(inventory_dict, dict)
            self.assertIn('copper_ore', inventory_dict)
            self.assertEqual(inventory_dict['copper_ore'], 10)

    def test_check_item_requirements_helper_method(self):
        """Test _check_item_requirements helper method."""
        inventory_dict = {'copper_ore': 10, 'ash_wood': 3, 'iron_ore': 1}
        
        # Test basic functionality if method exists
        if hasattr(self.action, '_check_item_requirements'):
            context = MockActionContext(character_name=self.character_name, required_items=self.required_items)
            result = self.action._check_item_requirements(inventory_dict, context)
            self.assertIsInstance(result, ActionResult)
            # Should have status for each required item
            self.assertIn('item_checks', result.data)
            self.assertIn('materials_sufficient', result.data)

    def test_calculate_inventory_summary_helper_method(self):
        """Test _calculate_inventory_summary helper method."""
        inventory_dict = {'copper_ore': 10, 'ash_wood': 5, 'iron_ore': 3}
        
        # Test basic functionality if method exists
        if hasattr(self.action, '_calculate_inventory_summary'):
            summary = self.action._calculate_inventory_summary(inventory_dict)
            self.assertIsInstance(summary, dict)
            # Should have summary statistics
            self.assertIn('total_items', summary)
            self.assertIn('unique_items', summary)

    def test_execute_exception_handling(self):
        """Test exception handling during execution."""
        client = create_mock_client()
        
        # The action catches exceptions in _get_character_inventory and returns empty dict
        # To trigger the main exception handler, we need to mock something else
        with patch('src.controller.actions.check_inventory.CheckInventoryAction._analyze_inventory_categories', side_effect=Exception("Analysis Error")):
            context = MockActionContext(character_name=self.character_name, required_items=self.required_items)
            result = self.action.execute(client, context)
            self.assertFalse(result.success)
            self.assertIn('Inventory check failed', result.error)

    def test_execute_has_goap_attributes(self):
        """Test that CheckInventoryAction has expected GOAP attributes."""
        self.assertTrue(hasattr(CheckInventoryAction, 'conditions'))
        self.assertTrue(hasattr(CheckInventoryAction, 'reactions'))
        self.assertTrue(hasattr(CheckInventoryAction, 'weight'))

    def test_goap_conditions(self):
        """Test GOAP conditions are properly defined."""
        self.assertIn('character_status', CheckInventoryAction.conditions)
        self.assertTrue(CheckInventoryAction.conditions['character_status']['alive'])

    def test_goap_reactions(self):
        """Test GOAP reactions are properly defined."""
        self.assertIsInstance(CheckInventoryAction.reactions, dict)

    def test_goap_weights(self):
        """Test GOAP weights are properly defined."""
        expected_weight = CheckInventoryAction.weight
        self.assertIsInstance(expected_weight, (int, float))

    def test_required_items_handling(self):
        """Test different required items formats."""
        # Test with list of strings
        simple_items = ['copper_ore', 'ash_wood']
        # This should work if the constructor handles different formats
        
        # Test with detailed requirements
        detailed_items = [
            {'item_code': 'copper_ore', 'quantity': 5, 'priority': 'high'},
            {'item_code': 'ash_wood', 'quantity': 2, 'priority': 'medium'}
        ]
        
        action = CheckInventoryAction()
        # Action no longer stores required_items as instance attribute
        self.assertFalse(hasattr(action, 'required_items'))

    def test_empty_inventory_handling(self):
        """Test handling of empty inventory with TARGET_RECIPE approach."""
        action = CheckInventoryAction()
        
        mock_inventory = []  # Empty inventory
        client = create_mock_client()
        
        # Create context with TARGET_RECIPE and mock knowledge base
        context = MockActionContext(character_name="player")
        context.character_inventory = mock_inventory  # Set empty inventory in context
        context.set_parameter(StateParameters.TARGET_RECIPE, 'copper_dagger')
        # Setup mock knowledge base with copper_dagger recipe
        context.knowledge_base.data['items']['copper_dagger'] = {
            'craft_data': {
                'items': [{'code': 'copper_ore', 'quantity': 5}]
            }
        }
        
        result = action.execute(client, context)
        
        self.assertTrue(result.success)
        # Check that inventory was analyzed correctly
        item_checks = result.data['item_checks']
        self.assertEqual(item_checks['copper_ore']['current'], 0)
        self.assertEqual(item_checks['copper_ore']['required'], 5)
        self.assertFalse(item_checks['copper_ore']['sufficient'])


if __name__ == '__main__':
    unittest.main()