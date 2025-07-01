"""
Test for GOAP infinite loop fix when crafting weapons.

This test verifies that evaluate_weapon_recipes doesn't cause infinite replanning loops.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

from src.controller.goap_execution_manager import GOAPExecutionManager
from src.lib.goap_data import GoapData


class TestGOAPInfiniteLoopFix(unittest.TestCase):
    """Test that the GOAP planner doesn't get stuck in infinite loops."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = GOAPExecutionManager()
        
        # Create mock controller
        self.controller = Mock()
        self.controller.logger = Mock()
        self.controller.character_state = Mock()
        self.controller.map_state = Mock()
        self.controller.knowledge_base = Mock()
        
        # Create temporary world state file
        self.temp_world_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        self.temp_world_file.write("data:\n  best_weapon_selected: false\n")
        self.temp_world_file.close()
        
        # Mock world state that can be updated
        self.controller.world_state = GoapData(filename=self.temp_world_file.name)
        self.controller.world_state.data = {'best_weapon_selected': False}
        
        # Mock action context
        self.controller.action_context = {}
        
        # Create test actions config
        self.test_actions_config = {
            'evaluate_weapon_recipes': {
                'conditions': {
                    'character_alive': True,
                    'need_equipment': True,
                    'best_weapon_selected': False,
                    'character_safe': True
                },
                'reactions': {
                    'equipment_info_known': True,
                    'recipe_known': True,
                    'best_weapon_selected': True,
                    'craftable_weapon_identified': True
                }
            },
            'craft_item': {
                'conditions': {
                    'character_alive': True,
                    'recipe_known': True,
                    'has_materials': True
                },
                'reactions': {
                    'item_crafted': True
                }
            }
        }
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_world_file.name):
            os.unlink(self.temp_world_file.name)
    
    def test_evaluate_weapon_recipes_updates_world_state(self):
        """Test that evaluate_weapon_recipes updates world state with reactions."""
        # Simulate successful action execution
        self.controller._execute_single_action = Mock(return_value=True)
        
        # Call the update method
        self.manager._update_world_state_with_reactions(
            self.controller, 
            'evaluate_weapon_recipes', 
            self.test_actions_config
        )
        
        # Verify world state was updated
        self.assertTrue(self.controller.world_state.data['best_weapon_selected'])
        self.assertTrue(self.controller.world_state.data['equipment_info_known'])
        self.assertTrue(self.controller.world_state.data['recipe_known'])
        self.assertTrue(self.controller.world_state.data['craftable_weapon_identified'])
    
    def test_no_infinite_loop_after_weapon_evaluation(self):
        """Test that weapon evaluation doesn't trigger infinite replanning."""
        # Track how many times evaluate_weapon_recipes is called
        evaluation_count = 0
        
        def mock_execute_action(action_name, action_data):
            nonlocal evaluation_count
            if action_name == 'evaluate_weapon_recipes':
                evaluation_count += 1
                # Simulate successful evaluation that sets item_code
                self.controller.action_context['item_code'] = 'wooden_staff'
            return True
        
        self.controller._execute_single_action = mock_execute_action
        
        # Mock the should_replan method to track calls
        original_should_replan = self.manager._should_replan_after_discovery
        replan_count = 0
        
        def mock_should_replan(action, state):
            nonlocal replan_count
            result = original_should_replan(action, state)
            if action.get('name') == 'evaluate_weapon_recipes':
                replan_count += 1
            return result
        
        self.manager._should_replan_after_discovery = mock_should_replan
        
        # Create a plan with evaluate_weapon_recipes
        test_plan = [
            {'name': 'evaluate_weapon_recipes'},
            {'name': 'craft_item'}
        ]
        
        # Mock world state updates
        def mock_get_world_state(force_refresh=False):
            state = {'character_alive': True, 'need_equipment': True}
            # Include persisted world state
            if hasattr(self.controller.world_state, 'data'):
                state.update(self.controller.world_state.data)
            return state
        
        self.controller.get_current_world_state = mock_get_world_state
        
        # Mock replan method to return empty list (no more actions needed)
        self.manager._replan_from_current_position = Mock(return_value=[])
        
        # Execute the plan
        with patch.object(self.manager, '_load_actions_from_config', return_value=self.test_actions_config):
            result = self.manager._execute_plan_with_selective_replanning(
                test_plan, 
                self.controller, 
                {'has_better_weapon': True},
                max_iterations=10
            )
        
        # Verify evaluate_weapon_recipes was only called once
        self.assertEqual(evaluation_count, 1, "evaluate_weapon_recipes should only run once")
        
        # Verify replanning was limited
        self.assertLessEqual(replan_count, 2, "Should not replan more than once after weapon evaluation")
    
    def test_second_weapon_evaluation_skips_replanning(self):
        """Test that subsequent weapon evaluations don't trigger replanning."""
        # Reset the manager's replan counter
        self.manager._weapon_eval_replans = 0
        
        # Create action data
        action = {'name': 'evaluate_weapon_recipes'}
        state = {'best_weapon_selected': True}
        
        # First evaluation should trigger replan
        result1 = self.manager._should_replan_after_discovery(action, state)
        self.assertTrue(result1, "First weapon evaluation should trigger replanning")
        
        # Second evaluation should NOT trigger replan
        result2 = self.manager._should_replan_after_discovery(action, state)
        self.assertFalse(result2, "Second weapon evaluation should not trigger replanning")
        
        # Verify counter was incremented
        self.assertEqual(self.manager._weapon_eval_replans, 1)
    
    def test_world_state_merge_includes_weapon_selection(self):
        """Test that world state merge includes best_weapon_selected flag."""
        from src.controller.ai_player_controller import AIPlayerController
        
        # Create a mock controller with proper world state
        with patch('src.controller.ai_player_controller.ActionExecutor'):
            # Create controller with proper initialization
            controller = Mock()
            controller.character_state = Mock()
            controller.world_state = Mock()
            controller.goal_manager = Mock()
            controller.knowledge_base = Mock()
            controller.map_state = Mock()
            controller.logger = Mock()
            
            # Add the get_current_world_state method
            from src.controller.ai_player_controller import AIPlayerController
            controller.get_current_world_state = AIPlayerController.get_current_world_state.__get__(controller)
            
            # Set up world state
            controller.world_state = Mock()
            controller.world_state.data = {
                'best_weapon_selected': True,
                'equipment_info_known': True,
                'recipe_known': True,
                'craftable_weapon_identified': True
            }
            
            # Mock goal manager's calculate_world_state
            controller.goal_manager.calculate_world_state = Mock(return_value={
                'character_alive': True,
                'need_equipment': True
            })
            
            # Get current world state
            state = controller.get_current_world_state()
            
            # Verify merged state includes weapon selection flags
            self.assertTrue(state.get('best_weapon_selected'), "State should include best_weapon_selected")
            self.assertTrue(state.get('equipment_info_known'), "State should include equipment_info_known")
            self.assertTrue(state.get('recipe_known'), "State should include recipe_known")
            self.assertTrue(state.get('craftable_weapon_identified'), "State should include craftable_weapon_identified")


if __name__ == '__main__':
    unittest.main()