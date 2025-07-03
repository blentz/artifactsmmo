"""
Tests for Equipment Slot Selection Action Chain

Tests the complete action chain:
AnalyzeEquipmentGapsAction → SelectOptimalSlotAction → EvaluateRecipesAction
"""

import tempfile
import unittest
from unittest.mock import Mock, patch

from src.controller.actions.analyze_equipment_gaps import AnalyzeEquipmentGapsAction
from src.controller.actions.evaluate_recipes import EvaluateRecipesAction
from src.controller.actions.select_optimal_slot import SelectOptimalSlotAction
from src.game.character.state import CharacterState
from src.game.map.state import MapState
from src.lib.action_context import ActionContext


class TestEquipmentSlotSelection(unittest.TestCase):
    """Test suite for equipment slot selection action chain"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create action instances
        self.analyze_action = AnalyzeEquipmentGapsAction()
        self.select_action = SelectOptimalSlotAction()
        self.evaluate_action = EvaluateRecipesAction()
        
        # Create mock states
        self.character_state = Mock(spec=CharacterState)
        self.map_state = Mock(spec=MapState)
        self.action_context = ActionContext()
        self.action_context.character_state = self.character_state
        self.action_context.map_state = self.map_state
        self.mock_client = Mock()
        
        # Mock character data with mixed equipment
        self.character_state.data = {
            'level': 5,
            'weapon_slot': 'wooden_stick',
            'body_armor_slot': 'leather_armor',
            # Missing helmet (should have high urgency)
            'inventory': [
                {'code': 'ash_wood', 'quantity': 10},
                {'code': 'copper_ore', 'quantity': 8},
                {'code': 'iron_ore', 'quantity': 5}
            ],
            'skills': {
                'weaponcrafting': 4,
                'gearcrafting': 5,  # Increase to handle level 4+ recipes
                'jewelrycrafting': 2
            }
        }
        
        # Set equipment status in world state
        self.action_context.set_result('equipment_status', {
            'weapon': 'wooden_stick',
            'body_armor': 'leather_armor'
            # helmet is missing
        })
        
    def test_complete_action_chain_weaponcrafting(self):
        """Test complete chain for weaponcrafting skill XP"""
        # Set target skill
        self.action_context.set_parameter('target_craft_skill', 'weaponcrafting')
        
        # Step 1: Analyze equipment gaps
        with patch('src.lib.yaml_data.YamlData') as mock_yaml:
            mock_yaml.return_value.data = self._get_test_config()
            
            result1 = self.analyze_action.execute(self.mock_client, self.action_context)
            self.assertTrue(result1['success'])
            
            # Verify gap analysis is available
            gap_analysis = self.action_context.get_parameter('equipment_gap_analysis')
            self.assertIsNotNone(gap_analysis)
            self.assertIn('weapon', gap_analysis)
            self.assertIn('helmet', gap_analysis)
            
            # Step 2: Select optimal slot
            result2 = self.select_action.execute(self.mock_client, self.action_context)
            self.assertTrue(result2['success'])
            
            # Should select a weaponcrafting slot (weapon or shield)
            selected_slot = self.action_context.get_parameter('target_equipment_slot')
            weaponcrafting_slots = ['weapon', 'shield']
            self.assertIn(selected_slot, weaponcrafting_slots)
            
            # Step 3: Evaluate recipes for selected slot
            # Create recipes for both possible weaponcrafting slots
            mock_response = Mock()
            mock_response.data = [
                self._create_mock_item('iron_sword', 5, 'weaponcrafting',
                                     [{'code': 'iron_ore', 'quantity': 3}],
                                     {'attack_fire': 35}, 'weapon'),
                self._create_mock_item('iron_shield', 4, 'weaponcrafting',
                                     [{'code': 'iron_ore', 'quantity': 2}],
                                     {'res_fire': 20, 'hp': 30}, 'shield')
            ]
            
            with patch('artifactsmmo_api_client.api.items.get_all_items_items_get.sync') as mock_get_items:
                mock_get_items.return_value = mock_response
                
                result3 = self.evaluate_action.execute(self.mock_client, self.action_context)
                if not result3['success']:
                    print(f"Recipe evaluation failed: {result3.get('error', 'Unknown error')}")
                self.assertTrue(result3['success'])
                
                # Verify recipe selection - should select appropriate item for the chosen slot
                selected_item = self.action_context.get_parameter('selected_item_code')
                selected_slot = self.action_context.get_parameter('target_equipment_slot')
                
                if selected_slot == 'weapon':
                    self.assertEqual(selected_item, 'iron_sword')
                elif selected_slot == 'shield':
                    self.assertEqual(selected_item, 'iron_shield')
                else:
                    self.fail(f"Unexpected slot selected: {selected_slot}")
                
    def test_complete_action_chain_gearcrafting(self):
        """Test complete chain for gearcrafting skill XP"""
        # Set target skill
        self.action_context.set_parameter('target_craft_skill', 'gearcrafting')
        
        # Step 1: Analyze equipment gaps
        with patch('src.lib.yaml_data.YamlData') as mock_yaml:
            mock_yaml.return_value.data = self._get_test_config()
            
            result1 = self.analyze_action.execute(self.mock_client, self.action_context)
            self.assertTrue(result1['success'])
            
            # Step 2: Select optimal slot
            result2 = self.select_action.execute(self.mock_client, self.action_context)
            self.assertTrue(result2['success'])
            
            # Should select helmet (missing equipment = 100 urgency)
            selected_slot = self.action_context.get_parameter('target_equipment_slot')
            self.assertEqual(selected_slot, 'helmet')
            
            # Step 3: Evaluate recipes for selected slot
            # Create recipes for gearcrafting slots
            mock_response = Mock()
            mock_response.data = [
                self._create_mock_item('iron_helmet', 4, 'gearcrafting',
                                     [{'code': 'iron_ore', 'quantity': 4}],
                                     {'hp': 40, 'res_fire': 15}, 'helmet'),
                self._create_mock_item('iron_armor', 5, 'gearcrafting',
                                     [{'code': 'iron_ore', 'quantity': 6}],
                                     {'hp': 60, 'res_fire': 25}, 'body_armor'),
                self._create_mock_item('iron_boots', 3, 'gearcrafting',
                                     [{'code': 'iron_ore', 'quantity': 3}],
                                     {'hp': 25, 'res_fire': 10}, 'boots')
            ]
            
            with patch('artifactsmmo_api_client.api.items.get_all_items_items_get.sync') as mock_get_items:
                mock_get_items.return_value = mock_response
                
                result3 = self.evaluate_action.execute(self.mock_client, self.action_context)
                self.assertTrue(result3['success'])
                
                # Verify recipe selection matches the selected slot
                selected_item = self.action_context.get_parameter('selected_item_code')
                selected_slot = self.action_context.get_parameter('target_equipment_slot')
                
                # Should select appropriate item for the chosen gearcrafting slot
                valid_items = ['iron_helmet', 'iron_armor', 'iron_boots']
                self.assertIn(selected_item, valid_items)
                
    def test_slot_prioritization_missing_vs_outdated(self):
        """Test that missing equipment gets higher priority than outdated equipment"""
        self.action_context.set_parameter('target_craft_skill', 'gearcrafting')
        
        with patch('src.lib.yaml_data.YamlData') as mock_yaml:
            mock_yaml.return_value.data = self._get_test_config()
            
            # Analyze equipment
            result1 = self.analyze_action.execute(self.mock_client, self.action_context)
            self.assertTrue(result1['success'])
            
            gap_analysis = self.action_context.get_parameter('equipment_gap_analysis')
            
            # Missing helmet should have higher urgency than existing body_armor
            helmet_urgency = gap_analysis['helmet']['urgency_score']
            body_armor_urgency = gap_analysis['body_armor']['urgency_score']
            
            self.assertGreater(helmet_urgency, body_armor_urgency)
            self.assertTrue(gap_analysis['helmet']['missing'])
            self.assertFalse(gap_analysis['body_armor']['missing'])
            
    def test_skill_slot_compatibility_validation(self):
        """Test that slot selection respects skill-slot mappings"""
        self.action_context.set_parameter('target_craft_skill', 'jewelrycrafting')
        
        with patch('src.lib.yaml_data.YamlData') as mock_yaml:
            mock_yaml.return_value.data = self._get_test_config()
            
            # Analyze and select
            self.analyze_action.execute(self.mock_client, self.action_context)
            result = self.select_action.execute(self.mock_client, self.action_context)
            
            self.assertTrue(result['success'])
            
            # Should only select from jewelry slots
            selected_slot = self.action_context.get_parameter('target_equipment_slot')
            jewelry_slots = ['amulet', 'ring1', 'ring2']
            self.assertIn(selected_slot, jewelry_slots)
            
    def test_equipment_gap_scoring(self):
        """Test equipment gap scoring logic"""
        with patch('src.lib.yaml_data.YamlData') as mock_yaml:
            mock_yaml.return_value.data = self._get_test_config()
            
            result = self.analyze_action.execute(self.mock_client, self.action_context)
            self.assertTrue(result['success'])
            
            gap_analysis = self.action_context.get_parameter('equipment_gap_analysis')
            
            # Weapon (level 1 vs char level 5) should have high urgency
            weapon_data = gap_analysis['weapon']
            self.assertEqual(weapon_data['level_difference'], 4)  # 5 - 1
            self.assertGreater(weapon_data['urgency_score'], 50)
            
            # Missing helmet should have maximum urgency
            helmet_data = gap_analysis['helmet']
            self.assertTrue(helmet_data['missing'])
            self.assertEqual(helmet_data['urgency_score'], 100)
            
    def test_error_handling_missing_dependencies(self):
        """Test error handling when action dependencies are missing"""
        # Try to select slot without gap analysis (now checked first)
        result = self.select_action.execute(self.mock_client, self.action_context)
        self.assertFalse(result['success'])
        self.assertIn('Equipment gap analysis not available', result['error'])
        
        # Try to select slot with gap analysis but no target skill (should work with fallback)
        self.action_context.set_parameter('equipment_gap_analysis', {'weapon': {'urgency_score': 50, 'missing': False}})
        with patch('src.lib.yaml_data.YamlData') as mock_yaml:
            # Provide test config for the action
            mock_yaml.return_value.data = {
                'slot_priorities': {'weapon': 100},
                'skill_slot_mappings': {'weaponcrafting': ['weapon']}
            }
            result = self.select_action.execute(self.mock_client, self.action_context)
            self.assertTrue(result['success'])  # Should succeed with fallback skill
        
        # Try to evaluate recipes without target slot (clear the slot set by previous action)
        self.action_context.set_parameter('target_equipment_slot', None)
        if 'target_equipment_slot' in self.action_context.action_results:
            del self.action_context.action_results['target_equipment_slot']
        result = self.evaluate_action.execute(self.mock_client, self.action_context)
        self.assertFalse(result['success'])
        self.assertIn('No target equipment slot specified', result['error'])
        
    def test_config_fallback_handling(self):
        """Test that actions handle config loading failures gracefully"""
        with patch('src.lib.yaml_data.YamlData', side_effect=Exception("Config load failed")):
            # Should use fallback configuration
            result = self.analyze_action.execute(self.mock_client, self.action_context)
            self.assertTrue(result['success'])  # Should still work with fallbacks
            
    def _get_test_config(self):
        """Get test configuration data"""
        return {
            'all_equipment_slots': ['weapon', 'shield', 'helmet', 'body_armor', 'leg_armor', 'boots', 'amulet', 'ring1', 'ring2'],
            'slot_priorities': {
                'weapon': 100,
                'shield': 90,
                'body_armor': 85,
                'helmet': 80,
                'leg_armor': 75,
                'boots': 70,
                'amulet': 60,
                'ring1': 50,
                'ring2': 50
            },
            'skill_slot_mappings': {
                'weaponcrafting': ['weapon', 'shield'],
                'gearcrafting': ['helmet', 'body_armor', 'leg_armor', 'boots'],
                'jewelrycrafting': ['amulet', 'ring1', 'ring2']
            },
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
        
    def _create_mock_item(self, item_code: str, item_level: int, craft_skill: str, 
                         required_items: list, effects: dict, item_slot: str = None):
        """Helper method to create mock item with craft information"""
        # Infer slot from item name if not provided
        if item_slot is None:
            if 'sword' in item_code or 'staff' in item_code or 'stick' in item_code:
                item_slot = 'weapon'
            elif 'shield' in item_code:
                item_slot = 'shield'
            elif 'helmet' in item_code:
                item_slot = 'helmet'
            elif 'armor' in item_code:
                item_slot = 'body_armor'
            elif 'boots' in item_code:
                item_slot = 'boots'
            else:
                item_slot = 'weapon'  # Default fallback
        
        mock_item = Mock()
        mock_item.code = item_code
        mock_item.to_dict.return_value = {
            'code': item_code,
            'level': item_level,
            'slot': item_slot,
            'effects': effects
        }
        
        # Mock craft information
        mock_craft = Mock()
        mock_craft.level = item_level
        mock_craft.skill = craft_skill
        mock_craft.items = []
        
        for req_item in required_items:
            mock_craft_item = Mock()
            mock_craft_item.code = req_item['code']
            mock_craft_item.quantity = req_item['quantity']
            mock_craft.items.append(mock_craft_item)
            
        mock_item.craft = mock_craft
        
        return mock_item


if __name__ == '__main__':
    unittest.main()