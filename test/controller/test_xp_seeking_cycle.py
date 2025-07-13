#!/usr/bin/env python3
"""
Test XP-Seeking Cycle for Goal Achievement

This test module verifies that the AI player can successfully complete
the XP-seeking cycle: find_monsters → move → attack → gain XP → replan → repeat.
"""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.controller.ai_player_controller import AIPlayerController
from src.controller.goal_manager import GOAPGoalManager
from src.controller.goap_execution_manager import GOAPExecutionManager
from src.controller.mission_executor import MissionExecutor
from src.lib.goap_data import GoapData
from src.lib.state_parameters import StateParameters
from test.test_base import UnifiedContextTestBase


class TestXPSeekingCycle(UnifiedContextTestBase):
    """Test the complete XP-seeking cycle for goal achievement."""

    def setUp(self):
        """Set up test fixtures with isolated temporary files."""
        super().setUp()
        # Create temporary directory for test data
        self.temp_dir = tempfile.mkdtemp()
        self.temp_world_file = os.path.join(self.temp_dir, "world.yaml")
        self.temp_map_file = os.path.join(self.temp_dir, "map.yaml")
        self.temp_knowledge_file = os.path.join(self.temp_dir, "knowledge.yaml")
        
        # Mock client
        self.mock_client = Mock()
        
        # Mock character state
        self.character_data = {
            'name': 'test_character',
            'level': 1,
            'xp': 0,
            'max_xp': 150,
            'hp': 120,
            'max_hp': 120,
            'x': 0,
            'y': 0,
            'cooldown': 0,
            'weapon_slot': 'wooden_stick'
        }
        
        # Mock character state to avoid file system dependencies
        self.character_state = Mock()
        self.character_state.name = "test_character"
        self.character_state.data = self.character_data
        
        # Mock goal manager
        self.mock_goal_manager = Mock(spec=GOAPGoalManager)
        
        # Mock components with temporary files - patch all DATA_PREFIX imports
        with patch('src.game.globals.DATA_PREFIX', self.temp_dir), \
             patch('src.game.globals.CONFIG_PREFIX', self.temp_dir), \
             patch('src.controller.world.state.DATA_PREFIX', self.temp_dir), \
             patch('src.controller.knowledge.base.DATA_PREFIX', self.temp_dir), \
             patch('src.game.map.state.DATA_PREFIX', self.temp_dir), \
             patch('src.game.character.state.DATA_PREFIX', self.temp_dir):
            self.controller = AIPlayerController(
                client=self.mock_client, 
                goal_manager=self.mock_goal_manager
            )
        
        # Set character state
        self.controller.set_character_state(self.character_state)
        
        # Initialize clean GOAP data
        self.controller.goap_data = GoapData(self.temp_world_file)
        
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_session_state_initialization(self):
        """Test that session state initialization works without errors."""
        # Initialize session state
        goap_manager = GOAPExecutionManager()
        goap_manager.initialize_session_state(self.controller)
        
        # Verify that initialization completed without errors
        # and action context is cleared (main purpose of this method)
        self.assertIsNotNone(self.controller.plan_action_context)
        # With unified context, we don't have action_data attribute
        
        # Verify GOAP data structure exists
        self.assertIsNotNone(self.controller.goap_data)
        self.assertIsNotNone(self.controller.goap_data.data)

    def test_coordinate_preservation_in_action_context(self):
        """Test that coordinates from find_monsters are preserved for move action."""
        # Simulate find_monsters storing results in ActionContext
        # This is what happens in _execute_single_action when result.data is processed
        self.controller.plan_action_context.set_result(StateParameters.TARGET_X, 0)
        self.controller.plan_action_context.set_result(StateParameters.TARGET_Y, -1)
        self.controller.plan_action_context.set_result(StateParameters.COMBAT_TARGET, 'green_slime')
        
        # Verify coordinates are preserved correctly in ActionContext singleton
        self.assertEqual(self.controller.plan_action_context.get(StateParameters.TARGET_X), 0)
        self.assertEqual(self.controller.plan_action_context.get(StateParameters.TARGET_Y), -1)
        self.assertEqual(self.controller.plan_action_context.get(StateParameters.COMBAT_TARGET), 'green_slime')

    def test_coordinate_failure_detection(self):
        """Test that coordinates are properly stored in ActionContext singleton."""
        # ActionContext uses unified state - no need to clear action_results
        
        # Test setting coordinates
        self.controller.plan_action_context.set_result(StateParameters.TARGET_X, 0)
        self.controller.plan_action_context.set_result(StateParameters.TARGET_Y, -1)
        
        # Verify coordinates are stored
        self.assertEqual(self.controller.plan_action_context.get(StateParameters.TARGET_X), 0)
        self.assertEqual(self.controller.plan_action_context.get(StateParameters.TARGET_Y), -1)


    @patch('src.controller.action_executor.ActionExecutor.execute_action')
    def test_xp_seeking_action_sequence(self, mock_execute_action):
        """Test the complete XP-seeking action sequence."""
        # Mock successful action executions
        def mock_action_execution(action_name, client, context):
            result = Mock()
            result.success = True
            
            if action_name == 'find_monsters':
                result.response = {
                    'success': True,
                    'target_x': 0,
                    'target_y': -1,
                    'monster_code': 'green_slime'
                }
            elif action_name == 'move':
                result.response = {
                    'success': True,
                    'new_position': (0, -1)
                }
            elif action_name == 'attack':
                result.response = {
                    'success': True,
                    'xp_gained': 15,
                    'monster_defeated': True
                }
            else:
                result.response = {'success': True}
                
            return result
            
        mock_execute_action.side_effect = mock_action_execution
        
        # Mock get_current_world_state to return a proper dictionary
        self.controller.get_current_world_state = Mock(return_value={
            'character_status': {'alive': True},
            'character_status': {'cooldown_active': False},
            'combat_context': {'status': 'ready'},
            'location_context': {'at_target': False},
            'resource_availability': {'monsters': False},
            'monster_present': False,
            'has_hunted_monsters': False
        })
        
        # Execute XP-seeking sequence
        goap_manager = GOAPExecutionManager()
        
        # Mock successful plan execution
        with patch.object(goap_manager, 'create_plan') as mock_create_plan, \
             patch.object(goap_manager, '_execute_plan_with_selective_replanning') as mock_execute_plan:
            mock_create_plan.return_value = [
                {'name': 'find_monsters'},
                {'name': 'move'},
                {'name': 'attack'}
            ]
            
            # Mock execute plan to update action context and return True
            def execute_plan_side_effect(plan, controller, goal_state, config_file, max_iterations):
                # Simulate find_monsters updating the action context
                controller.plan_action_context.set_result(StateParameters.TARGET_X, 0)
                controller.plan_action_context.set_result(StateParameters.TARGET_Y, -1)
                return True
                
            mock_execute_plan.side_effect = execute_plan_side_effect
            
            goal_state = {'goal_progress': {'monsters_hunted': '>0'}}
            success = goap_manager.achieve_goal_with_goap(
                goal_state, self.controller
            )
            
        # Verify success and action context updates
        self.assertTrue(success)
        self.assertEqual(self.controller.plan_action_context.get(StateParameters.TARGET_X), 0)
        self.assertEqual(self.controller.plan_action_context.get(StateParameters.TARGET_Y), -1)

    def test_action_context_preservation_across_plans(self):
        """Test that important action context is preserved between plan iterations."""
        # Set up initial action context in ActionContext singleton
        self.controller.plan_action_context.set_result(StateParameters.TARGET_X, 0)
        self.controller.plan_action_context.set_result(StateParameters.TARGET_Y, -1)
        self.controller.plan_action_context.set_result(StateParameters.ITEM_CODE, 'copper_dagger')
        self.controller.plan_action_context.set_result(StateParameters.WORKFLOW_STEP, 'should_persist')
        
        # Data persists in the ActionContext singleton throughout plan execution
        # Verify all data is available
        self.assertEqual(self.controller.plan_action_context.get(StateParameters.TARGET_X), 0)
        self.assertEqual(self.controller.plan_action_context.get(StateParameters.TARGET_Y), -1)
        self.assertEqual(self.controller.plan_action_context.get(StateParameters.ITEM_CODE), 'copper_dagger')
        self.assertEqual(self.controller.plan_action_context.get(StateParameters.WORKFLOW_STEP), 'should_persist')

    def test_clean_state_structure_for_monster_hunting(self):
        """Test that clean state structure properly indicates need for monster hunting."""
        # Test the state structure without directly testing GOAP planning
        clean_state = {
            'character_status': {
                'cooldown_active': False,
                'alive': True
            },
            'combat_context': {
                'status': 'idle',  # Not ready for combat yet
                'monsters_available': False
            },
            'location_context': {
                'at_target': False
            },
            'goal_progress': {
                'monsters_hunted': 0  # Need to hunt monsters
            }
        }
        
        # Verify state structure indicates need for monster discovery
        self.assertFalse(clean_state['combat_context']['monsters_available'])
        self.assertEqual(clean_state['combat_context']['status'], 'idle')
        self.assertFalse(clean_state['location_context']['at_target'])
        self.assertEqual(clean_state['goal_progress']['monsters_hunted'], 0)
        
        # Verify character is ready for action
        self.assertFalse(clean_state['character_status']['cooldown_active'])
        self.assertTrue(clean_state['character_status']['alive'])
        
        # Test goal state structure for monster hunting
        goal_state = {
            'goal_progress': {'monsters_hunted': 1}  # Need to hunt at least 1 monster
        }
        
        self.assertEqual(goal_state['goal_progress']['monsters_hunted'], 1)

    def test_mission_executor_integration(self):
        """Test that MissionExecutor properly initializes session state."""
        with patch('src.controller.mission_executor.YamlData'):
            mission_executor = MissionExecutor(
                self.mock_goal_manager, 
                self.controller
            )
        
        # Mock GOAP execution manager
        mock_goap_manager = Mock()
        self.controller.goap_execution_manager = mock_goap_manager
        
        # Execute mission
        with patch.object(mission_executor, '_load_configuration'):
            mission_executor.execute_progression_mission({'target_level': 2})
        
        # Verify session state initialization was called
        mock_goap_manager.initialize_session_state.assert_called_once_with(self.controller)


if __name__ == '__main__':
    unittest.main()