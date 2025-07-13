"""
Comprehensive unit tests for simplified goal manager to achieve 100% coverage.

Tests the architecturally compliant GOAPGoalManager that contains no business logic.
"""

import tempfile
import unittest
from unittest.mock import Mock, patch

from src.controller.goal_manager import GOAPGoalManager


class TestGOAPGoalManagerComprehensive(unittest.TestCase):
    """Test suite for simplified GOAPGoalManager."""
    
    def setUp(self):
        """Set up test environment with mocked configuration."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock configuration data
        self.mock_config_data = {
            'goal_templates': {
                'hunt_monsters': {
                    'description': 'Hunt monsters for XP',
                    'objective_type': 'combat',
                    'target_state': {'goal_progress.has_gained_xp': True},
                    'strategy': {'max_iterations': 10}
                },
                'get_healthy': {
                    'description': 'Get to safety',
                    'target_state': {'character_status.healthy': True},
                    'strategy': {'safety_priority': True}
                }
            },
            'goal_selection_rules': {
                'emergency': [
                    {
                        'condition': {'character_status.healthy': False},
                        'goal': 'get_healthy',
                        'priority': 100
                    }
                ],
                'progression': [
                    {
                        'condition': {'character_status.healthy': True},
                        'goal': 'hunt_monsters',
                        'priority': 70
                    }
                ]
            },
            'thresholds': {
                'max_goap_iterations': 50,
                'default_search_radius': 2
            }
        }
        
        # Create goal manager with mocked configuration
        with patch('src.lib.yaml_data.YamlData') as mock_yaml_data:
            mock_yaml_instance = Mock()
            mock_yaml_instance.data = self.mock_config_data
            mock_yaml_data.return_value = mock_yaml_instance
            
            self.goal_manager = GOAPGoalManager()
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_init_with_custom_config_file(self):
        """Test initialization with custom config file."""
        with patch('src.lib.yaml_data.YamlData') as mock_yaml_data:
            mock_yaml_instance = Mock()
            mock_yaml_instance.data = self.mock_config_data
            mock_yaml_data.return_value = mock_yaml_instance
            
            goal_manager = GOAPGoalManager(config_file="custom_config.yaml")
            self.assertIsNotNone(goal_manager)
    
    def test_select_goal_emergency_priority(self):
        """Test select_goal with emergency conditions."""
        current_state = {'character_status.healthy': False}
        
        result = self.goal_manager.select_goal(current_state)
        self.assertEqual(result[0], 'get_healthy')
    
    def test_select_goal_progression(self):
        """Test select_goal with progression conditions."""
        current_state = {'character_status.healthy': True}
        
        result = self.goal_manager.select_goal(current_state)
        self.assertEqual(result[0], 'hunt_monsters')
    
    def test_select_goal_no_matching_conditions(self):
        """Test select_goal when no conditions match."""
        current_state = {}  # No matching conditions
        
        result = self.goal_manager.select_goal(current_state)
        self.assertIsNone(result)
    
    def test_select_goal_with_available_goals_filter(self):
        """Test select_goal with available_goals filter."""
        current_state = {'character_status.healthy': False}
        
        result = self.goal_manager.select_goal(current_state, available_goals=['hunt_monsters'])
        self.assertIsNone(result)  # get_healthy not in available_goals
    
    def test_select_goal_missing_goal_template(self):
        """Test select_goal when goal template is missing."""
        # Add rule for nonexistent goal
        self.goal_manager.goal_selection_rules['test'] = [
            {
                'condition': {'test_condition': True},
                'goal': 'nonexistent_goal',
                'priority': 50
            }
        ]
        
        current_state = {'test_condition': True}
        result = self.goal_manager.select_goal(current_state)
        self.assertIsNone(result)
    
    def test_check_condition_simple_equality(self):
        """Test _check_condition with simple equality."""
        condition = {'character_status.healthy': True}
        state = {'character_status.healthy': True}
        
        result = self.goal_manager._check_condition(condition, state)
        self.assertTrue(result)
    
    def test_check_condition_inequality(self):
        """Test _check_condition with inequality."""
        condition = {'character_status.healthy': True}
        state = {'character_status.healthy': False}
        
        result = self.goal_manager._check_condition(condition, state)
        self.assertFalse(result)
    
    def test_check_condition_list_values(self):
        """Test _check_condition with list values."""
        condition = {'materials.status': ['insufficient', 'gathering']}
        state = {'materials.status': 'insufficient'}
        
        result = self.goal_manager._check_condition(condition, state)
        self.assertTrue(result)
        
        state = {'materials.status': 'sufficient'}
        result = self.goal_manager._check_condition(condition, state)
        self.assertFalse(result)
    
    def test_check_condition_comparison_operators(self):
        """Test _check_condition with comparison operators."""
        condition = {'character_status.hp_percentage': '>=50'}
        state = {'character_status.hp_percentage': 75}
        
        result = self.goal_manager._check_condition(condition, state)
        self.assertTrue(result)
        
        condition = {'character_status.hp_percentage': '<50'}
        result = self.goal_manager._check_condition(condition, state)
        self.assertFalse(result)
    
    def test_check_condition_null_checks(self):
        """Test _check_condition with null checks."""
        condition = {'equipment_status.weapon': '!null'}
        state = {'equipment_status.weapon': 'wooden_sword'}
        
        result = self.goal_manager._check_condition(condition, state)
        self.assertTrue(result)
        
        condition = {'equipment_status.shield': 'null'}
        state = {'equipment_status.shield': None}
        
        result = self.goal_manager._check_condition(condition, state)
        self.assertTrue(result)
    
    def test_check_condition_string_equality(self):
        """Test _check_condition with string equality."""
        condition = {'combat_context.status': 'idle'}
        state = {'combat_context.status': 'idle'}
        
        result = self.goal_manager._check_condition(condition, state)
        self.assertTrue(result)
    
    def test_check_condition_missing_value(self):
        """Test _check_condition with missing state value."""
        condition = {'nonexistent_key': True}
        state = {}
        
        result = self.goal_manager._check_condition(condition, state)
        self.assertFalse(result)
    
    def test_generate_goal_state(self):
        """Test generate_goal_state method."""
        goal_config = {
            'target_state': {'character_status.level': 5},
            'parameters': {'max_attempts': 3}
        }
        current_state = {}
        
        result = self.goal_manager.generate_goal_state(
            'test_goal', goal_config, current_state
        )
        
        self.assertEqual(result, {'character_status.level': 5})
    
    def test_generate_goal_state_empty_target(self):
        """Test generate_goal_state with empty target_state."""
        goal_config = {}
        current_state = {}
        
        result = self.goal_manager.generate_goal_state(
            'test_goal', goal_config, current_state
        )
        
        self.assertEqual(result, {})
    
    def test_get_goal_strategy(self):
        """Test get_goal_strategy method."""
        goal_config = {
            'strategy': {
                'custom_setting': True,
                'hunt_radius': 15
            }
        }
        
        result = self.goal_manager.get_goal_strategy('test_goal', goal_config)
        
        # Should merge with defaults
        self.assertEqual(result['max_iterations'], 50)  # From thresholds in mock
        self.assertEqual(result['hunt_radius'], 15)     # From goal config
        self.assertTrue(result['safety_priority'])      # Default
        self.assertTrue(result['custom_setting'])       # From goal config
    
    def test_get_goal_strategy_empty_config(self):
        """Test get_goal_strategy with empty config."""
        goal_config = {}
        
        result = self.goal_manager.get_goal_strategy('test_goal', goal_config)
        
        # Should have defaults
        self.assertEqual(result['max_iterations'], 50)
        self.assertEqual(result['hunt_radius'], 2)
        self.assertTrue(result['safety_priority'])
    
    def test_get_threshold(self):
        """Test get_threshold method."""
        result = self.goal_manager.get_threshold('max_goap_iterations')
        self.assertEqual(result, 50)
        
        result = self.goal_manager.get_threshold('nonexistent', 'default_value')
        self.assertEqual(result, 'default_value')
    
    def test_reload_configuration(self):
        """Test reload_configuration method."""
        with patch.object(self.goal_manager.config_data, 'load') as mock_load:
            with patch.object(self.goal_manager, '_load_configuration') as mock_load_config:
                self.goal_manager.reload_configuration()
                
                mock_load.assert_called_once()
                mock_load_config.assert_called_once()


if __name__ == '__main__':
    unittest.main()