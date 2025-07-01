"""Unit tests for MoveToWorkshopAction class."""

import unittest
from unittest.mock import Mock, patch

from artifactsmmo_api_client.client import AuthenticatedClient
from src.controller.actions.move_to_workshop import MoveToWorkshopAction


class TestMoveToWorkshopAction(unittest.TestCase):
    """Test cases for MoveToWorkshopAction class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.char_name = "test_character"
        self.client = Mock(spec=AuthenticatedClient)
    
    def test_initialization(self):
        """Test MoveToWorkshopAction initialization."""
        # Action should have no parameters stored as instance variables
        action = MoveToWorkshopAction()
        self.assertIsInstance(action, MoveToWorkshopAction)
        self.assertFalse(hasattr(action, 'character_name'))
        self.assertFalse(hasattr(action, 'target_x'))
        self.assertFalse(hasattr(action, 'target_y'))
    
    def test_repr(self):
        """Test string representation."""
        action = MoveToWorkshopAction()
        expected = "MoveToWorkshopAction()"
        self.assertEqual(repr(action), expected)
    
    def test_class_attributes(self):
        """Test GOAP class attributes."""
        self.assertIsInstance(MoveToWorkshopAction.conditions, dict)
        self.assertIsInstance(MoveToWorkshopAction.reactions, dict)
        self.assertIsInstance(MoveToWorkshopAction.weights, dict)
        
        # Check specific conditions
        self.assertTrue(MoveToWorkshopAction.conditions["character_alive"])
        self.assertTrue(MoveToWorkshopAction.conditions["can_move"])
        self.assertTrue(MoveToWorkshopAction.conditions["workshops_discovered"])
        
        # Check reactions
        self.assertTrue(MoveToWorkshopAction.reactions["at_workshop"])
        self.assertTrue(MoveToWorkshopAction.reactions["at_target_location"])
        
        # Check weights
        self.assertEqual(MoveToWorkshopAction.weights["at_workshop"], 10)
    
    def test_get_target_coordinates_from_context(self):
        """Test coordinate extraction from context parameters."""
        from test.fixtures import MockActionContext
        action = MoveToWorkshopAction()
        context = MockActionContext(character_name=self.char_name, target_x=45, target_y=55)
        x, y = action.get_target_coordinates(context)
        self.assertEqual((x, y), (45, 55))
    
    def test_get_target_coordinates_from_context_target(self):
        """Test coordinate extraction from context with target_x/target_y."""
        from test.fixtures import MockActionContext
        action = MoveToWorkshopAction()
        context = MockActionContext(character_name=self.char_name, target_x=150, target_y=250)
        x, y = action.get_target_coordinates(context)
        self.assertEqual((x, y), (150, 250))
    
    def test_get_target_coordinates_from_context_workshop(self):
        """Test coordinate extraction from context with workshop_x/workshop_y."""
        from test.fixtures import MockActionContext
        action = MoveToWorkshopAction()
        context = MockActionContext(character_name=self.char_name, workshop_x=350, workshop_y=450)
        x, y = action.get_target_coordinates(context)
        self.assertEqual((x, y), (350, 450))
    
    def test_get_target_coordinates_precedence(self):
        """Test coordinate precedence (target_x over workshop_x)."""
        from test.fixtures import MockActionContext
        action = MoveToWorkshopAction()
        # Should use target_x/target_y over workshop_x/workshop_y
        context = MockActionContext(character_name=self.char_name, target_x=10, target_y=20, workshop_x=100, workshop_y=200)
        x, y = action.get_target_coordinates(context)
        self.assertEqual((x, y), (10, 20))
    
    def test_get_target_coordinates_context_precedence(self):
        """Test context coordinate precedence (target_x over workshop_x)."""
        from test.fixtures import MockActionContext
        action = MoveToWorkshopAction()
        # target_x/target_y should take precedence over workshop_x/workshop_y
        context = MockActionContext(
            character_name=self.char_name,
            target_x=50, target_y=60,
            workshop_x=70, workshop_y=80
        )
        x, y = action.get_target_coordinates(context)
        self.assertEqual((x, y), (50, 60))
    
    def test_get_target_coordinates_no_coordinates(self):
        """Test coordinate extraction when no coordinates available."""
        from test.fixtures import MockActionContext
        action = MoveToWorkshopAction()
        context = MockActionContext(character_name=self.char_name)
        x, y = action.get_target_coordinates(context)
        self.assertEqual((x, y), (None, None))
    
    def test_build_movement_context_basic(self):
        """Test basic movement context building."""
        from test.fixtures import MockActionContext
        action = MoveToWorkshopAction()
        action_context = MockActionContext(character_name=self.char_name)
        context = action.build_movement_context(action_context)
        
        # Should always include at_workshop
        self.assertTrue(context['at_workshop'])
    
    def test_build_movement_context_with_workshop_info(self):
        """Test movement context building with workshop information."""
        from test.fixtures import MockActionContext
        action = MoveToWorkshopAction()
        action_context = MockActionContext(
            character_name=self.char_name,
            workshop_type='weaponcrafting',
            workshop_code='weaponcrafting_workshop'
        )
        context = action.build_movement_context(action_context)
        
        self.assertTrue(context['at_workshop'])
        self.assertEqual(context['workshop_type'], 'weaponcrafting')
        self.assertEqual(context['workshop_code'], 'weaponcrafting_workshop')
    
    def test_build_movement_context_partial_info(self):
        """Test movement context building with partial workshop information."""
        from test.fixtures import MockActionContext
        action = MoveToWorkshopAction()
        
        # Only workshop_type
        action_context = MockActionContext(character_name=self.char_name, workshop_type='cooking')
        context = action.build_movement_context(action_context)
        self.assertTrue(context['at_workshop'])
        self.assertEqual(context['workshop_type'], 'cooking')
        self.assertNotIn('workshop_code', context)
        
        # Only workshop_code
        action_context = MockActionContext(character_name=self.char_name, workshop_code='cooking_workshop')
        context = action.build_movement_context(action_context)
        self.assertTrue(context['at_workshop'])
        self.assertEqual(context['workshop_code'], 'cooking_workshop')
        self.assertNotIn('workshop_type', context)
    
    @patch('src.controller.actions.movement_base.move_character_api')
    def test_execute_success_with_init_coordinates(self, mock_move_api):
        """Test successful execution with coordinates from initialization."""
        # Mock API response
        mock_response = Mock()
        mock_response.data = Mock(cooldown={"total_seconds": 4})
        mock_move_api.return_value = mock_response
        
        # Execute action
        from test.fixtures import MockActionContext
        action = MoveToWorkshopAction()
        context = MockActionContext(character_name=self.char_name, target_x=25, target_y=35, workshop_type='jewelrycrafting')
        result = action.execute(self.client, context)
        
        # Verify API call
        mock_move_api.assert_called_once()
        call_args = mock_move_api.call_args
        self.assertEqual(call_args.kwargs['name'], self.char_name)
        self.assertEqual(call_args.kwargs['client'], self.client)
        
        # Check destination
        destination = call_args.kwargs['body']
        self.assertEqual(destination.x, 25)
        self.assertEqual(destination.y, 35)
        
        # Verify response
        self.assertTrue(result['success'])
        self.assertTrue(result['moved'])
        self.assertEqual(result['target_x'], 25)
        self.assertEqual(result['target_y'], 35)
        self.assertTrue(result['at_workshop'])
        self.assertEqual(result['workshop_type'], 'jewelrycrafting')
    
    @patch('src.controller.actions.movement_base.move_character_api')
    def test_execute_success_with_context_coordinates(self, mock_move_api):
        """Test successful execution with coordinates from context."""
        # Mock API response
        mock_response = Mock()
        mock_response.data = Mock(cooldown=None)
        mock_move_api.return_value = mock_response
        
        # Execute action
        from test.fixtures import MockActionContext
        action = MoveToWorkshopAction()
        context = MockActionContext(
            character_name=self.char_name,
            target_x=40,
            target_y=50,
            workshop_type='gearcrafting',
            workshop_code='gearcrafting_workshop'
        )
        result = action.execute(self.client, context)
        
        # Verify response
        self.assertTrue(result['success'])
        self.assertEqual(result['target_x'], 40)
        self.assertEqual(result['target_y'], 50)
        self.assertTrue(result['at_workshop'])
        self.assertEqual(result['workshop_type'], 'gearcrafting')
        self.assertEqual(result['workshop_code'], 'gearcrafting_workshop')
    
    @patch('src.controller.actions.movement_base.move_character_api')
    def test_execute_already_at_destination(self, mock_move_api):
        """Test execution when already at destination."""
        # Mock API to raise "already at destination" error
        mock_move_api.side_effect = Exception("490 Already at destination")
        
        # Execute action
        from test.fixtures import MockActionContext
        action = MoveToWorkshopAction()
        context = MockActionContext(character_name=self.char_name, target_x=15, target_y=25, workshop_type='alchemy')
        result = action.execute(self.client, context)
        
        # Verify it's treated as success
        self.assertTrue(result['success'])
        self.assertFalse(result['moved'])
        self.assertTrue(result['already_at_destination'])
        self.assertEqual(result['target_x'], 15)
        self.assertEqual(result['target_y'], 25)
        self.assertTrue(result['at_workshop'])
        self.assertEqual(result['workshop_type'], 'alchemy')
    
    def test_execute_no_client(self):
        """Test execution without client."""
        from test.fixtures import MockActionContext
        action = MoveToWorkshopAction()
        context = MockActionContext(character_name=self.char_name, target_x=8, target_y=18)
        result = action.execute(None, context)
        
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])
    
    def test_execute_no_coordinates(self):
        """Test execution without coordinates."""
        from test.fixtures import MockActionContext
        action = MoveToWorkshopAction()
        context = MockActionContext(character_name=self.char_name)
        result = action.execute(self.client, context)
        
        self.assertFalse(result['success'])
        self.assertIn('No valid coordinates provided', result['error'])
    
    def test_execute_partial_coordinates(self):
        """Test execution with partial coordinates."""
        from test.fixtures import MockActionContext
        action = MoveToWorkshopAction()
        
        # Only target_x
        context = MockActionContext(character_name=self.char_name, target_x=20)
        result = action.execute(self.client, context)
        self.assertFalse(result['success'])
        self.assertIn('No valid coordinates provided', result['error'])
        
        # Only workshop_y
        context = MockActionContext(character_name=self.char_name, workshop_y=30)
        result = action.execute(self.client, context)
        self.assertFalse(result['success'])
        self.assertIn('No valid coordinates provided', result['error'])
    
    @patch('src.controller.actions.movement_base.move_character_api')
    def test_execute_api_error(self, mock_move_api):
        """Test execution with API error."""
        # Mock API to raise error
        mock_move_api.side_effect = Exception("Connection timeout")
        
        # Execute action
        from test.fixtures import MockActionContext
        action = MoveToWorkshopAction()
        context = MockActionContext(character_name=self.char_name, target_x=6, target_y=16)
        result = action.execute(self.client, context)
        
        # Should return error
        self.assertFalse(result['success'])
        self.assertIn('Connection timeout', result['error'])
        self.assertEqual(result['target_x'], 6)
        self.assertEqual(result['target_y'], 16)
    
    def test_inheritance_from_movement_base(self):
        """Test that MoveToWorkshopAction properly inherits from MovementActionBase."""
        action = MoveToWorkshopAction()
        
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
        action = MoveToWorkshopAction()
        
        # Test distance calculation
        distance = action.calculate_distance(5, 10, 8, 14)
        self.assertEqual(distance, 7)  # |8-5| + |14-10| = 3 + 4 = 7
        
        distance = action.calculate_distance(15, 25, 15, 25)
        self.assertEqual(distance, 0)  # Same location
    
    def test_workshop_specific_functionality(self):
        """Test workshop-specific functionality vs resource functionality."""
        from test.fixtures import MockActionContext
        workshop_action = MoveToWorkshopAction()
        
        # Test that workshop context is different from resource context
        action_context = MockActionContext(
            character_name=self.char_name,
            workshop_type='cooking',
            workshop_code='cooking_workshop'
        )
        workshop_context = workshop_action.build_movement_context(action_context)
        
        # Should include workshop-specific fields
        self.assertTrue(workshop_context['at_workshop'])
        self.assertEqual(workshop_context['workshop_type'], 'cooking')
        self.assertEqual(workshop_context['workshop_code'], 'cooking_workshop')
        
        # Should not include resource-specific fields
        self.assertNotIn('at_resource_location', workshop_context)
        self.assertNotIn('resource_code', workshop_context)
    
    def test_coordinate_extraction_workshop_specific(self):
        """Test that workshop-specific coordinate extraction works."""
        from test.fixtures import MockActionContext
        action = MoveToWorkshopAction()
        
        # Test workshop_x/workshop_y extraction
        context = MockActionContext(character_name=self.char_name, workshop_x=100, workshop_y=200)
        x, y = action.get_target_coordinates(context)
        self.assertEqual((x, y), (100, 200))
        
        # Test mixed context (should prefer target_x/target_y)
        context = MockActionContext(
            character_name=self.char_name,
            target_x=300, target_y=400,
            workshop_x=500, workshop_y=600
        )
        x, y = action.get_target_coordinates(context)
        self.assertEqual((x, y), (300, 400))
        
        # Test with only workshop coordinates
        context = MockActionContext(character_name=self.char_name, workshop_x=700, workshop_y=800)
        x, y = action.get_target_coordinates(context)
        self.assertEqual((x, y), (700, 800))


if __name__ == '__main__':
    unittest.main()