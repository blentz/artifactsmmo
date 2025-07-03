"""
Test module for DetermineWorkshopRequirementsAction.
"""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.determine_workshop_requirements import DetermineWorkshopRequirementsAction
from src.lib.action_context import ActionContext


class TestDetermineWorkshopRequirementsAction(unittest.TestCase):
    """Test cases for DetermineWorkshopRequirementsAction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = DetermineWorkshopRequirementsAction()
        self.client = Mock()
        
        # Create context with knowledge base
        self.context = ActionContext()
        self.context.character_name = "test_character"
        self.context.knowledge_base = Mock()
        self.context.knowledge_base.data = {}
        
    def test_initialization(self):
        """Test action initialization."""
        self.assertIsInstance(self.action, DetermineWorkshopRequirementsAction)
        
    def test_repr(self):
        """Test string representation."""
        self.assertEqual(repr(self.action), "DetermineWorkshopRequirementsAction()")
        
    def test_execute_success(self):
        """Test successful workshop requirements determination."""
        # Setup transformations
        self.context['transformations_needed'] = [
            ('copper_ore', 'copper', 5),
            ('iron_ore', 'iron', 3)
        ]
        
        # Mock workshop determination
        with patch.object(self.action, '_determine_workshop_for_transformation') as mock_determine:
            mock_determine.side_effect = ['mining', 'mining']
            
            result = self.action.execute(self.client, self.context)
            
            self.assertTrue(result['success'])
            self.assertEqual(len(result['workshop_requirements']), 2)
            self.assertEqual(result['unique_workshops'], ['mining'])
            
            # Check stored context
            workshop_reqs = self.context.get('workshop_requirements')
            self.assertEqual(len(workshop_reqs), 2)
            self.assertEqual(workshop_reqs[0]['workshop_type'], 'mining')
            
    def test_execute_mixed_workshops(self):
        """Test with different workshop types."""
        self.context['transformations_needed'] = [
            ('copper_ore', 'copper', 5),
            ('ash_wood', 'ash_plank', 10)
        ]
        
        with patch.object(self.action, '_determine_workshop_for_transformation') as mock_determine:
            mock_determine.side_effect = ['mining', 'woodcutting']
            
            result = self.action.execute(self.client, self.context)
            
            self.assertTrue(result['success'])
            self.assertEqual(set(result['unique_workshops']), {'mining', 'woodcutting'})
            
    def test_execute_no_transformations(self):
        """Test with no transformations needed."""
        self.context['transformations_needed'] = []
        
        result = self.action.execute(self.client, self.context)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['workshop_requirements'], [])
        self.assertEqual(result['unique_workshops'], [])
        
    def test_execute_exception_handling(self):
        """Test exception handling."""
        self.context['transformations_needed'] = [('test', 'test', 1)]
        
        with patch.object(self.action, '_determine_workshop_for_transformation') as mock_determine:
            mock_determine.side_effect = Exception("Test error")
            
            result = self.action.execute(self.client, self.context)
            
            self.assertFalse(result['success'])
            self.assertIn("Failed to determine workshop requirements", result['error'])
            
    def test_determine_workshop_for_transformation_success(self):
        """Test determining workshop from API."""
        # Mock API response
        item_response = Mock()
        item_response.data = Mock()
        item_response.data.craft = Mock()
        item_response.data.craft.skill = 'mining'
        
        with patch('artifactsmmo_api_client.api.items.get_item_items_code_get.sync') as mock_api:
            mock_api.return_value = item_response
            
            with patch.object(self.action, '_get_workshop_for_skill') as mock_get_workshop:
                mock_get_workshop.return_value = 'mining'
                
                result = self.action._determine_workshop_for_transformation(
                    'copper_ore', 'copper', self.client, self.context.knowledge_base
                )
                
                self.assertEqual(result, 'mining')
                
    def test_determine_workshop_no_craft_data(self):
        """Test when item has no craft data."""
        item_response = Mock()
        item_response.data = Mock()
        item_response.data.craft = None
        
        with patch('artifactsmmo_api_client.api.items.get_item_items_code_get.sync') as mock_api:
            mock_api.return_value = item_response
            
            result = self.action._determine_workshop_for_transformation(
                'test', 'test', self.client, self.context.knowledge_base
            )
            
            self.assertIsNone(result)
            
    def test_determine_workshop_exception(self):
        """Test workshop determination with exception."""
        with patch('artifactsmmo_api_client.api.items.get_item_items_code_get.sync') as mock_api:
            mock_api.side_effect = Exception("API error")
            
            result = self.action._determine_workshop_for_transformation(
                'error', 'error', self.client, self.context.knowledge_base
            )
            
            self.assertIsNone(result)
            
    def test_get_workshop_for_skill_from_knowledge_base(self):
        """Test getting workshop from knowledge base."""
        knowledge_base = Mock()
        knowledge_base.data = {
            'workshops': {
                'mining_workshop_1': {'skill': 'mining'},
                'woodcutting_workshop_east': {'skill': 'woodcutting'}
            }
        }
        
        result = self.action._get_workshop_for_skill('mining', knowledge_base)
        self.assertEqual(result, 'mining')
        
        result = self.action._get_workshop_for_skill('woodcutting', knowledge_base)
        self.assertEqual(result, 'woodcutting')
        
    def test_get_workshop_for_skill_fallback_mapping(self):
        """Test fallback skill to workshop mapping."""
        knowledge_base = Mock()
        knowledge_base.data = {}
        
        # Test direct mappings
        self.assertEqual(self.action._get_workshop_for_skill('mining', knowledge_base), 'mining')
        self.assertEqual(self.action._get_workshop_for_skill('smelting', knowledge_base), 'mining')
        self.assertEqual(self.action._get_workshop_for_skill('woodcutting', knowledge_base), 'woodcutting')
        self.assertEqual(self.action._get_workshop_for_skill('woodworking', knowledge_base), 'woodcutting')
        self.assertEqual(self.action._get_workshop_for_skill('weaponcrafting', knowledge_base), 'weaponcrafting')
        self.assertEqual(self.action._get_workshop_for_skill('cooking', knowledge_base), 'cooking')
        
        # Test unknown skill defaults to itself
        self.assertEqual(self.action._get_workshop_for_skill('unknown_skill', knowledge_base), 'unknown_skill')
        
    def test_workshop_requirements_structure(self):
        """Test the structure of workshop requirements output."""
        self.context['transformations_needed'] = [
            ('copper_ore', 'copper', 5)
        ]
        
        with patch.object(self.action, '_determine_workshop_for_transformation') as mock_determine:
            mock_determine.return_value = 'mining'
            
            result = self.action.execute(self.client, self.context)
            
            workshop_reqs = self.context.get('workshop_requirements')
            self.assertEqual(len(workshop_reqs), 1)
            
            req = workshop_reqs[0]
            self.assertIn('raw_material', req)
            self.assertIn('refined_material', req)
            self.assertIn('quantity', req)
            self.assertIn('workshop_type', req)
            
            self.assertEqual(req['raw_material'], 'copper_ore')
            self.assertEqual(req['refined_material'], 'copper')
            self.assertEqual(req['quantity'], 5)
            self.assertEqual(req['workshop_type'], 'mining')


if __name__ == '__main__':
    unittest.main()