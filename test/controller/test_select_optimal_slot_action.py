"""
Tests for SelectOptimalSlotAction
"""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.select_optimal_slot import SelectOptimalSlotAction
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from test.test_base import UnifiedContextTestBase


class TestSelectOptimalSlotAction(UnifiedContextTestBase):
    """Test suite for SelectOptimalSlotAction"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        # Create a fresh action instance for each test to avoid state pollution
        self.action = SelectOptimalSlotAction()
        self.action.config = None  # Ensure config is reset
        self.mock_client = Mock()
        
        # Mock the YamlData constructor to prevent actual file loading
        self.yaml_patcher = patch('src.controller.actions.select_optimal_slot.YamlData')
        self.mock_yaml_class = self.yaml_patcher.start()
        
    def tearDown(self):
        """Clean up after each test"""
        # Stop the YamlData patch
        if hasattr(self, 'yaml_patcher'):
            self.yaml_patcher.stop()
            
        # Reset the action's cached config to prevent pollution
        if hasattr(self, 'action'):
            self.action.config = None
        
        # Clear context parameters that might pollute other tests
        if hasattr(self, 'context'):
            self.context.set(StateParameters.TARGET_CRAFT_SKILL, None)
            self.context.set(StateParameters.EQUIPMENT_GAP_ANALYSIS, None)
            self.context.set(StateParameters.TARGET_SLOT, None)
            self.context.set(StateParameters.SLOT_SELECTION_REASONING, None)
            
        super().tearDown()
        
    def test_select_highest_priority_missing_slot(self):
        """Test selection of highest priority missing equipment slot"""
        # Set up gap analysis with missing slots
        gap_analysis = {
            'weapon': {'urgency_score': 100, 'missing': True, 'reason': 'empty_slot'},
            'helmet': {'urgency_score': 100, 'missing': True, 'reason': 'empty_slot'},
            'boots': {'urgency_score': 100, 'missing': True, 'reason': 'empty_slot'}
        }
        
        self.context.set(StateParameters.EQUIPMENT_GAP_ANALYSIS, gap_analysis)
        self.context.set(StateParameters.TARGET_CRAFT_SKILL, 'gearcrafting')
        
        # Configure the mocked YamlData
        mock_yaml_instance = Mock()
        mock_yaml_instance.data = self._get_test_config()
        self.mock_yaml_class.return_value = mock_yaml_instance
        
        result = self.action.execute(self.mock_client, self.context)
        
        self.assertTrue(result.success)
        
        # Should select helmet (priority 80) over boots (priority 70)
        selected_slot = self.context.get(StateParameters.TARGET_SLOT)
        self.assertEqual(selected_slot, 'helmet')
        
        # Verify reasoning is stored
        reasoning = self.context.get(StateParameters.SLOT_SELECTION_REASONING)
        self.assertEqual(reasoning['selected_slot'], 'helmet')
        self.assertEqual(reasoning['target_skill'], 'gearcrafting')
            
    def test_select_outdated_over_adequate_equipment(self):
        """Test selection prioritizes badly outdated equipment over adequate equipment"""
        gap_analysis = {
            'weapon': {'urgency_score': 80, 'missing': False, 'reason': 'equipment 4 levels behind'},
            'helmet': {'urgency_score': 20, 'missing': False, 'reason': 'equipment 1 level behind'}
        }
        
        self.context.set(StateParameters.EQUIPMENT_GAP_ANALYSIS, gap_analysis)
        self.context.set(StateParameters.TARGET_CRAFT_SKILL, 'weaponcrafting')
        
        # Configure the mocked YamlData
        mock_yaml_instance = Mock()
        mock_yaml_instance.data = self._get_test_config()
        self.mock_yaml_class.return_value = mock_yaml_instance
        
        result = self.action.execute(self.mock_client, self.context)
            
        self.assertTrue(result.success)
        
        # Should select weapon due to higher urgency despite helmet being available
        selected_slot = self.context.get(StateParameters.TARGET_SLOT)
        self.assertEqual(selected_slot, 'weapon')
            
    def test_slot_filtering_by_skill(self):
        """Test that only slots compatible with target skill are considered"""
        gap_analysis = {
            'weapon': {'urgency_score': 90, 'missing': True, 'reason': 'empty_slot'},
            'helmet': {'urgency_score': 95, 'missing': True, 'reason': 'empty_slot'},
            'amulet': {'urgency_score': 85, 'missing': True, 'reason': 'empty_slot'}
        }
        
        self.context.set(StateParameters.EQUIPMENT_GAP_ANALYSIS, gap_analysis)
        self.context.set(StateParameters.TARGET_CRAFT_SKILL, 'jewelrycrafting')
        
        # Configure the mocked YamlData
        mock_yaml_instance = Mock()
        mock_yaml_instance.data = self._get_test_config()
        self.mock_yaml_class.return_value = mock_yaml_instance
        
        result = self.action.execute(self.mock_client, self.context)
            
        self.assertTrue(result.success)
        
        # Should only consider jewelry slots, select amulet
        selected_slot = self.context.get(StateParameters.TARGET_SLOT)
        self.assertEqual(selected_slot, 'amulet')
            
    def test_combined_scoring_priority_and_urgency(self):
        """Test combined scoring of priority weight and urgency"""
        gap_analysis = {
            'weapon': {'urgency_score': 60, 'missing': False, 'reason': 'equipment 3 levels behind'},
            'shield': {'urgency_score': 80, 'missing': False, 'reason': 'equipment 4 levels behind'}
        }
        
        self.context.set(StateParameters.EQUIPMENT_GAP_ANALYSIS, gap_analysis)
        self.context.set(StateParameters.TARGET_CRAFT_SKILL, 'weaponcrafting')
        
        # Configure the mocked YamlData
        mock_yaml_instance = Mock()
        mock_yaml_instance.data = self._get_test_config()
        self.mock_yaml_class.return_value = mock_yaml_instance
        
        result = self.action.execute(self.mock_client, self.context)
            
        self.assertTrue(result.success)
        
        # weapon: 60 * (100/100) = 60
        # shield: 80 * (90/100) = 72
        # Should select shield despite weapon having higher base priority
        selected_slot = self.context.get(StateParameters.TARGET_SLOT)
        self.assertEqual(selected_slot, 'shield')
            
    def test_error_handling_missing_gap_analysis(self):
        """Test error when equipment gap analysis is missing"""
        self.context.set(StateParameters.TARGET_CRAFT_SKILL, 'weaponcrafting')
        
        result = self.action.execute(self.mock_client, self.context)
        
        self.assertFalse(result.success)
        self.assertIn('Equipment gap analysis not available', result.error)
        
    def test_error_handling_missing_gap_analysis_data(self):
        """Test error when gap analysis is empty"""
        self.context.set(StateParameters.EQUIPMENT_GAP_ANALYSIS, {})
        
        result = self.action.execute(self.mock_client, self.context)
        
        self.assertFalse(result.success)
        self.assertIn('Equipment gap analysis not available', result.error)
        
    def test_error_handling_unknown_skill(self):
        """Test error when target skill has no mapped slots"""
        gap_analysis = {'weapon': {'urgency_score': 50, 'missing': False}}
        
        self.context.set(StateParameters.EQUIPMENT_GAP_ANALYSIS, gap_analysis)
        self.context.set(StateParameters.TARGET_CRAFT_SKILL, 'unknown_skill')
        
        # Configure the mocked YamlData
        mock_yaml_instance = Mock()
        mock_yaml_instance.data = self._get_test_config()
        self.mock_yaml_class.return_value = mock_yaml_instance
        
        result = self.action.execute(self.mock_client, self.context)
        
        self.assertFalse(result.success)
        self.assertIn("No equipment slots mapped for skill 'unknown_skill'", result.error)
            
    def test_no_valid_slots_in_gap_analysis(self):
        """Test error when no valid slots are found in gap analysis"""
        gap_analysis = {'unknown_slot': {'urgency_score': 50, 'missing': False}}
        
        self.context.set(StateParameters.EQUIPMENT_GAP_ANALYSIS, gap_analysis)
        self.context.set(StateParameters.TARGET_CRAFT_SKILL, 'weaponcrafting')
        
        # Configure the mocked YamlData
        mock_yaml_instance = Mock()
        mock_yaml_instance.data = self._get_test_config()
        self.mock_yaml_class.return_value = mock_yaml_instance
        
        result = self.action.execute(self.mock_client, self.context)
        
        self.assertFalse(result.success)
        self.assertIn('No valid slots found for skill weaponcrafting', result.error)
            
    def test_alternatives_tracking(self):
        """Test that alternative slot options are tracked in reasoning"""
        gap_analysis = {
            'helmet': {'urgency_score': 85, 'missing': True, 'reason': 'empty_slot'},
            'body_armor': {'urgency_score': 70, 'missing': False, 'reason': 'equipment 2 levels behind'},
            'leg_armor': {'urgency_score': 60, 'missing': False, 'reason': 'equipment 1 level behind'},
            'boots': {'urgency_score': 90, 'missing': True, 'reason': 'empty_slot'}
        }
        
        self.context.set(StateParameters.EQUIPMENT_GAP_ANALYSIS, gap_analysis)
        self.context.set(StateParameters.TARGET_CRAFT_SKILL, 'gearcrafting')
        
        # Configure the mocked YamlData
        mock_yaml_instance = Mock()
        mock_yaml_instance.data = self._get_test_config()
        self.mock_yaml_class.return_value = mock_yaml_instance
        
        result = self.action.execute(self.mock_client, self.context)
            
        self.assertTrue(result.success)
        
        reasoning = self.context.get(StateParameters.SLOT_SELECTION_REASONING)
        alternatives = reasoning.get('alternatives', [])
        
        # Should have up to 3 alternatives listed
        self.assertLessEqual(len(alternatives), 3)
        self.assertGreater(len(alternatives), 0)
        
        # Each alternative should have required fields
        for alt in alternatives:
            self.assertIn('slot', alt)
            self.assertIn('score', alt)
            self.assertIn('reason', alt)
                
    def test_config_fallback_handling(self):
        """Test graceful handling of configuration loading failures"""
        gap_analysis = {'weapon': {'urgency_score': 50, 'missing': False}}
        
        self.context.set(StateParameters.EQUIPMENT_GAP_ANALYSIS, gap_analysis)
        self.context.set(StateParameters.TARGET_CRAFT_SKILL, 'weaponcrafting')
        
        # Create a new action instance
        action = SelectOptimalSlotAction()
        
        # Set up a pre-configured fallback config to avoid YamlData instantiation
        fallback_config = Mock()
        fallback_config.data = {
            'skill_slot_mappings': {
                'weaponcrafting': ['weapon', 'shield']
            },
            'slot_priorities': {
                'weapon': 100
            }
        }
        
        # Force config to use our fallback
        action.config = fallback_config
        
        result = action.execute(self.mock_client, self.context)
            
        # Should work with our fallback configuration
        self.assertTrue(result.success)
        self.assertEqual(self.context.get(StateParameters.TARGET_SLOT), 'weapon')
            
    def test_determine_default_craft_skill_from_knowledge_base(self):
        """Test automatic craft skill determination from knowledge base"""
        # Mock knowledge base with items data
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'items': {
                'iron_helmet': {
                    'type': 'helmet',
                    'subtype': 'armor',
                    'craft': {
                        'skill': 'gearcrafting',
                        'level': 5
                    }
                },
                'copper_sword': {
                    'type': 'weapon',
                    'subtype': 'sword',
                    'craft': {
                        'skill': 'weaponcrafting',
                        'level': 3
                    }
                }
            }
        }
        
        gap_analysis = {
            'helmet': {'urgency_score': 85, 'missing': True, 'reason': 'empty_slot'},
            'weapon': {'urgency_score': 70, 'missing': False, 'reason': 'adequate'}
        }
        
        # Clear any leftover target_craft_skill from previous tests
        self.context.set(StateParameters.TARGET_CRAFT_SKILL, None)
        self.context.set(StateParameters.EQUIPMENT_GAP_ANALYSIS, gap_analysis)
        self.context.knowledge_base = mock_knowledge_base
        
        # Configure the mocked YamlData
        mock_yaml_instance = Mock()
        mock_yaml_instance.data = self._get_test_config()
        self.mock_yaml_class.return_value = mock_yaml_instance
        
        result = self.action.execute(self.mock_client, self.context)
            
        self.assertTrue(result.success)
        
        # Should determine gearcrafting as the default skill for helmet
        reasoning = self.context.get(StateParameters.SLOT_SELECTION_REASONING)
        self.assertEqual(reasoning['target_skill'], 'gearcrafting')
    
    def test_get_craft_skills_for_slot(self):
        """Test craft skill extraction from knowledge base for specific slots"""
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'items': {
                'iron_helmet': {
                    'type': 'helmet',
                    'craft': {
                        'skill': 'gearcrafting'
                    }
                },
                'steel_helmet': {
                    'type': 'helmet',
                    'craft': {
                        'skill': 'gearcrafting'
                    }
                },
                'copper_sword': {
                    'type': 'weapon',
                    'craft': {
                        'skill': 'weaponcrafting'
                    }
                },
                'magic_ring': {
                    'type': 'ring',
                    'craft': {
                        'skill': 'jewelrycrafting'
                    }
                }
            }
        }
        
        # Test helmet slot should return gearcrafting
        skills = self.action._get_craft_skills_for_slot(mock_knowledge_base, 'helmet')
        self.assertEqual(skills, ['gearcrafting'])
        
        # Test weapon slot should return weaponcrafting
        skills = self.action._get_craft_skills_for_slot(mock_knowledge_base, 'weapon')
        self.assertEqual(skills, ['weaponcrafting'])
        
        # Test ring slot should return jewelrycrafting
        skills = self.action._get_craft_skills_for_slot(mock_knowledge_base, 'ring1')
        self.assertEqual(skills, ['jewelrycrafting'])
        
        # Test empty knowledge base
        mock_knowledge_base.data = {'items': {}}
        skills = self.action._get_craft_skills_for_slot(mock_knowledge_base, 'weapon')
        self.assertEqual(skills, [])
        
        # Test missing items key
        mock_knowledge_base.data = {}
        skills = self.action._get_craft_skills_for_slot(mock_knowledge_base, 'weapon')
        self.assertEqual(skills, [])
    
    def test_item_fits_slot_string_matching(self):
        """Test item-to-slot matching using string patterns"""
        # Test direct type matching
        item_data = {'type': 'helmet', 'subtype': 'armor'}
        self.assertTrue(self.action._item_fits_slot(item_data, 'helmet'))
        
        # Test subtype matching
        item_data = {'type': 'armor', 'subtype': 'helmet'}
        self.assertTrue(self.action._item_fits_slot(item_data, 'helmet'))
        
        # Test reverse matching (item type in slot name)
        item_data = {'type': 'weapon', 'subtype': 'sword'}
        self.assertTrue(self.action._item_fits_slot(item_data, 'weapon'))
        
        # Test no match
        item_data = {'type': 'consumable', 'subtype': 'food'}
        self.assertFalse(self.action._item_fits_slot(item_data, 'helmet'))
        
        # Test effects-based matching
        item_data = {
            'type': 'equipment',
            'subtype': 'gear',
            'effects': [
                {'name': 'helmet_defense_bonus', 'value': 10}
            ]
        }
        self.assertTrue(self.action._item_fits_slot(item_data, 'helmet'))
    
    def test_check_derived_slot_patterns(self):
        """Test derived pattern matching for complex slot relationships"""
        # Test ring pattern matching
        item_data = {'type': 'ring', 'subtype': 'jewelry'}
        result = self.action._check_derived_slot_patterns('ring', 'jewelry', 'ring1', item_data)
        self.assertTrue(result)
        
        result = self.action._check_derived_slot_patterns('ring', 'jewelry', 'ring2', item_data)
        self.assertTrue(result)
        
        # Test armor pattern matching
        armor_item_data = {'type': 'armor', 'subtype': 'chest_armor'}
        result = self.action._check_derived_slot_patterns('armor', 'chest_armor', 'body_armor', armor_item_data)
        self.assertTrue(result)
        
        helmet_item_data = {'type': 'helmet', 'subtype': 'head_armor'}
        result = self.action._check_derived_slot_patterns('helmet', 'head_armor', 'helmet', helmet_item_data)
        self.assertTrue(result)
        
        # Test no match
        consumable_item_data = {'type': 'consumable', 'subtype': 'food'}
        result = self.action._check_derived_slot_patterns('consumable', 'food', 'weapon', consumable_item_data)
        self.assertFalse(result)
    
    def test_fallback_when_knowledge_base_empty(self):
        """Test skill selection when knowledge base has no relevant data"""
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {'items': {}}
        
        gap_analysis = {
            'helmet': {'urgency_score': 85, 'missing': True, 'reason': 'empty_slot'}
        }
        
        # Clear any leftover target_craft_skill from previous tests
        self.context.set(StateParameters.TARGET_CRAFT_SKILL, None)
        self.context.set(StateParameters.EQUIPMENT_GAP_ANALYSIS, gap_analysis)
        self.context.knowledge_base = mock_knowledge_base
        
        # Configure the mocked YamlData
        mock_yaml_instance = Mock()
        mock_yaml_instance.data = self._get_test_config()
        self.mock_yaml_class.return_value = mock_yaml_instance
        
        result = self.action.execute(self.mock_client, self.context)
            
        self.assertTrue(result.success)
        
        # Should intelligently select a skill that works with available equipment slots
        reasoning = self.context.get(StateParameters.SLOT_SELECTION_REASONING)
        self.assertEqual(reasoning['target_skill'], 'gearcrafting')  # gearcrafting includes helmet
    
    def test_multiple_craft_skills_random_selection(self):
        """Test skill selection when multiple craft skills are possible for a slot"""
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'items': {
                'item1': {
                    'type': 'helmet',
                    'craft': {'skill': 'gearcrafting'}
                },
                'item2': {
                    'type': 'helmet', 
                    'craft': {'skill': 'jewelrycrafting'}  # Use a skill that exists in test config
                }
            }
        }
        
        gap_analysis = {
            'helmet': {'urgency_score': 85, 'missing': True, 'reason': 'empty_slot'}
        }
        
        self.context.set(StateParameters.EQUIPMENT_GAP_ANALYSIS, gap_analysis)
        self.context.knowledge_base = mock_knowledge_base
        
        # Configure the mocked YamlData
        mock_yaml_instance = Mock()
        mock_yaml_instance.data = self._get_test_config()
        self.mock_yaml_class.return_value = mock_yaml_instance
        
        # Run multiple times to test different selections
        skills_found = set()
        for _ in range(10):
            result = self.action.execute(self.mock_client, self.context)
            self.assertTrue(result.success)
            
            reasoning = self.context.get(StateParameters.SLOT_SELECTION_REASONING)
            self.assertIsNotNone(reasoning)
            skills_found.add(reasoning['target_skill'])
            
            # Reset context for next iteration
            self.context.set(StateParameters.SLOT_SELECTION_REASONING, None)
        
        # Should intelligently select a skill that works with the available slots
        # Since helmet is available and gearcrafting maps to helmet, it should select gearcrafting
        self.assertTrue(len(skills_found) >= 1)
        self.assertIn('gearcrafting', skills_found)  # gearcrafting includes helmet in mapping
    
    def _get_test_config(self):
        """Get test configuration data"""
        return {
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
            }
        }


if __name__ == '__main__':
    unittest.main()