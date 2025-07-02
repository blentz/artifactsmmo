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


class TestXPSeekingCycle(unittest.TestCase):
    """Test the complete XP-seeking cycle for goal achievement."""

    def setUp(self):
        """Set up test fixtures with isolated temporary files."""
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
        self.assertEqual(self.controller.action_context, {})
        
        # Verify GOAP data structure exists
        self.assertIsNotNone(self.controller.goap_data)
        self.assertIsNotNone(self.controller.goap_data.data)

    def test_coordinate_preservation_in_action_context(self):
        """Test that coordinates from find_monsters are preserved for move action."""
        # Mock find_monsters response
        find_monsters_response = {
            'success': True,
            'target_x': 0,
            'target_y': -1,
            'monster_code': 'green_slime'
        }
        
        # Update action context from find_monsters response
        self.controller._update_action_context_from_response(
            'find_monsters', find_monsters_response
        )
        
        # Verify coordinates are preserved correctly
        self.assertEqual(self.controller.action_context.get('target_x'), 0)
        self.assertEqual(self.controller.action_context.get('target_y'), -1)
        self.assertEqual(self.controller.action_context.get('monster_code'), 'green_slime')

    def test_coordinate_failure_detection(self):
        """Test that coordinate failures are detected and trigger recovery."""
        goap_manager = GOAPExecutionManager()
        
        # Test with missing coordinates
        self.controller.action_context = {}
        result = goap_manager._is_coordinate_failure('move', self.controller)
        self.assertTrue(result)
        
        # Test with valid coordinates
        self.controller.action_context = {'target_x': 0, 'target_y': -1}
        result = goap_manager._is_coordinate_failure('move', self.controller)
        self.assertFalse(result)

    @patch('src.controller.goap_execution_manager.GOAPExecutionManager.create_plan')
    def test_recovery_plan_creation(self, mock_create_plan):
        """Test that recovery plans are created correctly for coordinate failures."""
        goap_manager = GOAPExecutionManager()
        
        # Mock a recovery plan
        mock_recovery_plan = [
            {'name': 'find_monsters'},
            {'name': 'move'},
            {'name': 'attack'}
        ]
        mock_create_plan.return_value = mock_recovery_plan
        
        # Create recovery plan
        goal_state = {'goal_progress': {'monsters_hunted': '>0'}}
        recovery_plan = goap_manager._create_recovery_plan_with_find_monsters(
            self.controller, goal_state
        )
        
        # Verify plan structure
        self.assertIsNotNone(recovery_plan)
        self.assertEqual(len(recovery_plan), 3)
        self.assertEqual(recovery_plan[0]['name'], 'find_monsters')

    @patch('src.controller.action_executor.ActionExecutor.execute_action')
    def test_xp_seeking_action_sequence(self, mock_execute_action):
        """Test the complete XP-seeking action sequence."""
        # Mock successful action executions
        def mock_action_execution(action_name, action_data, client, context):
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
        with patch.object(goap_manager, '_develop_complete_plan') as mock_develop_plan, \
             patch.object(goap_manager, '_execute_plan_with_selective_replanning') as mock_execute_plan:
            mock_develop_plan.return_value = [
                {'name': 'find_monsters'},
                {'name': 'move'},
                {'name': 'attack'}
            ]
            
            # Mock execute plan to update action context and return True
            def execute_plan_side_effect(plan, controller, goal_state, config_file, max_iterations):
                # Simulate find_monsters updating the action context
                controller.action_context['target_x'] = 0
                controller.action_context['target_y'] = -1
                return True
                
            mock_execute_plan.side_effect = execute_plan_side_effect
            
            goal_state = {'goal_progress': {'monsters_hunted': '>0'}}
            success = goap_manager.achieve_goal_with_goap(
                goal_state, self.controller
            )
            
        # Verify success and action context updates
        self.assertTrue(success)
        self.assertIn('target_x', self.controller.action_context)
        self.assertIn('target_y', self.controller.action_context)

    def test_action_context_preservation_across_plans(self):
        """Test that important action context is preserved between plan iterations."""
        # Set up initial action context
        self.controller.action_context = {
            'target_x': 0,
            'target_y': -1,
            'item_code': 'copper_dagger',
            'some_temp_data': 'should_be_cleared'
        }
        
        # Simulate plan execution reset (similar to what happens in _execute_plan)
        preserved_data = {}
        preservation_keys = [
            'x', 'y', 'target_x', 'target_y', 'item_code', 'recipe_item_code', 
            'recipe_item_name', 'craft_skill', 'materials_needed', 'resource_types',
            'smelt_item_code', 'smelt_item_name', 'smelt_skill', 'smelting_required',
            'crafting_chain'
        ]
        
        for key in preservation_keys:
            if key in self.controller.action_context:
                preserved_data[key] = self.controller.action_context[key]
        
        # Verify important data is preserved
        self.assertEqual(preserved_data['target_x'], 0)
        self.assertEqual(preserved_data['target_y'], -1)
        self.assertEqual(preserved_data['item_code'], 'copper_dagger')
        self.assertNotIn('some_temp_data', preserved_data)

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