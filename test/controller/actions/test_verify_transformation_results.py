"""
Test module for VerifyTransformationResultsAction.
"""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.verify_transformation_results import VerifyTransformationResultsAction
from src.lib.action_context import ActionContext


class TestVerifyTransformationResultsAction(unittest.TestCase):
    """Test cases for VerifyTransformationResultsAction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = VerifyTransformationResultsAction()
        self.client = Mock()
        
        # Create context
        self.context = ActionContext()
        self.context.character_name = "test_character"
        self.context.knowledge_base = Mock()
        
    def test_initialization(self):
        """Test action initialization."""
        self.assertIsInstance(self.action, VerifyTransformationResultsAction)
        
    def test_repr(self):
        """Test string representation."""
        self.assertEqual(repr(self.action), "VerifyTransformationResultsAction()")
        
    def test_execute_no_transformations(self):
        """Test execution with no transformations to verify."""
        self.context['transformations_completed'] = []
        
        result = self.action.execute(self.client, self.context)
        
        self.assertTrue(result['success'])
        self.assertTrue(result['verified'])
        self.assertIn("No transformations to verify", result['message'])
        
    def test_execute_all_verified(self):
        """Test when all transformations are verified."""
        self.context['transformations_completed'] = [
            {
                'raw_material': 'copper_ore',
                'refined_material': 'copper',
                'quantity': 5
            },
            {
                'raw_material': 'iron_ore',
                'refined_material': 'iron',
                'quantity': 3
            }
        ]
        
        # Mock inventory check
        with patch('src.controller.actions.verify_transformation_results.CheckInventoryAction') as mock_check_class:
            mock_check = Mock()
            mock_check.execute.return_value = {
                'success': True,
                'inventory_status': {
                    'copper': {'available': 5},
                    'iron': {'available': 3}
                }
            }
            mock_check_class.return_value = mock_check
            
            result = self.action.execute(self.client, self.context)
            
            self.assertTrue(result['success'])
            self.assertTrue(result['all_verified'])
            self.assertEqual(len(result['verification_results']), 2)
            
            # Check individual verifications
            for verification in result['verification_results']:
                self.assertTrue(verification['verified'])
                
    def test_execute_partial_verification(self):
        """Test when some transformations fail verification."""
        self.context['transformations_completed'] = [
            {
                'raw_material': 'copper_ore',
                'refined_material': 'copper',
                'quantity': 5
            },
            {
                'raw_material': 'iron_ore',
                'refined_material': 'iron',
                'quantity': 3
            }
        ]
        
        # Mock inventory check - iron missing
        with patch('src.controller.actions.verify_transformation_results.CheckInventoryAction') as mock_check_class:
            mock_check = Mock()
            mock_check.execute.return_value = {
                'success': True,
                'inventory_status': {
                    'copper': {'available': 5}
                    # iron not in inventory
                }
            }
            mock_check_class.return_value = mock_check
            
            result = self.action.execute(self.client, self.context)
            
            self.assertTrue(result['success'])  # Action succeeds even if verification fails
            self.assertFalse(result['all_verified'])
            
            # Check individual results
            verifications = result['verification_results']
            copper_result = next(v for v in verifications if v['material'] == 'copper')
            iron_result = next(v for v in verifications if v['material'] == 'iron')
            
            self.assertTrue(copper_result['verified'])
            self.assertEqual(copper_result['available'], 5)
            
            self.assertFalse(iron_result['verified'])
            self.assertEqual(iron_result['available'], 0)
            
    def test_execute_insufficient_quantity(self):
        """Test when quantity is insufficient."""
        self.context['transformations_completed'] = [
            {
                'raw_material': 'copper_ore',
                'refined_material': 'copper',
                'quantity': 5
            }
        ]
        
        # Mock inventory check - only 3 copper available
        with patch('src.controller.actions.verify_transformation_results.CheckInventoryAction') as mock_check_class:
            mock_check = Mock()
            mock_check.execute.return_value = {
                'success': True,
                'inventory_status': {
                    'copper': {'available': 3}
                }
            }
            mock_check_class.return_value = mock_check
            
            result = self.action.execute(self.client, self.context)
            
            self.assertTrue(result['success'])
            self.assertFalse(result['all_verified'])
            
            verification = result['verification_results'][0]
            self.assertFalse(verification['verified'])
            self.assertEqual(verification['expected'], 5)
            self.assertEqual(verification['available'], 3)
            
    def test_execute_inventory_check_fails(self):
        """Test when inventory check fails."""
        self.context['transformations_completed'] = [
            {'refined_material': 'copper', 'quantity': 5}
        ]
        
        with patch('src.controller.actions.verify_transformation_results.CheckInventoryAction') as mock_check_class:
            mock_check = Mock()
            mock_check.execute.return_value = {'success': False}
            mock_check_class.return_value = mock_check
            
            result = self.action.execute(self.client, self.context)
            
            self.assertFalse(result['success'])
            self.assertIn("Could not verify inventory", result['error'])
            
    def test_execute_exception_handling(self):
        """Test exception handling."""
        self.context['transformations_completed'] = [
            {'refined_material': 'copper', 'quantity': 5}
        ]
        
        with patch('src.controller.actions.verify_transformation_results.CheckInventoryAction') as mock_check_class:
            mock_check_class.side_effect = Exception("Test error")
            
            result = self.action.execute(self.client, self.context)
            
            self.assertFalse(result['success'])
            self.assertIn("Failed to verify transformation results", result['error'])
            
    def test_duplicate_materials_handling(self):
        """Test handling of duplicate materials in transformations."""
        self.context['transformations_completed'] = [
            {
                'raw_material': 'copper_ore',
                'refined_material': 'copper',
                'quantity': 5
            },
            {
                'raw_material': 'more_copper_ore',
                'refined_material': 'copper',  # Same refined material
                'quantity': 3
            }
        ]
        
        with patch('src.controller.actions.verify_transformation_results.CheckInventoryAction') as mock_check_class:
            mock_check = Mock()
            mock_check.execute.return_value = {
                'success': True,
                'inventory_status': {
                    'copper': {'available': 8}  # Total from both transformations
                }
            }
            mock_check_class.return_value = mock_check
            
            result = self.action.execute(self.client, self.context)
            
            # Should only check copper once in inventory
            mock_check.execute.assert_called_once()
            check_context = mock_check.execute.call_args[0][1]
            self.assertEqual(check_context['required_items'], ['copper'])
            
            # Both transformations should be verified
            self.assertTrue(result['all_verified'])
            self.assertEqual(len(result['verification_results']), 2)
            
    def test_transformation_without_quantity(self):
        """Test transformation without quantity field."""
        self.context['transformations_completed'] = [
            {
                'refined_material': 'copper'
                # No quantity field
            }
        ]
        
        with patch('src.controller.actions.verify_transformation_results.CheckInventoryAction') as mock_check_class:
            mock_check = Mock()
            mock_check.execute.return_value = {
                'success': True,
                'inventory_status': {
                    'copper': {'available': 1}
                }
            }
            mock_check_class.return_value = mock_check
            
            result = self.action.execute(self.client, self.context)
            
            self.assertTrue(result['success'])
            self.assertTrue(result['all_verified'])
            
            verification = result['verification_results'][0]
            self.assertEqual(verification['expected'], 0)  # Default when not specified
            self.assertTrue(verification['verified'])  # 1 >= 0
            
    def test_check_inventory_context_preservation(self):
        """Test that original context is preserved when calling CheckInventoryAction."""
        self.context['transformations_completed'] = [
            {'refined_material': 'copper', 'quantity': 5}
        ]
        self.context['some_other_data'] = 'preserved'
        
        with patch('src.controller.actions.verify_transformation_results.CheckInventoryAction') as mock_check_class:
            mock_check = Mock()
            mock_check.execute.return_value = {
                'success': True,
                'inventory_status': {'copper': {'available': 5}}
            }
            mock_check_class.return_value = mock_check
            
            result = self.action.execute(self.client, self.context)
            
            # Check that CheckInventoryAction received a context with original data
            check_context = mock_check.execute.call_args[0][1]
            self.assertEqual(check_context.character_name, 'test_character')
            self.assertEqual(check_context.get('some_other_data'), 'preserved')
            self.assertEqual(check_context['required_items'], ['copper'])


if __name__ == '__main__':
    unittest.main()