"""
Test Navigate to Workshop Action

Streamlined tests focusing on the public interface and subgoal behavior.
"""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.navigate_to_workshop import NavigateToWorkshopAction
from src.controller.actions.base import ActionResult
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from test.test_base import UnifiedContextTestBase


class TestNavigateToWorkshopAction(UnifiedContextTestBase):
    """Test the NavigateToWorkshopAction class public interface."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.action = NavigateToWorkshopAction()
        self.client = Mock()
        self.context.set(StateParameters.CHARACTER_NAME, "test_character")
        
        # Mock knowledge base
        self.mock_kb = Mock()
        self.mock_kb.data = {}
        self.context.knowledge_base = self.mock_kb
        
    def test_init(self):
        """Test action initialization."""
        action = NavigateToWorkshopAction()
        self.assertIsNotNone(action)
        
    def test_repr(self):
        """Test string representation."""
        result = repr(self.action)
        self.assertIn("NavigateToWorkshopAction", result)
        
    def test_goap_parameters(self):
        """Test GOAP parameters are properly defined."""
        # Test conditions exist
        self.assertIn('character_status', self.action.conditions)
        
        # Test reactions exist  
        self.assertIn('at_workshop', self.action.reactions)
        
        # Test weight is defined
        self.assertIsInstance(self.action.weight, (int, float))
        self.assertGreater(self.action.weight, 0)

    def test_execute_no_workshop_type(self):
        """Test execution without workshop type."""
        result = self.action.execute(self.client, self.context)
        
        self.assertIsInstance(result, ActionResult)
        self.assertFalse(result.success)
        self.assertIn("No workshop type specified", result.error)

    def test_execute_workshop_not_found(self):
        """Test when workshop location not found."""
        self.context.set(StateParameters.WORKSHOP_TYPE, 'unknown')
        
        # Mock _find_workshop_location to return None
        with patch.object(self.action, '_find_workshop_location') as mock_find:
            mock_find.return_value = None
            
            result = self.action.execute(self.client, self.context)
            
            self.assertIsInstance(result, ActionResult)
            self.assertFalse(result.success)
            self.assertIn("Could not find unknown workshop", result.error)

    def test_execute_already_at_workshop(self):
        """Test when already at the workshop."""
        self.context.set(StateParameters.WORKSHOP_TYPE, 'mining')
        
        # Mock character at workshop location
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.x = 10
        char_response.data.y = 20
        
        with patch('artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync') as mock_get_char:
            mock_get_char.return_value = char_response
            
            with patch.object(self.action, '_find_workshop_location') as mock_find:
                mock_find.return_value = (10, 20)  # Same location
                
                result = self.action.execute(self.client, self.context)
                
                self.assertIsInstance(result, ActionResult)
                self.assertTrue(result.success)
                self.assertTrue(result.data['already_at_workshop'])
                self.assertEqual(result.data['workshop_type'], 'mining')

    def test_execute_character_api_fails(self):
        """Test when character API fails."""
        self.context.set(StateParameters.WORKSHOP_TYPE, 'mining')
        
        # Mock workshop found but character API fails
        with patch.object(self.action, '_find_workshop_location') as mock_find:
            mock_find.return_value = (10, 20)
            
            with patch('artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync') as mock_get_char:
                mock_get_char.return_value = None
                
                result = self.action.execute(self.client, self.context)
                
                self.assertIsInstance(result, ActionResult)
                # Should still request movement subgoal even if character API fails initially
                # The actual movement action will handle the API failure

    def test_execute_requests_movement_subgoal(self):
        """Test that action requests movement subgoal when needed."""
        self.context.set(StateParameters.WORKSHOP_TYPE, 'mining')
        
        # Mock character at different location
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.x = 5
        char_response.data.y = 5
        
        with patch('artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync') as mock_get_char:
            mock_get_char.return_value = char_response
            
            with patch.object(self.action, '_find_workshop_location') as mock_find:
                mock_find.return_value = (10, 20)
                
                with patch.object(self.action, 'request_movement_subgoal') as mock_request:
                    mock_request.return_value = ActionResult(success=True, data={'subgoal_requested': True})
                    
                    result = self.action.execute(self.client, self.context)
                    
                    self.assertIsInstance(result, ActionResult)
                    # Verify movement subgoal was requested
                    mock_request.assert_called_once_with(self.context, 10, 20, preserve_keys=['workshop_type'])

    def test_execute_exception_handling(self):
        """Test exception handling."""
        self.context.set(StateParameters.WORKSHOP_TYPE, 'mining')
        
        with patch.object(self.action, '_find_workshop_location') as mock_find:
            mock_find.side_effect = Exception("Test error")
            
            result = self.action.execute(self.client, self.context)
            
            self.assertIsInstance(result, ActionResult)
            self.assertFalse(result.success)
            self.assertIn("Failed to navigate to workshop", result.error)

    def test_verify_workshop_arrival_success(self):
        """Test workshop arrival verification."""
        self.context.set(StateParameters.TARGET_X, 10)
        self.context.set(StateParameters.TARGET_Y, 20)
        
        result = self.action._verify_workshop_arrival(self.client, self.context, 'mining')
        
        self.assertIsInstance(result, ActionResult)
        self.assertTrue(result.success)
        self.assertTrue(result.data['moved_to_workshop'])
        self.assertEqual(result.data['workshop_type'], 'mining')

    def test_verify_workshop_arrival_no_coordinates(self):
        """Test workshop arrival verification with missing coordinates."""
        # Don't set target coordinates
        
        result = self.action._verify_workshop_arrival(self.client, self.context, 'mining')
        
        self.assertIsInstance(result, ActionResult)
        self.assertFalse(result.success)
        self.assertIn("No target coordinates found", result.error)

    def test_find_workshop_location_in_workshops(self):
        """Test finding workshop in workshops data."""
        knowledge_base = Mock()
        knowledge_base.data = {
            'workshops': {
                'mining_workshop_1': {'x': 10, 'y': 20},
                'woodcutting_workshop_east': {'x': 30, 'y': 40}
            }
        }
        
        result = self.action._find_workshop_location('mining', knowledge_base)
        self.assertEqual(result, (10, 20))
        
        result = self.action._find_workshop_location('woodcutting', knowledge_base)
        self.assertEqual(result, (30, 40))

    def test_find_workshop_location_in_maps(self):
        """Test finding workshop in maps data."""
        knowledge_base = Mock()
        knowledge_base.data = {
            'workshops': {},
            'maps': {
                '10,20': {
                    'content': {
                        'type': 'workshop',
                        'code': 'mining_workshop'
                    }
                },
                '30,40': {
                    'content': {
                        'type': 'resource',
                        'code': 'copper_ore'
                    }
                }
            }
        }
        
        result = self.action._find_workshop_location('mining', knowledge_base)
        self.assertEqual(result, (10, 20))

    def test_find_workshop_location_not_found(self):
        """Test when workshop location is not found."""
        knowledge_base = Mock()
        knowledge_base.data = {'workshops': {}, 'maps': {}}
        
        result = self.action._find_workshop_location('unknown', knowledge_base)
        self.assertIsNone(result)

    def test_find_workshop_location_no_knowledge_base(self):
        """Test when knowledge base is not available."""
        result = self.action._find_workshop_location('mining', None)
        self.assertIsNone(result)

    def test_find_workshop_location_invalid_map_coords(self):
        """Test handling of invalid map coordinates."""
        knowledge_base = Mock()
        knowledge_base.data = {
            'workshops': {},
            'maps': {
                'invalid,coords': {
                    'content': {
                        'type': 'workshop',
                        'code': 'mining_workshop'
                    }
                }
            }
        }
        
        result = self.action._find_workshop_location('mining', knowledge_base)
        self.assertIsNone(result)

    def test_find_workshop_location_missing_coordinates(self):
        """Test handling of missing coordinates in workshop data."""
        knowledge_base = Mock()
        knowledge_base.data = {
            'workshops': {
                'mining_workshop_1': {'x': 10},  # Missing y coordinate
                'mining_workshop_2': {'y': 20}   # Missing x coordinate
            }
        }
        
        result = self.action._find_workshop_location('mining', knowledge_base)
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()