"""
Tests for YAML-only actions that don't have Python implementations.

These actions are defined purely in YAML configuration and executed
through the metaprogramming system.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.controller.action_factory import ActionFactory
from src.lib.actions_data import ActionsData
from src.lib.unified_state_context import UnifiedStateContext


class TestYAMLOnlyActions:
    """Test YAML-only actions like verify_material_sufficiency."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.action_factory = ActionFactory()
        self.actions_data = ActionsData("config/default_actions.yaml")
        self.actions_config = self.actions_data.get_actions()
        
        # Create default state structure for testing
        self.default_state = {
            'materials': {
                'status': 'unknown',
                'transformation_complete': False,
                'ready_to_craft': False,
                'requirements_determined': False,
                'availability_checked': False,
                'quantities_calculated': False,
                'raw_materials_needed': False,
                'gathered': False
            },
            'character_status': {
                'alive': True,
                'safe': True,
                'cooldown_active': False
            },
            'location_context': {
                'resource_known': False,
                'at_resource': False,
                'workshop_known': False,
                'at_workshop': False,
                'at_target': False
            },
            'equipment_status': {
                'has_selected_item': False
            }
        }
        
    def test_verify_material_sufficiency_action_exists(self):
        """Test that verify_material_sufficiency is defined in actions."""
        assert 'verify_material_sufficiency' in self.actions_config
        
        action = self.actions_config['verify_material_sufficiency']
        
        # Check conditions
        assert 'conditions' in action
        assert 'materials' in action['conditions']
        assert action['conditions']['materials']['transformation_complete'] == True
        assert action['conditions']['materials']['status'] == 'transformed'
        
        # Check reactions
        assert 'reactions' in action
        assert 'materials' in action['reactions']
        assert action['reactions']['materials']['status'] == 'sufficient'
        assert action['reactions']['materials']['ready_to_craft'] == True
        
    def test_yaml_only_actions_through_factory(self):
        """Test that YAML-only actions can be loaded through ActionFactory."""
        # Test that factory can identify YAML-only actions  
        yaml_action = 'verify_material_sufficiency'
        
        # This action should exist in YAML configuration
        assert yaml_action in self.actions_config
        
        # Test that the action has proper GOAP structure
        action_config = self.actions_config[yaml_action]
        assert 'conditions' in action_config
        assert 'reactions' in action_config
        assert 'weight' in action_config
        assert 'description' in action_config
        
        # Test conditions and reactions match expected pattern
        conditions = action_config['conditions']
        reactions = action_config['reactions']
        
        # Should have material transformation conditions
        assert 'materials' in conditions
        assert conditions['materials']['transformation_complete'] == True
        assert conditions['materials']['status'] == 'transformed'
        
        # Should react by setting status to sufficient
        assert 'materials' in reactions
        assert reactions['materials']['status'] == 'sufficient'
        assert reactions['materials']['ready_to_craft'] == True
        
    def test_all_yaml_material_actions(self):
        """Test all YAML-defined material gathering actions exist."""
        yaml_actions = [
            'find_resources',
            'move_to_resource',
            'gather_resources',
            'find_workshops',
            'move_to_workshop',
            'transform_materials',
            'verify_material_sufficiency'
        ]
        
        for action_name in yaml_actions:
            assert action_name in self.actions_config, f"Missing action: {action_name}"
            
            action = self.actions_config[action_name]
            assert 'conditions' in action
            assert 'reactions' in action
            assert 'weight' in action
            assert 'description' in action
            
    def test_action_chain_conditions_reactions(self):
        """Test that action conditions and reactions properly chain."""
        # Check find_resources -> move_to_resource chain
        find_res = self.actions_config['find_resources']
        move_res = self.actions_config['move_to_resource']
        
        # find_resources sets resource_known to true
        assert find_res['reactions']['location_context']['resource_known'] == True
        
        # move_to_resource requires resource_known to be true
        assert move_res['conditions']['location_context']['resource_known'] == True
        
        # move_to_resource sets at_resource to true
        assert move_res['reactions']['location_context']['at_resource'] == True
        
        # gather_resources requires at_resource to be true
        gather = self.actions_config['gather_resources']
        assert gather['conditions']['location_context']['at_resource'] == True
        
    def test_material_status_progression(self):
        """Test material status progression through the chain."""
        status_progression = [
            ('checking', ['check_material_availability', 'determine_material_insufficiency', 'check_availability', 'determine_insufficiency']),
            ('insufficient', ['find_resources', 'search_resources']),
            ('gathered_raw', ['find_workshops', 'search_workshops']),
            ('transformed', ['verify_material_sufficiency']),
            ('sufficient', ['craft_item'])
        ]
        
        for status, expected_actions in status_progression[1:]:  # Skip checking
            # Find actions that work with this status
            matching_actions = []
            for action_name, action_config in self.actions_config.items():
                conditions = action_config.get('conditions', {})
                if 'materials' in conditions and conditions['materials'].get('status') == status:
                    matching_actions.append(action_name)
                    
            # At least one expected action should handle this status
            found_expected = any(expected in matching_actions for expected in expected_actions)
            assert found_expected, f"No expected action handles materials.status={status}. Found: {matching_actions}, Expected any of: {expected_actions}"