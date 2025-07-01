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
        """Test that session state is properly initialized for XP-seeking."""
        # Initialize session state
        goap_manager = GOAPExecutionManager()
        goap_manager.initialize_session_state(self.controller)
        
        # Verify GOAP state is clean
        world_data = self.controller.goap_data.data
        self.assertFalse(world_data.get('monsters_available', True))
        self.assertFalse(world_data.get('monster_present', True))
        self.assertFalse(world_data.get('at_target_location', True))
        self.assertTrue(world_data.get('can_move', False))
        self.assertTrue(world_data.get('can_attack', False))
        
        # Verify action context is cleared
        self.assertEqual(self.controller.action_context, {})

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
        goal_state = {'has_hunted_monsters': True}
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
            'character_alive': True,
            'can_move': True,
            'can_attack': True,
            'at_target_location': False,
            'monsters_available': False,
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
            
            goal_state = {'has_hunted_monsters': True}
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

    @patch('src.controller.ai_player_controller.AIPlayerController.get_current_world_state')
    def test_clean_state_forces_find_monsters_plan(self, mock_get_state):
        """Test that clean state forces GOAP to create plans starting with find_monsters."""
        # Mock clean state (monsters not available)
        mock_get_state.return_value = {
            'can_move': True,
            'can_attack': True,
            'character_alive': True,
            'monsters_available': False,  # KEY: Forces find_monsters
            'monster_present': False,     # KEY: Forces find_monsters
            'at_target_location': False
        }
        
        goap_manager = GOAPExecutionManager()
        
        with patch.object(goap_manager, '_load_actions_from_config') as mock_load_actions:
            # Mock actions config
            mock_load_actions.return_value = {
                'find_monsters': {
                    'conditions': {'can_move': True},
                    'reactions': {'monsters_available': True, 'monster_present': True},
                    'weight': 1.0
                },
                'move': {
                    'conditions': {'monsters_available': True, 'can_move': True},
                    'reactions': {'at_target_location': True},
                    'weight': 1.0
                },
                'attack': {
                    'conditions': {'monster_present': True, 'at_target_location': True},
                    'reactions': {'has_hunted_monsters': True, 'monster_defeated': True},
                    'weight': 1.0
                }
            }
            
            start_state = mock_get_state.return_value
            goal_state = {'has_hunted_monsters': True}
            
            plan = goap_manager.create_plan(start_state, goal_state, mock_load_actions.return_value)
            
            # Verify plan starts with find_monsters
            self.assertIsNotNone(plan)
            self.assertGreaterEqual(len(plan), 3)  # Should be 3-action plan
            self.assertEqual(plan[0]['name'], 'find_monsters')

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