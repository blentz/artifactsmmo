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
    """Test architecture-compliant YAML actions defined in default_actions.yaml."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.action_factory = ActionFactory()
        self.actions_data = ActionsData("config/default_actions.yaml")
        self.actions_config = self.actions_data.get_actions()
        
        # Create default state structure for testing (architecture-compliant)
        self.default_state = {
            'character_status.healthy': True,
            'character_status.cooldown_active': False,
            'materials.status': 'unknown',
            'materials.gathered': False,
            'combat_context.status': 'idle',
            'equipment_status.item_crafted': False,
            'equipment_status.equipped': False,
            'resource_availability.monsters': False
        }
        
    def test_core_actions_exist(self):
        """Test that core architecture-compliant actions are defined."""
        # Test core actions from architecture-compliant configuration
        core_actions = ['move', 'find_monsters', 'attack', 'gather_resources', 'craft_item', 'equip_item', 'rest', 'wait']
        
        for action_name in core_actions:
            assert action_name in self.actions_config, f"Core action {action_name} should exist"
            
            action = self.actions_config[action_name]
            assert 'conditions' in action, f"Action {action_name} should have conditions"
            assert 'reactions' in action, f"Action {action_name} should have reactions"
            assert 'weight' in action, f"Action {action_name} should have weight"
            assert 'description' in action, f"Action {action_name} should have description"
        
    def test_architecture_compliant_actions(self):
        """Test that actions follow architecture compliance patterns."""
        # Test core action that uses subgoal request patterns
        gather_action = 'gather_resources'
        
        # This action should exist in YAML configuration
        assert gather_action in self.actions_config
        
        # Test that the action has proper GOAP structure
        action_config = self.actions_config[gather_action]
        assert 'conditions' in action_config
        assert 'reactions' in action_config
        assert 'weight' in action_config
        assert 'description' in action_config
        
        # Test conditions use valid StateParameters (flat format)
        conditions = action_config['conditions']
        reactions = action_config['reactions']
        
        # Should have character health conditions (architecture-compliant)
        assert 'character_status.healthy' in conditions
        assert conditions['character_status.healthy'] == True
        
        # Should react by setting materials status (flat format)
        assert 'materials.status' in reactions
        assert reactions['materials.status'] == 'gathered'
        
    def test_all_core_actions_exist(self):
        """Test all core architecture-compliant actions exist."""
        core_actions = [
            'move',
            'find_monsters', 
            'attack',
            'gather_resources',
            'craft_item',
            'equip_item',
            'rest',
            'wait'
        ]
        
        for action_name in core_actions:
            assert action_name in self.actions_config, f"Missing core action: {action_name}"
            
            action = self.actions_config[action_name]
            assert 'conditions' in action
            assert 'reactions' in action
            assert 'weight' in action
            assert 'description' in action
            
    def test_action_chain_conditions_reactions(self):
        """Test that action conditions and reactions properly chain using subgoal patterns."""
        # Check find_monsters -> attack chain (architecture-compliant)
        find_monsters = self.actions_config['find_monsters']
        attack = self.actions_config['attack']
        
        # find_monsters sets monsters available and combat ready (flat format)
        assert find_monsters['reactions']['resource_availability.monsters'] == True
        assert find_monsters['reactions']['combat_context.status'] == 'ready'
        
        # attack requires monsters available and combat ready (flat format)
        assert attack['conditions']['resource_availability.monsters'] == True
        assert attack['conditions']['combat_context.status'] == 'ready'
        
        # attack sets combat status to completed (flat format)
        assert attack['reactions']['combat_context.status'] == 'completed'
        
    def test_material_status_progression(self):
        """Test material status progression using architecture-compliant subgoal patterns."""
        # Test gather_resources -> craft_item -> equip_item chain
        gather = self.actions_config['gather_resources']
        craft = self.actions_config['craft_item']
        equip = self.actions_config['equip_item']
        
        # gather_resources handles insufficient materials
        assert gather['conditions']['materials.status'] == 'insufficient'
        assert gather['reactions']['materials.status'] == 'gathered'
        
        # craft_item requires sufficient materials
        assert craft['conditions']['materials.status'] == 'sufficient' 
        assert craft['reactions']['equipment_status.item_crafted'] == True
        
        # equip_item requires crafted item
        assert equip['conditions']['equipment_status.item_crafted'] == True
        assert equip['reactions']['equipment_status.equipped'] == True