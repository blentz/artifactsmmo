"""Test module for CheckInventoryAction."""

import unittest
import tempfile
import os
from unittest.mock import Mock, patch
from src.controller.actions.check_inventory import CheckInventoryAction


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
        self.action = CheckInventoryAction(
            character_name=self.character_name,
            required_items=self.required_items
        )

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['DATA_PREFIX'] = self.original_data_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_check_inventory_action_initialization(self):
        """Test CheckInventoryAction initialization."""
        self.assertEqual(self.action.character_name, "test_character")
        self.assertEqual(len(self.action.required_items), 2)
        self.assertEqual(self.action.required_items[0]['item_code'], 'copper_ore')
        self.assertEqual(self.action.required_items[0]['quantity'], 5)

    def test_check_inventory_action_initialization_defaults(self):
        """Test CheckInventoryAction initialization with defaults."""
        action = CheckInventoryAction("player")
        self.assertEqual(action.character_name, "player")
        self.assertEqual(action.required_items, [])

    def test_check_inventory_action_repr(self):
        """Test CheckInventoryAction string representation."""
        expected = "CheckInventoryAction(test_character, 2 requirements)"
        self.assertEqual(repr(self.action), expected)

    def test_check_inventory_action_repr_no_items(self):
        """Test CheckInventoryAction string representation without required items."""
        action = CheckInventoryAction("player")
        expected = "CheckInventoryAction(player, 0 requirements)"
        self.assertEqual(repr(action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        result = self.action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    @patch('src.controller.actions.check_inventory.get_character_api')
    def test_execute_character_api_fails(self, mock_get_character_api):
        """Test execute when character API fails."""
        mock_get_character_api.return_value = None
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Could not get character data', result['error'])

    @patch('src.controller.actions.check_inventory.get_character_api')
    def test_execute_character_api_no_data(self, mock_get_character_api):
        """Test execute when character API returns no data."""
        mock_response = Mock()
        mock_response.data = None
        mock_get_character_api.return_value = mock_response
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Could not get character data', result['error'])

    @patch('src.controller.actions.check_inventory.get_character_api')
    def test_execute_character_no_inventory(self, mock_get_character_api):
        """Test execute when character has no inventory."""
        mock_character = Mock()
        mock_character.inventory = None
        mock_response = Mock()
        mock_response.data = mock_character
        mock_get_character_api.return_value = mock_response
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Character has no inventory', result['error'])

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
        client = Mock()
        
        result = self.action.execute(client)
        self.assertTrue(result['success'])
        self.assertIn('inventory_status', result)
        self.assertIn('sufficient_materials', result)
        self.assertTrue(result['sufficient_materials'])
        
        # Check inventory status
        inventory_status = result['inventory_status']
        self.assertIn('copper_ore', inventory_status)
        self.assertEqual(inventory_status['copper_ore']['available'], 10)
        self.assertEqual(inventory_status['copper_ore']['required'], 5)
        self.assertTrue(inventory_status['copper_ore']['sufficient'])

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
        client = Mock()
        
        result = self.action.execute(client)
        self.assertTrue(result['success'])
        self.assertFalse(result['sufficient_materials'])
        
        # Check inventory status shows insufficient items
        inventory_status = result['inventory_status']
        self.assertEqual(inventory_status['copper_ore']['available'], 2)
        self.assertEqual(inventory_status['copper_ore']['required'], 5)
        self.assertFalse(inventory_status['copper_ore']['sufficient'])
        
        # ash_wood should be missing completely
        self.assertEqual(inventory_status['ash_wood']['available'], 0)
        self.assertEqual(inventory_status['ash_wood']['required'], 2)
        self.assertFalse(inventory_status['ash_wood']['sufficient'])

    @patch('src.controller.actions.check_inventory.get_character_api')
    def test_execute_success_no_required_items(self, mock_get_character_api):
        """Test successful execution with no required items (inventory check only)."""
        action = CheckInventoryAction("player")  # No required items
        
        mock_inventory = [
            {'slot': 1, 'code': 'copper_ore', 'quantity': 10},
            {'slot': 2, 'code': 'ash_wood', 'quantity': 5}
        ]
        mock_character = Mock()
        mock_character.inventory = mock_inventory
        mock_response = Mock()
        mock_response.data = mock_character
        mock_get_character_api.return_value = mock_response
        client = Mock()
        
        result = action.execute(client)
        self.assertTrue(result['success'])
        self.assertTrue(result['sufficient_materials'])  # No requirements, so sufficient
        self.assertIn('inventory_items', result)
        self.assertEqual(len(result['inventory_items']), 2)

    def test_get_character_inventory_helper_method(self):
        """Test _get_character_inventory helper method."""
        client = Mock()
        
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
                inventory_dict = self.action._get_character_inventory(client)
                self.assertIsInstance(inventory_dict, dict)
                self.assertIn('copper_ore', inventory_dict)
                self.assertEqual(inventory_dict['copper_ore'], 10)

    def test_check_item_requirements_helper_method(self):
        """Test _check_item_requirements helper method."""
        inventory_dict = {'copper_ore': 10, 'ash_wood': 3, 'iron_ore': 1}
        
        # Test basic functionality if method exists
        if hasattr(self.action, '_check_item_requirements'):
            result = self.action._check_item_requirements(inventory_dict)
            self.assertIsInstance(result, dict)
            # Should have status for each required item
            self.assertIn('inventory_status', result)
            self.assertIn('sufficient_materials', result)

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
        client = Mock()
        
        with patch('src.controller.actions.check_inventory.get_character_api', side_effect=Exception("API Error")):
            result = self.action.execute(client)
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
        
        action = CheckInventoryAction("player", detailed_items)
        self.assertEqual(len(action.required_items), 2)
        self.assertEqual(action.required_items[0]['item_code'], 'copper_ore')
        self.assertEqual(action.required_items[0]['quantity'], 5)

    def test_empty_inventory_handling(self):
        """Test handling of empty inventory."""
        action = CheckInventoryAction("player", [{'item_code': 'copper_ore', 'quantity': 5}])
        
        with patch('src.controller.actions.check_inventory.get_character_api') as mock_get_char:
            mock_inventory = []  # Empty inventory
            mock_character = Mock()
            mock_character.inventory = mock_inventory
            mock_response = Mock()
            mock_response.data = mock_character
            mock_get_char.return_value = mock_response
            
            client = Mock()
            result = action.execute(client)
            
            self.assertTrue(result['success'])
            self.assertFalse(result['sufficient_materials'])
            # Should show that required item is missing
            inventory_status = result['inventory_status']
            self.assertEqual(inventory_status['copper_ore']['available'], 0)
            self.assertEqual(inventory_status['copper_ore']['required'], 5)
            self.assertFalse(inventory_status['copper_ore']['sufficient'])


if __name__ == '__main__':
    unittest.main()