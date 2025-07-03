"""
Test module for AnalyzeMaterialsForTransformationAction.
"""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.analyze_materials_for_transformation import AnalyzeMaterialsForTransformationAction
from src.lib.action_context import ActionContext


class TestAnalyzeMaterialsForTransformationAction(unittest.TestCase):
    """Test cases for AnalyzeMaterialsForTransformationAction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = AnalyzeMaterialsForTransformationAction()
        self.client = Mock()
        
        # Create context with knowledge base
        self.context = ActionContext()
        self.context.character_name = "test_character"
        self.context.knowledge_base = Mock()
        self.context.knowledge_base.data = {}
        
    def test_initialization(self):
        """Test action initialization."""
        self.assertIsInstance(self.action, AnalyzeMaterialsForTransformationAction)
        
    def test_repr(self):
        """Test string representation."""
        self.assertEqual(repr(self.action), "AnalyzeMaterialsForTransformationAction()")
        
    def test_execute_with_target_item(self):
        """Test analyzing materials with a target item."""
        # Setup inventory
        self.context['inventory'] = [
            Mock(code='copper_ore', quantity=10),
            Mock(code='iron_ore', quantity=5)
        ]
        self.context['target_item'] = 'iron_sword'
        
        # Setup knowledge base
        self.context.knowledge_base.data = {
            'material_transformations': {
                'copper_ore': 'copper',
                'iron_ore': 'iron'
            }
        }
        
        # Mock item requirements
        with patch.object(self.action, '_get_item_requirements') as mock_get_req:
            mock_get_req.return_value = {'iron': 3, 'wood': 1}
            
            result = self.action.execute(self.client, self.context)
            
            self.assertTrue(result['success'])
            self.assertEqual(result['transformation_count'], 1)  # Only iron_ore needed
            transformations = result['transformations']
            self.assertEqual(len(transformations), 1)
            self.assertEqual(transformations[0], ('iron_ore', 'iron', 3))  # Only need 3 iron
            
    def test_execute_without_target_item(self):
        """Test analyzing materials without a target item."""
        # Setup inventory
        self.context['inventory'] = [
            Mock(code='copper_ore', quantity=10)
        ]
        
        # Setup knowledge base
        self.context.knowledge_base.data = {
            'material_transformations': {
                'copper_ore': 'copper'
            }
        }
        
        # Setup action config
        self.context['action_config'] = {
            'default_transform_quantity': 5
        }
        
        result = self.action.execute(self.client, self.context)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['transformation_count'], 1)
        transformations = result['transformations']
        self.assertEqual(transformations[0], ('copper_ore', 'copper', 5))
        
    def test_execute_no_transformations_available(self):
        """Test when no transformations are available."""
        self.context['inventory'] = [
            Mock(code='unknown_item', quantity=10)
        ]
        
        self.context.knowledge_base.data = {
            'material_transformations': {}
        }
        
        result = self.action.execute(self.client, self.context)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['transformation_count'], 0)
        self.assertEqual(result['transformations'], [])
        
    def test_execute_empty_inventory(self):
        """Test with empty inventory."""
        self.context['inventory'] = []
        
        result = self.action.execute(self.client, self.context)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['transformation_count'], 0)
        
    def test_execute_exception_handling(self):
        """Test exception handling."""
        self.context['inventory'] = [Mock(code='test', quantity=1)]
        
        # Make knowledge base raise exception
        self.context.knowledge_base.data = Mock(side_effect=Exception("Test error"))
        
        result = self.action.execute(self.client, self.context)
        
        self.assertFalse(result['success'])
        self.assertIn("Failed to analyze materials", result['error'])
        
    def test_build_inventory_dict_mixed_formats(self):
        """Test building inventory dict with mixed formats."""
        inventory = [
            Mock(code='item1', quantity=5),  # Object format
            {'code': 'item2', 'quantity': 3},  # Dict format
            {'code': 'item3'},  # Missing quantity
            Mock(code='item4', quantity=0),  # Zero quantity
            "invalid"  # Invalid format
        ]
        
        result = self.action._build_inventory_dict(inventory)
        
        self.assertEqual(result, {
            'item1': 5,
            'item2': 3
        })
        
    def test_get_transformation_mappings_from_items(self):
        """Test getting transformations from items data."""
        self.context.knowledge_base.data = {
            'items': {
                'copper': {
                    'craft_data': {
                        'items': [{'code': 'copper_ore'}]
                    }
                },
                'bronze': {  # Multiple inputs, should be skipped
                    'craft_data': {
                        'items': [
                            {'code': 'copper'},
                            {'code': 'tin'}
                        ]
                    }
                }
            }
        }
        
        result = self.action._get_transformation_mappings(self.context.knowledge_base)
        
        self.assertEqual(result, {'copper_ore': 'copper'})
        
    def test_is_raw_material(self):
        """Test raw material identification."""
        self.assertTrue(self.action._is_raw_material('copper_ore'))
        self.assertTrue(self.action._is_raw_material('iron_ore'))
        self.assertTrue(self.action._is_raw_material('ash_wood'))
        self.assertTrue(self.action._is_raw_material('coal'))
        
        self.assertFalse(self.action._is_raw_material('copper'))
        self.assertFalse(self.action._is_raw_material('iron'))
        self.assertFalse(self.action._is_raw_material('sword'))
        
    def test_get_item_requirements_success(self):
        """Test getting item requirements successfully."""
        # Mock API response
        item_response = Mock()
        item_response.data = Mock()
        item_response.data.craft = Mock()
        item_response.data.craft.items = [
            Mock(code='iron', quantity=3),
            Mock(code='wood', quantity=1)
        ]
        
        with patch('artifactsmmo_api_client.api.items.get_item_items_code_get.sync') as mock_api:
            mock_api.return_value = item_response
            
            result = self.action._get_item_requirements('iron_sword', self.client)
            
            self.assertEqual(result, {'iron': 3, 'wood': 1})
            
    def test_get_item_requirements_exception(self):
        """Test getting item requirements with exception."""
        with patch('artifactsmmo_api_client.api.items.get_item_items_code_get.sync') as mock_api:
            mock_api.side_effect = Exception("API error")
            
            result = self.action._get_item_requirements('error_item', self.client)
            
            self.assertEqual(result, {})
            
    def test_analyze_for_target_item_with_existing_materials(self):
        """Test analyzing when some refined materials already exist."""
        inventory_dict = {
            'copper_ore': 10,
            'copper': 2  # Already have some copper
        }
        
        transformations_map = {'copper_ore': 'copper'}
        
        with patch.object(self.action, '_get_item_requirements') as mock_get_req:
            mock_get_req.return_value = {'copper': 5}  # Need 5 total
            
            result = self.action._analyze_for_target_item(
                inventory_dict, transformations_map, 'copper_sword', self.client
            )
            
            # Should only transform 3 more (need 5, have 2)
            self.assertEqual(result, [('copper_ore', 'copper', 3)])
            
    def test_analyze_general_transformations_respects_config(self):
        """Test general transformations respect configuration."""
        inventory_dict = {'copper_ore': 100}
        transformations_map = {'copper_ore': 'copper'}
        
        # Set low default quantity
        self.context['action_config'] = {
            'default_transform_quantity': 2
        }
        
        result = self.action._analyze_general_transformations(
            inventory_dict, transformations_map, self.context
        )
        
        # Should only transform 2 despite having 100
        self.assertEqual(result, [('copper_ore', 'copper', 2)])


if __name__ == '__main__':
    unittest.main()