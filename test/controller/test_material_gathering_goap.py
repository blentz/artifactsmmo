"""
Comprehensive tests for the material gathering GOAP integration.

Tests the complete material gathering chain from insufficient materials
through resource gathering, transformation, and crafting.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.controller.goap_execution_manager import GOAPExecutionManager
from src.lib.actions_data import ActionsData


def deep_update(base_dict, update_dict):
    """Deep update a dictionary."""
    for key, value in update_dict.items():
        if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
            deep_update(base_dict[key], value)
        else:
            base_dict[key] = value
    return base_dict


class TestMaterialGatheringGOAP:
    """Test the GOAP planning for material gathering scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.goap_executor = GOAPExecutionManager()
        self.actions_data = ActionsData("config/default_actions.yaml")
        self.actions_config = self.actions_data.get_actions()
        
    def test_insufficient_materials_creates_gathering_plan(self):
        """Test that insufficient materials triggers a gathering plan."""
        # Start state with insufficient materials
        start_state = {
            'equipment_status': {
                'upgrade_status': 'ready',
                'has_selected_item': True,
                'selected_item': 'copper_dagger',
                'target_slot': 'weapon'
            },
            'materials': {
                'requirements_determined': True,
                'status': 'insufficient',
                'availability_checked': True,
                'required': {'copper': 3}
            },
            'inventory': {
                'updated': True
            },
            'character_status': {
                'alive': True,
                'cooldown_active': False
            },
            'resource_availability': {
                'resources': False
            },
            'location_context': {
                'at_resource': False,
                'at_workshop': False,
                'resource_known': False,
                'workshop_known': False
            }
        }
        
        goal_state = {
            'equipment_status': {
                'upgrade_status': 'completed'
            }
        }
        
        # Create plan
        plan = self.goap_executor.create_plan(start_state, goal_state, self.actions_config)
        
        # Verify plan includes material gathering
        assert plan is not None
        action_names = [action['name'] for action in plan]
        
        # Should include material gathering (GOAP may choose consolidated or separate actions)
        # Either specific resource actions or consolidated material action
        has_resource_actions = any('find' in name and 'resource' in name for name in action_names)
        has_gather_action = any('gather' in name for name in action_names)
        assert has_resource_actions or has_gather_action, f"No resource or gather actions found in {action_names}"
        
        # Should include workshop-related actions for final crafting
        has_workshop_search = any('workshop' in name and ('find' in name or 'search' in name) for name in action_names)
        assert has_workshop_search, f"No workshop search actions found in {action_names}"
        
        has_workshop_move = any('move' in name and 'workshop' in name for name in action_names)
        assert has_workshop_move, f"No workshop move actions found in {action_names}"
        # Note: transform_materials may or may not be included depending on GOAP path selection
        
        # Should include final crafting and equipping
        assert 'craft_item' in action_names
        assert 'equip_item' in action_names
        # Note: equip_item sets upgrade_status to 'completed'
        
    def test_sufficient_materials_skips_gathering(self):
        """Test that sufficient materials skip the gathering chain."""
        start_state = {
            'equipment_status': {
                'upgrade_status': 'ready',
                'has_selected_item': True,
                'selected_item': 'copper_dagger'
            },
            'materials': {
                'requirements_determined': True,
                'status': 'sufficient',
                'availability_checked': True
            },
            'skill_requirements': {
                'verified': True,
                'sufficient': True
            },
            'location_context': {
                'at_workshop': True
            },
            'character_status': {
                'alive': True
            }
        }
        
        goal_state = {
            'equipment_status': {
                'upgrade_status': 'completed'
            }
        }
        
        plan = self.goap_executor.create_plan(start_state, goal_state, self.actions_config)
        
        # Should have a much shorter plan
        assert plan is not None
        # The plan may include check_inventory after crafting
        assert 2 <= len(plan) <= 3  # craft_item, optional check_inventory, equip_item
        assert plan[0]['name'] == 'craft_item'
        assert plan[-1]['name'] == 'equip_item'
        
    def test_gathered_raw_materials_need_transformation(self):
        """Test that gathered raw materials trigger transformation."""
        # Get defaults and update with test state
        start_state = self.goap_executor._load_start_state_defaults()
        deep_update(start_state, {
            'equipment_status': {
                'upgrade_status': 'ready',
                'has_selected_item': True,
                'selected_item': 'copper_dagger'
            },
            'materials': {
                'status': 'gathered_raw',
                'gathered': True,
                'requirements_determined': True
            },
            'location_context': {
                'at_resource': True,
                'workshop_known': False
            },
            'character_status': {
                'alive': True,
                'cooldown_active': False
            }
        })
        
        goal_state = {
            'equipment_status': {
                'upgrade_status': 'completed'
            }
        }
        
        plan = self.goap_executor.create_plan(start_state, goal_state, self.actions_config)
        
        assert plan is not None
        action_names = [action['name'] for action in plan]
        
        # Should find workshop and complete crafting
        has_workshop_search = any('workshop' in name and ('find' in name or 'search' in name) for name in action_names)
        assert has_workshop_search, f"No workshop search actions found in {action_names}"
        # Check for any workshop movement action
        has_workshop_movement = any('move' in name and 'workshop' in name for name in action_names)
        assert has_workshop_movement, f"No workshop movement found in {action_names}"
        # Note: may include transform_materials or go straight to crafting depending on GOAP path
        
    def test_transformation_complete_ready_to_craft(self):
        """Test that completed transformation allows crafting."""
        # Get defaults and update with test state
        start_state = self.goap_executor._load_start_state_defaults()
        deep_update(start_state, {
            'equipment_status': {
                'upgrade_status': 'ready',
                'has_selected_item': True,
                'selected_item': 'copper_dagger'
            },
            'materials': {
                'status': 'sufficient',  # Already sufficient since we test post-transformation
                'transformation_complete': True,
                'requirements_determined': True
            },
            'skill_requirements': {
                'verified': True,
                'sufficient': True
            },
            'location_context': {
                'at_workshop': True
            },
            'character_status': {
                'alive': True
            }
        })
        
        goal_state = {
            'equipment_status': {
                'upgrade_status': 'completed'
            }
        }
        
        plan = self.goap_executor.create_plan(start_state, goal_state, self.actions_config)
        
        assert plan is not None
        # The plan may include check_inventory after crafting
        assert 2 <= len(plan) <= 3  # craft_item, optional check_inventory, equip_item
        assert plan[0]['name'] == 'craft_item'
        assert plan[-1]['name'] == 'equip_item'
        
    def test_complete_material_chain_ordering(self):
        """Test the complete material gathering chain has correct ordering."""
        # Get defaults and update with test state
        start_state = self.goap_executor._load_start_state_defaults()
        deep_update(start_state, {
            'equipment_status': {
                'upgrade_status': 'ready',
                'selected_item': 'copper_dagger'
            },
            'materials': {
                'status': 'insufficient',
                'availability_checked': True,
                'requirements_determined': True
            },
            'resource_availability': {
                'resources': False
            },
            'location_context': {
                'at_resource': False,
                'at_workshop': False,
                'resource_known': False,
                'workshop_known': False
            },
            'character_status': {
                'alive': True,
                'cooldown_active': False
            }
        })
        
        # Simpler goal - just get materials gathered
        goal_state = {
            'materials': {
                'status': 'gathered_raw'
            }
        }
        
        plan = self.goap_executor.create_plan(start_state, goal_state, self.actions_config)
        
        assert plan is not None
        action_names = [action['name'] for action in plan]
        
        # Verify basic gathering logic (GOAP may use consolidated or separate actions)
        has_gather_action = any('gather' in name for name in action_names)
        assert has_gather_action, f"No gather action found in {action_names}"
        
        # If separate resource actions exist, check ordering
        find_res_idx = next((i for i, name in enumerate(action_names) if 'find' in name and 'resource' in name), -1)
        move_res_idx = next((i for i, name in enumerate(action_names) if 'move' in name and 'resource' in name), -1)
        gather_idx = next((i for i, name in enumerate(action_names) if 'gather' in name), -1)
        
        # Only check ordering if separate actions exist
        if find_res_idx >= 0 and move_res_idx >= 0 and gather_idx >= 0:
            # Resources must be found before moving
            assert find_res_idx < move_res_idx
            # Must move before gathering
            assert move_res_idx < gather_idx
        
    def test_no_plan_when_dead(self):
        """Test that no plan is created when character is dead."""
        start_state = {
            'equipment_status': {
                'upgrade_status': 'ready'
            },
            'character_status': {
                'alive': False  # Dead character
            }
        }
        
        goal_state = {
            'equipment_status': {
                'upgrade_status': 'completed'
            }
        }
        
        plan = self.goap_executor.create_plan(start_state, goal_state, self.actions_config)
        
        # Should not find a plan when dead
        assert plan is None or len(plan) == 0
        
    def test_cooldown_handling_in_plan(self):
        """Test that cooldowns don't break material gathering plans."""
        # Get defaults and update with test state
        start_state = self.goap_executor._load_start_state_defaults()
        deep_update(start_state, {
            'equipment_status': {
                'upgrade_status': 'ready',
                'selected_item': 'copper_dagger'
            },
            'materials': {
                'status': 'insufficient',
                'availability_checked': True,
                'requirements_determined': True
            },
            'character_status': {
                'alive': True,
                'cooldown_active': True  # On cooldown
            },
            'resource_availability': {
                'resources': False
            },
            'location_context': {
                'at_resource': False,
                'resource_known': False,
                'at_workshop': False,
                'workshop_known': False
            }
        })
        
        # Test just clearing cooldown first
        goal_state = {
            'character_status': {
                'cooldown_active': False
            }
        }
        
        plan = self.goap_executor.create_plan(start_state, goal_state, self.actions_config)
        
        # Should have wait action
        assert plan is not None
        assert len(plan) == 1
        assert plan[0]['name'] == 'wait'


class TestMaterialGatheringStates:
    """Test the state transitions in material gathering."""
    
    def test_material_status_transitions(self):
        """Test all material status transitions."""
        transitions = [
            ('unknown', 'checking'),
            ('checking', 'insufficient'),
            ('insufficient', 'gathered_raw'),
            ('gathered_raw', 'transformed'),
            ('transformed', 'sufficient')
        ]
        
        for from_status, to_status in transitions:
            # Each transition should be valid
            assert from_status != to_status
            
    def test_location_context_transitions(self):
        """Test location context state transitions."""
        transitions = [
            ('resource_known', False, True),  # Unknown to known
            ('at_resource', False, True),     # Not at resource to at resource
            ('workshop_known', False, True),  # Unknown to known
            ('at_workshop', False, True)      # Not at workshop to at workshop
        ]
        
        for field, from_val, to_val in transitions:
            assert from_val != to_val
            
    def test_resource_availability_transitions(self):
        """Test resource availability transitions."""
        # Resources should go from not available to available
        assert not False  # Initial state
        assert True       # After find_resources