"""Test module for LookupItemInfoAction."""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.lookup_item_info import LookupItemInfoAction

from test.base_test import BaseTest
from test.fixtures import MockActionContext, create_mock_client


class TestLookupItemInfoAction(BaseTest):
    """Test cases for LookupItemInfoAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.item_code = "copper_sword"
        self.search_term = "sword"
        self.item_type = "weapon"
        self.max_level = 10
        
        self.action_with_code = LookupItemInfoAction()
        self.action_with_search = LookupItemInfoAction()
        
        # Mock client
        self.mock_client = create_mock_client()
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up mock objects
        self.mock_client = None
        self.action_with_code = None
        self.action_with_search = None
        
        # Clear any patches that might be active
        patch.stopall()

    def test_lookup_item_info_action_initialization_with_code(self):
        """Test LookupItemInfoAction initialization with item code."""
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(self.action_with_code, 'item_code'))
        self.assertFalse(hasattr(self.action_with_code, 'search_term'))
        self.assertFalse(hasattr(self.action_with_code, 'item_type'))
        self.assertFalse(hasattr(self.action_with_code, 'max_level'))

    def test_lookup_item_info_action_initialization_with_search(self):
        """Test LookupItemInfoAction initialization with search parameters."""
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(self.action_with_search, 'item_code'))
        self.assertFalse(hasattr(self.action_with_search, 'search_term'))
        self.assertFalse(hasattr(self.action_with_search, 'item_type'))
        self.assertFalse(hasattr(self.action_with_search, 'max_level'))

    def test_lookup_item_info_action_initialization_defaults(self):
        """Test LookupItemInfoAction initialization with defaults."""
        action = LookupItemInfoAction()
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(action, 'item_code'))
        self.assertFalse(hasattr(action, 'search_term'))
        self.assertFalse(hasattr(action, 'item_type'))
        self.assertFalse(hasattr(action, 'max_level'))

    def test_lookup_item_info_action_repr_with_code(self):
        """Test LookupItemInfoAction string representation with item code."""
        # Repr is now simplified
        expected = "LookupItemInfoAction()"
        self.assertEqual(repr(self.action_with_code), expected)

    def test_lookup_item_info_action_repr_with_search(self):
        """Test LookupItemInfoAction string representation with search parameters."""
        # Repr is now simplified
        expected = "LookupItemInfoAction()"
        self.assertEqual(repr(self.action_with_search), expected)

    def test_lookup_item_info_action_repr_no_parameters(self):
        """Test LookupItemInfoAction string representation with no parameters."""
        action = LookupItemInfoAction()
        expected = "LookupItemInfoAction()"
        self.assertEqual(repr(action), expected)

    def test_lookup_item_info_action_repr_partial_parameters(self):
        """Test LookupItemInfoAction string representation with partial parameters."""
        action = LookupItemInfoAction()
        expected = "LookupItemInfoAction()"
        self.assertEqual(repr(action), expected)

    def test_execute_no_client(self):
        """Test lookup fails without client."""
        
        context = MockActionContext(character_name="test_char", item_code=self.item_code)
        result = self.action_with_code.execute(None, context)
        # With centralized validation, None client triggers validation error
        self.assertFalse(result.success)
        # Direct action execution bypasses centralized validation
        self.assertIsNotNone(result.error)

    def test_execute_has_goap_attributes(self):
        """Test that LookupItemInfoAction has expected GOAP attributes."""
        self.assertTrue(hasattr(LookupItemInfoAction, 'conditions'))
        self.assertTrue(hasattr(LookupItemInfoAction, 'reactions'))
        self.assertTrue(hasattr(LookupItemInfoAction, 'weight'))

    @patch('src.controller.actions.lookup_item_info.LookupItemInfoAction._lookup_specific_item')
    def test_execute_with_item_code(self, mock_lookup_specific):
        """Test execute with specific item code."""
        mock_result = {'success': True, 'item_code': self.item_code}
        mock_lookup_specific.return_value = mock_result
        
        
        context = MockActionContext(character_name="test_char", item_code=self.item_code)
        result = self.action_with_code.execute(self.mock_client, context)
        
        mock_lookup_specific.assert_called_once_with(self.mock_client, self.item_code)
        self.assertEqual(result, mock_result)

    @patch('src.controller.actions.lookup_item_info.LookupItemInfoAction._determine_equipment_to_craft')
    def test_execute_with_search_parameters(self, mock_determine_equipment):
        """Test execute with search parameters."""
        mock_result = {'success': False, 'error': 'No suitable equipment recipes found for current character level'}
        mock_determine_equipment.return_value = mock_result
        
        
        context = MockActionContext(character_name="test_char", search_term=self.search_term, 
                                  item_type=self.item_type, max_level=self.max_level)
        result = self.action_with_search.execute(self.mock_client, context)
        
        mock_determine_equipment.assert_called_once_with(self.mock_client, context)
        self.assertEqual(result, mock_result)

    @patch('src.controller.actions.lookup_item_info.LookupItemInfoAction._lookup_specific_item')
    def test_execute_exception_handling(self, mock_lookup_specific):
        """Test exception handling during lookup."""
        mock_lookup_specific.side_effect = Exception("Network error")
        
        context = MockActionContext(character_name="test_char", item_code=self.item_code)
        
        # Temporarily disable logging to avoid handler issues in tests
        import logging
        original_level = logging.root.level
        logging.disable(logging.CRITICAL)
        
        try:
            result = self.action_with_code.execute(self.mock_client, context)
            self.assertFalse(result.success)
            self.assertIn('Item lookup failed: Network error', result.error)
        finally:
            # Re-enable logging
            logging.disable(original_level)

    @patch('src.controller.actions.lookup_item_info.get_item_api')
    def test_lookup_specific_item_success_minimal(self, mock_get_item_api):
        """Test _lookup_specific_item with minimal item data."""
        # Mock item response with minimal data - use spec to control attributes
        mock_item_data = Mock(spec=['name', 'description', 'type', 'level'])
        mock_item_data.name = 'Copper Sword'
        mock_item_data.description = 'A basic sword'
        mock_item_data.type = 'weapon'
        mock_item_data.level = 1
        # Ensure craft and effects attributes don't exist
        
        mock_item_response = Mock()
        mock_item_response.data = mock_item_data
        mock_get_item_api.return_value = mock_item_response
        
        # Create context for test
        
        context = MockActionContext(character_name="test_char")
        result = self.action_with_code._lookup_specific_item(self.mock_client, self.item_code)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['item_code'], self.item_code)
        self.assertEqual(result['name'], 'Copper Sword')
        self.assertEqual(result['description'], 'A basic sword')
        self.assertEqual(result['type'], 'weapon')
        self.assertFalse(result['craftable'])

    @patch('src.controller.actions.lookup_item_info.get_item_api')
    def test_lookup_specific_item_success_with_craft(self, mock_get_item_api):
        """Test _lookup_specific_item with crafting information."""
        # Mock craft item
        mock_craft_item = Mock()
        mock_craft_item.code = 'copper'
        mock_craft_item.quantity = 2
        
        # Mock craft info
        mock_craft = Mock()
        mock_craft.skill = 'weaponcrafting'
        mock_craft.level = 5
        mock_craft.items = [mock_craft_item]
        
        # Mock item data with craft info - use spec to control attributes
        mock_item_data = Mock(spec=['name', 'type', 'craft'])
        mock_item_data.name = 'Iron Sword'
        mock_item_data.type = 'weapon'
        mock_item_data.craft = mock_craft
        
        mock_item_response = Mock()
        mock_item_response.data = mock_item_data
        mock_get_item_api.return_value = mock_item_response
        
        # Create context for test
        
        context = MockActionContext(character_name="test_char")
        result = self.action_with_code._lookup_specific_item(self.mock_client, self.item_code)
        
        self.assertTrue(result['success'])
        self.assertTrue(result['craftable'])
        self.assertEqual(result['craft_skill'], 'weaponcrafting')
        self.assertEqual(result['craft_level'], 5)
        self.assertEqual(len(result['craft_items']), 1)
        self.assertEqual(result['craft_items'][0]['code'], 'copper')
        self.assertEqual(result['craft_items'][0]['quantity'], 2)

    @patch('src.controller.actions.lookup_item_info.get_item_api')
    def test_lookup_specific_item_success_with_effects(self, mock_get_item_api):
        """Test _lookup_specific_item with effects information."""
        # Mock effect
        mock_effect = Mock()
        mock_effect.name = 'attack'
        mock_effect.value = 10
        
        # Mock item data with effects - use spec to control attributes
        mock_item_data = Mock(spec=['name', 'type', 'effects'])
        mock_item_data.name = 'Magic Sword'
        mock_item_data.type = 'weapon'
        mock_item_data.effects = [mock_effect]
        
        mock_item_response = Mock()
        mock_item_response.data = mock_item_data
        mock_get_item_api.return_value = mock_item_response
        
        # Create context for test
        
        context = MockActionContext(character_name="test_char")
        result = self.action_with_code._lookup_specific_item(self.mock_client, self.item_code)
        
        self.assertTrue(result['success'])
        self.assertEqual(len(result['effects']), 1)
        self.assertEqual(result['effects'][0]['name'], 'attack')
        self.assertEqual(result['effects'][0]['value'], 10)

    @patch('src.controller.actions.lookup_item_info.get_item_api')
    def test_lookup_specific_item_not_found(self, mock_get_item_api):
        """Test _lookup_specific_item when item not found."""
        mock_get_item_api.return_value = None
        
        # Create context for test
        
        context = MockActionContext(character_name="test_char")
        result = self.action_with_code._lookup_specific_item(self.mock_client, self.item_code)
        
        self.assertFalse(result['success'])
        self.assertIn(f'Item {self.item_code} not found', result['error'])

    @patch('src.controller.actions.lookup_item_info.get_item_api')
    def test_lookup_specific_item_no_data(self, mock_get_item_api):
        """Test _lookup_specific_item when API returns no data."""
        mock_item_response = Mock()
        mock_item_response.data = None
        mock_get_item_api.return_value = mock_item_response
        
        # Create context for test
        
        context = MockActionContext(character_name="test_char")
        result = self.action_with_code._lookup_specific_item(self.mock_client, self.item_code)
        
        self.assertFalse(result['success'])
        self.assertIn(f'Item {self.item_code} not found', result['error'])

    def test_search_items_not_available(self):
        """Test _search_items returns error about missing API."""
        
        context = MockActionContext(character_name="test_char")
        result = self.action_with_search._search_items(self.mock_client)
        
        self.assertFalse(result['success'])
        self.assertIn('Item search not available', result['error'])
        self.assertIn('get_all_items API endpoint missing', result['error'])

    @patch('src.controller.actions.lookup_item_info.LookupItemInfoAction._lookup_specific_item')
    def test_lookup_crafting_materials_item_not_found(self, mock_lookup_specific):
        """Test lookup_crafting_materials when item not found."""
        mock_lookup_specific.return_value = {'success': False, 'error': 'Item not found'}
        
        
        context = MockActionContext(character_name="test_char")
        result = self.action_with_code.lookup_crafting_materials(self.mock_client, self.item_code, context)
        
        self.assertFalse(result['success'])
        self.assertIn(f'Item {self.item_code} is not craftable or not found', result['error'])

    @patch('src.controller.actions.lookup_item_info.LookupItemInfoAction._lookup_specific_item')
    def test_lookup_crafting_materials_not_craftable(self, mock_lookup_specific):
        """Test lookup_crafting_materials when item not craftable."""
        mock_lookup_specific.return_value = {
            'success': True,
            'craftable': False,
            'name': 'Basic Item'
        }
        
        
        context = MockActionContext(character_name="test_char")
        result = self.action_with_code.lookup_crafting_materials(self.mock_client, self.item_code, context)
        
        self.assertFalse(result['success'])
        self.assertIn(f'Item {self.item_code} is not craftable or not found', result['error'])

    @patch('src.controller.actions.lookup_item_info.get_resource_api')
    @patch('src.controller.actions.lookup_item_info.get_item_api')
    @patch('src.controller.actions.lookup_item_info.LookupItemInfoAction._lookup_specific_item')
    def test_lookup_crafting_materials_success_basic(self, mock_lookup_specific, mock_get_item_api, mock_get_resource_api):
        """Test lookup_crafting_materials with basic material."""
        # Mock item lookup
        mock_lookup_specific.return_value = {
            'success': True,
            'craftable': True,
            'name': 'Iron Sword',
            'craft_skill': 'weaponcrafting',
            'craft_level': 10,
            'craft_items': [{'code': 'iron', 'quantity': 3}]
        }
        
        # Mock material item response
        mock_material_data = Mock()
        mock_material_data.name = 'Iron'
        mock_material_data.type = 'resource'
        
        mock_material_response = Mock()
        mock_material_response.data = mock_material_data
        mock_get_item_api.return_value = mock_material_response
        
        # Mock resource API (material is a resource)
        mock_resource_data = Mock()
        mock_resource_data.skill = 'mining'
        mock_resource_data.level = 5
        
        # Create mock drop that matches the material needed
        mock_drop = Mock()
        mock_drop.code = 'iron'
        mock_resource_data.drops = [mock_drop]
        
        mock_resource_response = Mock()
        mock_resource_response.data = mock_resource_data
        mock_get_resource_api.return_value = mock_resource_response
        
        
        context = MockActionContext(character_name="test_char")
        result = self.action_with_code.lookup_crafting_materials(self.mock_client, self.item_code, context)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['item_code'], self.item_code)
        self.assertEqual(result['item_name'], 'Iron Sword')
        self.assertEqual(result['craft_skill'], 'weaponcrafting')
        self.assertEqual(result['craft_level'], 10)
        self.assertEqual(len(result['materials']), 1)
        
        material = result['materials'][0]
        self.assertEqual(material['code'], 'iron')
        self.assertEqual(material['name'], 'Iron')
        self.assertEqual(material['quantity_needed'], 3)
        self.assertTrue(material['is_resource'])
        self.assertEqual(material['skill_required'], 'mining')
        self.assertEqual(material['level_required'], 5)

    @patch('src.controller.actions.lookup_item_info.get_resource_api')
    @patch('src.controller.actions.lookup_item_info.get_item_api')
    @patch('src.controller.actions.lookup_item_info.LookupItemInfoAction._lookup_specific_item')
    def test_lookup_crafting_materials_success_non_resource(self, mock_lookup_specific, mock_get_item_api, mock_get_resource_api):
        """Test lookup_crafting_materials with non-resource material."""
        # Mock item lookup
        mock_lookup_specific.return_value = {
            'success': True,
            'craftable': True,
            'name': 'Magic Sword',
            'craft_skill': 'weaponcrafting',
            'craft_level': 15,
            'craft_items': [{'code': 'gem', 'quantity': 1}]
        }
        
        # Mock material item response
        mock_material_data = Mock()
        mock_material_data.name = 'Magic Gem'
        mock_material_data.type = 'consumable'
        
        mock_material_response = Mock()
        mock_material_response.data = mock_material_data
        mock_get_item_api.return_value = mock_material_response
        
        # Mock resource API (material is NOT a resource)
        mock_get_resource_api.return_value = None
        
        
        context = MockActionContext(character_name="test_char")
        result = self.action_with_code.lookup_crafting_materials(self.mock_client, self.item_code, context)
        
        self.assertTrue(result['success'])
        self.assertEqual(len(result['materials']), 1)
        
        material = result['materials'][0]
        self.assertEqual(material['code'], 'gem')
        self.assertEqual(material['name'], 'Magic Gem')
        self.assertFalse(material['is_resource'])

    @patch('src.controller.actions.lookup_item_info.get_resource_api')
    @patch('src.controller.actions.lookup_item_info.get_item_api')
    @patch('src.controller.actions.lookup_item_info.LookupItemInfoAction._lookup_specific_item')
    def test_lookup_crafting_materials_resource_api_exception(self, mock_lookup_specific, mock_get_item_api, mock_get_resource_api):
        """Test lookup_crafting_materials handles resource API exceptions."""
        # Mock item lookup
        mock_lookup_specific.return_value = {
            'success': True,
            'craftable': True,
            'name': 'Test Item',
            'craft_skill': 'crafting',
            'craft_level': 5,
            'craft_items': [{'code': 'test_material', 'quantity': 2}]
        }
        
        # Mock material item response
        mock_material_data = Mock()
        mock_material_data.name = 'Test Material'
        mock_material_data.type = 'material'
        
        mock_material_response = Mock()
        mock_material_response.data = mock_material_data
        mock_get_item_api.return_value = mock_material_response
        
        # Mock resource API exception
        mock_get_resource_api.side_effect = Exception("API error")
        
        
        context = MockActionContext(character_name="test_char")
        result = self.action_with_code.lookup_crafting_materials(self.mock_client, self.item_code, context)
        
        self.assertTrue(result['success'])
        self.assertEqual(len(result['materials']), 1)
        
        material = result['materials'][0]
        self.assertFalse(material['is_resource'])

    @patch('src.controller.actions.lookup_item_info.get_resource_api')
    @patch('src.controller.actions.lookup_item_info.get_item_api')
    @patch('src.controller.actions.lookup_item_info.LookupItemInfoAction._lookup_specific_item')
    def test_lookup_crafting_materials_material_not_found(self, mock_lookup_specific, mock_get_item_api, mock_get_resource_api):
        """Test lookup_crafting_materials when material item not found."""
        # Mock item lookup
        mock_lookup_specific.return_value = {
            'success': True,
            'craftable': True,
            'name': 'Test Item',
            'craft_skill': 'crafting',
            'craft_level': 5,
            'craft_items': [{'code': 'unknown_material', 'quantity': 1}]
        }
        
        # Mock material item not found
        mock_get_item_api.return_value = None
        
        
        context = MockActionContext(character_name="test_char")
        result = self.action_with_code.lookup_crafting_materials(self.mock_client, self.item_code, context)
        
        # Should still succeed but skip materials that can't be found
        self.assertTrue(result['success'])
        self.assertEqual(len(result['materials']), 0)

    @patch('src.controller.actions.lookup_item_info.LookupItemInfoAction._lookup_specific_item')
    def test_lookup_crafting_materials_no_craft_items(self, mock_lookup_specific):
        """Test lookup_crafting_materials with no craft items."""
        # Mock item lookup with no craft_items
        mock_lookup_specific.return_value = {
            'success': True,
            'craftable': True,
            'name': 'Simple Item',
            'craft_skill': 'crafting',
            'craft_level': 1
            # No 'craft_items' key
        }
        
        
        context = MockActionContext(character_name="test_char")
        result = self.action_with_code.lookup_crafting_materials(self.mock_client, self.item_code, context)
        
        self.assertTrue(result['success'])
        self.assertEqual(len(result['materials']), 0)


if __name__ == '__main__':
    unittest.main()