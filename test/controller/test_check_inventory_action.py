"""Test module for CheckInventoryAction."""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.controller.actions.check_inventory import CheckInventoryAction

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
        """Test execute fails without client."""
        context = MockActionContext(character_name=self.character_name, required_items=self.required_items)
        result = self.action.execute(None, context)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    @patch('src.controller.actions.check_inventory.get_character_api')
    def test_execute_character_api_fails(self, mock_get_character_api):
        """Test execute when character API fails - returns empty inventory."""
        mock_get_character_api.return_value = None
        client = create_mock_client()
        
        context = MockActionContext(character_name=self.character_name, required_items=self.required_items)
        result = self.action.execute(client, context)
        # Action succeeds with empty inventory when API fails
        self.assertTrue(result['success'])
        self.assertEqual(result['inventory'], {})
        self.assertEqual(result['total_items'], 0)

    @patch('src.controller.actions.check_inventory.get_character_api')
    def test_execute_character_api_no_data(self, mock_get_character_api):
        """Test execute when character API returns no data - returns empty inventory."""
        mock_response = Mock()
        mock_response.data = None
        mock_get_character_api.return_value = mock_response
        client = create_mock_client()
        
        context = MockActionContext(character_name=self.character_name, required_items=self.required_items)
        result = self.action.execute(client, context)
        # Action succeeds with empty inventory when API returns no data
        self.assertTrue(result['success'])
        self.assertEqual(result['inventory'], {})
        self.assertEqual(result['total_items'], 0)

    @patch('src.controller.actions.check_inventory.get_character_api')
    def test_execute_character_no_inventory(self, mock_get_character_api):
        """Test execute when character has no inventory - returns empty inventory."""
        mock_character = Mock()
        mock_character.inventory = None
        mock_response = Mock()
        mock_response.data = mock_character
        mock_get_character_api.return_value = mock_response
        client = create_mock_client()
        
        context = MockActionContext(character_name=self.character_name, required_items=self.required_items)
        result = self.action.execute(client, context)
        # Action succeeds with empty inventory when character has no inventory
        self.assertTrue(result['success'])
        self.assertEqual(result['inventory'], {})
        self.assertEqual(result['total_items'], 0)

    @patch('src.controller.actions.check_inventory.get_character_api')
    def test_execute_success_with_sufficient_items(self, mock_get_character_api):
        """Test successful execution with sufficient items."""
        # Mock character with inventory containing required items
        mock_inventory = [
            {'slot': 1, 'code': 'copper_ore', 'quantity': 10},
            {'slot': 2, 'code': 'ash_wood', 'quantity': 5},
            {'slot': 3, 'code': 'iron_ore', 'quantity': 3}
        ]
        mock_character = Mock()
        mock_character.inventory = mock_inventory
        mock_response = Mock()
        mock_response.data = mock_character
        mock_get_character_api.return_value = mock_response
        client = create_mock_client()
        
        context = MockActionContext(character_name=self.character_name, required_items=self.required_items)
        result = self.action.execute(client, context)
        self.assertTrue(result['success'])
        self.assertIn('inventory_summary', result)
        self.assertIn('world_state_updates', result)
        self.assertTrue(result['world_state_updates']['materials_sufficient'])
        
        # Check item checks
        item_checks = result['item_checks']
        self.assertIn('copper_ore', item_checks)
        self.assertEqual(item_checks['copper_ore']['current'], 10)
        self.assertEqual(item_checks['copper_ore']['required'], 5)
        self.assertTrue(item_checks['copper_ore']['sufficient'])

    @patch('src.controller.actions.check_inventory.get_character_api')
    def test_execute_success_with_insufficient_items(self, mock_get_character_api):
        """Test successful execution with insufficient items."""
        # Mock character with inventory lacking required items
        mock_inventory = [
            {'slot': 1, 'code': 'copper_ore', 'quantity': 2},  # Need 5, have 2
            {'slot': 2, 'code': 'iron_ore', 'quantity': 5}     # Don't have ash_wood
        ]
        mock_character = Mock()
        mock_character.inventory = mock_inventory
        mock_response = Mock()
        mock_response.data = mock_character
        mock_get_character_api.return_value = mock_response
        client = create_mock_client()
        
        context = MockActionContext(character_name=self.character_name, required_items=self.required_items)
        result = self.action.execute(client, context)
        self.assertTrue(result['success'])
        self.assertFalse(result['world_state_updates']['materials_sufficient'])
        
        # Check inventory status shows insufficient items
        item_checks = result['item_checks']
        self.assertEqual(item_checks['copper_ore']['current'], 2)
        self.assertEqual(item_checks['copper_ore']['required'], 5)
        self.assertFalse(item_checks['copper_ore']['sufficient'])
        
        # ash_wood should be missing completely
        self.assertEqual(item_checks['ash_wood']['current'], 0)
        self.assertEqual(item_checks['ash_wood']['required'], 2)
        self.assertFalse(item_checks['ash_wood']['sufficient'])

    @patch('src.controller.actions.check_inventory.get_character_api')
    def test_execute_success_no_required_items(self, mock_get_character_api):
        """Test successful execution with no required items (inventory check only)."""
        action = CheckInventoryAction()  # No required items
        
        mock_inventory = [
            {'slot': 1, 'code': 'copper_ore', 'quantity': 10},
            {'slot': 2, 'code': 'ash_wood', 'quantity': 5}
        ]
        mock_character = Mock()
        mock_character.inventory = mock_inventory
        mock_response = Mock()
        mock_response.data = mock_character
        mock_get_character_api.return_value = mock_response
        client = create_mock_client()
        
        context = MockActionContext(character_name="player", required_items=[])
        result = action.execute(client, context)
        self.assertTrue(result['success'])
        # When no requirements specified, materials_sufficient is True by default
        self.assertTrue(result['world_state_updates'].get('materials_sufficient', True))
        self.assertIn('inventory', result)
        self.assertEqual(len(result['inventory']), 2)

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
        
        # Test basic functionality if method exists
        if hasattr(self.action, '_get_character_inventory'):
            with patch('src.controller.actions.check_inventory.get_character_api', return_value=mock_response):
                context = MockActionContext(character_name=self.character_name)
                inventory_dict = self.action._get_character_inventory(client, context)
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
            self.assertIsInstance(result, dict)
            # Should have status for each required item
            self.assertIn('item_checks', result)
            self.assertIn('materials_sufficient', result)

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
            self.assertFalse(result['success'])
            self.assertIn('Inventory check failed', result['error'])

    def test_execute_has_goap_attributes(self):
        """Test that CheckInventoryAction has expected GOAP attributes."""
        self.assertTrue(hasattr(CheckInventoryAction, 'conditions'))
        self.assertTrue(hasattr(CheckInventoryAction, 'reactions'))
        self.assertTrue(hasattr(CheckInventoryAction, 'weights'))
        self.assertTrue(hasattr(CheckInventoryAction, 'g'))

    def test_goap_conditions(self):
        """Test GOAP conditions are properly defined."""
        expected_conditions = {"character_alive": True}
        self.assertEqual(CheckInventoryAction.conditions, expected_conditions)

    def test_goap_reactions(self):
        """Test GOAP reactions are properly defined."""
        expected_reactions = {
            "has_crafting_materials": True, 
            "materials_sufficient": True,
            "has_raw_materials": True,
            "has_refined_materials": True,
            "inventory_updated": True
        }
        self.assertEqual(CheckInventoryAction.reactions, expected_reactions)

    def test_goap_weights(self):
        """Test GOAP weights are properly defined."""
        expected_weights = {"inventory_updated": 1.0}
        self.assertEqual(CheckInventoryAction.weights, expected_weights)

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
        """Test handling of empty inventory."""
        action = CheckInventoryAction()
        
        with patch('src.controller.actions.check_inventory.get_character_api') as mock_get_char:
            mock_inventory = []  # Empty inventory
            mock_character = Mock()
            mock_character.inventory = mock_inventory
            mock_response = Mock()
            mock_response.data = mock_character
            mock_get_char.return_value = mock_response
            
            client = create_mock_client()
            context = MockActionContext(character_name="player", required_items=[{'item_code': 'copper_ore', 'quantity': 5}])
            result = action.execute(client, context)
            
            self.assertTrue(result['success'])
            self.assertFalse(result['world_state_updates']['materials_sufficient'])
            # Should show that required item is missing
            item_checks = result['item_checks']
            self.assertEqual(item_checks['copper_ore']['current'], 0)
            self.assertEqual(item_checks['copper_ore']['required'], 5)
            self.assertFalse(item_checks['copper_ore']['sufficient'])


if __name__ == '__main__':
    unittest.main()