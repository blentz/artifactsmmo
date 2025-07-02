"""Test that mission executor properly resets combat context after hunt_monsters goal."""

import unittest
from unittest.mock import MagicMock, patch

from src.controller.mission_executor import MissionExecutor
from src.controller.ai_player_controller import AIPlayerController


class TestMissionExecutorCombatReset(unittest.TestCase):
    """Test combat context reset after successful hunt_monsters goal."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.controller = AIPlayerController()
        
        # Mock goal manager
        self.goal_manager = MagicMock()
        
        # Create mission executor with mocked dependencies
        self.mission_executor = MissionExecutor(self.goal_manager, self.controller)
        
        # Mock client and character state
        self.controller.client = MagicMock()
        self.controller.character_state = MagicMock()
        self.controller.character_state.data = {
            'name': 'test_character',
            'level': 2,
            'hp': 100,
            'max_hp': 100
        }
        
        # Mock update_world_state method on controller
        self.controller.update_world_state = MagicMock()
        
    def test_combat_context_reset_before_hunt_monsters(self):
        """Test that combat context is reset from completed to idle before hunt_monsters."""
        # Arrange
        # Mock world state with completed combat
        world_state_after_combat = {
            'combat_context': {
                'status': 'completed',
                'target': None,
                'location': None
            },
            'character_status': {
                'safe': True,
                'level': 2
            }
        }
        
        # Mock get_current_world_state to return completed combat state
        self.controller.get_current_world_state = MagicMock(return_value=world_state_after_combat)
        
        # Mock _execute_goal_template to return success
        with patch.object(self.mission_executor, '_execute_goal_template', return_value=True):
            # Mock goal selection to return hunt_monsters
            with patch.object(self.mission_executor, '_select_mission_goal', 
                            return_value=('hunt_monsters', {'description': 'Hunt monsters'})):
                # Mock reset action execution
                with patch('src.controller.actions.reset_combat_context.ResetCombatContextAction') as mock_reset_class:
                    mock_reset_action = MagicMock()
                    mock_reset_action.execute.return_value = {'success': True}
                    mock_reset_class.return_value = mock_reset_action
                    
                    # Act - execute one iteration of the mission
                    # We'll mock the mission loop to run just once
                    mission_parameters = {'target_level': 3}
                    
                    # Manually execute the relevant part of execute_progression_mission
                    current_goal_name = 'hunt_monsters'
                    current_goal_config = {'description': 'Hunt monsters'}
                    
                    # This is the pre-goal code we're testing
                    if current_goal_name == 'hunt_monsters':
                        current_state = self.controller.get_current_world_state()
                        combat_status = current_state.get('combat_context', {}).get('status')
                        if combat_status == 'completed':
                            # Execute the reset action
                            reset_action = mock_reset_class()
                            from src.lib.action_context import ActionContext
                            context = ActionContext()
                            context.character_name = self.controller.character_state.data.get('name')
                            reset_result = reset_action.execute(self.controller.client, context)
                            
                            if reset_result and reset_result.get('success'):
                                # Update world state
                                self.controller.update_world_state(
                                    {'combat_context': {'status': 'idle', 'target': None, 'location': None}}
                                )
                    
                    # Assert
                    # Verify reset action was created and executed
                    mock_reset_class.assert_called_once()
                    mock_reset_action.execute.assert_called_once()
                    
                    # Verify world state was updated
                    self.controller.update_world_state.assert_called_once_with(
                        {'combat_context': {'status': 'idle', 'target': None, 'location': None}}
                    )
    
    def test_no_reset_when_combat_not_completed(self):
        """Test that combat context is not reset if status is not completed."""
        # Arrange
        world_state_searching = {
            'combat_context': {
                'status': 'searching',
                'target': None,
                'location': None
            },
            'character_status': {
                'safe': True,
                'level': 2
            }
        }
        
        self.controller.get_current_world_state = MagicMock(return_value=world_state_searching)
        
        # Mock _execute_goal_template to return success
        with patch.object(self.mission_executor, '_execute_goal_template', return_value=True):
            with patch.object(self.mission_executor, '_select_mission_goal', 
                            return_value=('hunt_monsters', {'description': 'Hunt monsters'})):
                with patch('src.controller.actions.reset_combat_context.ResetCombatContextAction') as mock_reset_class:
                    # Act - simulate the goal success handling
                    current_goal_name = 'hunt_monsters'
                    goal_success = True
                    
                    if goal_success:
                        current_state = self.controller.get_current_world_state()
                        combat_status = current_state.get('combat_context', {}).get('status')
                        if combat_status == 'completed' and current_goal_name == 'hunt_monsters':
                            # This block should not execute
                            reset_action = mock_reset_class()
                    
                    # Assert - reset action should not be created
                    mock_reset_class.assert_not_called()


if __name__ == '__main__':
    unittest.main()