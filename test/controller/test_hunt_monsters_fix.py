"""Test for hunt_monsters goal fix - attack action sets has_gained_xp flag."""

import tempfile
import unittest
from unittest.mock import Mock, patch

from src.controller.goap_execution_manager import GOAPExecutionManager


class TestHuntMonstersFix(unittest.TestCase):
    """Test that hunt_monsters goal can now find a valid plan after attack action fix."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock default state
        self.mock_state_defaults = {
            'character_status': {
                'level': 1,
                'hp_percentage': 100.0,
                'alive': True,
                'safe': True,
                'cooldown_active': False
            },
            'combat_context': {
                'status': 'idle'
            },
            'goal_progress': {
                'has_gained_xp': False,
                'monsters_hunted': 0
            },
            'resource_availability': {
                'monsters': False
            }
        }
        
        # Create GOAP execution manager
        with patch('src.controller.goap_execution_manager.YamlData') as mock_yaml_data:
            mock_yaml_instance = Mock()
            mock_yaml_instance.data = {'state_defaults': self.mock_state_defaults}
            mock_yaml_data.return_value = mock_yaml_instance
            
            self.goap_manager = GOAPExecutionManager()
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @patch('src.controller.goap_execution_manager.YamlData')
    def test_hunt_monsters_goal_can_find_plan(self, mock_yaml_data):
        """Test that hunt_monsters goal can now find a valid GOAP plan."""
        # Mock action configurations with the fixed attack action
        mock_actions = {
            'initiate_combat_search': {
                'conditions': {
                    'combat_context': {'status': 'idle'},
                    'character_status': {'alive': True, 'cooldown_active': False}
                },
                'reactions': {
                    'combat_context': {'status': 'searching'}
                },
                'weight': 2.0
            },
            'find_monsters': {
                'conditions': {
                    'combat_context': {'status': 'searching'},
                    'resource_availability': {'monsters': False},
                    'character_status': {'alive': True}
                },
                'reactions': {
                    'resource_availability': {'monsters': True},
                    'combat_context': {'status': 'ready'}
                },
                'weight': 2.0
            },
            'attack': {
                'conditions': {
                    'combat_context': {'status': 'ready'},
                    'character_status': {'safe': True, 'alive': True}
                },
                'reactions': {
                    'combat_context': {'status': 'completed'},
                    'goal_progress': {
                        'monsters_hunted': '+1',
                        'has_gained_xp': True  # This is the fix!
                    }
                },
                'weight': 3.0
            }
        }
        
        # Mock the YAML data loading
        mock_yaml_instance = Mock()
        mock_yaml_instance.data = {
            'state_defaults': self.mock_state_defaults,
            'actions': mock_actions
        }
        mock_yaml_data.return_value = mock_yaml_instance
        
        # Create fresh manager with mocked action data
        goap_manager = GOAPExecutionManager()
        
        # Define the hunt_monsters goal state
        goal_state = {
            'goal_progress': {
                'has_gained_xp': True
            }
        }
        
        # Create the plan
        start_state = self.mock_state_defaults.copy()
        plan = goap_manager.create_plan(start_state, goal_state, mock_actions)
        
        # Verify that a plan was found
        self.assertIsNotNone(plan, "hunt_monsters goal should now find a valid plan")
        self.assertGreater(len(plan), 0, "Plan should contain at least one action")
        
        # Verify the plan contains the expected actions
        action_names = [action.get('name', 'unknown') for action in plan]
        self.assertIn('attack', action_names, "Plan should include attack action")
        
        # Find the attack action in the plan
        attack_action = None
        for action in plan:
            if action.get('name') == 'attack':
                attack_action = action
                break
        
        self.assertIsNotNone(attack_action, "Attack action should be in the plan")
    
    @patch('src.controller.goap_execution_manager.YamlData')
    def test_attack_action_sets_has_gained_xp(self, mock_yaml_data):
        """Test that attack action properly sets has_gained_xp flag."""
        # Load the actual default actions configuration to test the fix
        from src.lib.yaml_data import YamlData
        
        # Load real config to verify our fix
        actual_actions_config = YamlData('config/default_actions.yaml')
        attack_config = actual_actions_config.data['actions']['attack']
        
        # Verify the fix is in place
        self.assertIn('goal_progress', attack_config['reactions'], 
                     "Attack action should have goal_progress reactions")
        self.assertIn('has_gained_xp', attack_config['reactions']['goal_progress'],
                     "Attack action should set has_gained_xp in reactions")
        self.assertTrue(attack_config['reactions']['goal_progress']['has_gained_xp'],
                       "Attack action should set has_gained_xp to True")
    
    def test_attack_action_increments_monsters_hunted(self):
        """Test that attack action still increments monsters_hunted counter."""
        from src.lib.yaml_data import YamlData
        
        # Load real config to verify both effects are present
        actual_actions_config = YamlData('config/default_actions.yaml')
        attack_config = actual_actions_config.data['actions']['attack']
        
        # Verify both reactions are present
        goal_progress_reactions = attack_config['reactions']['goal_progress']
        
        self.assertIn('monsters_hunted', goal_progress_reactions,
                     "Attack action should still increment monsters_hunted")
        self.assertEqual(goal_progress_reactions['monsters_hunted'], '+1',
                        "Attack action should increment monsters_hunted by 1")
        self.assertIn('has_gained_xp', goal_progress_reactions,
                     "Attack action should also set has_gained_xp")
        self.assertTrue(goal_progress_reactions['has_gained_xp'],
                       "Attack action should set has_gained_xp to True")


if __name__ == '__main__':
    unittest.main()