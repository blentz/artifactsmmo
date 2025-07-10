"""
Comprehensive tests for diagnostic tools module.

Tests cover all functionality including offline simulation, live execution,
state handling, and error conditions.
"""

import json
import logging
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

from src.diagnostic_tools import DiagnosticTools
from src.lib.state_parameters import StateParameters


class TestDiagnosticTools(TestCase):
    """Test cases for DiagnosticTools class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = MagicMock()
        self.mock_logger = MagicMock()
        
    def tearDown(self):
        """Clean up after tests."""
        # Reset any mocks
        self.mock_client.reset_mock()
        
    @patch('src.diagnostic_tools.GoapData')
    def test_init_offline_mode_default(self, mock_goap_data):
        """Test initialization in offline mode with default state."""
        # Mock the GOAP data loading
        mock_goap_data.return_value.data = {'test': 'state'}
        
        tools = DiagnosticTools(client=self.mock_client, offline=True)
        
        self.assertTrue(tools.offline)
        self.assertIsNone(tools.controller)
        self.assertEqual(tools.current_state, {'test': 'state'})
        
    def test_init_clean_state(self):
        """Test initialization with clean state."""
        tools = DiagnosticTools(client=self.mock_client, clean_state=True)
        
        # Verify clean state structure uses flat parameters
        self.assertIn(StateParameters.CHARACTER_ALIVE, tools.current_state)
        self.assertIn(StateParameters.COMBAT_STATUS, tools.current_state)
        self.assertIn(StateParameters.EQUIPMENT_UPGRADE_STATUS, tools.current_state)
        self.assertTrue(tools.current_state[StateParameters.CHARACTER_ALIVE])
        self.assertEqual(tools.current_state[StateParameters.CHARACTER_LEVEL], 1)
        
    def test_init_custom_state_json(self):
        """Test initialization with custom JSON state."""
        custom_state = json.dumps({
            StateParameters.CHARACTER_ALIVE: True,
            StateParameters.CHARACTER_LEVEL: 5
        })
        
        tools = DiagnosticTools(client=self.mock_client, custom_state=custom_state)
        
        self.assertEqual(tools.current_state[StateParameters.CHARACTER_LEVEL], 5)
        
    def test_init_custom_state_dict(self):
        """Test initialization with custom dict state."""
        custom_state = {
            StateParameters.CHARACTER_ALIVE: False,
            StateParameters.CHARACTER_LEVEL: 10
        }
        
        tools = DiagnosticTools(client=self.mock_client, custom_state=custom_state)
        
        self.assertEqual(tools.current_state[StateParameters.CHARACTER_LEVEL], 10)
        self.assertFalse(tools.current_state[StateParameters.CHARACTER_ALIVE])
        
    @patch('src.diagnostic_tools.AIPlayerController')
    @patch('src.diagnostic_tools.CharacterState')
    @patch('src.diagnostic_tools.MapState')
    def test_init_live_mode(self, mock_map_state, mock_char_state, mock_controller):
        """Test initialization in live mode."""
        tools = DiagnosticTools(
            client=self.mock_client,
            offline=False,
            clean_state=True
        )
        
        self.assertFalse(tools.offline)
        self.assertIsNotNone(tools.controller)
        mock_controller.assert_called_once()
        mock_char_state.assert_called_once()
        mock_map_state.assert_called_once()
        
    def test_parse_custom_state_invalid_json(self):
        """Test parsing invalid JSON state."""
        with patch.object(DiagnosticTools, '_get_clean_state') as mock_clean:
            mock_clean.return_value = {'clean': 'state'}
            
            tools = DiagnosticTools(
                client=self.mock_client,
                custom_state='invalid json {'
            )
            
            self.assertEqual(tools.current_state, {'clean': 'state'})
            
    def test_parse_goal_string_template(self):
        """Test parsing goal string that matches a template."""
        tools = DiagnosticTools(client=self.mock_client)
        tools.goal_manager.goal_templates = {
            'test_goal': {
                'target_state': {
                    'character_status': {'level': 10}
                }
            }
        }
        
        result = tools._parse_goal_string('test_goal')
        
        self.assertEqual(result, {'character_status': {'level': 10}})
        
    def test_parse_goal_string_nested_expression(self):
        """Test parsing nested goal expression."""
        tools = DiagnosticTools(client=self.mock_client)
        
        result = tools._parse_goal_string('character_status.alive=true')
        
        # Architecture compliance - system now uses flattened StateParameters
        self.assertEqual(result, {
            'character_status.alive': True
        })
        
    def test_parse_goal_string_simple_expression(self):
        """Test parsing simple goal expression."""
        tools = DiagnosticTools(client=self.mock_client)
        
        result = tools._parse_goal_string('test_flag=false')
        
        self.assertEqual(result, {'test_flag': False})
        
    def test_parse_goal_string_level_pattern(self):
        """Test parsing level-based goal."""
        tools = DiagnosticTools(client=self.mock_client)
        
        result = tools._parse_goal_string('reach level 25')
        
        # Architecture compliance - system now uses flattened StateParameters
        self.assertEqual(result, {
            'character_status.level': 25
        })
        
    def test_parse_value_types(self):
        """Test value parsing for different types."""
        tools = DiagnosticTools(client=self.mock_client)
        
        self.assertTrue(tools._parse_value('true'))
        self.assertTrue(tools._parse_value('True'))
        self.assertFalse(tools._parse_value('false'))
        self.assertFalse(tools._parse_value('False'))
        self.assertIsNone(tools._parse_value('null'))
        self.assertIsNone(tools._parse_value('None'))
        self.assertEqual(tools._parse_value('42'), 42)
        self.assertEqual(tools._parse_value('3.14'), 3.14)
        self.assertEqual(tools._parse_value('hello'), 'hello')
        
    def test_parse_plan_string_arrow_separator(self):
        """Test parsing plan with arrow separator."""
        tools = DiagnosticTools(client=self.mock_client)
        
        result = tools._parse_plan_string('move->attack->rest')
        
        self.assertEqual(result, ['move', 'attack', 'rest'])
        
    def test_parse_plan_string_comma_separator(self):
        """Test parsing plan with comma separator."""
        tools = DiagnosticTools(client=self.mock_client)
        
        result = tools._parse_plan_string('move, attack, rest')
        
        self.assertEqual(result, ['move', 'attack', 'rest'])
        
    def test_parse_plan_string_single_action(self):
        """Test parsing plan with single action."""
        tools = DiagnosticTools(client=self.mock_client)
        
        result = tools._parse_plan_string('rest')
        
        self.assertEqual(result, ['rest'])
        
    def test_check_conditions_nested_success(self):
        """Test checking nested conditions that pass."""
        tools = DiagnosticTools(client=self.mock_client)
        
        conditions = {
            'character_status': {
                'alive': True,
                'level': 5
            },
            'simple_flag': True
        }
        
        state = {
            'character_status': {
                'alive': True,
                'level': 5,
                'hp': 100
            },
            'simple_flag': True,
            'extra_field': 'ignored'
        }
        
        # Use _simulate_action_with_goap_logic which includes condition checking
        action_cfg = {
            'conditions': conditions,
            'reactions': {},
            'weight': 1.0
        }
        success, cost = tools._simulate_action_with_goap_logic('test_action', action_cfg, state)
        
        self.assertTrue(success)
        self.assertGreater(cost, 0)  # Should return positive cost when successful
        
    def test_check_conditions_nested_failure(self):
        """Test checking nested conditions that fail."""
        tools = DiagnosticTools(client=self.mock_client)
        
        conditions = {
            'character_status': {
                'alive': True,
                'level': 10
            },
            'simple_flag': False
        }
        
        state = {
            'character_status': {
                'alive': True,
                'level': 5
            },
            'simple_flag': True
        }
        
        # Use _simulate_action_with_goap_logic which includes condition checking
        action_cfg = {
            'conditions': conditions,
            'reactions': {},
            'weight': 1.0
        }
        success, cost = tools._simulate_action_with_goap_logic('test_action', action_cfg, state)
        
        self.assertFalse(success)  # Should fail because conditions don't match
        self.assertEqual(cost, 0)   # Should return 0 cost when failed
        
    @patch('src.diagnostic_tools.ActionsData')
    @patch('logging.Logger.info')
    @patch('logging.Logger.error')
    def test_show_goal_plan_offline_no_plan(self, mock_error, mock_info, mock_actions_data):
        """Test showing goal plan when no plan can be found."""
        # Mock actions data
        mock_actions_data.return_value.get_actions.return_value = {}
        
        tools = DiagnosticTools(client=self.mock_client, clean_state=True)
        tools.goap_executor.create_plan = MagicMock(return_value=None)
        
        tools.show_goal_plan('impossible_goal')
        
        # Verify error handling was called
        self.assertTrue(any('No plan found' in str(call) for call in mock_info.call_args_list))
        
    @patch('src.diagnostic_tools.ActionsData')
    @patch('logging.Logger.info')
    def test_show_goal_plan_offline_with_plan(self, mock_info, mock_actions_data):
        """Test showing goal plan with successful plan generation."""
        # Mock actions data
        mock_actions = {
            'move': {
                'conditions': {StateParameters.CHARACTER_ALIVE: True},
                'reactions': {'location_context.at_target': True},
                'weight': 1
            }
        }
        mock_actions_data.return_value.get_actions.return_value = mock_actions
        
        tools = DiagnosticTools(client=self.mock_client, clean_state=True)
        tools.goap_executor.create_plan = MagicMock(return_value=[
            {'name': 'move'}
        ])
        
        tools.show_goal_plan('location_context.at_target=true')
        
        # Verify plan was displayed
        self.assertTrue(any('Plan found with 1 actions' in str(call) for call in mock_info.call_args_list))
        
    @patch('src.diagnostic_tools.ActionsData')
    @patch('logging.Logger.info')
    def test_show_goal_plan_live_success(self, mock_info, mock_actions_data):
        """Test showing goal plan with live execution."""
        # Mock actions data
        mock_actions_data.return_value.get_actions.return_value = {}
        
        tools = DiagnosticTools(client=self.mock_client, offline=False, clean_state=True)
        tools.goap_executor.create_plan = MagicMock(return_value=[{'name': 'test'}])
        tools._execute_plan_live = MagicMock(return_value=True)
        
        tools.show_goal_plan('test_goal')
        
        tools._execute_plan_live.assert_called_once()
        self.assertTrue(any('Plan executed successfully' in str(call) for call in mock_info.call_args_list))
        
    @patch('src.diagnostic_tools.ActionsData')
    @patch('logging.Logger.error')
    def test_evaluate_user_plan_unknown_action(self, mock_error, mock_actions_data):
        """Test evaluating plan with unknown action."""
        mock_actions_data.return_value.get_actions.return_value = {
            'move': {},
            'attack': {}
        }
        
        tools = DiagnosticTools(client=self.mock_client, clean_state=True)
        
        tools.evaluate_user_plan('move->unknown_action->attack')
        
        # Verify error was logged
        self.assertTrue(any("Unknown action 'unknown_action'" in str(call) for call in mock_error.call_args_list))
        
    @patch('src.diagnostic_tools.ActionsData')
    @patch('logging.Logger.info')
    def test_evaluate_user_plan_offline_success(self, mock_info, mock_actions_data):
        """Test evaluating valid plan in offline mode."""
        mock_actions = {
            'rest': {
                'conditions': {StateParameters.CHARACTER_ALIVE: True},
                'reactions': {StateParameters.CHARACTER_HP: 100},
                'weight': 1
            }
        }
        mock_actions_data.return_value.get_actions.return_value = mock_actions
        
        tools = DiagnosticTools(client=self.mock_client, clean_state=True)
        
        tools.evaluate_user_plan('rest')
        
        # Verify success
        self.assertTrue(any('Plan is VALID' in str(call) for call in mock_info.call_args_list))
        
    def test_simulate_action_conditions_not_met(self):
        """Test simulating action when conditions aren't met."""
        tools = DiagnosticTools(client=self.mock_client, clean_state=True)
        
        action_cfg = {
            'conditions': {
                'character_status': {'level': 10}
            },
            'reactions': {},
            'weight': 1
        }
        
        state = tools.current_state.copy()
        # Use _simulate_action_with_goap_logic instead of removed _simulate_action
        success, cost = tools._simulate_action_with_goap_logic('test', action_cfg, state)
        
        self.assertFalse(success)  # Should fail because level requirement not met
        self.assertEqual(cost, 0)   # Should return 0 cost when failed
        
    def test_simulate_action_with_nested_reactions(self):
        """Test simulating action with nested reactions."""
        tools = DiagnosticTools(client=self.mock_client, clean_state=True)
        
        action_cfg = {
            'conditions': {
                StateParameters.CHARACTER_ALIVE: True
            },
            'reactions': {
                StateParameters.CHARACTER_LEVEL: 2,
                StateParameters.CHARACTER_XP_PERCENTAGE: 50
            },
            'weight': 2.5
        }
        
        state = tools.current_state.copy()
        # Use _simulate_action_with_goap_logic instead of removed _simulate_action
        success, cost = tools._simulate_action_with_goap_logic('test', action_cfg, state)
        
        self.assertTrue(success)
        self.assertEqual(cost, 2.5)  # Should return the weight value as cost
        
        # Check reactions were applied to the state
        self.assertEqual(state[StateParameters.CHARACTER_LEVEL], 2)
        self.assertEqual(state[StateParameters.CHARACTER_XP_PERCENTAGE], 50)
        
    def test_execute_action_live_no_controller(self):
        """Test live execution without controller."""
        tools = DiagnosticTools(client=self.mock_client, offline=True)
        
        result = tools._execute_action_live('test', {})
        
        self.assertFalse(result)
        
    def test_execute_action_live_success(self):
        """Test successful live action execution."""
        tools = DiagnosticTools(client=self.mock_client, offline=False, clean_state=True)
        tools.controller._execute_single_action = MagicMock(return_value=True)
        tools.controller.get_current_world_state = MagicMock(return_value={'updated': 'state'})
        
        result = tools._execute_action_live('test', {})
        
        self.assertTrue(result)
        self.assertEqual(tools.current_state, {'updated': 'state'})
        
    def test_execute_action_live_exception(self):
        """Test live action execution with exception."""
        tools = DiagnosticTools(client=self.mock_client, offline=False, clean_state=True)
        tools.controller._execute_single_action = MagicMock(side_effect=Exception('Test error'))
        
        result = tools._execute_action_live('test', {})
        
        self.assertFalse(result)
        
    def test_execute_plan_live_success(self):
        """Test successful live plan execution."""
        tools = DiagnosticTools(client=self.mock_client, offline=False, clean_state=True)
        tools.controller.execute_plan = MagicMock(return_value=True)
        tools.controller.get_current_world_state = MagicMock(return_value={'final': 'state'})
        
        plan = [{'name': 'action1'}, {'name': 'action2'}]
        result = tools._execute_plan_live(plan)
        
        self.assertTrue(result)
        self.assertEqual(tools.controller.current_plan, plan)
        self.assertEqual(tools.current_state, {'final': 'state'})
        
    def test_format_state_for_display(self):
        """Test state formatting for display."""
        tools = DiagnosticTools(client=self.mock_client)
        
        state = {
            'simple': 'value',
            'nested': {
                'key1': 'value1',
                'key2': 42
            },
            'list': [1, 2, 3]
        }
        
        result = tools._format_state_for_display(state)
        
        self.assertIn('simple: value', result)
        self.assertIn('nested: {key1: value1, key2: 42}', result)
        self.assertIn('list: [3 items]', result)
        
    def test_has_nested_changes(self):
        """Test detecting nested dictionary changes."""
        tools = DiagnosticTools(client=self.mock_client)
        
        dict1 = {'a': 1, 'b': {'c': 2}}
        dict2 = {'a': 1, 'b': {'c': 2}}
        dict3 = {'a': 1, 'b': {'c': 3}}
        
        self.assertFalse(tools._has_nested_changes(dict1, dict2))
        self.assertTrue(tools._has_nested_changes(dict1, dict3))
        
    @patch('logging.Logger.info')
    def test_display_state_changes(self, mock_info):
        """Test displaying state changes."""
        tools = DiagnosticTools(client=self.mock_client)
        
        initial = {
            'character_status': {
                'level': 1,
                'hp': 100
            },
            'unchanged': 'value'
        }
        
        final = {
            'character_status': {
                'level': 2,
                'hp': 80
            },
            'unchanged': 'value',
            'new_field': 'new'
        }
        
        tools._display_state_changes(initial, final)
        
        # Verify changes were logged
        calls = [str(call) for call in mock_info.call_args_list]
        self.assertTrue(any('level: 1 → 2' in call for call in calls))
        self.assertTrue(any('hp: 100 → 80' in call for call in calls))
        self.assertTrue(any('new_field: None → new' in call for call in calls))


class TestDiagnosticToolsIntegration(TestCase):
    """Integration tests for diagnostic tools."""
    
    @patch('src.diagnostic_tools.GoapData')
    @patch('src.diagnostic_tools.ActionsData')
    @patch('logging.Logger.info')
    def test_full_offline_goal_planning(self, mock_info, mock_actions_data, mock_goap_data):
        """Test complete offline goal planning workflow."""
        # Set up mocks
        mock_goap_data.return_value.data = {
            'character_status': {
                'alive': True,
                'level': 1
            }
        }
        
        mock_actions_data.return_value.get_actions.return_value = {
            'level_up': {
                'conditions': {
                    StateParameters.CHARACTER_ALIVE: True
                },
                'reactions': {
                    StateParameters.CHARACTER_LEVEL: 2
                },
                'weight': 5
            }
        }
        
        # Create tools and test
        tools = DiagnosticTools(offline=True)
        tools.goap_executor.create_plan = MagicMock(return_value=[
            {'name': 'level_up'}
        ])
        
        tools.show_goal_plan('character_status.level=2')
        
        # Verify workflow
        self.assertTrue(any('OFFLINE simulation' in str(call) for call in mock_info.call_args_list))
        self.assertTrue(any('Plan found' in str(call) for call in mock_info.call_args_list))
        
    @patch('src.diagnostic_tools.ActionsData')
    @patch('logging.Logger.info')
    def test_full_plan_evaluation_workflow(self, mock_info, mock_actions_data):
        """Test complete plan evaluation workflow."""
        mock_actions = {
            'move': {
                'conditions': {StateParameters.CHARACTER_ALIVE: True},
                'reactions': {'location_context.at_target': True},
                'weight': 1
            },
            'attack': {
                'conditions': {
                    'location_context.at_target': True,
                    StateParameters.CHARACTER_ALIVE: True
                },
                'reactions': {'combat_context': {'status': 'completed'}},
                'weight': 3
            }
        }
        mock_actions_data.return_value.get_actions.return_value = mock_actions
        
        tools = DiagnosticTools(clean_state=True)
        tools.evaluate_user_plan('move->attack')
        
        # Verify evaluation completed
        self.assertTrue(any('Plan is VALID' in str(call) for call in mock_info.call_args_list))
        self.assertTrue(any('Total cost: 4' in str(call) for call in mock_info.call_args_list))