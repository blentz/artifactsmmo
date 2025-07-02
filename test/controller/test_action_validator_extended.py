"""Test module for extended Action Validator features."""

import unittest
from unittest.mock import Mock, patch

from src.controller.action_validator import ActionValidator, ValidationError, ValidationWarning


class TestActionValidatorExtended(unittest.TestCase):
    """Test cases for extended ActionValidator features."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create validator with test configuration
        self.patcher = patch('src.controller.action_validator.YamlData')
        mock_yaml = self.patcher.start()
        mock_yaml.return_value.data = {
            'validation_rules': {
                'global': [],
                'actions': {
                    'craft_item': [
                        {'type': 'required_params', 'params': ['item_code']},
                        {'type': 'location_has_content', 'content_type': 'workshop'},
                        {'type': 'workshop_compatible', 'item_param': 'item_code'}
                    ],
                    'gather_resources': [
                        {'type': 'location_has_content', 'content_type': 'resource'},
                        {'type': 'resource_matches_target', 'resource_param': 'target_resource'}
                    ]
                }
            }
        }
        self.validator = ActionValidator()
    
    def tearDown(self):
        """Clean up patches."""
        self.patcher.stop()
    
    def test_location_has_content_validator_success(self):
        """Test location_has_content validator with correct content."""
        params = {}
        rule = {'content_type': 'workshop'}
        
        # Mock context with proper workshop location
        context = Mock()
        character_state = Mock()
        character_state.data = {'x': 10, 'y': 20}
        context.character_state = character_state
        
        map_state = Mock()
        map_state.data = {
            '10,20': {
                'content': {'type': 'workshop', 'code': 'weaponcrafting'}
            }
        }
        context.map_state = map_state
        
        error = self.validator._validate_location_has_content(params, rule, context)
        self.assertIsNone(error)
    
    def test_location_has_content_validator_wrong_type(self):
        """Test location_has_content validator with wrong content type."""
        params = {}
        rule = {'content_type': 'workshop'}
        
        # Mock context with resource location instead of workshop
        context = Mock()
        character_state = Mock()
        character_state.data = {'x': 10, 'y': 20}
        context.character_state = character_state
        
        map_state = Mock()
        map_state.data = {
            '10,20': {
                'content': {'type': 'resource', 'code': 'tree'}
            }
        }
        context.map_state = map_state
        
        error = self.validator._validate_location_has_content(params, rule, context)
        self.assertIsNotNone(error)
        self.assertIsInstance(error, ValidationError)
        self.assertIn("does not have expected content type", error.message)
    
    def test_location_has_content_validator_no_position(self):
        """Test location_has_content validator without character position."""
        params = {}
        rule = {'content_type': 'workshop'}
        
        context = Mock()
        context.character_state = None
        
        error = self.validator._validate_location_has_content(params, rule, context)
        self.assertIsNotNone(error)
        self.assertIsInstance(error, ValidationWarning)
        self.assertIn("no character state", error.message)
    
    def test_workshop_compatible_validator_success(self):
        """Test workshop_compatible validator with matching workshop."""
        params = {'item_code': 'wooden_sword'}
        rule = {'item_param': 'item_code'}
        
        # Mock context
        context = Mock()
        character_state = Mock()
        character_state.data = {'x': 10, 'y': 20}
        context.character_state = character_state
        
        # Mock knowledge base
        knowledge_base = Mock()
        knowledge_base.get_item_data.return_value = {
            'craft': {'skill': 'weaponcrafting'}
        }
        context.knowledge_base = knowledge_base
        
        # Mock map state with weaponcrafting workshop
        map_state = Mock()
        map_state.data = {
            '10,20': {
                'content': {'type': 'workshop', 'code': 'weaponcrafting'}
            }
        }
        context.map_state = map_state
        
        error = self.validator._validate_workshop_compatible(params, rule, context)
        self.assertIsNone(error)
    
    def test_workshop_compatible_validator_mismatch(self):
        """Test workshop_compatible validator with wrong workshop type."""
        params = {'item_code': 'wooden_sword'}
        rule = {'item_param': 'item_code'}
        
        # Mock context
        context = Mock()
        character_state = Mock()
        character_state.data = {'x': 10, 'y': 20}
        context.character_state = character_state
        
        # Mock knowledge base - item requires weaponcrafting
        knowledge_base = Mock()
        knowledge_base.get_item_data.return_value = {
            'craft': {'skill': 'weaponcrafting'}
        }
        context.knowledge_base = knowledge_base
        
        # Mock map state with cooking workshop
        map_state = Mock()
        map_state.data = {
            '10,20': {
                'content': {'type': 'workshop', 'code': 'cooking'}
            }
        }
        context.map_state = map_state
        
        error = self.validator._validate_workshop_compatible(params, rule, context)
        self.assertIsNotNone(error)
        self.assertIsInstance(error, ValidationError)
        self.assertIn("Workshop type mismatch", error.message)
        self.assertIn("weaponcrafting but at cooking", error.message)
    
    def test_resource_matches_target_validator_success(self):
        """Test resource_matches_target validator with matching resource."""
        params = {'target_resource': 'tree'}
        rule = {'param': 'target_resource'}
        
        # Mock context
        context = Mock()
        context.character_x = 10
        context.character_y = 20
        
        # Mock map state with tree resource
        map_state = Mock()
        map_state.get_location.return_value = {
            'content': {'type': 'resource', 'code': 'tree'}
        }
        context.map_state = map_state
        
        error = self.validator._validate_resource_matches_target(params, rule, context)
        self.assertIsNone(error)
    
    def test_resource_matches_target_validator_mismatch(self):
        """Test resource_matches_target validator with wrong resource."""
        params = {'resource_type': 'tree'}
        rule = {'resource_param': 'resource_type'}
        
        # Mock context
        context = Mock()
        character_state = Mock()
        character_state.data = {'x': 10, 'y': 20}
        context.character_state = character_state
        
        # Mock map state with iron resource instead of tree
        map_state = Mock()
        map_state.data = {
            '10,20': {
                'content': {'type': 'resource', 'code': 'iron'}
            }
        }
        context.map_state = map_state
        
        error = self.validator._validate_resource_matches_target(params, rule, context)
        self.assertIsNotNone(error)
        self.assertIsInstance(error, ValidationError)
        self.assertIn("expected 'tree'", error.message)
    
    def test_resource_matches_target_validator_no_target(self):
        """Test resource_matches_target validator without target (should pass)."""
        params = {}  # No target_resource specified
        rule = {'param': 'target_resource'}
        
        context = Mock()
        
        error = self.validator._validate_resource_matches_target(params, rule, context)
        self.assertIsNone(error)  # Should pass when no target specified
    
    def test_full_action_validation_craft_item(self):
        """Test full validation flow for craft_item action."""
        action_name = 'craft_item'
        params = {'item_code': 'wooden_sword'}
        
        # Mock context with all required data
        context = Mock()
        context.character_x = 10
        context.character_y = 20
        
        # Mock map state
        map_state = Mock()
        map_state.get_location.return_value = {
            'content': {'type': 'workshop', 'code': 'weaponcrafting'}
        }
        context.map_state = map_state
        
        # Mock knowledge base
        knowledge_base = Mock()
        knowledge_base.get_item_data.return_value = {
            'craft': {'skill': 'weaponcrafting'}
        }
        context.knowledge_base = knowledge_base
        
        # Mock character state (for character_alive check)
        character_state = Mock()
        character_state.hp = 50
        context.character_state = character_state
        
        result = self.validator.validate_action(action_name, params, context)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)


if __name__ == '__main__':
    unittest.main()