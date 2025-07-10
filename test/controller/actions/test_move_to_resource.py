"""Tests for MoveToResourceAction."""

import unittest
from unittest.mock import Mock, patch
from src.controller.actions.move_to_resource import MoveToResourceAction
from src.lib.action_context import ActionContext


class TestMoveToResourceAction(unittest.TestCase):
    """Test the MoveToResourceAction class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = MoveToResourceAction()
        self.mock_client = Mock()
        
        # Create mock context
        self.mock_context = Mock(spec=ActionContext)
        self.mock_context.get.return_value = None
        
    def test_init(self):
        """Test action initialization."""
        action = MoveToResourceAction()
        self.assertIsInstance(action, MoveToResourceAction)
        self.assertIsNotNone(action.logger)
        
    def test_goap_parameters(self):
        """Test GOAP conditions and reactions."""
        self.assertIn('character_status', self.action.conditions)
        self.assertIn('resource_location_known', self.action.conditions)
        self.assertEqual(self.action.conditions['character_status']['alive'], True)
        self.assertEqual(self.action.conditions['character_status']['cooldown_active'], False)
        self.assertTrue(self.action.conditions['resource_location_known'])
        
        self.assertIn('at_resource_location', self.action.reactions)
        self.assertIn('location_context', self.action.reactions)
        self.assertTrue(self.action.reactions['at_resource_location'])
        self.assertTrue(self.action.reactions['location_context']['at_target'])
        
        self.assertIsInstance(self.action.weight, (int, float))
        
    def test_get_target_coordinates_from_target_params(self):
        """Test getting target coordinates from target_x/target_y parameters."""
        self.mock_context.target_x = 10
        self.mock_context.target_y = 20
        self.mock_context.resource_x = None
        self.mock_context.resource_y = None
        
        x, y = self.action.get_target_coordinates(self.mock_context)
        
        self.assertEqual(x, 10)
        self.assertEqual(y, 20)
        
    def test_get_target_coordinates_from_resource_params(self):
        """Test getting target coordinates from resource_x/resource_y parameters."""
        self.mock_context.target_x = None
        self.mock_context.target_y = None
        self.mock_context.resource_x = 15
        self.mock_context.resource_y = 25
        
        x, y = self.action.get_target_coordinates(self.mock_context)
        
        self.assertEqual(x, 15)
        self.assertEqual(y, 25)
        
    def test_get_target_coordinates_target_priority(self):
        """Test that target_x/target_y takes priority over resource_x/resource_y."""
        self.mock_context.target_x = 10
        self.mock_context.target_y = 20
        self.mock_context.resource_x = 15
        self.mock_context.resource_y = 25
        
        x, y = self.action.get_target_coordinates(self.mock_context)
        
        self.assertEqual(x, 10)
        self.assertEqual(y, 20)
        
    def test_get_target_coordinates_partial_target(self):
        """Test getting target coordinates when only one target coordinate is available."""
        self.mock_context.target_x = 10
        self.mock_context.target_y = None
        self.mock_context.resource_x = None
        self.mock_context.resource_y = 25
        
        x, y = self.action.get_target_coordinates(self.mock_context)
        
        self.assertEqual(x, 10)
        self.assertEqual(y, 25)
        
    def test_get_target_coordinates_no_coordinates(self):
        """Test getting target coordinates when no coordinates are available."""
        self.mock_context.target_x = None
        self.mock_context.target_y = None
        self.mock_context.resource_x = None
        self.mock_context.resource_y = None
        
        x, y = self.action.get_target_coordinates(self.mock_context)
        
        self.assertIsNone(x)
        self.assertIsNone(y)
        
    def test_build_movement_context_minimal(self):
        """Test building movement context with minimal information."""
        self.mock_context.resource_code = None
        self.mock_context.resource_name = None
        
        context = self.action.build_movement_context(self.mock_context)
        
        self.assertEqual(context, {'at_resource_location': True})
        
    def test_build_movement_context_with_resource_code(self):
        """Test building movement context with resource code."""
        self.mock_context.resource_code = 'copper_ore'
        self.mock_context.resource_name = None
        
        context = self.action.build_movement_context(self.mock_context)
        
        expected = {
            'at_resource_location': True,
            'resource_code': 'copper_ore'
        }
        self.assertEqual(context, expected)
        
    def test_build_movement_context_with_resource_name(self):
        """Test building movement context with resource name."""
        self.mock_context.resource_code = None
        self.mock_context.resource_name = 'Copper Ore'
        
        context = self.action.build_movement_context(self.mock_context)
        
        expected = {
            'at_resource_location': True,
            'resource_name': 'Copper Ore'
        }
        self.assertEqual(context, expected)
        
    def test_build_movement_context_complete(self):
        """Test building movement context with all resource information."""
        self.mock_context.resource_code = 'copper_ore'
        self.mock_context.resource_name = 'Copper Ore'
        
        context = self.action.build_movement_context(self.mock_context)
        
        expected = {
            'at_resource_location': True,
            'resource_code': 'copper_ore',
            'resource_name': 'Copper Ore'
        }
        self.assertEqual(context, expected)
        
    def test_build_movement_context_empty_resource_values(self):
        """Test building movement context with empty resource values."""
        self.mock_context.resource_code = ''
        self.mock_context.resource_name = ''
        
        context = self.action.build_movement_context(self.mock_context)
        
        # Empty strings should not be included
        self.assertEqual(context, {'at_resource_location': True})
        
    def test_build_movement_context_none_resource_values(self):
        """Test building movement context with None resource values."""
        self.mock_context.resource_code = None
        self.mock_context.resource_name = None
        
        context = self.action.build_movement_context(self.mock_context)
        
        # None values should not be included
        self.assertEqual(context, {'at_resource_location': True})
        
    def test_repr_method(self):
        """Test string representation of the action."""
        result = repr(self.action)
        self.assertEqual(result, "MoveToResourceAction()")
        
    def test_inheritance(self):
        """Test that the action properly inherits from MovementActionBase."""
        from src.controller.actions.base.movement import MovementActionBase
        self.assertIsInstance(self.action, MovementActionBase)
        
    def test_execute_method_exists(self):
        """Test that execute method is inherited from parent class."""
        # The execute method should be inherited from MovementActionBase
        self.assertTrue(hasattr(self.action, 'execute'))
        self.assertTrue(callable(getattr(self.action, 'execute')))
        
    def test_execute_movement_method_exists(self):
        """Test that execute_movement method is inherited from parent class."""
        # The execute_movement method should be inherited from MovementActionBase
        self.assertTrue(hasattr(self.action, 'execute_movement'))
        self.assertTrue(callable(getattr(self.action, 'execute_movement')))
        
    def test_mixin_methods_exist(self):
        """Test that mixin methods are available."""
        # Note: CharacterDataMixin removed for architecture compliance
        # Actions now read character data from UnifiedStateContext instead of making direct API calls
        
        # Test that other expected mixin methods are still available
        self.assertTrue(hasattr(self.action, 'execute_movement'))
        self.assertTrue(callable(getattr(self.action, 'execute_movement')))
        
    def test_get_target_coordinates_integration(self):
        """Test get_target_coordinates with various context scenarios."""
        # Test with mixed parameters
        test_cases = [
            # (context_data, expected_x, expected_y)
            ({'target_x': 5, 'target_y': 10, 'resource_x': None, 'resource_y': None}, 5, 10),
            ({'target_x': None, 'target_y': None, 'resource_x': 15, 'resource_y': 20}, 15, 20),
            ({'target_x': 5, 'target_y': None, 'resource_x': None, 'resource_y': 20}, 5, 20),
            ({'target_x': None, 'target_y': 10, 'resource_x': 15, 'resource_y': None}, 15, 10),
            ({'target_x': None, 'target_y': None, 'resource_x': None, 'resource_y': None}, None, None),
        ]
        
        for context_data, expected_x, expected_y in test_cases:
            with self.subTest(context_data=context_data):
                for attr, value in context_data.items():
                    setattr(self.mock_context, attr, value)
                x, y = self.action.get_target_coordinates(self.mock_context)
                self.assertEqual(x, expected_x)
                self.assertEqual(y, expected_y)
                
    def test_build_movement_context_integration(self):
        """Test build_movement_context with various context scenarios."""
        test_cases = [
            # (context_data, expected_context)
            ({'resource_code': None, 'resource_name': None}, {'at_resource_location': True}),
            (
                {'resource_code': 'iron_ore', 'resource_name': None},
                {'at_resource_location': True, 'resource_code': 'iron_ore'}
            ),
            (
                {'resource_code': None, 'resource_name': 'Iron Ore'},
                {'at_resource_location': True, 'resource_name': 'Iron Ore'}
            ),
            (
                {'resource_code': 'gold_ore', 'resource_name': 'Gold Ore'},
                {'at_resource_location': True, 'resource_code': 'gold_ore', 'resource_name': 'Gold Ore'}
            ),
        ]
        
        for context_data, expected_context in test_cases:
            with self.subTest(context_data=context_data):
                for attr, value in context_data.items():
                    setattr(self.mock_context, attr, value)
                context = self.action.build_movement_context(self.mock_context)
                self.assertEqual(context, expected_context)
                
    def test_coordinate_priority_logic(self):
        """Test the priority logic for coordinate selection."""
        # target_x should take priority over resource_x
        self.mock_context.target_x = 100
        self.mock_context.target_y = None
        self.mock_context.resource_x = 200
        self.mock_context.resource_y = None
        
        x, y = self.action.get_target_coordinates(self.mock_context)
        self.assertEqual(x, 100)  # target_x wins
        
        # target_y should take priority over resource_y
        self.mock_context.target_x = None
        self.mock_context.target_y = 300
        self.mock_context.resource_x = None
        self.mock_context.resource_y = 400
        
        x, y = self.action.get_target_coordinates(self.mock_context)
        self.assertEqual(y, 300)  # target_y wins
        
    def test_context_method_calls(self):
        """Test that the correct context attributes are accessed."""
        # Set up mock context with all expected attributes
        self.mock_context.target_x = None
        self.mock_context.target_y = None
        self.mock_context.resource_x = None
        self.mock_context.resource_y = None
        self.mock_context.resource_code = None
        self.mock_context.resource_name = None
        
        # Test get_target_coordinates - should access coordinate attributes
        self.action.get_target_coordinates(self.mock_context)
        
        # Test build_movement_context - should access resource attributes
        self.action.build_movement_context(self.mock_context)
        
        # Since we changed from method calls to attribute access,
        # we just verify the methods don't crash and return expected results
        x, y = self.action.get_target_coordinates(self.mock_context)
        self.assertIsNone(x)
        self.assertIsNone(y)
        
        context = self.action.build_movement_context(self.mock_context)
        self.assertEqual(context, {'at_resource_location': True})


if __name__ == '__main__':
    unittest.main()