"""
Comprehensive unit tests for goal manager to achieve 100% coverage.

This test file provides comprehensive coverage for the GOAPGoalManager class,
testing all methods including edge cases and error conditions.
"""

import copy
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock

from src.controller.goal_manager import GOAPGoalManager


class TestGOAPGoalManagerComprehensive(unittest.TestCase):
    """Comprehensive test suite for GOAPGoalManager."""
    
    def setUp(self):
        """Set up test environment with mocked configuration."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock configuration data
        self.mock_config_data = {
            'goal_templates': {
                'hunt_monsters': {
                    'description': 'Hunt monsters for XP',
                    'target_state': {'character_status': {'level': '>1'}},
                    'strategy': {'max_iterations': 10}
                },
                'craft_selected_item': {
                    'description': 'Craft selected item',
                    'target_state': {'equipment_status': {'upgrade_status': 'completed'}},
                    'parameters': {'target_level': 5}
                },
                'get_to_safety': {
                    'description': 'Get to safety',
                    'target_state': {'character_status': {'safe': True}},
                    'strategy': {'safety_priority': True}
                }
            },
            'goal_selection_rules': {
                'emergency': [
                    {
                        'condition': {'character_status': {'hp_percentage': '<30'}},
                        'goal': 'get_to_safety',
                        'priority': 100
                    }
                ],
                'maintenance': [
                    {
                        'condition': {'character_status': {'alive': True}},
                        'goal': 'get_to_safety',
                        'priority': 80
                    }
                ],
                'equipment': [
                    {
                        'condition': {'equipment_status': {'weapon': '!null'}},
                        'goal': 'craft_selected_item',
                        'priority': 60
                    }
                ],
                'skill_progression': [
                    {
                        'condition': {'skills': {'weaponcrafting': {'level': '>=2'}}},
                        'goal': 'craft_selected_item',
                        'priority': 50
                    }
                ],
                'exploration': [
                    {
                        'condition': {'location_context': {'current': {'type': 'unknown'}}},
                        'goal': 'hunt_monsters',
                        'priority': 40
                    }
                ]
            },
            'state_calculation_rules': {},
            'state_mappings': {
                'character_status': {
                    'needs_healing': {
                        'source': 'character_status.hp_percentage',
                        'condition': '< 50'
                    },
                    'can_level_up': {
                        'source': 'character_status.xp_percentage',
                        'condition': '>= 90'
                    }
                },
                'equipment_status': {
                    'has_weapon': {
                        'source': 'equipment_status.weapon',
                        'condition': '!= null'
                    }
                },
                'skills': {
                    'meets_target_level': {
                        'source': 'skills.weaponcrafting.level',
                        'condition': '>= {target_level}'
                    }
                }
            },
            'thresholds': {
                'max_goap_iterations': 10,
                'default_search_radius': 8,
                'hp_emergency_threshold': 20
            }
        }
        
        self.mock_state_defaults = {
            'character_status': {
                'level': 1,
                'hp_percentage': 100,
                'xp_percentage': 0,
                'alive': True,
                'safe': True,
                'cooldown_active': False
            },
            'equipment_status': {
                'weapon': None,
                'armor': None,
                'shield': None,
                'helmet': None,
                'boots': None,
                'selected_item': None,
                'upgrade_status': 'none'
            },
            'location_context': {
                'current': {'x': 0, 'y': 0, 'type': 'unknown'}
            },
            'materials': {
                'inventory': {}
            },
            'skills': {},
            'combat_context': {
                'recent_win_rate': 1.0
            }
        }
        
        # Create goal manager with mocked configuration
        with patch('src.lib.yaml_data.YamlData') as mock_yaml_data:
            mock_yaml_instance = Mock()
            mock_yaml_instance.data = self.mock_config_data
            mock_yaml_data.return_value = mock_yaml_instance
            
            # Mock state defaults configuration
            mock_state_defaults_instance = Mock()
            mock_state_defaults_instance.data = {'state_defaults': self.mock_state_defaults}
            
            with patch('src.controller.goal_manager.YamlData') as mock_yaml_data2:
                mock_yaml_data2.side_effect = [mock_yaml_instance, mock_state_defaults_instance]
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
            
            with patch('src.controller.goal_manager.YamlData'):
                goal_manager = GOAPGoalManager(config_file="custom_config.yaml")
                self.assertIsNotNone(goal_manager)
    
    def test_load_configuration_exception_handling(self):
        """Test _load_configuration with exception handling."""
        with patch('src.lib.yaml_data.YamlData') as mock_yaml_data:
            # Mock to raise exception during _load_configuration
            mock_yaml_instance = Mock()
            mock_yaml_instance.data.get.side_effect = Exception("Test exception")
            mock_yaml_data.return_value = mock_yaml_instance
            
            # Mock state defaults config
            mock_state_defaults_instance = Mock()
            mock_state_defaults_instance.data = {'state_defaults': self.mock_state_defaults}
            
            with patch('src.controller.goal_manager.YamlData') as mock_yaml_data2:
                mock_yaml_data2.side_effect = [mock_yaml_instance, mock_state_defaults_instance]
                goal_manager = GOAPGoalManager()
                
                # Should have empty configurations due to fallback
                self.assertEqual(goal_manager.goal_templates, {})
                self.assertEqual(goal_manager.goal_selection_rules, {})
    
    def test_calculate_world_state_no_character_state(self):
        """Test calculate_world_state with no character state."""
        result = self.goal_manager.calculate_world_state(None)
        
        # Should return default state structure
        self.assertIn('character_status', result)
        self.assertIn('equipment_status', result)
        self.assertIn('location_context', result)
    
    def test_calculate_world_state_character_without_data(self):
        """Test calculate_world_state with character state without data."""
        mock_character_state = Mock()
        delattr(mock_character_state, 'data')  # Remove data attribute entirely
        
        result = self.goal_manager.calculate_world_state(mock_character_state)
        
        # Should return default state structure
        self.assertIn('character_status', result)
    
    def test_calculate_world_state_complete(self):
        """Test calculate_world_state with complete character data."""
        char_data = {
            'hp': 80,
            'max_hp': 100,
            'level': 5,
            'xp': 120,
            'max_xp': 150,
            'x': 2,
            'y': 3,
            'cooldown': 0,
            'cooldown_expiration': None,
            'weapon_slot': 'wooden_sword',
            'body_armor_slot': 'leather_armor',
            'shield_slot': None,
            'helmet_slot': None,
            'boots_slot': 'leather_boots',
            'inventory': [
                {'code': 'ash_wood', 'quantity': 5},
                {'code': 'iron_ore', 'quantity': 2}
            ],
            'weaponcrafting_level': 3,
            'weaponcrafting_xp': 250,
            'gearcrafting_level': 2,
            'gearcrafting_xp': 150
        }
        
        mock_character_state = Mock()
        mock_character_state.data = char_data
        
        mock_map_state = Mock()
        mock_map_state.get_location = Mock(return_value={'type': 'workshop'})
        
        result = self.goal_manager.calculate_world_state(mock_character_state, mock_map_state)
        
        # Validate character status
        self.assertEqual(result['character_status']['level'], 5)
        self.assertEqual(result['character_status']['hp_percentage'], 80)
        self.assertEqual(result['character_status']['xp_percentage'], 80)
        self.assertTrue(result['character_status']['alive'])
        self.assertTrue(result['character_status']['safe'])
        self.assertFalse(result['character_status']['cooldown_active'])
        
        # Validate equipment status
        self.assertEqual(result['equipment_status']['weapon'], 'wooden_sword')
        self.assertEqual(result['equipment_status']['armor'], 'leather_armor')
        self.assertIsNone(result['equipment_status']['shield'])
        self.assertEqual(result['equipment_status']['boots'], 'leather_boots')
        
        # Validate location context
        self.assertEqual(result['location_context']['current']['x'], 2)
        self.assertEqual(result['location_context']['current']['y'], 3)
        self.assertEqual(result['location_context']['current']['type'], 'workshop')
        
        # Validate materials inventory
        self.assertEqual(result['materials']['inventory']['ash_wood'], 5)
        self.assertEqual(result['materials']['inventory']['iron_ore'], 2)
        
        # Validate skills
        self.assertEqual(result['skills']['weaponcrafting']['level'], 3)
        self.assertEqual(result['skills']['weaponcrafting']['xp'], 250)
        self.assertEqual(result['skills']['gearcrafting']['level'], 2)
        self.assertEqual(result['skills']['gearcrafting']['xp'], 150)
    
    def test_determine_location_type_no_map_state(self):
        """Test _determine_location_type with no map state."""
        char_data = {'x': 1, 'y': 2}
        result = self.goal_manager._determine_location_type(char_data, None)
        self.assertEqual(result, "unknown")
    
    def test_determine_location_type_with_map_state(self):
        """Test _determine_location_type with map state."""
        char_data = {'x': 1, 'y': 2}
        mock_map_state = Mock()
        mock_map_state.get_location = Mock(return_value={'type': 'bank'})
        
        result = self.goal_manager._determine_location_type(char_data, mock_map_state)
        self.assertEqual(result, "bank")
        
        mock_map_state.get_location.assert_called_once_with(1, 2)
    
    def test_determine_location_type_no_location_data(self):
        """Test _determine_location_type when map returns no location data."""
        char_data = {'x': 1, 'y': 2}
        mock_map_state = Mock()
        mock_map_state.get_location = Mock(return_value=None)
        
        result = self.goal_manager._determine_location_type(char_data, mock_map_state)
        self.assertEqual(result, "unknown")
    
    def test_select_goal_no_available_goals(self):
        """Test select_goal with no available goals."""
        current_state = self.mock_state_defaults.copy()
        result = self.goal_manager.select_goal(current_state, available_goals=[])
        self.assertIsNone(result)
    
    def test_select_goal_emergency_priority(self):
        """Test select_goal with emergency conditions."""
        current_state = self.mock_state_defaults.copy()
        current_state['character_status']['hp_percentage'] = 25  # Emergency condition
        
        result = self.goal_manager.select_goal(current_state)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'get_to_safety')
    
    def test_select_safety_goal_with_weights(self):
        """Test _select_safety_goal with goal weights."""
        current_state = self.mock_state_defaults.copy()
        current_state['character_status']['hp_percentage'] = 25
        
        goal_weights = {'get_to_safety': 10.0}
        result = self.goal_manager._select_safety_goal(current_state, ['get_to_safety'], goal_weights)
        
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'get_to_safety')
    
    def test_select_xp_goal_hierarchical_not_safe(self):
        """Test _select_xp_goal_hierarchical when character is not safe."""
        current_state = self.mock_state_defaults.copy()
        current_state['character_status']['safe'] = False
        
        result = self.goal_manager._select_xp_goal_hierarchical(current_state, ['hunt_monsters'])
        self.assertIsNone(result)
    
    def test_select_xp_goal_hierarchical_combat_viable(self):
        """Test _select_xp_goal_hierarchical with combat viable."""
        current_state = self.mock_state_defaults.copy()
        current_state['character_status']['safe'] = True
        current_state['character_status']['alive'] = True
        current_state['character_status']['hp_percentage'] = 50
        current_state['character_status']['cooldown_active'] = False
        current_state['character_status']['level'] = 2
        
        # Mock random to ensure deterministic result
        with patch('random.uniform', return_value=1.0):
            result = self.goal_manager._select_xp_goal_hierarchical(current_state, ['hunt_monsters'])
            self.assertIsNotNone(result)
            self.assertEqual(result[0], 'hunt_monsters')
    
    def test_select_xp_goal_hierarchical_crafting_viable(self):
        """Test _select_xp_goal_hierarchical with crafting viable."""
        current_state = self.mock_state_defaults.copy()
        current_state['character_status']['safe'] = True
        current_state['character_status']['alive'] = True
        current_state['character_status']['level'] = 3
        current_state['character_status']['cooldown_active'] = False
        current_state['equipment_status']['selected_item'] = 'wooden_sword'
        current_state['equipment_status']['upgrade_status'] = 'in_progress'  # Not completed
        
        # Mock random to ensure we select crafting goal
        with patch('random.uniform', return_value=0.5):  # Low value to select first available goal
            result = self.goal_manager._select_xp_goal_hierarchical(current_state, ['craft_selected_item'])
            self.assertIsNotNone(result)
            self.assertEqual(result[0], 'craft_selected_item')
    
    def test_select_support_goal_equipment_category(self):
        """Test _select_support_goal with equipment category."""
        current_state = self.mock_state_defaults.copy()
        current_state['equipment_status']['weapon'] = 'wooden_sword'
        
        result = self.goal_manager._select_support_goal(current_state, ['craft_selected_item'])
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'craft_selected_item')
    
    def test_select_support_goal_no_suitable_goal(self):
        """Test _select_support_goal when no suitable goal is found."""
        current_state = self.mock_state_defaults.copy()
        
        with patch.object(self.goal_manager.logger, 'warning') as mock_warning:
            result = self.goal_manager._select_support_goal(current_state, ['nonexistent_goal'])
            self.assertIsNone(result)
            mock_warning.assert_called_once()
    
    def test_is_crafting_goal_viable_low_level(self):
        """Test _is_crafting_goal_viable with low character level."""
        current_state = self.mock_state_defaults.copy()
        current_state['character_status']['level'] = 1
        
        result = self.goal_manager._is_crafting_goal_viable('craft_selected_item', current_state)
        self.assertFalse(result)
    
    def test_is_crafting_goal_viable_on_cooldown(self):
        """Test _is_crafting_goal_viable when on cooldown."""
        current_state = self.mock_state_defaults.copy()
        current_state['character_status']['level'] = 3
        current_state['character_status']['cooldown_active'] = True
        
        result = self.goal_manager._is_crafting_goal_viable('craft_selected_item', current_state)
        self.assertFalse(result)
    
    def test_is_crafting_goal_viable_craft_selected_item_no_selection(self):
        """Test _is_crafting_goal_viable for craft_selected_item with no selection."""
        current_state = self.mock_state_defaults.copy()
        current_state['character_status']['level'] = 3
        current_state['equipment_status']['selected_item'] = None
        
        result = self.goal_manager._is_crafting_goal_viable('craft_selected_item', current_state)
        self.assertFalse(result)
    
    def test_is_crafting_goal_viable_craft_selected_item_completed(self):
        """Test _is_crafting_goal_viable for craft_selected_item when completed."""
        current_state = self.mock_state_defaults.copy()
        current_state['character_status']['level'] = 3
        current_state['equipment_status']['selected_item'] = 'wooden_sword'
        current_state['equipment_status']['upgrade_status'] = 'completed'
        
        result = self.goal_manager._is_crafting_goal_viable('craft_selected_item', current_state)
        self.assertFalse(result)
    
    def test_is_crafting_goal_viable_success(self):
        """Test _is_crafting_goal_viable success case."""
        current_state = self.mock_state_defaults.copy()
        current_state['character_status']['level'] = 3
        current_state['character_status']['cooldown_active'] = False
        
        result = self.goal_manager._is_crafting_goal_viable('upgrade_weapon', current_state)
        self.assertTrue(result)
    
    def test_is_combat_viable_low_hp(self):
        """Test _is_combat_viable with low HP."""
        current_state = self.mock_state_defaults.copy()
        current_state['character_status']['hp_percentage'] = 10
        
        result = self.goal_manager._is_combat_viable(current_state)
        self.assertFalse(result)
    
    def test_is_combat_viable_on_cooldown(self):
        """Test _is_combat_viable when on cooldown."""
        current_state = self.mock_state_defaults.copy()
        current_state['character_status']['cooldown_active'] = True
        
        result = self.goal_manager._is_combat_viable(current_state)
        self.assertFalse(result)
    
    def test_is_combat_viable_low_win_rate(self):
        """Test _is_combat_viable with low win rate."""
        current_state = self.mock_state_defaults.copy()
        current_state['combat_context'] = {'recent_win_rate': 0.1}
        
        result = self.goal_manager._is_combat_viable(current_state)
        self.assertFalse(result)
    
    def test_is_combat_viable_success(self):
        """Test _is_combat_viable success case."""
        current_state = self.mock_state_defaults.copy()
        current_state['character_status']['hp_percentage'] = 80
        current_state['character_status']['cooldown_active'] = False
        current_state['character_status']['level'] = 5
        
        result = self.goal_manager._is_combat_viable(current_state)
        self.assertTrue(result)
    
    def test_check_goal_condition_simple_equality(self):
        """Test _check_goal_condition with simple equality."""
        condition = {'character_status': {'level': 5}}
        state = {'character_status': {'level': 5}}
        
        result = self.goal_manager._check_goal_condition(condition, state)
        self.assertTrue(result)
    
    def test_check_goal_condition_inequality(self):
        """Test _check_goal_condition with inequality."""
        condition = {'character_status': {'level': 3}}
        state = {'character_status': {'level': 5}}
        
        result = self.goal_manager._check_goal_condition(condition, state)
        self.assertFalse(result)
    
    def test_check_goal_condition_comparison_operators(self):
        """Test _check_goal_condition with comparison operators."""
        condition = {'character_status': {'hp_percentage': '>=50'}}
        state = {'character_status': {'hp_percentage': 75}}
        
        result = self.goal_manager._check_goal_condition(condition, state)
        self.assertTrue(result)
        
        # Test less than
        condition = {'character_status': {'hp_percentage': '<50'}}
        result = self.goal_manager._check_goal_condition(condition, state)
        self.assertFalse(result)
        
        # Test greater than
        condition = {'character_status': {'hp_percentage': '>50'}}
        result = self.goal_manager._check_goal_condition(condition, state)
        self.assertTrue(result)
        
        # Test less than or equal
        condition = {'character_status': {'hp_percentage': '<=75'}}
        result = self.goal_manager._check_goal_condition(condition, state)
        self.assertTrue(result)
    
    def test_check_goal_condition_null_checks(self):
        """Test _check_goal_condition with null checks."""
        condition = {'equipment_status': {'weapon': '!null'}}
        state = {'equipment_status': {'weapon': 'wooden_sword'}}
        
        result = self.goal_manager._check_goal_condition(condition, state)
        self.assertTrue(result)
        
        # Test null condition
        condition = {'equipment_status': {'shield': 'null'}}
        state = {'equipment_status': {'shield': None}}
        
        result = self.goal_manager._check_goal_condition(condition, state)
        self.assertTrue(result)
    
    def test_check_goal_condition_nested_dict(self):
        """Test _check_goal_condition with nested dictionary conditions."""
        condition = {'skills': {'weaponcrafting': {'level': '>=2'}}}
        state = {'skills': {'weaponcrafting': {'level': 3}}}
        
        result = self.goal_manager._check_goal_condition(condition, state)
        self.assertTrue(result)
    
    def test_check_goal_condition_exception_handling(self):
        """Test _check_goal_condition with exception handling."""
        condition = {'invalid_path': {'nonexistent': 'value'}}
        state = {}
        
        with patch.object(self.goal_manager.logger, 'warning') as mock_warning:
            result = self.goal_manager._check_goal_condition(condition, state)
            self.assertFalse(result)
    
    def test_get_nested_value_simple(self):
        """Test _get_nested_value with simple key."""
        data = {'character_status': {'level': 5}}
        result = self.goal_manager._get_nested_value(data, 'character_status')
        self.assertEqual(result, {'level': 5})
    
    def test_get_nested_value_nested(self):
        """Test _get_nested_value with nested key."""
        data = {'character_status': {'level': 5}}
        result = self.goal_manager._get_nested_value(data, 'character_status.level')
        self.assertEqual(result, 5)
    
    def test_get_nested_value_missing_key(self):
        """Test _get_nested_value with missing key."""
        data = {'character_status': {'level': 5}}
        result = self.goal_manager._get_nested_value(data, 'character_status.missing')
        self.assertIsNone(result)
    
    def test_get_nested_value_non_dict(self):
        """Test _get_nested_value when encountering non-dict value."""
        data = {'character_status': 'not_a_dict'}
        result = self.goal_manager._get_nested_value(data, 'character_status.level')
        self.assertIsNone(result)
    
    def test_apply_state_mappings_to_selection_state(self):
        """Test _apply_state_mappings_to_selection_state."""
        state = {
            'character_status': {'hp_percentage': 40, 'xp_percentage': 95},
            'equipment_status': {'weapon': 'wooden_sword'},
            'skills': {'weaponcrafting': {'level': 6}}
        }
        parameters = {'target_level': 5}
        
        result = self.goal_manager._apply_state_mappings_to_selection_state(state, parameters)
        
        # Should add computed flags
        self.assertIn('needs_healing', result['character_status'])
        self.assertTrue(result['character_status']['needs_healing'])  # hp < 50
        self.assertTrue(result['character_status']['can_level_up'])   # xp >= 90
        self.assertTrue(result['equipment_status']['has_weapon'])     # weapon != null
        self.assertTrue(result['skills']['meets_target_level'])       # level >= target_level
    
    def test_apply_state_mappings_to_selection_state_missing_parameter(self):
        """Test _apply_state_mappings_to_selection_state with missing parameter."""
        state = {'skills': {'weaponcrafting': {'level': 3}}}
        
        # No target_level parameter provided
        result = self.goal_manager._apply_state_mappings_to_selection_state(state, {})
        
        # Should skip mappings that require missing parameters
        self.assertNotIn('meets_target_level', result.get('skills', {}))
    
    def test_evaluate_condition_less_than(self):
        """Test _evaluate_condition with less than operator."""
        result = self.goal_manager._evaluate_condition(30, '< 50')
        self.assertTrue(result)
        
        result = self.goal_manager._evaluate_condition(60, '< 50')
        self.assertFalse(result)
    
    def test_evaluate_condition_greater_than(self):
        """Test _evaluate_condition with greater than operator."""
        result = self.goal_manager._evaluate_condition(60, '> 50')
        self.assertTrue(result)
        
        result = self.goal_manager._evaluate_condition(30, '> 50')
        self.assertFalse(result)
    
    def test_evaluate_condition_equals(self):
        """Test _evaluate_condition with equals operator."""
        result = self.goal_manager._evaluate_condition(50, '== 50')
        self.assertTrue(result)
        
        result = self.goal_manager._evaluate_condition(True, '== true')
        self.assertTrue(result)
        
        result = self.goal_manager._evaluate_condition(False, '== false')
        self.assertTrue(result)
        
        result = self.goal_manager._evaluate_condition(None, '== null')
        self.assertTrue(result)
    
    def test_evaluate_condition_not_equals(self):
        """Test _evaluate_condition with not equals operator."""
        result = self.goal_manager._evaluate_condition(50, '!= 30')
        self.assertTrue(result)
        
        result = self.goal_manager._evaluate_condition(None, '!= null')
        self.assertFalse(result)
    
    def test_evaluate_condition_default_equality(self):
        """Test _evaluate_condition with default equality."""
        result = self.goal_manager._evaluate_condition(50, '50')
        self.assertTrue(result)
        
        result = self.goal_manager._evaluate_condition('test', 'test')
        self.assertTrue(result)
    
    def test_generate_goal_state(self):
        """Test generate_goal_state method."""
        goal_config = {
            'target_state': {'character_status': {'level': '>5'}},
            'parameters': {'max_attempts': 3}
        }
        current_state = self.mock_state_defaults.copy()
        
        result = self.goal_manager.generate_goal_state(
            'test_goal', goal_config, current_state, extra_param='value'
        )
        
        self.assertIn('character_status', result)
    
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
        self.assertEqual(result['max_iterations'], 10)  # From thresholds
        self.assertEqual(result['hunt_radius'], 15)     # From goal config
        self.assertTrue(result['safety_priority'])      # Default
        self.assertTrue(result['custom_setting'])       # From goal config
    
    def test_get_threshold(self):
        """Test get_threshold method."""
        result = self.goal_manager.get_threshold('max_goap_iterations')
        self.assertEqual(result, 10)
        
        result = self.goal_manager.get_threshold('nonexistent', 'default_value')
        self.assertEqual(result, 'default_value')
    
    def test_reload_configuration(self):
        """Test reload_configuration method."""
        with patch.object(self.goal_manager.config_data, 'load') as mock_load:
            with patch.object(self.goal_manager, '_load_configuration') as mock_load_config:
                with patch.object(self.goal_manager.logger, 'info') as mock_info:
                    self.goal_manager.reload_configuration()
                    
                    mock_load.assert_called_once()
                    mock_load_config.assert_called_once()
                    mock_info.assert_called_once()


if __name__ == '__main__':
    unittest.main()