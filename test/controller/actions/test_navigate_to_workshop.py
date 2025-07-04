"""
Test module for NavigateToWorkshopAction.
"""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.navigate_to_workshop import NavigateToWorkshopAction
from src.controller.actions.base import ActionResult
from src.lib.action_context import ActionContext


class TestNavigateToWorkshopAction(unittest.TestCase):
    """Test cases for NavigateToWorkshopAction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = NavigateToWorkshopAction()
        self.client = Mock()
        
        # Create context
        self.context = ActionContext()
        self.context.character_name = "test_character"
        self.context.knowledge_base = Mock()
        self.context.knowledge_base.data = {}
        self.context.map_state = Mock()
        
    def test_initialization(self):
        """Test action initialization."""
        self.assertIsInstance(self.action, NavigateToWorkshopAction)
        
    def test_repr(self):
        """Test string representation."""
        self.assertEqual(repr(self.action), "NavigateToWorkshopAction()")
        
    def test_execute_no_workshop_type(self):
        """Test execution without workshop type."""
        result = self.action.execute(self.client, self.context)
        
        self.assertFalse(result.success)
        self.assertIn("No workshop type specified", result.error)
        
    def test_execute_already_at_workshop(self):
        """Test when already at the workshop."""
        self.context['workshop_type'] = 'mining'
        
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
                
                self.assertTrue(result.success)
                self.assertTrue(result.data['already_at_workshop'])
                self.assertEqual(result.data['workshop_type'], 'mining')
                self.assertEqual(result.data['location'], {'x': 10, 'y': 20})
                
    def test_execute_successful_movement(self):
        """Test successful movement to workshop."""
        self.context['workshop_type'] = 'mining'
        
        # Mock character at different location
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.x = 5
        char_response.data.y = 5
        
        with patch('artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync') as mock_get_char:
            mock_get_char.return_value = char_response
            
            with patch.object(self.action, '_find_workshop_location') as mock_find:
                mock_find.return_value = (10, 20)
                
                with patch('src.controller.actions.navigate_to_workshop.MoveAction') as mock_move_class:
                    mock_move = Mock()
                    mock_move.execute.return_value = ActionResult(success=True)
                    mock_move_class.return_value = mock_move
                    
                    result = self.action.execute(self.client, self.context)
                    
                    self.assertTrue(result.success)
                    self.assertTrue(result.data['moved_to_workshop'])
                    self.assertEqual(result.data['workshop_type'], 'mining')
                    self.assertEqual(result.data['location'], {'x': 10, 'y': 20})
                    
    def test_execute_workshop_not_found(self):
        """Test when workshop location not found."""
        self.context['workshop_type'] = 'unknown'
        
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.x = 5
        char_response.data.y = 5
        
        with patch('artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync') as mock_get_char:
            mock_get_char.return_value = char_response
            
            with patch.object(self.action, '_find_workshop_location') as mock_find:
                mock_find.return_value = None
                
                result = self.action.execute(self.client, self.context)
                
                self.assertFalse(result.success)
                self.assertIn("Could not find unknown workshop", result.error)
                
    def test_execute_movement_fails(self):
        """Test when movement to workshop fails."""
        self.context['workshop_type'] = 'mining'
        
        char_response = Mock()
        char_response.data = Mock()
        char_response.data.x = 5
        char_response.data.y = 5
        
        with patch('artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync') as mock_get_char:
            mock_get_char.return_value = char_response
            
            with patch.object(self.action, '_find_workshop_location') as mock_find:
                mock_find.return_value = (10, 20)
                
                with patch('src.controller.actions.navigate_to_workshop.MoveAction') as mock_move_class:
                    mock_move = Mock()
                    mock_move.execute.return_value = ActionResult(success=False)
                    mock_move_class.return_value = mock_move
                    
                    result = self.action.execute(self.client, self.context)
                    
                    self.assertFalse(result.success)
                    self.assertIn("Failed to move to mining workshop", result.error)
                    
    def test_execute_character_api_fails(self):
        """Test when character API fails."""
        self.context['workshop_type'] = 'mining'
        
        with patch('artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync') as mock_get_char:
            mock_get_char.return_value = None
            
            result = self.action.execute(self.client, self.context)
            
            self.assertFalse(result.success)
            self.assertIn("Could not get character location", result.error)
            
    def test_execute_exception_handling(self):
        """Test exception handling."""
        self.context['workshop_type'] = 'mining'
        
        with patch('artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync') as mock_get_char:
            mock_get_char.side_effect = Exception("Test error")
            
            result = self.action.execute(self.client, self.context)
            
            self.assertFalse(result.success)
            self.assertIn("Failed to navigate to workshop", result.error)
            
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
        
        # Non-workshop content should not match
        result = self.action._find_workshop_location('copper', knowledge_base)
        self.assertIsNone(result)
        
    def test_find_workshop_location_not_found(self):
        """Test when workshop not found."""
        knowledge_base = Mock()
        knowledge_base.data = {'workshops': {}, 'maps': {}}
        
        result = self.action._find_workshop_location('unknown', knowledge_base)
        self.assertIsNone(result)
        
    def test_find_workshop_location_no_knowledge_base(self):
        """Test with no knowledge base."""
        result = self.action._find_workshop_location('mining', None)
        self.assertIsNone(result)
        
    def test_find_workshop_location_missing_coordinates(self):
        """Test workshop with missing coordinates."""
        knowledge_base = Mock()
        knowledge_base.data = {
            'workshops': {
                'mining_workshop_1': {'x': 10},  # Missing y
                'woodcutting_workshop': {}  # Missing both
            }
        }
        
        result = self.action._find_workshop_location('mining', knowledge_base)
        self.assertIsNone(result)
        
        result = self.action._find_workshop_location('woodcutting', knowledge_base)
        self.assertIsNone(result)
        
    def test_find_workshop_location_invalid_map_coords(self):
        """Test invalid coordinates in maps data."""
        knowledge_base = Mock()
        knowledge_base.data = {
            'maps': {
                'invalid_coords': {
                    'content': {
                        'type': 'workshop',
                        'code': 'mining_workshop'
                    }
                }
            }
        }
        
        result = self.action._find_workshop_location('mining', knowledge_base)
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()