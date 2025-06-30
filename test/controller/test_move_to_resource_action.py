"""Unit tests for MoveToResourceAction class."""

import unittest
from unittest.mock import Mock, patch
from typing import Tuple, Optional

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
        # Test with coordinates
        action = MoveToResourceAction(character_name=self.char_name, target_x=10, target_y=20)
        self.assertEqual(action.character_name, self.char_name)
        self.assertEqual(action.target_x, 10)
        self.assertEqual(action.target_y, 20)
        
        # Test without coordinates
        action = MoveToResourceAction(character_name=self.char_name)
        self.assertEqual(action.character_name, self.char_name)
        self.assertIsNone(action.target_x)
        self.assertIsNone(action.target_y)
    
    def test_repr(self):
        """Test string representation."""
        action = MoveToResourceAction(character_name=self.char_name, target_x=5, target_y=15)
        expected = f"MoveToResourceAction({self.char_name}, 5, 15)"
        self.assertEqual(repr(action), expected)
    
    def test_class_attributes(self):
        """Test GOAP class attributes."""
        self.assertIsInstance(MoveToResourceAction.conditions, dict)
        self.assertIsInstance(MoveToResourceAction.reactions, dict)
        self.assertIsInstance(MoveToResourceAction.weights, dict)
        
        # Check specific conditions
        self.assertTrue(MoveToResourceAction.conditions["character_alive"])
        self.assertTrue(MoveToResourceAction.conditions["can_move"])
        self.assertTrue(MoveToResourceAction.conditions["resource_location_known"])
        
        # Check reactions
        self.assertTrue(MoveToResourceAction.reactions["at_resource_location"])
        self.assertTrue(MoveToResourceAction.reactions["at_target_location"])
        
        # Check weights
        self.assertEqual(MoveToResourceAction.weights["at_resource_location"], 10)
    
    def test_get_target_coordinates_from_init(self):
        """Test coordinate extraction from initialization parameters."""
        action = MoveToResourceAction(character_name=self.char_name, target_x=25, target_y=35)
        x, y = action.get_target_coordinates()
        self.assertEqual((x, y), (25, 35))
    
    def test_get_target_coordinates_from_context_target(self):
        """Test coordinate extraction from context with target_x/target_y."""
        action = MoveToResourceAction(character_name=self.char_name)
        x, y = action.get_target_coordinates(target_x=100, target_y=200)
        self.assertEqual((x, y), (100, 200))
    
    def test_get_target_coordinates_from_context_resource(self):
        """Test coordinate extraction from context with resource_x/resource_y."""
        action = MoveToResourceAction(character_name=self.char_name)
        x, y = action.get_target_coordinates(resource_x=300, resource_y=400)
        self.assertEqual((x, y), (300, 400))
    
    def test_get_target_coordinates_precedence(self):
        """Test coordinate precedence (init params over context)."""
        action = MoveToResourceAction(character_name=self.char_name, target_x=10, target_y=20)
        # Should use init params even if context provides different values
        x, y = action.get_target_coordinates(target_x=100, target_y=200)
        self.assertEqual((x, y), (10, 20))
    
    def test_get_target_coordinates_context_precedence(self):
        """Test context coordinate precedence (target_x over resource_x)."""
        action = MoveToResourceAction(character_name=self.char_name)
        # target_x/target_y should take precedence over resource_x/resource_y
        x, y = action.get_target_coordinates(
            target_x=50, target_y=60,
            resource_x=70, resource_y=80
        )
        self.assertEqual((x, y), (50, 60))
    
    def test_get_target_coordinates_no_coordinates(self):
        """Test coordinate extraction when no coordinates available."""
        action = MoveToResourceAction(character_name=self.char_name)
        x, y = action.get_target_coordinates()
        self.assertEqual((x, y), (None, None))
    
    def test_build_movement_context_basic(self):
        """Test basic movement context building."""
        action = MoveToResourceAction(character_name=self.char_name)
        context = action.build_movement_context()
        
        # Should always include at_resource_location
        self.assertTrue(context['at_resource_location'])
    
    def test_build_movement_context_with_resource_info(self):
        """Test movement context building with resource information."""
        action = MoveToResourceAction(character_name=self.char_name)
        context = action.build_movement_context(
            resource_code='iron_ore',
            resource_name='Iron Ore'
        )
        
        self.assertTrue(context['at_resource_location'])
        self.assertEqual(context['resource_code'], 'iron_ore')
        self.assertEqual(context['resource_name'], 'Iron Ore')
    
    def test_build_movement_context_partial_info(self):
        """Test movement context building with partial resource information."""
        action = MoveToResourceAction(character_name=self.char_name)
        
        # Only resource_code
        context = action.build_movement_context(resource_code='copper_ore')
        self.assertTrue(context['at_resource_location'])
        self.assertEqual(context['resource_code'], 'copper_ore')
        self.assertNotIn('resource_name', context)
        
        # Only resource_name
        context = action.build_movement_context(resource_name='Copper Ore')
        self.assertTrue(context['at_resource_location'])
        self.assertEqual(context['resource_name'], 'Copper Ore')
        self.assertNotIn('resource_code', context)
    
    @patch('src.controller.actions.movement_base.move_character_api')
    def test_execute_success_with_init_coordinates(self, mock_move_api):
        """Test successful execution with coordinates from initialization."""
        # Mock API response
        mock_response = Mock()
        mock_response.data = Mock(cooldown={"total_seconds": 3})
        mock_move_api.return_value = mock_response
        
        # Execute action
        action = MoveToResourceAction(character_name=self.char_name, target_x=15, target_y=25)
        result = action.execute(self.client, resource_code='ash_wood')
        
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
        self.assertTrue(result['success'])
        self.assertTrue(result['moved'])
        self.assertEqual(result['target_x'], 15)
        self.assertEqual(result['target_y'], 25)
        self.assertTrue(result['at_resource_location'])
        self.assertEqual(result['resource_code'], 'ash_wood')
    
    @patch('src.controller.actions.movement_base.move_character_api')
    def test_execute_success_with_context_coordinates(self, mock_move_api):
        """Test successful execution with coordinates from context."""
        # Mock API response
        mock_response = Mock()
        mock_response.data = Mock(cooldown=None)
        mock_move_api.return_value = mock_response
        
        # Execute action
        action = MoveToResourceAction(character_name=self.char_name)
        result = action.execute(
            self.client,
            target_x=30,
            target_y=40,
            resource_code='copper_ore',
            resource_name='Copper Ore'
        )
        
        # Verify response
        self.assertTrue(result['success'])
        self.assertEqual(result['target_x'], 30)
        self.assertEqual(result['target_y'], 40)
        self.assertTrue(result['at_resource_location'])
        self.assertEqual(result['resource_code'], 'copper_ore')
        self.assertEqual(result['resource_name'], 'Copper Ore')
    
    @patch('src.controller.actions.movement_base.move_character_api')
    def test_execute_already_at_destination(self, mock_move_api):
        """Test execution when already at destination."""
        # Mock API to raise "already at destination" error
        mock_move_api.side_effect = Exception("490 Already at destination")
        
        # Execute action
        action = MoveToResourceAction(character_name=self.char_name, target_x=10, target_y=20)
        result = action.execute(self.client, resource_code='iron_ore')
        
        # Verify it's treated as success
        self.assertTrue(result['success'])
        self.assertFalse(result['moved'])
        self.assertTrue(result['already_at_destination'])
        self.assertEqual(result['target_x'], 10)
        self.assertEqual(result['target_y'], 20)
        self.assertTrue(result['at_resource_location'])
        self.assertEqual(result['resource_code'], 'iron_ore')
    
    def test_execute_no_client(self):
        """Test execution without client."""
        action = MoveToResourceAction(character_name=self.char_name, target_x=5, target_y=10)
        result = action.execute(None)
        
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])
    
    def test_execute_no_coordinates(self):
        """Test execution without coordinates."""
        action = MoveToResourceAction(character_name=self.char_name)
        result = action.execute(self.client)
        
        self.assertFalse(result['success'])
        self.assertIn('No valid coordinates provided', result['error'])
    
    def test_execute_partial_coordinates(self):
        """Test execution with partial coordinates."""
        action = MoveToResourceAction(character_name=self.char_name)
        
        # Only target_x
        result = action.execute(self.client, target_x=10)
        self.assertFalse(result['success'])
        self.assertIn('No valid coordinates provided', result['error'])
        
        # Only resource_y
        result = action.execute(self.client, resource_y=20)
        self.assertFalse(result['success'])
        self.assertIn('No valid coordinates provided', result['error'])
    
    @patch('src.controller.actions.movement_base.move_character_api')
    def test_execute_api_error(self, mock_move_api):
        """Test execution with API error."""
        # Mock API to raise error
        mock_move_api.side_effect = Exception("Network error")
        
        # Execute action
        action = MoveToResourceAction(character_name=self.char_name, target_x=5, target_y=10)
        result = action.execute(self.client)
        
        # Should return error
        self.assertFalse(result['success'])
        self.assertIn('Network error', result['error'])
        self.assertEqual(result['target_x'], 5)
        self.assertEqual(result['target_y'], 10)
    
    def test_inheritance_from_movement_base(self):
        """Test that MoveToResourceAction properly inherits from MovementActionBase."""
        action = MoveToResourceAction(character_name=self.char_name)
        
        # Should have MovementActionBase methods
        self.assertTrue(hasattr(action, 'execute_movement'))
        self.assertTrue(hasattr(action, 'calculate_distance'))
        
        # Should have ActionBase methods
        self.assertTrue(hasattr(action, 'get_success_response'))
        self.assertTrue(hasattr(action, 'get_error_response'))
        
        # Should have CharacterDataMixin methods
        self.assertTrue(hasattr(action, 'get_character_data'))
        self.assertTrue(hasattr(action, 'get_character_location'))
    
    def test_calculate_distance(self):
        """Test distance calculation functionality."""
        action = MoveToResourceAction(character_name=self.char_name)
        
        # Test distance calculation
        distance = action.calculate_distance(0, 0, 3, 4)
        self.assertEqual(distance, 7)  # Manhattan distance
        
        distance = action.calculate_distance(10, 20, 10, 20)
        self.assertEqual(distance, 0)  # Same location


if __name__ == '__main__':
    unittest.main()