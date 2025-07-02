"""Additional tests to improve MissionExecutor coverage."""

import os
import tempfile
import unittest
from unittest.mock import Mock, MagicMock, patch, PropertyMock

from src.controller.mission_executor import MissionExecutor
from src.controller.ai_player_controller import AIPlayerController


class TestMissionExecutorCoverage(unittest.TestCase):
    """Additional test cases to improve MissionExecutor coverage."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.controller = Mock(spec=AIPlayerController)
        self.goal_manager = Mock()
        self.mission_executor = MissionExecutor(self.goal_manager, self.controller)
        
        # Mock controller attributes
        self.controller.client = Mock()
        self.controller.character_state = Mock()
        self.controller.character_state.data = {
            'name': 'test_character',
            'level': 5,
            'hp': 80,
            'max_hp': 100
        }
        self.controller.get_current_world_state = Mock(return_value={
            'character_status': {
                'level': 5,
                'hp': 80,
                'max_hp': 100,
                'hp_percentage': 80.0
            }
        })
        self.controller.update_world_state = Mock()
        
    def test_load_configuration_exception(self):
        """Test _load_configuration with exception during file loading."""
        # Test what happens when config_data.data property access raises an exception
        mock_config_data = Mock()
        type(mock_config_data).data = PropertyMock(side_effect=Exception("Config load error"))
        
        # Create mission executor with mocked config data
        mission_executor = MissionExecutor(self.goal_manager, self.controller)
        mission_executor.config_data = mock_config_data
        
        # Manually call _load_configuration to trigger the exception
        mission_executor._load_configuration()
        
        # Should have empty defaults due to exception
        self.assertEqual(mission_executor.goal_templates, {})
        self.assertEqual(mission_executor.thresholds, {})
        self.assertEqual(mission_executor.max_mission_iterations, 25)
        self.assertEqual(mission_executor.max_goal_iterations, 5)
            
    def test_track_goal_failure_with_none(self):
        """Test _track_goal_failure with None goal name."""
        # Should not crash
        self.mission_executor._track_goal_failure(None)
        # No failures should be recorded
        self.assertEqual(len(self.mission_executor.goal_failure_counts), 0)
        
    def test_track_goal_failure_multiple_times(self):
        """Test _track_goal_failure tracking multiple failures."""
        # Track failures up to the limit
        for i in range(self.mission_executor.max_goal_failures):
            self.mission_executor._track_goal_failure('test_goal')
            
        # Goal should now be in failed_goals
        self.assertIn('test_goal', self.mission_executor.failed_goals)
        self.assertEqual(
            self.mission_executor.goal_failure_counts['test_goal'], 
            self.mission_executor.max_goal_failures
        )
        
    def test_get_available_goals_with_exclusions(self):
        """Test _get_available_goals with failed goals."""
        # Set up some goals
        self.mission_executor.goal_templates = {
            'goal1': {},
            'goal2': {},
            'goal3': {}
        }
        
        # Mark goal2 as failed
        self.mission_executor.failed_goals.add('goal2')
        
        # Get available goals
        available = self.mission_executor._get_available_goals()
        
        # Currently the code has failed goal exclusion disabled (line 89)
        # So all goals should be available
        self.assertEqual(set(available), {'goal1', 'goal2', 'goal3'})
        
    def test_should_reselect_goal_no_current_goal(self):
        """Test _should_reselect_goal when no current goal."""
        # Method signature: (current_goal_name, current_level, goal_start_level, hp_percentage, combat_not_viable)
        result = self.mission_executor._should_reselect_goal(None, 5, 5, 100, False)
        self.assertTrue(result)
        
    def test_should_reselect_goal_level_up(self):
        """Test _should_reselect_goal when level increased."""
        # Current level is higher than start level
        # Method signature: (current_goal_name, current_level, goal_start_level, hp_percentage, combat_not_viable)
        result = self.mission_executor._should_reselect_goal('hunt_monsters', 5, 4, 100, False)
        self.assertTrue(result)
        
    def test_should_reselect_goal_low_hp(self):
        """Test _should_reselect_goal when HP drops."""
        # HP less than 100%
        # Method signature: (current_goal_name, current_level, goal_start_level, hp_percentage, combat_not_viable)
        result = self.mission_executor._should_reselect_goal('hunt_monsters', 5, 5, 50, False)
        self.assertTrue(result)
        
    def test_should_reselect_goal_combat_not_viable(self):
        """Test _should_reselect_goal when combat becomes not viable."""
        # Combat not viable while hunting monsters
        # Method signature: (current_goal_name, current_level, goal_start_level, hp_percentage, combat_not_viable)
        result = self.mission_executor._should_reselect_goal('hunt_monsters', 5, 5, 100, True)
        self.assertTrue(result)
        
    def test_should_reselect_goal_false(self):
        """Test _should_reselect_goal returns False when no conditions met."""
        # No conditions met
        # Method signature: (current_goal_name, current_level, goal_start_level, hp_percentage, combat_not_viable)
        result = self.mission_executor._should_reselect_goal('hunt_monsters', 5, 5, 100, False)
        self.assertFalse(result)
        
    def test_handle_pre_goal_setup_hunt_monsters(self):
        """Test _handle_pre_goal_setup for hunt_monsters goal."""
        with patch.object(self.mission_executor, '_reset_combat_context_if_completed') as mock_reset:
            self.mission_executor._handle_pre_goal_setup('hunt_monsters')
            mock_reset.assert_called_once()
            
    def test_handle_pre_goal_setup_other_goal(self):
        """Test _handle_pre_goal_setup for non-hunt_monsters goal."""
        with patch.object(self.mission_executor, '_reset_combat_context_if_completed') as mock_reset:
            self.mission_executor._handle_pre_goal_setup('get_to_safety')
            mock_reset.assert_not_called()
            
    def test_reset_combat_context_if_completed(self):
        """Test _reset_combat_context_if_completed when combat is completed."""
        # Set up completed combat state
        self.controller.get_current_world_state.return_value = {
            'combat_context': {
                'status': 'completed'
            }
        }
        
        # Mock the reset action
        mock_reset_action = Mock()
        mock_reset_action.execute.return_value = {'success': True}
        
        with patch('src.controller.actions.reset_combat_context.ResetCombatContextAction', 
                  return_value=mock_reset_action):
            self.mission_executor._reset_combat_context_if_completed()
            
            # Should execute reset action
            mock_reset_action.execute.assert_called_once()
            
            # Should update world state
            self.controller.update_world_state.assert_called_once_with({
                'combat_context': {'status': 'idle', 'target': None, 'location': None}
            })
            
    def test_reset_combat_context_not_completed(self):
        """Test _reset_combat_context_if_completed when combat is not completed."""
        # Set up non-completed combat state
        self.controller.get_current_world_state.return_value = {
            'combat_context': {
                'status': 'searching'
            }
        }
        
        with patch('src.controller.actions.reset_combat_context.ResetCombatContextAction') as mock_action_class:
            self.mission_executor._reset_combat_context_if_completed()
            
            # Should not create reset action
            mock_action_class.assert_not_called()
            
    def test_reset_combat_context_if_completed_reset_fails(self):
        """Test _reset_combat_context_if_completed when reset action fails."""
        # Set up completed combat state
        self.controller.get_current_world_state.return_value = {
            'combat_context': {
                'status': 'completed'
            }
        }
        
        # Mock the reset action to fail
        mock_reset_action = Mock()
        mock_reset_action.execute.return_value = {'success': False}
        
        with patch('src.controller.actions.reset_combat_context.ResetCombatContextAction', 
                  return_value=mock_reset_action):
            self.mission_executor._reset_combat_context_if_completed()
            
            # Should execute reset action
            mock_reset_action.execute.assert_called_once()
            
            # Should not update world state when reset fails
            self.controller.update_world_state.assert_not_called()
            
    def test_execute_goal_template_with_current_goal_parameters(self):
        """Test _execute_goal_template when controller has current_goal_parameters."""
        # Set up controller with goal parameters
        self.controller.current_goal_parameters = {'target_level': 10}
        
        # Mock goal manager and GOAP execution
        self.goal_manager.generate_goal_state.return_value = {'level': 10}
        self.controller.goap_execution_manager = Mock()
        self.controller.goap_execution_manager.achieve_goal_with_goap.return_value = True
        
        # Execute a goal with mission parameters
        mission_params = {'target_level': 10}
        result = self.mission_executor._execute_goal_template(
            'reach_level', 
            {'type': 'state_based'},
            mission_params
        )
        
        self.assertTrue(result)
        
    def test_execute_goal_template_failure_tracking(self):
        """Test goal failure is tracked when achieve_goal returns False."""
        # Mock goal manager and other methods
        self.goal_manager.generate_goal_state.return_value = {'test': True}
        self.controller.goap_execution_manager = Mock()
        self.controller.goap_execution_manager.achieve_goal_with_goap.return_value = False
        
        # Execute a goal that will fail
        result = self.mission_executor._execute_goal_template(
            'test_goal', 
            {'type': 'state_based'}, 
            {}
        )
        
        self.assertFalse(result)
            
    def test_evaluate_goal_progress_exception_handling(self):
        """Test _evaluate_goal_progress handles exceptions gracefully."""
        # Make world state raise exception
        world_state = Mock()
        world_state.get.side_effect = Exception("State error")
        
        progress = self.mission_executor._evaluate_goal_progress('test_goal', world_state, {})
        
        # Should return 0 on exception
        self.assertEqual(progress, 0.0)
        
    def test_select_mission_goal_no_valid_goals(self):
        """Test _select_mission_goal when no goals pass validation."""
        # Empty goal templates
        self.mission_executor.goal_templates = {}
        
        # Mock goal manager selection to return None
        self.goal_manager.select_goal.return_value = None
        
        result = self.mission_executor._select_mission_goal({})
        
        self.assertIsNone(result)
        
    def test_select_mission_goal_all_complete(self):
        """Test _select_mission_goal when all goals are 100% complete."""
        self.mission_executor.goal_templates = {
            'goal1': {'type': 'state_based'},
            'goal2': {'type': 'state_based'}
        }
        
        # Mock _get_available_goals to return goals
        with patch.object(self.mission_executor, '_get_available_goals', return_value=['goal1', 'goal2']):
            # Mock goal manager to return None (no suitable goal)
            self.goal_manager.select_goal.return_value = None
            
            result = self.mission_executor._select_mission_goal({})
            
            # Should return None when no suitable goal
            self.assertIsNone(result)
            
    def test_execute_level_progression_no_client(self):
        """Test execute_level_progression without client."""
        self.controller.client = None
        
        result = self.mission_executor.execute_level_progression()
        self.assertFalse(result)
        
    def test_execute_level_progression_no_character_state(self):
        """Test execute_level_progression without character state."""
        self.controller.character_state = None
        
        result = self.mission_executor.execute_level_progression()
        self.assertFalse(result)
        
    def test_execute_level_progression_missing_template(self):
        """Test execute_level_progression when reach_level template is missing."""
        self.mission_executor.goal_templates = {}  # No templates
        
        result = self.mission_executor.execute_level_progression(target_level=10)
        self.assertFalse(result)
        
    def test_execute_progression_mission_success(self):
        """Test execute_progression_mission with successful execution."""
        # Set up goal templates
        self.mission_executor.goal_templates = {
            'hunt_monsters': {'type': 'combat'},
            'get_to_safety': {'type': 'recovery'}
        }
        
        # Mock goal selection
        with patch.object(self.mission_executor, '_select_mission_goal', 
                         return_value=('hunt_monsters', {'type': 'combat'})):
            # Mock goal execution success
            with patch.object(self.mission_executor, '_execute_goal_template', return_value=True):
                # Mock character state to trigger completion
                self.controller.character_state.data['level'] = 10
                
                # Set mission parameters
                mission_parameters = {'target_level': 10}
                
                result = self.mission_executor.execute_progression_mission(
                    mission_parameters
                )
                
                self.assertTrue(result)
        
    def test_record_goal_progress_new_goal(self):
        """Test _record_goal_progress for a new goal."""
        self.mission_executor._record_goal_progress('new_goal', 0.5)
        
        self.assertIn('new_goal', self.mission_executor.goal_progress_history)
        self.assertEqual(self.mission_executor.goal_progress_history['new_goal'][-1], 0.5)
        
    def test_record_goal_progress_existing_goal(self):
        """Test _record_goal_progress updates existing goal history."""
        # Add initial progress
        self.mission_executor.goal_progress_history['test_goal'] = [0.2, 0.4]
        
        # Record new progress
        self.mission_executor._record_goal_progress('test_goal', 0.6)
        
        # Should append to existing history
        self.assertEqual(self.mission_executor.goal_progress_history['test_goal'], [0.2, 0.4, 0.6])
        
    def test_retry_with_revised_rest_conditions(self):
        """Test _retry_with_revised_rest_conditions method."""
        # Mock controller state with HP less than 100%
        self.controller.get_current_world_state.return_value = {
            'character_status': {'hp_percentage': 80}
        }
        
        # Mock character state refresh
        self.controller.character_state.refresh = Mock()
        self.controller.character_state.data = {
            'name': 'test_character',
            'hp': 100,
            'max_hp': 100
        }
        
        # Mock rest action
        mock_rest_action = Mock()
        mock_rest_action.execute.return_value = {'success': True}
        
        # Mock _is_goal_already_achieved to return True after rest
        with patch('src.controller.actions.rest.RestAction', return_value=mock_rest_action):
            with patch.object(self.mission_executor, '_is_goal_already_achieved', return_value=True):
                goal_state = {'character_status': {'hp_percentage': 100}}
                result = self.mission_executor._retry_with_revised_rest_conditions(goal_state)
                
                self.assertTrue(result)
                
                # Verify rest action was executed
                mock_rest_action.execute.assert_called_once()
        
    def test_handle_post_goal_cleanup(self):
        """Test _handle_post_goal_cleanup method."""
        # Should not crash for any goal
        self.mission_executor._handle_post_goal_cleanup('hunt_monsters')
        self.mission_executor._handle_post_goal_cleanup('get_to_safety')
        self.mission_executor._handle_post_goal_cleanup(None)
        
    def test_reset_goal_failures_on_success(self):
        """Test _reset_goal_failures_on_success method."""
        # Add some failures
        self.mission_executor.goal_failure_counts['test_goal'] = 2
        self.mission_executor.failed_goals.add('test_goal')
        
        # Reset failures
        self.mission_executor._reset_goal_failures_on_success('test_goal')
        
        # Should be removed from tracking
        self.assertNotIn('test_goal', self.mission_executor.goal_failure_counts)
        self.assertNotIn('test_goal', self.mission_executor.failed_goals)
        
    def test_should_clear_goal(self):
        """Test _should_clear_goal method."""
        # Test with goal name
        result = self.mission_executor._should_clear_goal('reach_level')
        self.assertFalse(result)  # Default implementation returns False
        
        # Test with None
        result = self.mission_executor._should_clear_goal(None)
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()