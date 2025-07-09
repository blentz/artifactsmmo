"""
Test module for ExecuteMaterialTransformationAction.
"""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.execute_material_transformation import ExecuteMaterialTransformationAction
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from test.test_base import UnifiedContextTestBase


class TestExecuteMaterialTransformationAction(UnifiedContextTestBase):
    """Test cases for ExecuteMaterialTransformationAction."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.action = ExecuteMaterialTransformationAction()
        self.client = Mock()
        
        # Set character name in context
        self.context.set(StateParameters.CHARACTER_NAME, "test_character")
        
    def test_initialization(self):
        """Test action initialization."""
        self.assertIsInstance(self.action, ExecuteMaterialTransformationAction)
        
    def test_repr(self):
        """Test string representation."""
        self.assertEqual(repr(self.action), "ExecuteMaterialTransformationAction()")
        
    def test_execute_missing_parameters(self):
        """Test execution with missing parameters."""
        # Missing all parameters
        with patch.object(self.action, '_wait_for_cooldown'):
            result = self.action.execute(self.client, self.context)
            self.assertFalse(result.success)
            self.assertIn("Missing transformation parameters", result.error)
        
        # Missing refined_material
        self.context.set(StateParameters.RAW_MATERIAL, 'copper_ore')
        with patch.object(self.action, '_wait_for_cooldown'):
            result = self.action.execute(self.client, self.context)
            self.assertFalse(result.success)
            self.assertIn("Missing transformation parameters", result.error)
        
    def test_execute_successful_transformation(self):
        """Test successful material transformation."""
        self.context.set(StateParameters.RAW_MATERIAL, 'copper_ore')
        self.context.set(StateParameters.REFINED_MATERIAL, 'copper')
        self.context.set(StateParameters.QUANTITY, 5)
        
        # Mock crafting response
        craft_response = Mock()
        craft_response.data = Mock()
        craft_response.data.xp = 10
        craft_response.data.items = [
            Mock(code='copper', quantity=5)
        ]
        
        with patch.object(self.action, '_wait_for_cooldown'):
            with patch('src.controller.actions.execute_material_transformation.crafting_api') as mock_craft:
                mock_craft.return_value = craft_response
                
                result = self.action.execute(self.client, self.context)
                
                self.assertTrue(result.success)
                self.assertEqual(result.data['xp_gained'], 10)
                self.assertEqual(len(result.data['items_produced']), 1)
                self.assertEqual(result.data['items_produced'][0]['code'], 'copper')
                self.assertEqual(result.data['items_produced'][0]['quantity'], 5)
                
                # Check context was updated
                last_transformation = self.context.get(StateParameters.LAST_TRANSFORMATION)
                self.assertIsNotNone(last_transformation)
                self.assertTrue(last_transformation['success'])
                self.assertEqual(last_transformation['raw_material'], 'copper_ore')
                self.assertEqual(last_transformation['refined_material'], 'copper')
                
    def test_execute_with_default_quantity(self):
        """Test execution with default quantity."""
        self.context.set(StateParameters.RAW_MATERIAL, 'copper_ore')
        self.context.set(StateParameters.REFINED_MATERIAL, 'copper')
        # No quantity specified, should default to 1
        
        craft_response = Mock()
        craft_response.data = Mock()
        craft_response.data.xp = 5
        craft_response.data.items = [Mock(code='copper', quantity=1)]
        
        with patch.object(self.action, '_wait_for_cooldown'):
            with patch('src.controller.actions.execute_material_transformation.crafting_api') as mock_craft:
                mock_craft.return_value = craft_response
                
                result = self.action.execute(self.client, self.context)
                
                self.assertTrue(result.success)
                
                # Verify CraftingSchema was called with quantity=1
                from artifactsmmo_api_client.models.crafting_schema import CraftingSchema
                mock_craft.assert_called_once()
                args = mock_craft.call_args
                body = args[1]['body']
                self.assertIsInstance(body, CraftingSchema)
                self.assertEqual(body.quantity, 1)
                
    def test_execute_crafting_fails(self):
        """Test when crafting API fails."""
        self.context.set(StateParameters.RAW_MATERIAL, 'copper_ore')
        self.context.set(StateParameters.REFINED_MATERIAL, 'copper')
        self.context.set(StateParameters.QUANTITY, 5)
        
        with patch.object(self.action, '_wait_for_cooldown'):
            with patch('src.controller.actions.execute_material_transformation.crafting_api') as mock_craft:
                mock_craft.return_value = None
                
                result = self.action.execute(self.client, self.context)
                
                self.assertFalse(result.success)
                self.assertIn("Crafting failed for copper", result.error)
                
    def test_execute_exception_handling(self):
        """Test exception handling."""
        self.context.set(StateParameters.RAW_MATERIAL, 'copper_ore')
        self.context.set(StateParameters.REFINED_MATERIAL, 'copper')
        self.context.set(StateParameters.QUANTITY, 5)
        
        with patch.object(self.action, '_wait_for_cooldown'):
            with patch('src.controller.actions.execute_material_transformation.crafting_api') as mock_craft:
                mock_craft.side_effect = Exception("Test error")
                
                result = self.action.execute(self.client, self.context)
                
                self.assertFalse(result.success)
                self.assertIn("Failed to execute transformation", result.error)
                
    def test_wait_for_cooldown_active(self):
        """Test waiting for active cooldown."""
        # Mock character with cooldown
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.cooldown = 3  # 3 second cooldown
        
        # No longer using nested action_config - using default buffer
        
        with patch('artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync') as mock_get:
            mock_get.return_value = char_response
            
            with patch('src.controller.actions.execute_material_transformation.time.sleep') as mock_sleep:
                self.action._wait_for_cooldown(self.client, 'test_character', self.context)
                
                # Should sleep for cooldown + default buffer (1)
                mock_sleep.assert_called_once_with(4)
                
    def test_wait_for_cooldown_none(self):
        """Test when no cooldown active."""
        # Mock character with no cooldown
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.cooldown = 0
        
        with patch('artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync') as mock_get:
            mock_get.return_value = char_response
            
            with patch('src.controller.actions.execute_material_transformation.time.sleep') as mock_sleep:
                self.action._wait_for_cooldown(self.client, 'test_character', self.context)
                
                # Should not sleep
                mock_sleep.assert_not_called()
                
    def test_wait_for_cooldown_exception(self):
        """Test cooldown check with exception."""
        with patch('artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync') as mock_get:
            mock_get.side_effect = Exception("API error")
            
            # Should not raise, just log warning
            self.action._wait_for_cooldown(self.client, 'test_character', self.context)
            
    def test_wait_for_cooldown_default_buffer(self):
        """Test cooldown with default buffer."""
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.cooldown = 2
        
        # Using default buffer of 1
        
        with patch('artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync') as mock_get:
            mock_get.return_value = char_response
            
            with patch('src.controller.actions.execute_material_transformation.time.sleep') as mock_sleep:
                self.action._wait_for_cooldown(self.client, 'test_character', self.context)
                
                # Should sleep for cooldown + default buffer (1)
                mock_sleep.assert_called_once_with(3)
                
    def test_transformation_result_structure(self):
        """Test the structure of transformation result."""
        self.context.set(StateParameters.RAW_MATERIAL, 'copper_ore')
        self.context.set(StateParameters.REFINED_MATERIAL, 'copper')
        self.context.set(StateParameters.QUANTITY, 5)
        
        craft_response = Mock()
        craft_response.data = Mock()
        craft_response.data.xp = 10
        craft_response.data.items = [
            Mock(code='copper', quantity=5),
            Mock(code='bonus_item', quantity=1)  # Extra item
        ]
        
        with patch.object(self.action, '_wait_for_cooldown'):
            with patch('src.controller.actions.execute_material_transformation.crafting_api') as mock_craft:
                mock_craft.return_value = craft_response
                
                result = self.action.execute(self.client, self.context)
                
                self.assertTrue(result.success)
                
                transformation = result.data['transformation']
                self.assertEqual(transformation['raw_material'], 'copper_ore')
                self.assertEqual(transformation['refined_material'], 'copper')
                self.assertEqual(transformation['quantity_requested'], 5)
                self.assertTrue(transformation['success'])
                self.assertEqual(transformation['xp_gained'], 10)
                
                # Should include all items produced
                self.assertEqual(len(transformation['items_produced']), 2)
                
    def test_crafting_with_no_items_produced(self):
        """Test crafting that produces no items (edge case)."""
        self.context.set(StateParameters.RAW_MATERIAL, 'test')
        self.context.set(StateParameters.REFINED_MATERIAL, 'test')
        self.context.set(StateParameters.QUANTITY, 1)
        
        craft_response = Mock()
        craft_response.data = Mock()
        craft_response.data.xp = 5
        craft_response.data.items = None  # No items
        
        with patch.object(self.action, '_wait_for_cooldown'):
            with patch('src.controller.actions.execute_material_transformation.crafting_api') as mock_craft:
                mock_craft.return_value = craft_response
                
                result = self.action.execute(self.client, self.context)
                
                self.assertTrue(result.success)
                self.assertEqual(result.data['items_produced'], [])


if __name__ == '__main__':
    unittest.main()