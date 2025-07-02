"""
Tests for new validators in ActionValidator:
- location_has_content
- workshop_compatible
- resource_matches_target
"""

import unittest
from unittest.mock import Mock

from src.controller.action_validator import ActionValidator, ValidationError, ValidationWarning

from test.fixtures import MockActionContext


class TestActionValidatorNewValidators(unittest.TestCase):
    """Test the new validators for content-based validation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.validator = ActionValidator()
        
    def test_validate_location_has_content_workshop_success(self):
        """Test location_has_content validator when workshop is present."""
        # Setup context with workshop at location
        context = MockActionContext()
        context.character_state = Mock()
        context.character_state.data = {'x': 5, 'y': 10}
        
        # Setup map state with workshop content
        context.map_state = Mock()
        context.map_state.data = {
            '5,10': {
                'content': {
                    'type': 'workshop',
                    'code': 'weaponcrafting'
                }
            }
        }
        
        # Test validation
        params = {}
        rule = {'content_type': 'workshop'}
        
        result = self.validator._validate_location_has_content(params, rule, context)
        
        # Should succeed - no error
        self.assertIsNone(result)
        
    def test_validate_location_has_content_resource_mismatch(self):
        """Test location_has_content validator when content type doesn't match."""
        # Setup context with resource at location
        context = MockActionContext()
        context.character_state = Mock()
        context.character_state.data = {'x': 5, 'y': 10}
        
        # Setup map state with resource content
        context.map_state = Mock()
        context.map_state.data = {
            '5,10': {
                'content': {
                    'type': 'resource',
                    'code': 'iron_ore'
                }
            }
        }
        
        # Test validation expecting workshop
        params = {}
        rule = {'content_type': 'workshop'}
        
        result = self.validator._validate_location_has_content(params, rule, context)
        
        # Should fail - content type mismatch
        self.assertIsInstance(result, ValidationError)
        self.assertEqual(result.validator, "location_has_content")
        self.assertIn("does not have expected content type", result.message)
        self.assertEqual(result.details['expected_type'], 'workshop')
        self.assertEqual(result.details['actual_type'], 'resource')
        
    def test_validate_location_has_content_no_character_state(self):
        """Test location_has_content validator when character state is missing."""
        # Setup context without character state
        context = MockActionContext()
        context.character_state = None
        
        params = {}
        rule = {'content_type': 'workshop'}
        
        result = self.validator._validate_location_has_content(params, rule, context)
        
        # Should return warning
        self.assertIsInstance(result, ValidationWarning)
        self.assertEqual(result.validator, "location_has_content")
        self.assertIn("no character state", result.message)
        
    def test_validate_workshop_compatible_success(self):
        """Test workshop_compatible validator with matching workshop."""
        # Setup context
        context = MockActionContext()
        context.character_state = Mock()
        context.character_state.data = {'x': 5, 'y': 10}
        
        # Setup knowledge base with item data
        context.knowledge_base = Mock()
        context.knowledge_base.get_item_data = Mock(return_value={
            'code': 'iron_sword',
            'craft': {
                'skill': 'weaponcrafting',
                'materials': [{'code': 'iron_bar', 'quantity': 2}]
            }
        })
        
        # Setup map state with correct workshop
        context.map_state = Mock()
        context.map_state.data = {
            '5,10': {
                'content': {
                    'type': 'workshop',
                    'code': 'weaponcrafting'
                }
            }
        }
        
        # Test validation
        params = {'item_code': 'iron_sword'}
        rule = {'item_param': 'item_code'}
        
        result = self.validator._validate_workshop_compatible(params, rule, context)
        
        # Should succeed
        self.assertIsNone(result)
        
    def test_validate_workshop_compatible_wrong_workshop(self):
        """Test workshop_compatible validator with wrong workshop type."""
        # Setup context
        context = MockActionContext()
        context.character_state = Mock()
        context.character_state.data = {'x': 5, 'y': 10}
        
        # Setup knowledge base with item requiring weaponcrafting
        context.knowledge_base = Mock()
        context.knowledge_base.get_item_data = Mock(return_value={
            'code': 'iron_sword',
            'craft': {
                'skill': 'weaponcrafting',
                'materials': [{'code': 'iron_bar', 'quantity': 2}]
            }
        })
        
        # Setup map state with wrong workshop type
        context.map_state = Mock()
        context.map_state.data = {
            '5,10': {
                'content': {
                    'type': 'workshop',
                    'code': 'gearcrafting'  # Wrong type!
                }
            }
        }
        
        # Test validation
        params = {'item_code': 'iron_sword'}
        rule = {'item_param': 'item_code'}
        
        result = self.validator._validate_workshop_compatible(params, rule, context)
        
        # Should fail
        self.assertIsInstance(result, ValidationError)
        self.assertEqual(result.validator, "workshop_compatible")
        self.assertIn("Workshop type mismatch", result.message)
        self.assertEqual(result.details['required_skill'], 'weaponcrafting')
        self.assertEqual(result.details['current_workshop'], 'gearcrafting')
        
    def test_validate_workshop_compatible_item_not_craftable(self):
        """Test workshop_compatible validator with non-craftable item."""
        # Setup context
        context = MockActionContext()
        context.knowledge_base = Mock()
        context.knowledge_base.get_item_data = Mock(return_value={
            'code': 'raw_chicken',
            'type': 'resource'
            # No 'craft' field - not craftable
        })
        
        # Test validation
        params = {'item_code': 'raw_chicken'}
        rule = {'item_param': 'item_code'}
        
        result = self.validator._validate_workshop_compatible(params, rule, context)
        
        # Should fail
        self.assertIsInstance(result, ValidationError)
        self.assertEqual(result.validator, "workshop_compatible")
        self.assertIn("is not craftable", result.message)
        
    def test_validate_resource_matches_target_success(self):
        """Test resource_matches_target validator with matching resource."""
        # Setup context
        context = MockActionContext()
        context.character_state = Mock()
        context.character_state.data = {'x': 5, 'y': 10}
        
        # Setup map state with target resource
        context.map_state = Mock()
        context.map_state.data = {
            '5,10': {
                'content': {
                    'type': 'resource',
                    'code': 'iron_ore'
                }
            }
        }
        
        # Test validation
        params = {'resource_type': 'iron_ore'}
        rule = {'resource_param': 'resource_type'}
        
        result = self.validator._validate_resource_matches_target(params, rule, context)
        
        # Should succeed
        self.assertIsNone(result)
        
    def test_validate_resource_matches_target_mismatch(self):
        """Test resource_matches_target validator with wrong resource."""
        # Setup context
        context = MockActionContext()
        context.character_state = Mock()
        context.character_state.data = {'x': 5, 'y': 10}
        
        # Setup map state with different resource
        context.map_state = Mock()
        context.map_state.data = {
            '5,10': {
                'content': {
                    'type': 'resource',
                    'code': 'copper_ore'
                }
            }
        }
        
        # Test validation expecting iron_ore
        params = {'resource_type': 'iron_ore'}
        rule = {'resource_param': 'resource_type'}
        
        result = self.validator._validate_resource_matches_target(params, rule, context)
        
        # Should fail
        self.assertIsInstance(result, ValidationError)
        self.assertEqual(result.validator, "resource_matches_target")
        self.assertIn("expected", result.message)
        self.assertEqual(result.details['found_resource'], 'copper_ore')
        self.assertEqual(result.details['expected_resource'], 'iron_ore')
        
    def test_validate_resource_matches_target_no_resource(self):
        """Test resource_matches_target validator when location has no resource."""
        # Setup context
        context = MockActionContext()
        context.character_state = Mock()
        context.character_state.data = {'x': 5, 'y': 10}
        
        # Setup map state with non-resource content
        context.map_state = Mock()
        context.map_state.data = {
            '5,10': {
                'content': {
                    'type': 'workshop',
                    'code': 'weaponcrafting'
                }
            }
        }
        
        # Test validation
        params = {'resource_type': 'iron_ore'}
        rule = {'resource_param': 'resource_type'}
        
        result = self.validator._validate_resource_matches_target(params, rule, context)
        
        # Should fail
        self.assertIsInstance(result, ValidationError)
        self.assertEqual(result.validator, "resource_matches_target")
        self.assertIn("does not contain a resource", result.message)
        self.assertEqual(result.details['content_type'], 'workshop')
        
    def test_validate_resource_matches_target_no_target(self):
        """Test resource_matches_target validator when no target specified."""
        # Setup context
        context = MockActionContext()
        
        # Test validation with no target resource
        params = {}  # No resource_type parameter
        rule = {'resource_param': 'resource_type'}
        
        result = self.validator._validate_resource_matches_target(params, rule, context)
        
        # Should succeed - no target means any resource is fine
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()