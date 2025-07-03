"""
Tests for AnalyzeEquipmentGapsAction
"""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.analyze_equipment_gaps import AnalyzeEquipmentGapsAction
from src.game.character.state import CharacterState
from src.lib.action_context import ActionContext


class TestAnalyzeEquipmentGapsAction(unittest.TestCase):
    """Test suite for AnalyzeEquipmentGapsAction"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.action = AnalyzeEquipmentGapsAction()
        self.character_state = Mock(spec=CharacterState)
        self.action_context = ActionContext()
        self.action_context.character_state = self.character_state
        self.mock_client = Mock()
        
    def test_analyze_mixed_equipment_state(self):
        """Test analysis with mixed equipment (some missing, some outdated)"""
        self.character_state.data = {
            'level': 5,
            'weapon_slot': 'wooden_stick',
            'body_armor_slot': 'leather_armor'
            # helmet, leg_armor, boots missing
        }
        
        # Mock world state equipment via context
        # The action will access this via context.get('equipment_status')
        self.action_context.set_result('equipment_status', {
            'weapon': 'wooden_stick',
            'body_armor': 'leather_armor'
        })
        
        with patch('src.lib.yaml_data.YamlData') as mock_yaml:
            mock_yaml.return_value.data = self._get_test_config()
            
            result = self.action.execute(self.mock_client, self.action_context)
            
            self.assertTrue(result['success'])
            self.assertGreater(result['slots_analyzed'], 0)
            
            gap_analysis = self.action_context.get_parameter('equipment_gap_analysis')
            self.assertIsNotNone(gap_analysis)
            
            # Check weapon analysis
            weapon_data = gap_analysis['weapon']
            # With simplified implementation, weapon is detected
            self.assertFalse(weapon_data['missing'])
            
            # Check missing helmet
            helmet_data = gap_analysis['helmet']
            self.assertTrue(helmet_data['missing'])
            self.assertEqual(helmet_data['urgency_score'], 100)
            
            # Check body armor
            armor_data = gap_analysis['body_armor']
            self.assertFalse(armor_data['missing'])
            
    def test_analyze_no_equipment(self):
        """Test analysis with completely empty equipment"""
        self.character_state.data = {
            'level': 3
            # No equipment slots filled
        }
        
        # No equipment in world state
        self.action_context.set_result('equipment_status', {})
        
        with patch('src.lib.yaml_data.YamlData') as mock_yaml:
            mock_yaml.return_value.data = self._get_test_config()
            
            result = self.action.execute(self.mock_client, self.action_context)
            
            self.assertTrue(result['success'])
            
            gap_analysis = self.action_context.get_parameter('equipment_gap_analysis')
            
            # All slots should be missing with max urgency
            for slot_name, slot_data in gap_analysis.items():
                self.assertTrue(slot_data['missing'])
                self.assertEqual(slot_data['urgency_score'], 100)
                self.assertEqual(slot_data['reason'], 'empty_slot')
                
    def test_analyze_over_leveled_equipment(self):
        """Test analysis with equipment above character level"""
        self.character_state.data = {
            'level': 3,
            'weapon_slot': 'magic_sword'
        }
        
        # Mock world state equipment
        self.action_context.set_result('equipment_status', {
            'weapon': 'magic_sword'
        })
        
        with patch('src.lib.yaml_data.YamlData') as mock_yaml:
            mock_yaml.return_value.data = self._get_test_config()
            
            result = self.action.execute(self.mock_client, self.action_context)
            
            self.assertTrue(result['success'])
            
            gap_analysis = self.action_context.get_parameter('equipment_gap_analysis')
            weapon_data = gap_analysis['weapon']
            
            self.assertFalse(weapon_data['missing'])
            
    def test_stat_modifier_calculation(self):
        """Test that stat modifiers affect urgency scores"""
        # Test weapon with good stats vs no stats
        self.character_state.data = {
            'level': 5,
            'weapon_slot': 'basic_sword',
            'body_armor_slot': 'iron_armor'
        }
        
        # Mock world state equipment
        self.action_context.set_result('equipment_status', {
            'weapon': 'basic_sword',
            'body_armor': 'iron_armor'
        })
        
        with patch('src.lib.yaml_data.YamlData') as mock_yaml:
            mock_yaml.return_value.data = self._get_test_config()
            
            result = self.action.execute(self.mock_client, self.action_context)
            
            self.assertTrue(result['success'])
            
            gap_analysis = self.action_context.get_parameter('equipment_gap_analysis')
            
            # Weapon with no effects should have stat modifier penalty
            weapon_data = gap_analysis['weapon']
            self.assertGreater(weapon_data.get('stat_modifier', 0), 0)
            
            # Armor with good stats should have better score
            armor_data = gap_analysis['body_armor']
            self.assertLessEqual(armor_data.get('stat_modifier', 0), weapon_data.get('stat_modifier', 0))
            
    def test_error_handling_no_character_state(self):
        """Test error handling when character state is missing"""
        self.action_context.character_state = None
        
        result = self.action.execute(self.mock_client, self.action_context)
        
        self.assertFalse(result['success'])
        self.assertIn('No character state available', result['error'])
        
    def test_config_loading_fallback(self):
        """Test fallback behavior when config loading fails"""
        self.character_state.data = {
            'level': 2
        }
        
        # No equipment in world state
        self.action_context.set_result('equipment_status', {})
        
        with patch('src.lib.yaml_data.YamlData', side_effect=Exception("Config error")):
            result = self.action.execute(self.mock_client, self.action_context)
            
            # Should still work with fallback config
            self.assertTrue(result['success'])
            
            gap_analysis = self.action_context.get_parameter('equipment_gap_analysis')
            self.assertIsNotNone(gap_analysis)
            
    def test_ring_equipment_handling(self):
        """Test special handling for ring equipment slots"""
        self.character_state.data = {
            'level': 4,
            'ring1_slot': 'silver_ring'
        }
        
        # Mock world state equipment
        self.action_context.set_result('equipment_status', {
            'ring1': 'silver_ring'
        })
        
        with patch('src.lib.yaml_data.YamlData') as mock_yaml:
            mock_yaml.return_value.data = self._get_test_config()
            
            result = self.action.execute(self.mock_client, self.action_context)
            
            self.assertTrue(result['success'])
            
            gap_analysis = self.action_context.get_parameter('equipment_gap_analysis')
            
            # ring1 should show as equipped, ring2 as missing
            ring1_data = gap_analysis['ring1']
            ring2_data = gap_analysis['ring2']
            
            self.assertFalse(ring1_data['missing'])
            self.assertTrue(ring2_data['missing'])
            
    def _get_test_config(self):
        """Get test configuration data"""
        return {
            'all_equipment_slots': ['weapon', 'helmet', 'body_armor', 'leg_armor', 'boots', 'amulet', 'ring1', 'ring2'],
            'gap_analysis': {
                'level_penalties': {
                    'missing_item': 100,
                    'level_behind_1': 20,
                    'level_behind_2': 40,
                    'level_behind_3': 60,
                    'level_ahead': -10
                },
                'stat_weights': {
                    'weapon': {'attack_fire': 3.0, 'attack_earth': 3.0},
                    'armor': {'hp': 3.0, 'res_fire': 2.0},
                    'accessory': {'critical_strike': 3.0, 'wisdom': 2.5}
                }
            }
        }


if __name__ == '__main__':
    unittest.main()