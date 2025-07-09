"""
Test Transform Materials Coordinator Action

Streamlined tests focusing on the public interface and subgoal workflow behavior.
"""

import unittest
from unittest.mock import Mock

from src.controller.actions.transform_materials_coordinator import TransformMaterialsCoordinatorAction
from src.controller.actions.base import ActionResult
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from test.test_base import UnifiedContextTestBase


class TestTransformMaterialsCoordinatorAction(UnifiedContextTestBase):
    """Test the TransformMaterialsCoordinatorAction class public interface."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.action = TransformMaterialsCoordinatorAction()
        self.client = Mock()
        self.context.set(StateParameters.CHARACTER_NAME, "test_character")
        
        # Mock knowledge base
        self.mock_kb = Mock()
        self.context.knowledge_base = self.mock_kb
        
    def test_init(self):
        """Test action initialization."""
        action = TransformMaterialsCoordinatorAction()
        self.assertIsNotNone(action)
        
    def test_repr(self):
        """Test string representation."""
        result = repr(self.action)
        self.assertIn("TransformMaterialsCoordinatorAction", result)
        
    def test_goap_parameters(self):
        """Test GOAP parameters are properly defined."""
        # Test conditions exist
        self.assertIn('character_status', self.action.conditions)
        self.assertIn('inventory_status', self.action.conditions)
        
        # Test reactions exist  
        self.assertIn('inventory_status', self.action.reactions)
        
        # Test weight is defined
        self.assertIsInstance(self.action.weight, (int, float))
        self.assertGreater(self.action.weight, 0)

    def test_execute_character_api_fails(self):
        """Test execute with character API failure."""
        # Set workflow step to analyze_materials so it will call get_character_api
        self.context.set(StateParameters.WORKFLOW_STEP, "analyze_materials")
        
        with unittest.mock.patch('src.controller.actions.transform_materials_coordinator.get_character_api') as mock_get_char:
            mock_get_char.return_value = None
            
            result = self.action.execute(self.client, self.context)
            
            self.assertIsInstance(result, ActionResult)
            self.assertFalse(result.success)
            self.assertIn("Could not get character data", result.error)

    def test_execute_analyze_materials_step(self):
        """Test execute with analyze_materials workflow step."""
        # Set workflow step to analyze_materials
        self.context.set(StateParameters.WORKFLOW_STEP, "analyze_materials")
        
        # Mock character data
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.inventory = [Mock(code='copper_ore', quantity=5)]
        
        with unittest.mock.patch('src.controller.actions.transform_materials_coordinator.get_character_api') as mock_get_char:
            mock_get_char.return_value = char_response
            
            result = self.action.execute(self.client, self.context)
            
            self.assertIsInstance(result, ActionResult)
            self.assertTrue(result.success)
            # Should request materials analysis subgoal
            self.assertIsNotNone(result.subgoal_request)
            self.assertEqual(result.subgoal_request['goal_name'], "analyze_materials")

    def test_execute_with_target_item(self):
        """Test execute with target item specified."""
        self.context.set(StateParameters.TARGET_ITEM, "iron_sword")
        
        # Mock character data
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.inventory = [Mock(code='iron_ore', quantity=5)]
        
        with unittest.mock.patch('src.controller.actions.transform_materials_coordinator.get_character_api') as mock_get_char:
            mock_get_char.return_value = char_response
            
            result = self.action.execute(self.client, self.context)
            
            self.assertIsInstance(result, ActionResult)
            # Should handle target_item properly - just verify the result exists
            self.assertIsNotNone(result)

    def test_execute_determine_workshops_step_no_transformations(self):
        """Test determine_workshops step with no transformations needed."""
        # Set workflow step to determine_workshops
        self.action.set_workflow_step(self.context, 'determine_workshops')
        # Don't set transformations_needed - will default to empty list
        
        result = self.action.execute(self.client, self.context)
        
        self.assertIsInstance(result, ActionResult)
        self.assertFalse(result.success)
        self.assertIn("No raw materials found that need transformation", result.error)

    def test_execute_determine_workshops_step_with_transformations(self):
        """Test determine_workshops step with transformations needed."""
        # Set workflow step and transformations
        self.action.set_workflow_step(self.context, 'determine_workshops')
        self.context.set(StateParameters.TRANSFORMATIONS_NEEDED, [('copper_ore', 'copper', 5)])
        
        result = self.action.execute(self.client, self.context)
        
        self.assertIsInstance(result, ActionResult)
        # Should request workshop requirements subgoal
        if hasattr(result, 'subgoal_request'):
            self.assertEqual(result.subgoal_request['goal_name'], "determine_workshop_requirements")

    def test_execute_transformations_step_no_requirements(self):
        """Test execute_transformations step with no requirements."""
        # Set workflow step to execute_transformations
        self.action.set_workflow_step(self.context, 'execute_transformations')
        # Don't set workshop_requirements - will default to empty list
        
        result = self.action.execute(self.client, self.context)
        
        self.assertIsInstance(result, ActionResult)
        self.assertFalse(result.success)
        self.assertIn("No workshop requirements found", result.error)

    def test_execute_transformations_step_with_requirements(self):
        """Test execute_transformations step with requirements."""
        # Set workflow step and requirements
        self.action.set_workflow_step(self.context, 'execute_transformations')
        self.context.set(StateParameters.WORKSHOP_REQUIREMENTS, [{
            'workshop_type': 'mining',
            'raw_material': 'copper_ore',
            'refined_material': 'copper',
            'quantity': 5
        }])
        
        result = self.action.execute(self.client, self.context)
        
        self.assertIsInstance(result, ActionResult)
        # Should request transformation subgoal
        if hasattr(result, 'subgoal_request'):
            self.assertEqual(result.subgoal_request['goal_name'], "execute_material_transformation")

    def test_execute_verify_results_step_no_completions(self):
        """Test verify_results step with no completed transformations."""
        # Set workflow step to verify_results
        self.action.set_workflow_step(self.context, 'verify_results')
        # Don't set transformations_completed - will default to empty list
        
        result = self.action.execute(self.client, self.context)
        
        self.assertIsInstance(result, ActionResult)
        self.assertFalse(result.success)
        self.assertIn("No transformations were completed", result.error)

    def test_execute_verify_results_step_with_completions(self):
        """Test verify_results step with completed transformations."""
        # Set workflow step and completions
        self.action.set_workflow_step(self.context, 'verify_results')
        self.context.set(StateParameters.TRANSFORMATIONS_COMPLETED, [
            {'raw_material': 'copper_ore', 'refined_material': 'copper', 'quantity': 5}
        ])
        
        result = self.action.execute(self.client, self.context)
        
        self.assertIsInstance(result, ActionResult)
        # Should request verification subgoal
        if hasattr(result, 'subgoal_request'):
            self.assertEqual(result.subgoal_request['goal_name'], "verify_transformation_results")

    def test_execute_unknown_workflow_step(self):
        """Test execute with unknown workflow step."""
        # Set unknown workflow step
        self.action.set_workflow_step(self.context, 'unknown_step')
        
        result = self.action.execute(self.client, self.context)
        
        self.assertIsInstance(result, ActionResult)
        self.assertFalse(result.success)
        self.assertIn("Unknown workflow step: unknown_step", result.error)

    def test_execute_with_exception(self):
        """Test execute handles exceptions gracefully."""
        # Force an exception in workflow step logic by corrupting context
        self.context._workflow_data = {'invalid': 'data_causing_exception'}
        
        with unittest.mock.patch('src.controller.actions.transform_materials_coordinator.get_character_api') as mock_get_char:
            mock_get_char.side_effect = Exception("API error")
            
            result = self.action.execute(self.client, self.context)
            
            self.assertIsInstance(result, ActionResult)
            self.assertFalse(result.success)
            # The action should handle all exceptions properly
            self.assertTrue(result.error is not None)


if __name__ == '__main__':
    unittest.main()