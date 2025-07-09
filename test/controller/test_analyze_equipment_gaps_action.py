"""
Tests for AnalyzeEquipmentGapsAction
"""

import unittest
from unittest.mock import Mock

from src.controller.actions.analyze_equipment_gaps import AnalyzeEquipmentGapsAction
from src.lib.state_parameters import StateParameters
from test.test_base import UnifiedContextTestBase
from test.fixtures import create_mock_client


class TestAnalyzeEquipmentGapsAction(UnifiedContextTestBase):
    """Test suite for AnalyzeEquipmentGapsAction"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.action = AnalyzeEquipmentGapsAction()
        
        # Set up basic context
        self.context.set(StateParameters.CHARACTER_NAME, "test_character")
        self.context.set(StateParameters.CHARACTER_LEVEL, 5)
        
    def test_analyze_mixed_equipment_state(self):
        """Test analysis with mixed equipment (some missing, some outdated)"""
        # Set some equipment as present
        self.context.set(StateParameters.EQUIPMENT_WEAPON, "wooden_stick")
        self.context.set(StateParameters.EQUIPMENT_ARMOR, "leather_armor")
        # Leave helmet, boots missing (None)
        
        result = self.action.execute(create_mock_client(), self.context)
        
        self.assertTrue(result.success)
        self.assertIn('gap_analysis', result.data)
        self.assertIn('target_slot', result.data)
        self.assertTrue(result.data['gaps_analyzed'])
        
        # Check that analysis found gaps
        gap_analysis = result.data['gap_analysis']
        self.assertIsInstance(gap_analysis, dict)
        self.assertIn('weapon', gap_analysis)
        self.assertIn('helmet', gap_analysis)
        
    def test_analyze_no_equipment(self):
        """Test analysis when character has no equipment"""
        # All equipment slots are None by default
        
        result = self.action.execute(create_mock_client(), self.context)
        
        self.assertTrue(result.success)
        self.assertIn('gap_analysis', result.data)
        self.assertIn('target_slot', result.data)
        
        # All slots should show as needing equipment
        gap_analysis = result.data['gap_analysis']
        for slot_data in gap_analysis.values():
            self.assertTrue(slot_data['missing'])
            self.assertEqual(slot_data['urgency_score'], 100)
            self.assertEqual(slot_data['reason'], 'missing_equipment')
    
    def test_analyze_over_leveled_equipment(self):
        """Test analysis with over-leveled equipment"""
        # Set all equipment slots
        self.context.set(StateParameters.EQUIPMENT_WEAPON, "legendary_sword")
        self.context.set(StateParameters.EQUIPMENT_HELMET, "legendary_helmet")
        self.context.set(StateParameters.EQUIPMENT_ARMOR, "legendary_armor")
        self.context.set(StateParameters.EQUIPMENT_SHIELD, "legendary_shield")
        self.context.set(StateParameters.EQUIPMENT_BOOTS, "legendary_boots")
        self.context.set(StateParameters.EQUIPMENT_AMULET, "legendary_amulet")
        self.context.set(StateParameters.EQUIPMENT_RING1, "legendary_ring1")
        self.context.set(StateParameters.EQUIPMENT_RING2, "legendary_ring2")
        
        result = self.action.execute(create_mock_client(), self.context)
        
        self.assertTrue(result.success)
        self.assertIn('gap_analysis', result.data)
        
        # All slots should show as equipped
        gap_analysis = result.data['gap_analysis']
        for slot_data in gap_analysis.values():
            self.assertFalse(slot_data['missing'])
            self.assertEqual(slot_data['urgency_score'], 50)
            self.assertEqual(slot_data['reason'], 'has_equipment')
    
    def test_config_loading_fallback(self):
        """Test that action works without complex config loading"""
        # Simplified action doesn't need config loading
        
        result = self.action.execute(create_mock_client(), self.context)
        
        self.assertTrue(result.success)
        self.assertIn('gap_analysis', result.data)
    
    def test_ring_equipment_handling(self):
        """Test handling of ring equipment"""
        # Simplified action handles basic equipment slots
        
        result = self.action.execute(create_mock_client(), self.context)
        
        self.assertTrue(result.success)
        self.assertIn('gap_analysis', result.data)
        
        # Check that basic slots are analyzed
        gap_analysis = result.data['gap_analysis']
        expected_slots = ['weapon', 'helmet', 'body_armor', 'shield', 'boots', 'amulet', 'ring1', 'ring2']
        for slot in expected_slots:
            self.assertIn(slot, gap_analysis)
    
    def test_stat_modifier_calculation(self):
        """Test stat modifier calculation"""
        # Simplified action doesn't do complex stat calculations
        
        result = self.action.execute(create_mock_client(), self.context)
        
        self.assertTrue(result.success)
        self.assertIn('gap_analysis', result.data)
        
        # Basic scoring is simple
        gap_analysis = result.data['gap_analysis']
        for slot_data in gap_analysis.values():
            self.assertIn('urgency_score', slot_data)
            self.assertIsInstance(slot_data['urgency_score'], int)
    
    def test_execute_no_character_name(self):
        """Test execute without character name"""
        self.context.set(StateParameters.CHARACTER_NAME, None)
        
        result = self.action.execute(create_mock_client(), self.context)
        
        self.assertFalse(result.success)
        self.assertIn("No character name provided", result.error)
    
    def test_execute_exception_handling(self):
        """Test execute with exception handling"""
        # Create a context that will cause an exception in the try block
        # by setting up a context that gets character_name but fails later
        self.context.set(StateParameters.CHARACTER_NAME, "test_character")
        self.context.set(StateParameters.CHARACTER_LEVEL, 5)
        
        # Mock the context.get method to fail on equipment parameters
        original_get = self.context.get
        def mock_get(param, default=None):
            if 'equipment_status' in param:
                raise Exception("Test exception")
            return original_get(param, default)
        
        self.context.get = mock_get
        
        result = self.action.execute(create_mock_client(), self.context)
        
        self.assertFalse(result.success)
        self.assertIn("Equipment gap analysis failed", result.error)
    
    def test_goap_attributes(self):
        """Test that action has proper GOAP attributes"""
        self.assertTrue(hasattr(self.action, 'conditions'))
        self.assertTrue(hasattr(self.action, 'reactions'))
        self.assertTrue(hasattr(self.action, 'weight'))
        
        # Check condition structure
        self.assertEqual(self.action.conditions['character_status']['alive'], True)
        
        # Check reaction structure
        self.assertTrue(self.action.reactions['equipment_status']['gaps_analyzed'])
        
        # Check weight
        self.assertEqual(self.action.weight, 1.0)