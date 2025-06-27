"""
Test smart combat decision-making system.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

from src.controller.actions.attack import AttackAction
from src.controller.actions.find_monsters import FindMonstersAction
from src.controller.state_engine import StateCalculationEngine
from src.controller.knowledge.base import KnowledgeBase


class TestSmartCombatDecisions(unittest.TestCase):
    """Test the enhanced combat decision-making system."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.knowledge_file = os.path.join(self.temp_dir, 'test_knowledge.yaml')
        
        # Mock client
        self.mock_client = Mock()
        
        # Create knowledge base with combat data
        self.knowledge_base = KnowledgeBase(filename=self.knowledge_file)
        
        # Add test combat data - green_slime with poor win rate
        self.knowledge_base.data = {
            'monsters': {
                'green_slime': {
                    'code': 'green_slime',
                    'locations': [{'x': 0, 'y': -1}],
                    'combat_results': [
                        {'result': 'loss', 'character_level': 2},
                        {'result': 'loss', 'character_level': 2},
                        {'result': 'loss', 'character_level': 2},
                        {'result': 'loss', 'character_level': 2}
                    ]
                },
                'chicken': {
                    'code': 'chicken',
                    'locations': [{'x': 0, 'y': 1}],
                    'combat_results': [
                        {'result': 'win', 'character_level': 2},
                        {'result': 'win', 'character_level': 2},
                        {'result': 'loss', 'character_level': 2}
                    ]
                }
            }
        }
        
        # Mock character state
        self.character_state = Mock()
        self.character_state.data = {
            'hp': 125,
            'max_hp': 125,
            'x': 0,
            'y': 0,
            'level': 2
        }
    
    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_attack_action_combat_viability_check(self):
        """Test that AttackAction checks combat viability and refuses poor win rate fights."""
        attack_action = AttackAction('test_char')
        
        # Position character at green_slime location (poor win rate)
        self.character_state.data['x'] = 0
        self.character_state.data['y'] = -1
        
        # Create context with knowledge base
        context = {
            'knowledge_base': self.knowledge_base,
            'map_state': Mock()
        }
        
        # Execute attack with poor win rate monster
        result = attack_action.execute(self.mock_client, character_state=self.character_state, context=context)
        
        # Should refuse to attack due to poor win rate
        self.assertFalse(result['success'])
        self.assertIn('poor_win_rate', result.get('reason', ''))
    
    def test_attack_action_allows_good_win_rate(self):
        """Test that AttackAction allows combat with good win rate monsters."""
        attack_action = AttackAction('test_char')
        
        # Position character at chicken location (good win rate)
        self.character_state.data['x'] = 0  
        self.character_state.data['y'] = 1
        
        # Mock successful API response
        mock_response = Mock()
        mock_response.data.character.hp = 100
        mock_response.data.character.max_hp = 125
        mock_response.data.character.xp = 10
        mock_response.data.fight.result = 'win'
        mock_response.data.fight.monster.code = 'chicken'
        
        with patch('src.controller.actions.attack.fight_character_api', return_value=mock_response):
            # Create context with knowledge base - chicken has good win rate
            context = {
                'knowledge_base': self.knowledge_base,
                'map_state': Mock()
            }
            
            result = attack_action.execute(self.mock_client, character_state=self.character_state, context=context)
            
            # Should allow attack with good win rate monster
            self.assertTrue(result is not None)  # Action executed
    
    def test_find_monsters_prioritizes_good_win_rates(self):
        """Test that FindMonstersAction can prioritize based on win rates."""
        find_action = FindMonstersAction(
            character_x=0, character_y=0, 
            search_radius=5
        )
        
        # Test the monster selection logic directly
        locations_found = [
            ((0, -1), 'green_slime'),  # Poor win rate
            ((0, 1), 'chicken')        # Good win rate
        ]
        
        kwargs = {'knowledge_base': self.knowledge_base}
        best_monster = find_action._select_best_monster(locations_found, kwargs)
        
        # Should select chicken over green_slime due to better win rate
        self.assertIsNotNone(best_monster)
        self.assertEqual(best_monster['monster_code'], 'chicken')
        self.assertEqual(best_monster['location'], (0, 1))
        
        # Test win rate calculation
        green_slime_win_rate = find_action._get_monster_win_rate('green_slime', self.knowledge_base)
        chicken_win_rate = find_action._get_monster_win_rate('chicken', self.knowledge_base)
        
        self.assertEqual(green_slime_win_rate, 0.0)  # 0% win rate
        self.assertAlmostEqual(chicken_win_rate, 0.67, places=2)  # ~67% win rate
    
    def test_state_engine_combat_viability_detection(self):
        """Test that StateCalculationEngine detects poor combat viability."""
        state_engine = StateCalculationEngine()
        
        # Create state with knowledge base and character location
        state = {
            'knowledge_base': self.knowledge_base,
            'character_x': 0,
            'character_y': 0,  # Near green_slime with poor win rate
            'character_level': 2
        }
        
        # Test combat viability check
        is_not_viable = state_engine._check_combat_viability({}, state, {})
        
        # Should detect that combat is not viable due to green_slime's poor win rate
        self.assertTrue(is_not_viable)
    
    def test_knowledge_base_combat_data_structure(self):
        """Test that knowledge base correctly stores and retrieves combat data."""
        # Verify green_slime has poor win rate
        green_slime_data = self.knowledge_base.data['monsters']['green_slime']
        combat_results = green_slime_data['combat_results']
        
        wins = sum(1 for result in combat_results if result['result'] == 'win')
        total_combats = len(combat_results)
        win_rate = wins / total_combats
        
        self.assertEqual(wins, 0)  # No wins
        self.assertEqual(total_combats, 4)  # 4 total combats
        self.assertEqual(win_rate, 0.0)  # 0% win rate
        
        # Verify chicken has good win rate
        chicken_data = self.knowledge_base.data['monsters']['chicken']
        chicken_results = chicken_data['combat_results']
        
        chicken_wins = sum(1 for result in chicken_results if result['result'] == 'win')
        chicken_total = len(chicken_results)
        chicken_win_rate = chicken_wins / chicken_total
        
        self.assertEqual(chicken_wins, 2)  # 2 wins
        self.assertEqual(chicken_total, 3)  # 3 total combats
        self.assertAlmostEqual(chicken_win_rate, 0.67, places=2)  # ~67% win rate
    
    def test_emergency_equipment_upgrade_goal_triggered(self):
        """Test that poor combat viability triggers emergency equipment upgrade goal."""
        # This test will be implemented when goal manager refactoring is complete
        # For now, just verify the goal template exists in configuration
        from src.lib.yaml_data import YamlData
        from src.game.globals import DATA_PREFIX
        
        config_data = YamlData(f"{DATA_PREFIX}/goal_templates.yaml")
        goal_templates = config_data.data.get('goal_templates', {})
        goal_selection_rules = config_data.data.get('goal_selection_rules', {})
        
        # Verify emergency equipment upgrade goal exists
        self.assertIn('emergency_equipment_upgrade', goal_templates)
        
        # Verify emergency rule exists with high priority
        emergency_rules = goal_selection_rules.get('emergency', [])
        emergency_equipment_rule = None
        for rule in emergency_rules:
            if rule.get('goal') == 'emergency_equipment_upgrade':
                emergency_equipment_rule = rule
                break
        
        self.assertIsNotNone(emergency_equipment_rule)
        self.assertEqual(emergency_equipment_rule['priority'], 95)


if __name__ == '__main__':
    unittest.main()