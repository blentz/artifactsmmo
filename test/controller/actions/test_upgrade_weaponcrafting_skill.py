"""Tests for UpgradeWeaponcraftingSkillAction."""

import unittest
from unittest.mock import Mock, patch
from src.controller.actions.upgrade_weaponcrafting_skill import UpgradeWeaponcraftingSkillAction
from src.controller.actions.base import ActionResult
from src.lib.action_context import ActionContext


class TestUpgradeWeaponcraftingSkillAction(unittest.TestCase):
    """Test the UpgradeWeaponcraftingSkillAction class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = UpgradeWeaponcraftingSkillAction()
        self.mock_client = Mock()
        
        # Create mock context
        self.mock_context = Mock(spec=ActionContext)
        self.mock_context.character_name = 'test_character'
        self.mock_context.get.return_value = None
        
        # Create mock character data
        self.mock_character_data = Mock()
        self.mock_character_data.weaponcrafting_level = 0
        self.mock_character_data.inventory = []
        
    def test_init(self):
        """Test action initialization."""
        action = UpgradeWeaponcraftingSkillAction()
        self.assertIsInstance(action, UpgradeWeaponcraftingSkillAction)
        self.assertIsNotNone(action.logger)
        
    def test_goap_parameters(self):
        """Test GOAP conditions and reactions."""
        self.assertIn('character_status', self.action.conditions)
        self.assertIn('workshop_status', self.action.conditions)
        self.assertIn('inventory_status', self.action.conditions)
        
        self.assertEqual(self.action.conditions['character_status']['alive'], True)
        self.assertEqual(self.action.conditions['character_status']['safe'], True)
        self.assertEqual(self.action.conditions['workshop_status']['at_workshop'], True)
        self.assertEqual(self.action.conditions['inventory_status']['has_materials'], True)
        
        self.assertIn('skill_status', self.action.reactions)
        self.assertIn('character_status', self.action.reactions)
        self.assertTrue(self.action.reactions['skill_status']['weaponcrafting_level_sufficient'])
        self.assertTrue(self.action.reactions['skill_status']['xp_gained'])
        self.assertTrue(self.action.reactions['character_status']['stats_improved'])
        
        self.assertEqual(self.action.weight, 30)
        
    @patch('src.controller.actions.upgrade_weaponcrafting_skill.get_character_api')
    def test_execute_no_character_data(self, mock_get_character):
        """Test execute when character data cannot be retrieved."""
        mock_get_character.return_value = None
        
        result = self.action.execute(self.mock_client, self.mock_context)
        
        self.assertFalse(result.success)
        self.assertIn('Could not get character data', result.error)
        
    @patch('src.controller.actions.upgrade_weaponcrafting_skill.get_character_api')
    def test_execute_already_at_target_level(self, mock_get_character):
        """Test execute when character is already at target level."""
        # Setup character data with high skill level
        self.mock_character_data.weaponcrafting_level = 5
        mock_response = Mock()
        mock_response.data = self.mock_character_data
        mock_get_character.return_value = mock_response
        
        # Set target level lower than current
        self.mock_context.get.side_effect = lambda key, default=None: {
            'target_level': 3,
            'current_level': 0
        }.get(key, default)
        
        result = self.action.execute(self.mock_client, self.mock_context)
        
        self.assertTrue(result.success)
        self.assertTrue(result.data['skill_level_achieved'])
        self.assertEqual(result.data['current_weaponcrafting_level'], 5)
        self.assertEqual(result.data['target_level'], 3)
        
    @patch('src.controller.actions.upgrade_weaponcrafting_skill.craft_api')
    @patch('src.controller.actions.upgrade_weaponcrafting_skill.get_character_api')
    def test_execute_no_suitable_items(self, mock_get_character, mock_craft):
        """Test execute when no suitable items can be crafted."""
        # Setup character data with no inventory
        mock_response = Mock()
        mock_response.data = self.mock_character_data
        mock_get_character.return_value = mock_response
        
        self.mock_context.get.side_effect = lambda key, default=None: {
            'target_level': 1,
            'current_level': 0
        }.get(key, default)
        
        result = self.action.execute(self.mock_client, self.mock_context)
        
        self.assertFalse(result.success)
        self.assertIn('No suitable items to craft', result.error)
        
    @patch('src.controller.actions.upgrade_weaponcrafting_skill.craft_api')
    @patch('src.controller.actions.upgrade_weaponcrafting_skill.get_character_api')
    def test_execute_craft_failure(self, mock_get_character, mock_craft):
        """Test execute when crafting fails."""
        # Setup character data with materials
        mock_item = Mock()
        mock_item.code = 'ash_wood'
        mock_item.quantity = 5
        self.mock_character_data.inventory = [mock_item]
        
        mock_response = Mock()
        mock_response.data = self.mock_character_data
        mock_get_character.return_value = mock_response
        
        # Make crafting fail
        mock_craft.return_value = None
        
        self.mock_context.get.side_effect = lambda key, default=None: {
            'target_level': 1,
            'current_level': 0
        }.get(key, default)
        
        result = self.action.execute(self.mock_client, self.mock_context)
        
        self.assertFalse(result.success)
        self.assertIn('Failed to craft', result.error)
        
    @patch('src.controller.actions.upgrade_weaponcrafting_skill.craft_api')
    @patch('src.controller.actions.upgrade_weaponcrafting_skill.get_character_api')
    def test_execute_successful_craft_with_skill_gain(self, mock_get_character, mock_craft):
        """Test successful execute with skill level gain."""
        # Setup character data with materials
        mock_item = Mock()
        mock_item.code = 'ash_wood'
        mock_item.quantity = 5
        self.mock_character_data.inventory = [mock_item]
        
        # Setup initial character response
        mock_response = Mock()
        mock_response.data = self.mock_character_data
        
        # Setup updated character data after crafting
        mock_updated_character = Mock()
        mock_updated_character.weaponcrafting_level = 1
        mock_updated_response = Mock()
        mock_updated_response.data = mock_updated_character
        
        # Return different responses for consecutive calls
        mock_get_character.side_effect = [mock_response, mock_updated_response]
        
        # Setup craft response
        mock_craft_response = Mock()
        mock_craft_response.data = {'item': 'wooden_stick', 'success': True}
        mock_craft.return_value = mock_craft_response
        
        self.mock_context.get.side_effect = lambda key, default=None: {
            'target_level': 1,
            'current_level': 0
        }.get(key, default)
        
        result = self.action.execute(self.mock_client, self.mock_context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.data['item_crafted'], 'wooden_stick')
        self.assertTrue(result.data['skill_xp_gained'])
        self.assertEqual(result.data['previous_skill_level'], 0)
        self.assertEqual(result.data['current_weaponcrafting_level'], 1)
        self.assertEqual(result.data['target_level'], 1)
        self.assertTrue(result.data['target_achieved'])
        
    @patch('src.controller.actions.upgrade_weaponcrafting_skill.craft_api')
    @patch('src.controller.actions.upgrade_weaponcrafting_skill.get_character_api')
    def test_execute_successful_craft_no_updated_data(self, mock_get_character, mock_craft):
        """Test successful execute when updated character data can't be retrieved."""
        # Setup character data with materials
        mock_item = Mock()
        mock_item.code = 'ash_wood'
        mock_item.quantity = 5
        self.mock_character_data.inventory = [mock_item]
        
        # Setup initial character response
        mock_response = Mock()
        mock_response.data = self.mock_character_data
        
        # Return initial response first, then None for updated data
        mock_get_character.side_effect = [mock_response, None]
        
        # Setup craft response
        mock_craft_response = Mock()
        mock_craft_response.data = {'item': 'wooden_stick', 'success': True}
        mock_craft.return_value = mock_craft_response
        
        self.mock_context.get.side_effect = lambda key, default=None: {
            'target_level': 1,
            'current_level': 0
        }.get(key, default)
        
        result = self.action.execute(self.mock_client, self.mock_context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.data['item_crafted'], 'wooden_stick')
        self.assertTrue(result.data['skill_xp_gained'])
        self.assertEqual(result.data['current_weaponcrafting_level'], 0)  # No update available
        self.assertEqual(result.data['target_level'], 1)
        
    @patch('src.controller.actions.upgrade_weaponcrafting_skill.get_character_api')
    def test_execute_exception_handling(self, mock_get_character):
        """Test execute with exception handling."""
        mock_get_character.side_effect = Exception("API error")
        
        result = self.action.execute(self.mock_client, self.mock_context)
        
        self.assertFalse(result.success)
        self.assertIn('Weaponcrafting skill upgrade failed', result.error)
        self.assertIn('API error', result.error)
        
    def test_select_craft_item_no_skill_no_materials(self):
        """Test item selection with no skill and no materials."""
        self.mock_character_data.weaponcrafting_level = 0
        self.mock_character_data.inventory = []
        
        result = self.action._select_craft_item(self.mock_character_data)
        
        self.assertIsNone(result)
        
    def test_select_craft_item_with_materials_skill_0(self):
        """Test item selection with materials at skill level 0."""
        mock_item = Mock()
        mock_item.code = 'ash_wood'
        mock_item.quantity = 5
        self.mock_character_data.weaponcrafting_level = 0
        self.mock_character_data.inventory = [mock_item]
        
        result = self.action._select_craft_item(self.mock_character_data)
        
        self.assertEqual(result, 'wooden_stick')
        
    def test_select_craft_item_insufficient_materials(self):
        """Test item selection with insufficient materials."""
        mock_item = Mock()
        mock_item.code = 'ash_wood'
        mock_item.quantity = 1  # Need 2 for wooden_stick
        self.mock_character_data.weaponcrafting_level = 0
        self.mock_character_data.inventory = [mock_item]
        
        result = self.action._select_craft_item(self.mock_character_data)
        
        self.assertIsNone(result)
        
    def test_select_craft_item_higher_skill_level(self):
        """Test item selection with higher skill level."""
        mock_item = Mock()
        mock_item.code = 'ash_wood'
        mock_item.quantity = 5
        self.mock_character_data.weaponcrafting_level = 5  # Higher than 0
        self.mock_character_data.inventory = [mock_item]
        
        result = self.action._select_craft_item(self.mock_character_data)
        
        # Currently only handles skill level 0, so should return None
        self.assertIsNone(result)
        
    def test_select_craft_item_no_inventory_attribute(self):
        """Test item selection when character has no inventory attribute."""
        # Remove inventory attribute
        delattr(self.mock_character_data, 'inventory')
        self.mock_character_data.weaponcrafting_level = 0
        
        result = self.action._select_craft_item(self.mock_character_data)
        
        self.assertIsNone(result)
        
    def test_select_craft_item_invalid_inventory_items(self):
        """Test item selection with invalid inventory items."""
        # Create items without proper attributes
        mock_item1 = Mock()
        mock_item1.code = None
        mock_item1.quantity = 5
        
        mock_item2 = Mock()
        mock_item2.code = 'ash_wood'
        mock_item2.quantity = 0  # Zero quantity
        
        mock_item3 = Mock()
        # Missing attributes entirely
        
        self.mock_character_data.weaponcrafting_level = 0
        self.mock_character_data.inventory = [mock_item1, mock_item2, mock_item3]
        
        result = self.action._select_craft_item(self.mock_character_data)
        
        self.assertIsNone(result)
        
    def test_select_craft_item_exception_handling(self):
        """Test item selection with exception handling."""
        # Create a character data that will cause an exception
        mock_character_data = Mock()
        mock_character_data.weaponcrafting_level = 0
        # Make inventory access raise an exception
        type(mock_character_data).inventory = Mock(side_effect=Exception("Inventory error"))
        
        result = self.action._select_craft_item(mock_character_data)
        
        self.assertIsNone(result)
        
    def test_select_craft_item_mixed_inventory(self):
        """Test item selection with mixed valid/invalid inventory items."""
        # Valid item
        mock_valid_item = Mock()
        mock_valid_item.code = 'ash_wood'
        mock_valid_item.quantity = 3
        
        # Invalid items
        mock_invalid_item1 = Mock()
        mock_invalid_item1.code = ''
        mock_invalid_item1.quantity = 5
        
        mock_invalid_item2 = Mock()
        mock_invalid_item2.code = 'stone'
        mock_invalid_item2.quantity = 0
        
        self.mock_character_data.weaponcrafting_level = 0
        self.mock_character_data.inventory = [mock_invalid_item1, mock_valid_item, mock_invalid_item2]
        
        result = self.action._select_craft_item(self.mock_character_data)
        
        self.assertEqual(result, 'wooden_stick')
        
    def test_repr_method(self):
        """Test string representation of the action."""
        result = repr(self.action)
        self.assertEqual(result, "UpgradeWeaponcraftingSkillAction()")
        
    def test_inheritance(self):
        """Test that the action properly inherits from ActionBase."""
        from src.controller.actions.base import ActionBase
        self.assertIsInstance(self.action, ActionBase)
        
    def test_context_parameters_extraction(self):
        """Test parameter extraction from context."""
        # Test default values
        self.mock_context.get.side_effect = lambda key, default=None: default
        self.mock_context.character_name = 'test_char'
        
        # The execute method should handle missing parameters gracefully
        # We can't easily test this without mocking the API calls, but we can verify
        # that the context is accessed correctly
        
        with patch('artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync') as mock_get_char:
            mock_get_char.return_value = None
            result = self.action.execute(self.mock_client, self.mock_context)
            
            # Should fail due to no character data, but parameters should have been extracted
            self.assertFalse(result.success)
            
            # Verify context was accessed for target_level and current_level
            self.mock_context.get.assert_any_call('target_level', 1)
            self.mock_context.get.assert_any_call('current_level', 0)
            
    def test_error_result_format(self):
        """Test that error results are returned in proper format."""
        # Test the execute method returns proper ActionResult on error
        with patch('artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync') as mock_get_char:
            # Simulate an exception
            mock_get_char.side_effect = Exception("API error")
            result = self.action.execute(self.mock_client, self.mock_context)
            
            # Verify error result is returned properly
            self.assertIsInstance(result, ActionResult)
            self.assertFalse(result.success)
            self.assertIn("Weaponcrafting skill upgrade failed", result.error)


if __name__ == '__main__':
    unittest.main()