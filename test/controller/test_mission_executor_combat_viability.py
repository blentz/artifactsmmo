import unittest
from unittest.mock import Mock, patch

from src.controller.goal_manager import GOAPGoalManager
from src.controller.mission_executor import MissionExecutor


class TestMissionExecutorCombatViability(unittest.TestCase):
    """Test that mission executor properly handles combat not viable scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.goal_manager = Mock(spec=GOAPGoalManager)
        self.controller = Mock()
        
        # Set up character state
        self.controller.character_state = Mock()
        self.controller.character_state.data = {
            'level': 2,
            'hp': 100,
            'max_hp': 100,
            'x': 0,
            'y': 0
        }
        
        # Set up client
        self.controller.client = Mock()
        
        # Create mission executor
        self.mission_executor = MissionExecutor(self.goal_manager, self.controller)
        
    def test_goal_reselection_when_combat_not_viable(self):
        """Test that mission executor re-selects goal when combat is not viable."""
        # Configure world state to indicate combat is not viable
        world_state_viable = {
            'character_level': 2,
            'character_hp': 100,
            'character_max_hp': 100,
            'hp_percentage': 100,
            'character_safe': True,
            'combat_not_viable': False,  # Combat is viable initially
            'can_attack': True,
            'is_on_cooldown': False
        }
        
        world_state_not_viable = {
            'character_level': 2,
            'character_hp': 100,
            'character_max_hp': 100,
            'hp_percentage': 100,
            'character_safe': True,
            'combat_not_viable': True,  # Combat is now not viable
            'can_attack': True,
            'is_on_cooldown': False
        }
        
        # Configure controller to return different world states
        # The controller's get_current_world_state is called multiple times per iteration
        self.controller.get_current_world_state = Mock(side_effect=[
            world_state_viable,      # First iteration - initial check
            world_state_viable,      # First iteration - goal selection
            world_state_not_viable,  # Second iteration - check shows combat not viable
            world_state_not_viable,  # Second iteration - goal selection with combat_not_viable=True
            world_state_not_viable   # Additional calls
        ])
        
        # Configure goal selections
        hunt_goal = ('hunt_monsters', {'description': 'Hunt monsters'})
        upgrade_goal = ('upgrade_weapon', {'description': 'Upgrade weapon'})
        
        self.goal_manager.select_goal = Mock(side_effect=[
            hunt_goal,    # First selection
            upgrade_goal  # Second selection after combat not viable
        ])
        
        # Mock goal execution
        self.mission_executor._execute_goal_template = Mock(return_value=False)
        
        # Execute mission for 2 iterations
        self.mission_executor.max_mission_iterations = 2
        mission_params = {'target_level': 3}
        
        result = self.mission_executor.execute_progression_mission(mission_params)
        
        # Verify goal selection was called twice
        self.assertEqual(self.goal_manager.select_goal.call_count, 2)
        
        # Verify that hunt_monsters was selected first
        first_call_args = self.goal_manager.select_goal.call_args_list[0][0][0]
        self.assertFalse(first_call_args.get('combat_not_viable', False))
        
        # Verify that goal re-selection happened when combat became not viable
        second_call_args = self.goal_manager.select_goal.call_args_list[1][0][0]
        self.assertTrue(second_call_args.get('combat_not_viable', False))
        
        # Verify goal execution was called with both goals
        execute_calls = self.mission_executor._execute_goal_template.call_args_list
        self.assertEqual(len(execute_calls), 2)
        self.assertEqual(execute_calls[0][0][0], 'hunt_monsters')
        self.assertEqual(execute_calls[1][0][0], 'upgrade_weapon')
        
    def test_no_reselection_when_combat_viable(self):
        """Test that mission executor continues with hunt_monsters when combat is viable."""
        # Configure world state to indicate combat is always viable
        world_state = {
            'character_level': 2,
            'character_hp': 100,
            'character_max_hp': 100,
            'hp_percentage': 100,
            'character_safe': True,
            'combat_not_viable': False,  # Combat remains viable
            'can_attack': True,
            'is_on_cooldown': False
        }
        
        self.controller.get_current_world_state = Mock(return_value=world_state)
        
        # Configure goal selection
        hunt_goal = ('hunt_monsters', {'description': 'Hunt monsters'})
        self.goal_manager.select_goal = Mock(return_value=hunt_goal)
        
        # Mock goal execution
        self.mission_executor._execute_goal_template = Mock(return_value=True)
        
        # Execute mission for 2 iterations
        self.mission_executor.max_mission_iterations = 2
        mission_params = {'target_level': 3}
        
        result = self.mission_executor.execute_progression_mission(mission_params)
        
        # Verify goal selection was only called once (initial selection)
        self.assertEqual(self.goal_manager.select_goal.call_count, 1)
        
        # Verify goal execution was called multiple times with same goal
        execute_calls = self.mission_executor._execute_goal_template.call_args_list
        self.assertEqual(len(execute_calls), 2)
        self.assertEqual(execute_calls[0][0][0], 'hunt_monsters')
        self.assertEqual(execute_calls[1][0][0], 'hunt_monsters')
        
    def test_combat_viability_logging(self):
        """Test that appropriate log message is generated when switching due to combat viability."""
        # Configure world states - start viable, then become not viable
        world_state_viable = {
            'character_level': 2,
            'character_hp': 100,
            'character_max_hp': 100,
            'hp_percentage': 100,
            'character_safe': True,
            'combat_not_viable': False,
            'can_attack': True,
            'is_on_cooldown': False
        }
        
        world_state_not_viable = world_state_viable.copy()
        world_state_not_viable['combat_not_viable'] = True
        
        # First call for initial goal selection, second for reselection check, third for actual reselection
        self.controller.get_current_world_state = Mock(side_effect=[
            world_state_viable,      # Initial goal selection
            world_state_viable,      # First iteration check (still viable)
            world_state_not_viable,  # Second iteration check (now not viable)
            world_state_not_viable   # For goal reselection
        ])
        
        # Configure goals
        hunt_goal = ('hunt_monsters', {'description': 'Hunt monsters'})
        upgrade_goal = ('upgrade_weapon', {'description': 'Upgrade weapon'})
        
        self.goal_manager.select_goal = Mock(side_effect=[hunt_goal, upgrade_goal])
        
        # Mock goal execution - return True to continue but not complete
        self.mission_executor._execute_goal_template = Mock(return_value=True)
        
        # Capture log messages
        with patch.object(self.mission_executor.logger, 'info') as mock_info:
            self.mission_executor.max_mission_iterations = 2
            self.mission_executor.execute_progression_mission({'target_level': 5})  # High target to ensure no early exit
            
            # Check for combat viability log message
            log_messages = [call[0][0] for call in mock_info.call_args_list]
            combat_viability_logs = [msg for msg in log_messages if 'Combat no longer viable' in msg]
            
            self.assertEqual(len(combat_viability_logs), 1)
            self.assertIn('switching from hunt_monsters to equipment upgrade goals', combat_viability_logs[0])


if __name__ == '__main__':
    unittest.main()