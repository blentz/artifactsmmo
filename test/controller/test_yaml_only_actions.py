"""
Tests for YAML-only actions that don't have Python implementations.

These actions are defined purely in YAML configuration and executed
through the metaprogramming system.
"""

import pytest
from src.controller.goap_execution_manager import GOAPExecutionManager
from src.lib.actions_data import ActionsData


class TestYAMLOnlyActions:
    """Test YAML-only actions like verify_material_sufficiency."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.goap_executor = GOAPExecutionManager()
        self.actions_data = ActionsData("config/default_actions.yaml")
        self.actions_config = self.actions_data.get_actions()
        
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
        
    def test_yaml_only_actions_in_plan(self):
        """Test that YAML-only actions appear in GOAP plans."""
        # State after transformation
        start_state = self.goap_executor._load_start_state_defaults()
        start_state['materials']['status'] = 'transformed'
        start_state['materials']['transformation_complete'] = True
        start_state['character_status']['alive'] = True
        
        # Goal is to have sufficient materials
        goal_state = {
            'materials': {
                'status': 'sufficient'
            }
        }
        
        plan = self.goap_executor.create_plan(start_state, goal_state, self.actions_config)
        
        assert plan is not None
        assert len(plan) == 1
        assert plan[0]['name'] == 'verify_material_sufficiency'
        
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
            ('checking', 'check_material_availability'),
            ('insufficient', 'find_resources'),
            ('gathered_raw', 'find_workshops'),
            ('transformed', 'verify_material_sufficiency'),
            ('sufficient', 'craft_item')
        ]
        
        for status, expected_action in status_progression[1:]:  # Skip checking
            # Find actions that work with this status
            matching_actions = []
            for action_name, action_config in self.actions_config.items():
                conditions = action_config.get('conditions', {})
                if 'materials' in conditions and conditions['materials'].get('status') == status:
                    matching_actions.append(action_name)
                    
            assert expected_action in matching_actions, f"No action handles materials.status={status}"