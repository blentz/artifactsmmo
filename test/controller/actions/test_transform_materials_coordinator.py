"""
Test module for TransformMaterialsCoordinatorAction.
"""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.transform_materials_coordinator import TransformMaterialsCoordinatorAction
from src.lib.action_context import ActionContext


class TestTransformMaterialsCoordinatorAction(unittest.TestCase):
    """Test cases for TransformMaterialsCoordinatorAction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = TransformMaterialsCoordinatorAction()
        self.client = Mock()
        
        # Create context
        self.context = ActionContext()
        self.context.character_name = "test_character"
        self.context.knowledge_base = Mock()
        self.context.map_state = Mock()
        
    def test_initialization(self):
        """Test action initialization."""
        self.assertIsInstance(self.action, TransformMaterialsCoordinatorAction)
        
    def test_repr(self):
        """Test string representation."""
        self.assertEqual(repr(self.action), "TransformMaterialsCoordinatorAction()")
        
    def test_goap_parameters(self):
        """Test GOAP parameters are defined."""
        self.assertEqual(self.action.conditions, {
            'character_status': {
                'alive': True,
                'safe': True,
            },
            'inventory_status': {
                'has_raw_materials': True
            }
        })
        
        self.assertEqual(self.action.reactions, {
            'inventory_status': {
                'has_refined_materials': True,
                'materials_sufficient': True
            }
        })
        
        self.assertEqual(self.action.weights, {"inventory_status.has_refined_materials": 15})
        
    def test_execute_character_api_fails(self):
        """Test when character API fails."""
        with patch('src.controller.actions.transform_materials_coordinator.get_character_api') as mock_get_char:
            mock_get_char.return_value = None
            
            result = self.action.execute(self.client, self.context)
            
            self.assertFalse(result['success'])
            self.assertIn('Could not get character data', result['error'])
            
    def test_execute_no_raw_materials(self):
        """Test when no raw materials found."""
        # Mock character data
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.inventory = []
        
        with patch('src.controller.actions.transform_materials_coordinator.get_character_api') as mock_get_char:
            mock_get_char.return_value = char_response
            
            # Mock analyze action to return no transformations
            with patch('src.controller.actions.transform_materials_coordinator.AnalyzeMaterialsForTransformationAction') as mock_analyze_class:
                mock_analyze = Mock()
                mock_analyze.execute.return_value = {'success': True}
                mock_analyze_class.return_value = mock_analyze
                
                # Mock empty transformations in context
                def set_empty_transformations(client, context):
                    context.set_result('transformations_needed', [])
                    return {'success': True}
                
                mock_analyze.execute.side_effect = set_empty_transformations
                
                result = self.action.execute(self.client, self.context)
                
                self.assertFalse(result['success'])
                self.assertIn('No raw materials found that need transformation', result['error'])
                
    def test_execute_analyze_fails(self):
        """Test when analysis step fails."""
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.inventory = [Mock(code='copper_ore', quantity=5)]
        
        with patch('src.controller.actions.transform_materials_coordinator.get_character_api') as mock_get_char:
            mock_get_char.return_value = char_response
            
            with patch('src.controller.actions.transform_materials_coordinator.AnalyzeMaterialsForTransformationAction') as mock_analyze_class:
                mock_analyze = Mock()
                mock_analyze.execute.return_value = {'success': False}
                mock_analyze_class.return_value = mock_analyze
                
                result = self.action.execute(self.client, self.context)
                
                self.assertFalse(result['success'])
                self.assertIn('Failed to analyze materials', result['error'])
                
    def test_execute_workshop_determination_fails(self):
        """Test when workshop determination fails."""
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.inventory = [Mock(code='copper_ore', quantity=5)]
        
        with patch('src.controller.actions.transform_materials_coordinator.get_character_api') as mock_get_char:
            mock_get_char.return_value = char_response
            
            # Mock successful analysis
            with patch('src.controller.actions.transform_materials_coordinator.AnalyzeMaterialsForTransformationAction') as mock_analyze_class:
                mock_analyze = Mock()
                
                def set_transformations(client, context):
                    context.set_result('transformations_needed', [('copper_ore', 'copper', 5)])
                    return {'success': True}
                
                mock_analyze.execute.side_effect = set_transformations
                mock_analyze_class.return_value = mock_analyze
                
                # Mock failed workshop determination
                with patch('src.controller.actions.transform_materials_coordinator.DetermineWorkshopRequirementsAction') as mock_workshop_class:
                    mock_workshop = Mock()
                    mock_workshop.execute.return_value = {'success': False}
                    mock_workshop_class.return_value = mock_workshop
                    
                    result = self.action.execute(self.client, self.context)
                    
                    self.assertFalse(result['success'])
                    self.assertIn('Failed to determine workshop requirements', result['error'])
                    
    def test_execute_successful_single_transformation(self):
        """Test successful execution with single transformation."""
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.inventory = [Mock(code='copper_ore', quantity=5)]
        
        with patch('src.controller.actions.transform_materials_coordinator.get_character_api') as mock_get_char:
            mock_get_char.return_value = char_response
            
            # Mock all bridge actions
            with patch('src.controller.actions.transform_materials_coordinator.AnalyzeMaterialsForTransformationAction') as mock_analyze_class:
                mock_analyze = Mock()
                
                def set_transformations(client, context):
                    context.set_result('transformations_needed', [('copper_ore', 'copper', 5)])
                    return {'success': True}
                
                mock_analyze.execute.side_effect = set_transformations
                mock_analyze_class.return_value = mock_analyze
                
                with patch('src.controller.actions.transform_materials_coordinator.DetermineWorkshopRequirementsAction') as mock_workshop_class:
                    mock_workshop = Mock()
                    
                    def set_workshop_reqs(client, context):
                        context.set_result('workshop_requirements', [{
                            'raw_material': 'copper_ore',
                            'refined_material': 'copper',
                            'quantity': 5,
                            'workshop_type': 'mining'
                        }])
                        return {'success': True}
                    
                    mock_workshop.execute.side_effect = set_workshop_reqs
                    mock_workshop_class.return_value = mock_workshop
                    
                    with patch('src.controller.actions.transform_materials_coordinator.NavigateToWorkshopAction') as mock_nav_class:
                        mock_nav = Mock()
                        mock_nav.execute.return_value = {'success': True}
                        mock_nav_class.return_value = mock_nav
                        
                        with patch('src.controller.actions.transform_materials_coordinator.ExecuteMaterialTransformationAction') as mock_transform_class:
                            mock_transform = Mock()
                            
                            def set_transformation_result(client, context):
                                context.set_result('last_transformation', {
                                    'raw_material': 'copper_ore',
                                    'refined_material': 'copper',
                                    'quantity': 5,
                                    'success': True
                                })
                                return {'success': True}
                            
                            mock_transform.execute.side_effect = set_transformation_result
                            mock_transform_class.return_value = mock_transform
                            
                            with patch('src.controller.actions.transform_materials_coordinator.VerifyTransformationResultsAction') as mock_verify_class:
                                mock_verify = Mock()
                                mock_verify.execute.return_value = {
                                    'success': True,
                                    'verification_results': [{'verified': True}]
                                }
                                mock_verify_class.return_value = mock_verify
                                
                                result = self.action.execute(self.client, self.context)
                                
                                self.assertTrue(result['success'])
                                self.assertEqual(result['total_transformations'], 1)
                                self.assertEqual(len(result['materials_transformed']), 1)
                                
    def test_execute_multiple_transformations_same_workshop(self):
        """Test multiple transformations at same workshop."""
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.inventory = [
            Mock(code='copper_ore', quantity=5),
            Mock(code='iron_ore', quantity=3)
        ]
        
        with patch('src.controller.actions.transform_materials_coordinator.get_character_api') as mock_get_char:
            mock_get_char.return_value = char_response
            
            # Setup all mocks for two transformations
            with patch('src.controller.actions.transform_materials_coordinator.AnalyzeMaterialsForTransformationAction') as mock_analyze_class:
                mock_analyze = Mock()
                
                def set_transformations(client, context):
                    context.set_result('transformations_needed', [
                        ('copper_ore', 'copper', 5),
                        ('iron_ore', 'iron', 3)
                    ])
                    return {'success': True}
                
                mock_analyze.execute.side_effect = set_transformations
                mock_analyze_class.return_value = mock_analyze
                
                with patch('src.controller.actions.transform_materials_coordinator.DetermineWorkshopRequirementsAction') as mock_workshop_class:
                    mock_workshop = Mock()
                    
                    def set_workshop_reqs(client, context):
                        context.set_result('workshop_requirements', [
                            {
                                'raw_material': 'copper_ore',
                                'refined_material': 'copper',
                                'quantity': 5,
                                'workshop_type': 'mining'
                            },
                            {
                                'raw_material': 'iron_ore',
                                'refined_material': 'iron',
                                'quantity': 3,
                                'workshop_type': 'mining'  # Same workshop
                            }
                        ])
                        return {'success': True}
                    
                    mock_workshop.execute.side_effect = set_workshop_reqs
                    mock_workshop_class.return_value = mock_workshop
                    
                    with patch('src.controller.actions.transform_materials_coordinator.NavigateToWorkshopAction') as mock_nav_class:
                        mock_nav = Mock()
                        mock_nav.execute.return_value = {'success': True}
                        mock_nav_class.return_value = mock_nav
                        
                        with patch('src.controller.actions.transform_materials_coordinator.ExecuteMaterialTransformationAction') as mock_transform_class:
                            mock_transform = Mock()
                            
                            transformation_count = [0]
                            
                            def set_transformation_result(client, context):
                                transformation_count[0] += 1
                                if transformation_count[0] == 1:
                                    context.set_result('last_transformation', {
                                        'raw_material': 'copper_ore',
                                        'refined_material': 'copper',
                                        'quantity': 5,
                                        'success': True
                                    })
                                else:
                                    context.set_result('last_transformation', {
                                        'raw_material': 'iron_ore',
                                        'refined_material': 'iron',
                                        'quantity': 3,
                                        'success': True
                                    })
                                return {'success': True}
                            
                            mock_transform.execute.side_effect = set_transformation_result
                            mock_transform_class.return_value = mock_transform
                            
                            with patch('src.controller.actions.transform_materials_coordinator.VerifyTransformationResultsAction') as mock_verify_class:
                                mock_verify = Mock()
                                mock_verify.execute.return_value = {'success': True}
                                mock_verify_class.return_value = mock_verify
                                
                                result = self.action.execute(self.client, self.context)
                                
                                self.assertTrue(result['success'])
                                self.assertEqual(result['total_transformations'], 2)
                                
                                # Should only navigate once since same workshop
                                mock_nav.execute.assert_called_once()
                                
    def test_execute_navigation_fails(self):
        """Test when navigation to workshop fails."""
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.inventory = [Mock(code='copper_ore', quantity=5)]
        
        with patch('src.controller.actions.transform_materials_coordinator.get_character_api') as mock_get_char:
            mock_get_char.return_value = char_response
            
            # Setup mocks
            with patch('src.controller.actions.transform_materials_coordinator.AnalyzeMaterialsForTransformationAction') as mock_analyze_class:
                mock_analyze = Mock()
                
                def set_transformations(client, context):
                    context.set_result('transformations_needed', [('copper_ore', 'copper', 5)])
                    return {'success': True}
                
                mock_analyze.execute.side_effect = set_transformations
                mock_analyze_class.return_value = mock_analyze
                
                with patch('src.controller.actions.transform_materials_coordinator.DetermineWorkshopRequirementsAction') as mock_workshop_class:
                    mock_workshop = Mock()
                    
                    def set_workshop_reqs(client, context):
                        context.set_result('workshop_requirements', [{
                            'raw_material': 'copper_ore',
                            'refined_material': 'copper',
                            'quantity': 5,
                            'workshop_type': 'mining'
                        }])
                        return {'success': True}
                    
                    mock_workshop.execute.side_effect = set_workshop_reqs
                    mock_workshop_class.return_value = mock_workshop
                    
                    with patch('src.controller.actions.transform_materials_coordinator.NavigateToWorkshopAction') as mock_nav_class:
                        mock_nav = Mock()
                        mock_nav.execute.return_value = {'success': False}  # Navigation fails
                        mock_nav_class.return_value = mock_nav
                        
                        with patch('src.controller.actions.transform_materials_coordinator.VerifyTransformationResultsAction') as mock_verify_class:
                            mock_verify = Mock()
                            mock_verify.execute.return_value = {'success': True}
                            mock_verify_class.return_value = mock_verify
                            
                            result = self.action.execute(self.client, self.context)
                            
                            # Should fail since all transformations failed
                            self.assertFalse(result['success'])
                            self.assertIn('All material transformations failed', result['error'])
                            
    def test_execute_exception_handling(self):
        """Test exception handling in coordinator."""
        with patch('src.controller.actions.transform_materials_coordinator.get_character_api') as mock_get_char:
            mock_get_char.side_effect = Exception("Test error")
            
            result = self.action.execute(self.client, self.context)
            
            self.assertFalse(result['success'])
            self.assertIn("Material transformation workflow failed", result['error'])
            
    def test_execute_with_target_item(self):
        """Test execution with target item specified."""
        self.context['target_item'] = 'iron_sword'
        
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.inventory = [Mock(code='iron_ore', quantity=5)]
        
        with patch('src.controller.actions.transform_materials_coordinator.get_character_api') as mock_get_char:
            mock_get_char.return_value = char_response
            
            # Setup minimal mocks for success path
            with patch('src.controller.actions.transform_materials_coordinator.AnalyzeMaterialsForTransformationAction') as mock_analyze_class:
                mock_analyze = Mock()
                
                def set_transformations(client, context):
                    context.set_result('transformations_needed', [('iron_ore', 'iron', 3)])
                    return {'success': True}
                
                mock_analyze.execute.side_effect = set_transformations
                mock_analyze_class.return_value = mock_analyze
                
                with patch('src.controller.actions.transform_materials_coordinator.DetermineWorkshopRequirementsAction') as mock_workshop_class:
                    mock_workshop = Mock()
                    
                    def set_workshop_reqs(client, context):
                        context.set_result('workshop_requirements', [{
                            'raw_material': 'iron_ore',
                            'refined_material': 'iron',
                            'quantity': 3,
                            'workshop_type': 'mining'
                        }])
                        return {'success': True}
                    
                    mock_workshop.execute.side_effect = set_workshop_reqs
                    mock_workshop_class.return_value = mock_workshop
                    
                    with patch('src.controller.actions.transform_materials_coordinator.NavigateToWorkshopAction') as mock_nav_class:
                        mock_nav = Mock()
                        mock_nav.execute.return_value = {'success': True}
                        mock_nav_class.return_value = mock_nav
                        
                        with patch('src.controller.actions.transform_materials_coordinator.ExecuteMaterialTransformationAction') as mock_transform_class:
                            mock_transform = Mock()
                            
                            def set_transformation_result(client, context):
                                context.set_result('last_transformation', {
                                    'raw_material': 'iron_ore',
                                    'refined_material': 'iron',
                                    'quantity': 3,
                                    'success': True
                                })
                                return {'success': True}
                            
                            mock_transform.execute.side_effect = set_transformation_result
                            mock_transform_class.return_value = mock_transform
                            
                            with patch('src.controller.actions.transform_materials_coordinator.VerifyTransformationResultsAction') as mock_verify_class:
                                mock_verify = Mock()
                                mock_verify.execute.return_value = {'success': True}
                                mock_verify_class.return_value = mock_verify
                                
                                result = self.action.execute(self.client, self.context)
                                
                                self.assertTrue(result['success'])
                                self.assertEqual(result['target_item'], 'iron_sword')
                                
                                # Verify target_item was passed to analyze action
                                analyze_context = mock_analyze.execute.call_args[0][1]
                                self.assertEqual(analyze_context.get('target_item'), 'iron_sword')


if __name__ == '__main__':
    unittest.main()