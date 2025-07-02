"""Comprehensive tests for StateCalculationEngine."""

import os
import tempfile
import unittest
from unittest.mock import patch

from src.controller.state_engine import StateCalculationEngine


class TestStateCalculationEngine(unittest.TestCase):
    """Test cases for StateCalculationEngine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test configuration
        self.test_config = {
            'state_calculation': {
                'has_enough_hp': 'character_hp > 50',
                'is_high_level': 'character_level >= 10',
                'needs_rest': 'character_hp < 20',
                'combat_ready': 'has_enough_hp and character_level >= 5',
                'complex_condition': {
                    'formula': 'character_level > 5 and character_hp >= 30'
                }
            },
            'computed_states': {},
            'response_handlers': {
                'low_hp_response': {
                    'condition': 'character_hp < 20',
                    'action': 'rest',
                    'priority': 'high'
                }
            },
            'world_state_updates': {
                'character_alive': {
                    'condition': 'character_hp > 0',
                    'default': True
                }
            }
        }
        
        # Write test config to file
        import yaml
        config_file = os.path.join(self.temp_dir, 'state_engine.yaml')
        with open(config_file, 'w') as f:
            yaml.dump(self.test_config, f)
        
        # Create engine with test config
        with patch('src.game.globals.CONFIG_PREFIX', self.temp_dir):
            self.engine = StateCalculationEngine()
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test engine initialization."""
        self.assertIsNotNone(self.engine.state_rules)
        self.assertIsNotNone(self.engine.response_rules)
        self.assertIsNotNone(self.engine.update_rules)
        self.assertIsNotNone(self.engine.computed_states)
        self.assertIsNotNone(self.engine.response_handlers)
    
    def test_state_engine_methods_exist(self):
        """Test that expected methods exist on state engine."""
        # Test that essential methods exist
        self.assertTrue(hasattr(self.engine, 'calculate_derived_state'))
        self.assertTrue(hasattr(self.engine, 'reload_configuration'))
        self.assertTrue(hasattr(self.engine, 'register_response_handler'))
        self.assertTrue(hasattr(self.engine, '_load_configuration'))
        
        # Test that these are callable
        self.assertTrue(callable(self.engine.calculate_derived_state))
        self.assertTrue(callable(self.engine.reload_configuration))
    
    def test_calculate_derived_state_simple_formula(self):
        """Test calculation of derived state with simple formulas."""
        base_state = {
            'character_status.hp': 60,
            'character_status.level': 8,
            'character_status.hp_percentage': 75,
            'character_status.xp_percentage': 50,
            'character_status.cooldown_active': False
        }
        
        thresholds = {
            'safe_hp_percentage': 80,
            'rest_hp_percentage': 20,
            'attack_hp_percentage': 30
        }
        
        result = self.engine.calculate_derived_state(base_state, thresholds)
        
        # Test some actual state rules from the real config (consolidated format)
        self.assertFalse(result['character_status.safe'])  # 75 < 80
        self.assertFalse(result['character_status.needs_rest'])  # 75 > 20
        self.assertTrue(result['action_capabilities.can_attack'])  # 75 >= 30 and not on cooldown
    
    def test_calculate_derived_state_with_thresholds(self):
        """Test calculation with threshold substitution."""
        base_state = {
            'character_status.hp': 40,
            'character_status.level': 12,
            'character_status.hp_percentage': 95,
            'character_status.xp_percentage': 80,
            'character_status.cooldown_active': True
        }
        
        thresholds = {
            'safe_hp_percentage': 90,
            'attack_hp_percentage': 50
        }
        
        result = self.engine.calculate_derived_state(base_state, thresholds)
        
        # Test threshold substitution (consolidated format)
        self.assertTrue(result['character_status.safe'])  # 95 >= 90
        self.assertFalse(result['action_capabilities.can_attack'])  # On cooldown should prevent attack
    
    def test_evaluate_formula_with_boolean_logic(self):
        """Test formula evaluation with AND/OR logic."""
        state = {'character_hp': 60, 'character_level': 8, 'has_weapon': True}
        
        # Test AND logic
        result = self.engine._evaluate_formula('character_hp > 50 and character_level >= 5', state, {})
        self.assertTrue(result)
        
        result = self.engine._evaluate_formula('character_hp > 50 and character_level >= 10', state, {})
        self.assertFalse(result)
        
        # Test OR logic
        result = self.engine._evaluate_formula('character_hp < 30 or character_level >= 5', state, {})
        self.assertTrue(result)
        
        result = self.engine._evaluate_formula('character_hp < 30 or character_level < 5', state, {})
        self.assertFalse(result)
    
    def test_evaluate_simple_expression_comparisons(self):
        """Test simple expression evaluation with various comparison operators."""
        state = {'value': 10, 'other': 5}
        
        # Test all comparison operators
        self.assertTrue(self.engine._evaluate_simple_expression('value > 5', state))
        self.assertFalse(self.engine._evaluate_simple_expression('value > 15', state))
        
        self.assertTrue(self.engine._evaluate_simple_expression('value >= 10', state))
        self.assertFalse(self.engine._evaluate_simple_expression('value >= 15', state))
        
        self.assertTrue(self.engine._evaluate_simple_expression('value < 15', state))
        self.assertFalse(self.engine._evaluate_simple_expression('value < 5', state))
        
        self.assertTrue(self.engine._evaluate_simple_expression('value <= 10', state))
        self.assertFalse(self.engine._evaluate_simple_expression('value <= 5', state))
        
        self.assertTrue(self.engine._evaluate_simple_expression('value == 10', state))
        self.assertFalse(self.engine._evaluate_simple_expression('value == 5', state))
        
        self.assertTrue(self.engine._evaluate_simple_expression('value != 5', state))
        self.assertFalse(self.engine._evaluate_simple_expression('value != 10', state))
    
    def test_evaluate_simple_expression_negation(self):
        """Test expression evaluation with negation."""
        state = {'value': 10, 'flag': True}
        
        result = self.engine._evaluate_simple_expression('not value > 15', state)
        self.assertTrue(result)
        
        result = self.engine._evaluate_simple_expression('not value > 5', state)
        self.assertFalse(result)
    
    def test_resolve_value_types(self):
        """Test value resolution for different types."""
        state = {'num_value': 42, 'str_value': 'test', 'bool_value': True}
        
        # Test integer
        self.assertEqual(self.engine._resolve_value('42', state), 42)
        
        # Test float
        self.assertEqual(self.engine._resolve_value('3.14', state), 3.14)
        
        # Test boolean
        self.assertEqual(self.engine._resolve_value('true', state), True)
        self.assertEqual(self.engine._resolve_value('false', state), False)
        
        # Test string
        self.assertEqual(self.engine._resolve_value('test_string', state), 'test_string')
        
        # Test state reference
        self.assertEqual(self.engine._resolve_value('num_value', state), 42)
        self.assertEqual(self.engine._resolve_value('bool_value', state), True)
    
    
    def test_error_handling_in_state_calculation(self):
        """Test error handling during state calculation."""
        # Test with invalid state that should trigger errors
        base_state = {
            'character_hp': 50,
            'character_level': 'invalid_level',  # String instead of int
            'hp_percentage': None,  # None value
        }
        
        thresholds = {}
        
        # Should not crash and should set safe defaults
        result = self.engine.calculate_derived_state(base_state, thresholds)
        
        # Should still return a dict with some state values
        self.assertIsInstance(result, dict)
    
    
    def test_reload_configuration(self):
        """Test configuration reloading."""
        # Count initial rules
        initial_rule_count = len(self.engine.state_rules)
        
        # Reload should work without errors
        self.engine.reload_configuration()
        
        # Should still have rules (may be the same or different)
        self.assertIsInstance(self.engine.state_rules, dict)


class TestStateEngineHelperMethods(unittest.TestCase):
    """Test helper methods of StateCalculationEngine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Minimal config for testing
        self.test_config = {'state_calculation': {}}
        
        import yaml
        config_file = os.path.join(self.temp_dir, 'state_engine.yaml')
        with open(config_file, 'w') as f:
            yaml.dump(self.test_config, f)
        
        with patch('src.game.globals.CONFIG_PREFIX', self.temp_dir):
            self.engine = StateCalculationEngine()
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_register_response_handler(self):
        """Test response handler registration."""
        def test_handler(response_data, context):
            return f"handled: {response_data}"
        
        self.engine.register_response_handler('test_action', test_handler)
        
        self.assertIn('test_action', self.engine.response_handlers)
        self.assertEqual(self.engine.response_handlers['test_action'], test_handler)
    


if __name__ == '__main__':
    unittest.main()