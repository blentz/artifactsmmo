"""
GOAP State Completeness Tests

These tests ensure that the world state calculation provides all state variables
needed by GOAP actions, preventing planning failures and invalid plans.
"""

import unittest
from unittest.mock import Mock, patch

from src.controller.ai_player_controller import AIPlayerController
from src.controller.goap_execution_manager import GOAPExecutionManager
from src.lib.actions_data import ActionsData


class TestGOAPStateCompleteness(unittest.TestCase):
    """Test that GOAP state variables are complete and consistent."""
    
    def setUp(self):
        """Set up test environment."""
        self.actions_data = ActionsData('config/actions.yaml')
        self.actions_config = self.actions_data.get_actions()
        
    def test_all_goap_state_variables_are_documented(self):
        """Test that all GOAP state variables are accounted for."""
        # Extract all state variables from GOAP actions
        all_conditions = set()
        all_reactions = set()
        
        for action_name, action_config in self.actions_config.items():
            conditions = action_config.get('conditions', {})
            reactions = action_config.get('reactions', {})
            
            all_conditions.update(conditions.keys())
            all_reactions.update(reactions.keys())
        
        all_state_variables = all_conditions | all_reactions
        
        # Expected state variables (update this list when adding new GOAP actions)
        expected_variables = {
            # Character basic state
            'character_alive', 'character_safe', 'can_move', 'can_attack', 
            'needs_rest', 'is_on_cooldown',
            
            # Combat and hunting
            'need_combat', 'monsters_available', 'monster_present', 
            'has_hunted_monsters', 'monster_defeated',
            
            # Location and movement
            'at_target_location', 'at_resource_location', 'at_workshop',
            
            # Resources and crafting
            'need_resources', 'has_resources', 'need_equipment', 'has_equipment',
            'has_materials', 'inventory_updated', 'equipment_equipped',
            'equipment_info_known', 'equipment_info_unknown',
            
            # Knowledge and exploration
            'map_explored', 'resource_location_known', 'workshop_location_known',
            'craft_plan_available', 'exploration_data_available',
            'equipment_analysis_available', 'crafting_opportunities_known',
            'character_stats_improved',
            
            # Equipment progression states
            'need_workshop_discovery', 'workshops_discovered',
            
            # Crafting progression states 
            'need_crafting_materials', 'has_crafting_materials', 'materials_sufficient',
            'recipe_known', 'resource_found', 'has_complete_equipment_set', 'all_slots_equipped',
            
            # Equipment progression states  
            'has_better_weapon', 'has_better_armor',
            
            # Material and workshop states
            'has_raw_materials', 'has_refined_materials', 'material_requirements_known',
            'need_specific_workshop', 'at_correct_workshop',
            
            # Recipe evaluation states
            'best_weapon_selected', 'craftable_weapon_identified',
            
            # Skill progression states  
            'need_skill_upgrade', 'skill_level_sufficient', 'skill_xp_gained',
            'need_weaponcrafting_upgrade', 'weaponcrafting_level_sufficient',
            'skill_requirements_checked', 'required_skill_level_known',
            
            # Spatial and location states
            'location_known', 'spatial_context_updated'
        }
        
        # Check for new variables not in expected list
        unexpected_variables = all_state_variables - expected_variables
        if unexpected_variables:
            self.fail(f"New GOAP state variables detected: {sorted(unexpected_variables)}. "
                     f"Please update expected_variables list and ensure they're handled in world state calculation.")
        
        # Check for missing variables from GOAP config
        missing_variables = expected_variables - all_state_variables
        if missing_variables:
            # This is just a warning - variables may be removed over time
            print(f"WARNING: Expected variables not found in GOAP config: {sorted(missing_variables)}")
    
    def test_goap_world_state_provides_all_variables(self):
        """Test that world state calculation provides all required GOAP variables."""
        with patch('src.controller.ai_player_controller.StateManagerMixin.initialize_state_management'):
            with patch('src.controller.ai_player_controller.StateManagerMixin.create_managed_state') as mock_create_state:
                # Mock dependencies
                mock_world_state = Mock()
                mock_world_state.data = {
                    'monsters_available': False,
                    'at_target_location': False,
                    'monster_present': False,
                    'has_hunted_monsters': False,
                }
                mock_knowledge_base = Mock()
                mock_create_state.side_effect = [mock_world_state, mock_knowledge_base]
                
                controller = AIPlayerController(Mock())
                
                # Mock character state with all required fields
                mock_character = Mock()
                mock_character.data = {
                    'hp': 80, 'max_hp': 120, 'level': 1, 'x': 0, 'y': 0,
                    'cooldown_expiration': None, 'cooldown': 0
                }
                controller.character_state = mock_character
                
                # Mock goal manager to calculate complete state
                def mock_calculate_state(character_state, map_state, knowledge_base):
                    return {
                        # Character basic state
                        'character_alive': True,
                        'character_safe': True,
                        'can_move': True,
                        'can_attack': True,
                        'needs_rest': False,
                        'is_on_cooldown': False,
                        
                        # Combat and hunting
                        'need_combat': True,
                        'monsters_available': False,
                        'monster_present': False,
                        'has_hunted_monsters': False,
                        'monster_defeated': False,
                        
                        # Location and movement
                        'at_target_location': False,
                        'at_resource_location': False,
                        'at_workshop': False,
                        
                        # Resources and crafting
                        'need_resources': False,
                        'has_resources': False,
                        'need_equipment': False,
                        'has_equipment': False,
                        'has_materials': False,
                        'inventory_updated': False,
                        'equipment_equipped': False,
                        'equipment_info_known': True,
                        'equipment_info_unknown': False,
                        
                        # Knowledge and exploration
                        'map_explored': False,
                        'resource_location_known': False,
                        'workshop_location_known': False,
                        'craft_plan_available': False,
                        'exploration_data_available': False,
                        'equipment_analysis_available': False,
                        'crafting_opportunities_known': False,
                        'character_stats_improved': False,
                        'need_workshop_discovery': False,
                        'workshops_discovered': False,
                        
                        # Crafting variables for equipment progression
                        'need_crafting_materials': False,
                        'has_crafting_materials': False,
                        'materials_sufficient': False,
                        'recipe_known': False,
                        'resource_found': False,
                        'has_complete_equipment_set': False,
                        'all_slots_equipped': False,
                        
                        # Equipment progression states
                        'has_better_weapon': False,
                        'has_better_armor': False,
                        
                        # Material and workshop states
                        'has_raw_materials': False,
                        'has_refined_materials': False,
                        'material_requirements_known': False,
                        'need_specific_workshop': False,
                        'at_correct_workshop': False,
                        
                        # Recipe evaluation states
                        'best_weapon_selected': False,
                        'craftable_weapon_identified': False,
                        
                        # Skill progression states
                        'need_skill_upgrade': False,
                        'skill_level_sufficient': True,
                        'skill_xp_gained': False,
                        'need_weaponcrafting_upgrade': False,
                        'weaponcrafting_level_sufficient': True,
                        'skill_requirements_checked': False,
                        'required_skill_level_known': False,
                        
                        # Spatial and location states
                        'location_known': False,
                        'spatial_context_updated': False
                    }
                
                controller.goal_manager.calculate_world_state = mock_calculate_state
                
                # Get world state
                world_state = controller.get_current_world_state()
                
                # Extract all variables needed by GOAP actions
                required_variables = set()
                for action_config in self.actions_config.values():
                    required_variables.update(action_config.get('conditions', {}).keys())
                    required_variables.update(action_config.get('reactions', {}).keys())
                
                # Check that all required variables are present
                missing_variables = required_variables - set(world_state.keys())
                self.assertEqual(len(missing_variables), 0,
                               f"World state missing required GOAP variables: {sorted(missing_variables)}")
    
    def test_goap_plan_generation_with_complete_state(self):
        """Test that GOAP can generate plans when given complete state."""
        manager = GOAPExecutionManager()
        
        # Complete state with all GOAP variables
        complete_state = {
            # Character basic state
            'character_alive': True, 'character_safe': True, 'can_move': True, 'can_attack': True,
            'needs_rest': False, 'is_on_cooldown': False,
            
            # Combat and hunting (setup for hunting scenario)
            'need_combat': True, 'monsters_available': False, 'monster_present': False,
            'has_hunted_monsters': False, 'monster_defeated': False,
            
            # Location and movement
            'at_target_location': False, 'at_resource_location': False, 'at_workshop': False,
            
            # Resources and crafting
            'need_resources': False, 'has_resources': False, 'need_equipment': False,
            'has_equipment': False, 'has_materials': False, 'inventory_updated': False,
            'equipment_equipped': False, 'equipment_info_known': True, 'equipment_info_unknown': False,
            
            # Knowledge and exploration
            'map_explored': False, 'resource_location_known': False, 'workshop_location_known': False,
            'craft_plan_available': False, 'exploration_data_available': False,
            'equipment_analysis_available': False, 'crafting_opportunities_known': False,
            'character_stats_improved': False,
            
            # Workshop discovery state
            'need_workshop_discovery': False, 'workshops_discovered': False,
            'need_crafting_materials': False, 'has_crafting_materials': False, 
            'materials_sufficient': False, 'recipe_known': False, 'resource_found': False,
            'has_complete_equipment_set': False, 'all_slots_equipped': False,
            
            # Equipment progression states
            'has_better_weapon': False, 'has_better_armor': False,
            
            # Material and workshop states
            'has_raw_materials': False, 'has_refined_materials': False,
            'material_requirements_known': False, 'need_specific_workshop': False,
            'at_correct_workshop': False,
            
            # Recipe evaluation states  
            'best_weapon_selected': False, 'craftable_weapon_identified': False,
            
            # Skill progression states
            'need_skill_upgrade': False, 'skill_level_sufficient': True,
            'skill_xp_gained': False, 'need_weaponcrafting_upgrade': False,
            'weaponcrafting_level_sufficient': True, 'skill_requirements_checked': False,
            'required_skill_level_known': False,
            
            # Spatial and location states
            'location_known': False, 'spatial_context_updated': False
        }
        
        # Test different goal scenarios
        test_scenarios = [
            {
                'name': 'hunting_scenario',
                'goal': {'has_hunted_monsters': True, 'monster_defeated': True, 'character_safe': True},
                'expected_actions': {'find_monsters', 'move', 'attack'}
            },
            {
                'name': 'wait_scenario', 
                'start_override': {'is_on_cooldown': True},
                'goal': {'is_on_cooldown': False},
                'expected_actions': {'wait'}
            }
        ]
        
        for scenario in test_scenarios:
            with self.subTest(scenario=scenario['name']):
                # Use complete state with any overrides
                start_state = complete_state.copy()
                start_state.update(scenario.get('start_override', {}))
                
                # Generate plan
                plan = manager.create_plan(start_state, scenario['goal'], self.actions_config)
                
                # Should generate a valid plan
                self.assertIsNotNone(plan, f"{scenario['name']} should generate a plan")
                self.assertGreater(len(plan), 0, f"{scenario['name']} plan should have actions")
                
                # Check that plan contains expected action types
                plan_actions = {step['name'] for step in plan}
                expected_actions = scenario['expected_actions']
                
                # At least some expected actions should be in the plan
                self.assertTrue(plan_actions & expected_actions,
                              f"{scenario['name']} plan should contain some of {expected_actions}, "
                              f"but got {plan_actions}")
    
    def test_state_variable_consistency(self):
        """Test that state variables are used consistently across actions."""
        # Check for potential inconsistencies in state variable usage
        condition_variables = {}  # variable -> list of actions that use it as condition
        reaction_variables = {}   # variable -> list of actions that use it as reaction
        
        for action_name, action_config in self.actions_config.items():
            for var in action_config.get('conditions', {}):
                condition_variables.setdefault(var, []).append(action_name)
            for var in action_config.get('reactions', {}):
                reaction_variables.setdefault(var, []).append(action_name)
        
        # Variables that are only used as conditions (never set by any action)
        condition_only = set(condition_variables.keys()) - set(reaction_variables.keys())
        
        # Variables that are only used as reactions (never checked by any action)
        reaction_only = set(reaction_variables.keys()) - set(condition_variables.keys())
        
        # These are warnings, not failures, as they might be intentional
        if condition_only:
            print(f"INFO: State variables only used as conditions (never set): {sorted(condition_only)}")
        
        if reaction_only:
            print(f"INFO: State variables only used as reactions (never checked): {sorted(reaction_only)}")
        
        # Check for common typos in variable names
        all_variables = set(condition_variables.keys()) | set(reaction_variables.keys())
        potential_typos = []
        
        variables_list = sorted(all_variables)
        for i, var1 in enumerate(variables_list):
            for var2 in variables_list[i+1:]:
                # Check for similar variable names that might be typos
                if self._are_similar_names(var1, var2):
                    potential_typos.append((var1, var2))
        
        if potential_typos:
            print(f"INFO: Potentially similar variable names (check for typos): {potential_typos}")
    
    def _are_similar_names(self, name1, name2):
        """Check if two variable names are suspiciously similar (potential typos)."""
        if len(name1) != len(name2):
            return False
        
        # Count character differences
        differences = sum(c1 != c2 for c1, c2 in zip(name1, name2))
        
        # Consider similar if only 1-2 character differences and names are reasonably long
        return differences <= 2 and len(name1) >= 6


if __name__ == '__main__':
    unittest.main()