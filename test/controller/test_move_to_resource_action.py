"""Unit tests for MoveToResourceAction class."""

import unittest
from unittest.mock import Mock, patch

from artifactsmmo_api_client.client import AuthenticatedClient
from src.controller.actions.move_to_resource import MoveToResourceAction


class TestMoveToResourceAction(unittest.TestCase):
    """Test cases for MoveToResourceAction class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.char_name = "test_character"
        self.client = Mock(spec=AuthenticatedClient)
    
    def test_initialization(self):
        """Test MoveToResourceAction initialization."""
        # Action should have no parameters stored as instance variables
        action = MoveToResourceAction()
        self.assertIsInstance(action, MoveToResourceAction)
        self.assertFalse(hasattr(action, 'character_name'))
        self.assertFalse(hasattr(action, 'target_x'))
        self.assertFalse(hasattr(action, 'target_y'))
    
    def test_repr(self):
        """Test string representation."""
        action = MoveToResourceAction()
        expected = "MoveToResourceAction()"
        self.assertEqual(repr(action), expected)
    
    def test_class_attributes(self):
        """Test GOAP class attributes."""
        self.assertIsInstance(MoveToResourceAction.conditions, dict)
        self.assertIsInstance(MoveToResourceAction.reactions, dict)
        self.assertIsInstance(MoveToResourceAction.weight, (int, float))
        
        # Check specific conditions
        self.assertIn("character_status", MoveToResourceAction.conditions)
        self.assertTrue(MoveToResourceAction.conditions["character_status"]["alive"])
        self.assertFalse(MoveToResourceAction.conditions["character_status"]["cooldown_active"])
        self.assertTrue(MoveToResourceAction.conditions["resource_location_known"])
        
        # Check reactions
        self.assertTrue(MoveToResourceAction.reactions["at_resource_location"])
        self.assertIn("location_context", MoveToResourceAction.reactions)
        self.assertTrue(MoveToResourceAction.reactions["location_context"]["at_target"])
        
        # Check weights
        self.assertEqual(MoveToResourceAction.weight, 10)
    
    def test_get_target_coordinates_from_context(self):
        """Test coordinate extraction from context parameters."""
        from test.fixtures import MockActionContext
        action = MoveToResourceAction()
        context = MockActionContext(character_name=self.char_name, target_x=25, target_y=35)
        x, y = action.get_target_coordinates(context)
        self.assertEqual((x, y), (25, 35))
    
    def test_get_target_coordinates_from_context_target(self):
        """Test coordinate extraction from context with target_x/target_y."""
        from test.fixtures import MockActionContext
        action = MoveToResourceAction()
        context = MockActionContext(character_name=self.char_name, target_x=100, target_y=200)
        x, y = action.get_target_coordinates(context)
        self.assertEqual((x, y), (100, 200))
    
    def test_get_target_coordinates_from_context_resource(self):
        """Test coordinate extraction from context with resource_x/resource_y."""
        from test.fixtures import MockActionContext
        action = MoveToResourceAction()
        context = MockActionContext(character_name=self.char_name, resource_x=300, resource_y=400)
        x, y = action.get_target_coordinates(context)
        self.assertEqual((x, y), (300, 400))
    
    def test_get_target_coordinates_precedence(self):
        """Test coordinate precedence (target_x over resource_x)."""
        from test.fixtures import MockActionContext
        action = MoveToResourceAction()
        # Should use target_x/target_y over resource_x/resource_y
        context = MockActionContext(character_name=self.char_name, target_x=10, target_y=20, resource_x=100, resource_y=200)
        x, y = action.get_target_coordinates(context)
        self.assertEqual((x, y), (10, 20))
    
    def test_get_target_coordinates_context_precedence(self):
        """Test context coordinate precedence (target_x over resource_x)."""
        from test.fixtures import MockActionContext
        action = MoveToResourceAction()
        # target_x/target_y should take precedence over resource_x/resource_y
        context = MockActionContext(
            character_name=self.char_name,
            target_x=50, target_y=60,
            resource_x=70, resource_y=80
        )
        x, y = action.get_target_coordinates(context)
        self.assertEqual((x, y), (50, 60))
    
    def test_get_target_coordinates_no_coordinates(self):
        """Test coordinate extraction when no coordinates available."""
        from test.fixtures import MockActionContext
        action = MoveToResourceAction()
        context = MockActionContext(character_name=self.char_name)
        x, y = action.get_target_coordinates(context)
        self.assertEqual((x, y), (None, None))
    
    def test_build_movement_context_basic(self):
        """Test basic movement context building."""
        from test.fixtures import MockActionContext
        action = MoveToResourceAction()
        action_context = MockActionContext(character_name=self.char_name)
        context = action.build_movement_context(action_context)
        
        # Should always include at_resource_location
        self.assertTrue(context['at_resource_location'])
    
    def test_build_movement_context_with_resource_info(self):
        """Test movement context building with resource information."""
        from test.fixtures import MockActionContext
        action = MoveToResourceAction()
        action_context = MockActionContext(
            character_name=self.char_name,
            resource_code='iron_ore',
            resource_name='Iron Ore'
        )
        context = action.build_movement_context(action_context)
        
        self.assertTrue(context['at_resource_location'])
        self.assertEqual(context['resource_code'], 'iron_ore')
        self.assertEqual(context['resource_name'], 'Iron Ore')
    
    def test_build_movement_context_partial_info(self):
        """Test movement context building with partial resource information."""
        from test.fixtures import MockActionContext
        action = MoveToResourceAction()
        
        # Only resource_code
        action_context = MockActionContext(character_name=self.char_name, resource_code='copper_ore')
        context = action.build_movement_context(action_context)
        self.assertTrue(context['at_resource_location'])
        self.assertEqual(context['resource_code'], 'copper_ore')
        self.assertNotIn('resource_name', context)
        
        # Only resource_name
        action_context = MockActionContext(character_name=self.char_name, resource_name='Copper Ore')
        context = action.build_movement_context(action_context)
        self.assertTrue(context['at_resource_location'])
        self.assertEqual(context['resource_name'], 'Copper Ore')
        self.assertNotIn('resource_code', context)
    
    @patch('src.controller.actions.movement_base.move_character_api')
    def test_execute_success_with_context_coordinates(self, mock_move_api):
        """Test successful execution with coordinates from context."""
        from test.fixtures import MockActionContext
        # Mock API response
        mock_response = Mock()
        mock_response.data = Mock(cooldown={"total_seconds": 3})
        mock_move_api.return_value = mock_response
        
        # Execute action
        action = MoveToResourceAction()
        context = MockActionContext(character_name=self.char_name, target_x=15, target_y=25, resource_code='ash_wood')
        result = action.execute(self.client, context)
        
        # Verify API call
        mock_move_api.assert_called_once()
        call_args = mock_move_api.call_args
        self.assertEqual(call_args.kwargs['name'], self.char_name)
        self.assertEqual(call_args.kwargs['client'], self.client)
        
        # Check destination
        destination = call_args.kwargs['body']
        self.assertEqual(destination.x, 15)
        self.assertEqual(destination.y, 25)
        
        # Verify response
        self.assertTrue(result.success)
        self.assertTrue(result.data['moved'])
        self.assertEqual(result.data['target_x'], 15)
        self.assertEqual(result.data['target_y'], 25)
        self.assertTrue(result.data['at_resource_location'])
        self.assertEqual(result.data['resource_code'], 'ash_wood')
    
    @patch('src.controller.actions.movement_base.move_character_api')
    def test_execute_success_with_detailed_context(self, mock_move_api):
        """Test successful execution with detailed context."""
        from test.fixtures import MockActionContext
        # Mock API response
        mock_response = Mock()
        mock_response.data = Mock(cooldown=None)
        mock_move_api.return_value = mock_response
        
        # Execute action
        action = MoveToResourceAction()
        context = MockActionContext(
            character_name=self.char_name,
            target_x=30,
            target_y=40,
            resource_code='copper_ore',
            resource_name='Copper Ore'
        )
        result = action.execute(self.client, context)
        
        # Verify response
        self.assertTrue(result.success)
        self.assertEqual(result.data['target_x'], 30)
        self.assertEqual(result.data['target_y'], 40)
        self.assertTrue(result.data['at_resource_location'])
        self.assertEqual(result.data['resource_code'], 'copper_ore')
        self.assertEqual(result.data['resource_name'], 'Copper Ore')
    
    @patch('src.controller.actions.movement_base.move_character_api')
    def test_execute_already_at_destination(self, mock_move_api):
        """Test execution when already at destination."""
        from test.fixtures import MockActionContext
        # Mock API to raise "already at destination" error
        mock_move_api.side_effect = Exception("490 Already at destination")
        
        # Execute action
        action = MoveToResourceAction()
        context = MockActionContext(character_name=self.char_name, target_x=10, target_y=20, resource_code='iron_ore')
        result = action.execute(self.client, context)
        
        # Verify it's treated as success
        self.assertTrue(result.success)
        self.assertFalse(result.data['moved'])
        self.assertTrue(result.data['already_at_destination'])
        self.assertEqual(result.data['target_x'], 10)
        self.assertEqual(result.data['target_y'], 20)
        self.assertTrue(result.data['at_resource_location'])
        self.assertEqual(result.data['resource_code'], 'iron_ore')
    
    def test_execute_no_client(self):
        """Test execution without client."""
        from test.fixtures import MockActionContext
        action = MoveToResourceAction()
        context = MockActionContext(character_name=self.char_name, target_x=5, target_y=10)
        result = action.execute(None, context)
        # With centralized validation, None client triggers validation error
        self.assertFalse(result.success)
        # Direct action execution bypasses centralized validation
        self.assertIsNotNone(result.error)
    
    def test_execute_no_coordinates(self):
        """Test execution without coordinates."""
        from test.fixtures import MockActionContext
        action = MoveToResourceAction()
        context = MockActionContext(character_name=self.char_name)
        result = action.execute(self.client, context)
        
        self.assertFalse(result.success)
        self.assertIn('No valid coordinates provided', result.error)
    
    def test_execute_partial_coordinates(self):
        """Test execution with partial coordinates."""
        from test.fixtures import MockActionContext
        action = MoveToResourceAction()
        
        # Only target_x
        context = MockActionContext(character_name=self.char_name, target_x=10)
        result = action.execute(self.client, context)
        self.assertFalse(result.success)
        self.assertIn('No valid coordinates provided', result.error)
        
        # Only resource_y
        context = MockActionContext(character_name=self.char_name, resource_y=20)
        result = action.execute(self.client, context)
        self.assertFalse(result.success)
        self.assertIn('No valid coordinates provided', result.error)
    
    @patch('src.controller.actions.movement_base.move_character_api')
    def test_execute_api_error(self, mock_move_api):
        """Test execution with API error."""
        from test.fixtures import MockActionContext
        # Mock API to raise error
        mock_move_api.side_effect = Exception("Network error")
        
        # Execute action
        action = MoveToResourceAction()
        context = MockActionContext(character_name=self.char_name, target_x=5, target_y=10)
        result = action.execute(self.client, context)
        
        # Should return error
        self.assertFalse(result.success)
        self.assertIn('Network error', result.error)
        self.assertEqual(result.data['target_x'], 5)
        self.assertEqual(result.data['target_y'], 10)
    
    def test_inheritance_from_movement_base(self):
        """Test that MoveToResourceAction properly inherits from MovementActionBase."""
        action = MoveToResourceAction()
        
        # Should have MovementActionBase methods
        self.assertTrue(hasattr(action, 'execute_movement'))
        self.assertTrue(hasattr(action, 'calculate_distance'))
        
        # Should have ActionBase methods
        self.assertTrue(hasattr(action, 'create_success_result'))
        self.assertTrue(hasattr(action, 'create_error_result'))
        
        # Should have CharacterDataMixin methods
        self.assertTrue(hasattr(action, 'get_character_data'))
        self.assertTrue(hasattr(action, 'get_character_location'))
    
    def test_calculate_distance(self):
        """Test distance calculation functionality."""
        action = MoveToResourceAction()
        
        # Test distance calculation
        distance = action.calculate_distance(0, 0, 3, 4)
        self.assertEqual(distance, 7)  # Manhattan distance
        
        distance = action.calculate_distance(10, 20, 10, 20)
        self.assertEqual(distance, 0)  # Same location


if __name__ == '__main__':
    unittest.main()