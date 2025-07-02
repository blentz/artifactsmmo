"""Test that mission executor handles already-achieved goals correctly."""

import unittest
from unittest.mock import MagicMock, patch

from src.controller.mission_executor import MissionExecutor


class TestMissionExecutorGoalAchieved(unittest.TestCase):
    """Test early return when goals are already achieved."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.goal_manager = MagicMock()
        self.controller = MagicMock()
        
        # Set up character state
        self.controller.character_state = MagicMock()
        self.controller.character_state.data = {
            'name': 'test_character',
            'level': 2,
            'hp': 100,
            'max_hp': 100
        }
        
        # Mock client
        self.controller.client = MagicMock()
        
        # Create mission executor
        self.mission_executor = MissionExecutor(self.goal_manager, self.controller)
        
    def test_goal_already_achieved_returns_early(self):
        """Test that goals already achieved return success without GOAP planning."""
        # Set up world state where combat is already completed
        current_state = {
            'combat_context': {
                'status': 'completed',
                'target': None,
                'location': None,
                'recent_win_rate': 1.0
            },
            'character_status': {
                'level': 2,
                'safe': True,
                'hp_percentage': 100.0
            }
        }
        
        self.controller.get_current_world_state = MagicMock(return_value=current_state)
        
        # Set up goal state that's already achieved
        goal_state = {
            'combat_context': {
                'status': 'completed'
            },
            'character_status': {
                'safe': True
            }
        }
        
        self.goal_manager.generate_goal_state = MagicMock(return_value=goal_state)
        
        # Mock GOAP execution manager
        self.controller.goap_execution_manager = MagicMock()
        
        # Execute goal
        goal_config = {'description': 'Hunt monsters'}
        result = self.mission_executor._execute_goal_template('hunt_monsters', goal_config, {})
        
        # Assert
        self.assertTrue(result)
        # GOAP planning should NOT have been called
        self.controller.goap_execution_manager.achieve_goal_with_goap.assert_not_called()
        
    def test_goal_not_achieved_triggers_goap(self):
        """Test that unachieved goals trigger GOAP planning."""
        # Set up world state where combat is idle
        current_state = {
            'combat_context': {
                'status': 'idle',
                'target': None,
                'location': None
            },
            'character_status': {
                'level': 2,
                'safe': True,
                'hp_percentage': 100.0
            }
        }
        
        self.controller.get_current_world_state = MagicMock(return_value=current_state)
        
        # Set up goal state that's not achieved
        goal_state = {
            'combat_context': {
                'status': 'completed'
            },
            'character_status': {
                'safe': True
            }
        }
        
        self.goal_manager.generate_goal_state = MagicMock(return_value=goal_state)
        
        # Mock GOAP execution manager
        self.controller.goap_execution_manager = MagicMock()
        self.controller.goap_execution_manager.achieve_goal_with_goap = MagicMock(return_value=True)
        
        # Execute goal
        goal_config = {'description': 'Hunt monsters'}
        result = self.mission_executor._execute_goal_template('hunt_monsters', goal_config, {})
        
        # Assert
        self.assertTrue(result)
        # GOAP planning should have been called
        self.controller.goap_execution_manager.achieve_goal_with_goap.assert_called_once()
        
    def test_nested_state_comparison(self):
        """Test that nested state comparisons work correctly."""
        # Test various nested state scenarios
        test_cases = [
            # Goal achieved - subset match
            {
                'goal': {'a': {'b': 1}},
                'current': {'a': {'b': 1, 'c': 2}},
                'expected': True
            },
            # Goal not achieved - value mismatch
            {
                'goal': {'a': {'b': 1}},
                'current': {'a': {'b': 2}},
                'expected': False
            },
            # Goal not achieved - missing key
            {
                'goal': {'a': {'b': 1}},
                'current': {'a': {'c': 1}},
                'expected': False
            },
            # Goal achieved - complex nested
            {
                'goal': {'a': {'b': {'c': 'test'}}},
                'current': {'a': {'b': {'c': 'test', 'd': 'extra'}, 'e': 5}},
                'expected': True
            },
        ]
        
        for case in test_cases:
            result = self.mission_executor._is_goal_already_achieved(case['goal'], case['current'])
            self.assertEqual(result, case['expected'], 
                           f"Failed for goal={case['goal']}, current={case['current']}")


if __name__ == '__main__':
    unittest.main()