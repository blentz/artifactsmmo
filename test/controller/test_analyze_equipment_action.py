"""Test module for AnalyzeEquipmentAction."""

import unittest
from unittest.mock import patch

from src.controller.actions.analyze_equipment import AnalyzeEquipmentAction

from test.fixtures import (
    MockActionContext,
    MockCharacterData,
    MockInventoryItem,
    MockKnowledgeBase,
    cleanup_test_environment,
    create_mock_client,
    create_test_environment,
    mock_character_response,
)


class TestAnalyzeEquipmentAction(unittest.TestCase):
    """Test cases for AnalyzeEquipmentAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir, self.original_data_prefix = create_test_environment()
        
        self.action = AnalyzeEquipmentAction()

    def tearDown(self):
        """Clean up test fixtures."""
        cleanup_test_environment(self.temp_dir, self.original_data_prefix)

    def test_analyze_equipment_action_initialization(self):
        """Test AnalyzeEquipmentAction initialization."""
        # Action no longer has attributes since it uses ActionContext
        self.assertIsInstance(self.action, AnalyzeEquipmentAction)

    def test_analyze_equipment_action_goap_params(self):
        """Test AnalyzeEquipmentAction GOAP parameters."""
        # Test consolidated state format
        self.assertIn("character_status", self.action.conditions)
        self.assertEqual(self.action.conditions["character_status"]["alive"], True)
        
        self.assertIn("equipment_status", self.action.reactions)
        self.assertEqual(self.action.reactions["equipment_status"]["upgrade_status"], "analyzing")
        self.assertEqual(self.action.reactions["equipment_status"]["target_slot"], "weapon")

    def test_analyze_equipment_action_repr(self):
        """Test AnalyzeEquipmentAction string representation."""
        expected = "AnalyzeEquipmentAction()"
        self.assertEqual(repr(self.action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        context = MockActionContext(character_name="test_character")
        result = self.action.execute(None, context)
        # With centralized validation, None client triggers validation error
        self.assertFalse(result["success"])
        # Direct action execution bypasses centralized validation
        self.assertIn('error', result)

    @patch('src.controller.actions.analyze_equipment.get_character_api')
    def test_execute_no_character_data(self, mock_get_character):
        """Test execute fails when character data unavailable."""
        mock_get_character.return_value = None
        client = create_mock_client()
        
        context = MockActionContext(
            character_name="test_character",
            analysis_type="comprehensive",
            knowledge_base=MockKnowledgeBase()
        )
        result = self.action.execute(client, context)
        self.assertFalse(result['success'])
        self.assertIn('Could not get character data', result['error'])

    @patch('src.controller.actions.analyze_equipment.get_character_api')
    def test_execute_successful_basic_analysis(self, mock_get_character):
        """Test successful equipment analysis execution."""
        # Create character with basic equipment
        character_data = MockCharacterData(
            name="test_character",
            level=5,
            inventory=[MockInventoryItem("copper_dagger", 1)]
        )
        character_data.weapon_slot = "copper_dagger"
        character_data.helmet_slot = ""
        character_data.body_armor_slot = ""
        character_data.leg_armor_slot = ""
        character_data.boots_slot = ""
        character_data.ring1_slot = ""
        character_data.ring2_slot = ""
        character_data.amulet_slot = ""
        
        mock_get_character.return_value = mock_character_response(character_data)
        client = create_mock_client()
        
        context = MockActionContext(
            character_name="test_character",
            analysis_type="comprehensive",
            knowledge_base=MockKnowledgeBase()
        )
        result = self.action.execute(client, context)
        
        self.assertTrue(result['success'])
        self.assertTrue(result['equipment_analysis_available'])
        self.assertIn('current_equipment', result)
        self.assertIn('current_equipment', result)

    @patch('src.controller.actions.analyze_equipment.get_character_api')
    def test_execute_with_knowledge_base(self, mock_get_character):
        """Test execute with knowledge base integration."""
        character_data = MockCharacterData(name="test_character", level=3)
        mock_get_character.return_value = mock_character_response(character_data)
        
        # Create knowledge base with item data
        knowledge_base = MockKnowledgeBase()
        knowledge_base.data['items'] = {
            'copper_dagger': {
                'name': 'Copper Dagger',
                'level': 1,
                'type': 'weapon'
            },
            'iron_sword': {
                'name': 'Iron Sword', 
                'level': 3,
                'type': 'weapon'
            }
        }
        
        client = create_mock_client()
        context = MockActionContext(
            character_name="test_character",
            analysis_type="comprehensive",
            knowledge_base=knowledge_base
        )
        result = self.action.execute(client, context)
        
        self.assertTrue(result['success'])
        self.assertTrue(result['equipment_analysis_available'])

    @patch('src.controller.actions.analyze_equipment.get_character_api')
    def test_execute_exception_handling(self, mock_get_character):
        """Test exception handling during execution."""
        mock_get_character.side_effect = Exception("API Error")
        client = create_mock_client()
        
        context = MockActionContext(
            character_name="test_character",
            analysis_type="comprehensive",
            knowledge_base=MockKnowledgeBase()
        )
        result = self.action.execute(client, context)
        self.assertFalse(result['success'])
        self.assertIn('Equipment analysis failed: API Error', result['error'])

    def test_goap_attributes(self):
        """Test that AnalyzeEquipmentAction has expected GOAP attributes."""
        self.assertTrue(hasattr(AnalyzeEquipmentAction, 'conditions'))
        self.assertTrue(hasattr(AnalyzeEquipmentAction, 'reactions'))
        self.assertTrue(hasattr(AnalyzeEquipmentAction, 'weight'))

    def test_goap_conditions(self):
        """Test GOAP conditions are properly defined."""
        self.assertIsInstance(AnalyzeEquipmentAction.conditions, dict)
        self.assertIn('character_status', AnalyzeEquipmentAction.conditions)
        self.assertEqual(AnalyzeEquipmentAction.conditions['character_status']['alive'], True)

    def test_goap_reactions(self):
        """Test GOAP reactions are properly defined."""
        self.assertIsInstance(AnalyzeEquipmentAction.reactions, dict)
        self.assertIn('equipment_status', AnalyzeEquipmentAction.reactions)
        self.assertEqual(AnalyzeEquipmentAction.reactions['equipment_status']['upgrade_status'], 'analyzing')

    def test_goap_weights(self):
        """Test GOAP weights are properly defined."""
        self.assertIsInstance(AnalyzeEquipmentAction.weight, (int, float))
        self.assertEqual(AnalyzeEquipmentAction.weight, 1)

    @patch('src.controller.actions.analyze_equipment.get_character_api')
    def test_analyze_current_equipment_empty(self, mock_get_character):
        """Test analysis of character with no equipment."""
        character_data = MockCharacterData(name="test_character", level=1)
        # All equipment slots empty
        for slot in ['weapon_slot', 'helmet_slot', 'body_armor_slot', 
                    'leg_armor_slot', 'boots_slot', 'ring1_slot', 'ring2_slot', 'amulet_slot']:
            setattr(character_data, slot, "")
        
        mock_get_character.return_value = mock_character_response(character_data)
        client = create_mock_client()
        
        context = MockActionContext(
            character_name="test_character",
            analysis_type="comprehensive",
            knowledge_base=MockKnowledgeBase()
        )
        result = self.action.execute(client, context)
        
        self.assertTrue(result['success'])
        self.assertTrue(result['need_equipment'])
        self.assertEqual(result['equipment_coverage']['total_equipped'], 0)

    @patch('src.controller.actions.analyze_equipment.get_character_api')
    def test_equipment_coverage_calculation(self, mock_get_character):
        """Test equipment coverage calculation."""
        character_data = MockCharacterData(name="test_character", level=5)
        character_data.weapon_slot = "copper_dagger"
        character_data.helmet_slot = "leather_helmet"
        character_data.body_armor_slot = ""
        character_data.leg_armor_slot = ""
        character_data.boots_slot = ""
        character_data.ring1_slot = ""
        character_data.ring2_slot = ""
        character_data.amulet_slot = ""
        
        mock_get_character.return_value = mock_character_response(character_data)
        client = create_mock_client()
        
        context = MockActionContext(
            character_name="test_character",
            analysis_type="comprehensive",
            knowledge_base=MockKnowledgeBase()
        )
        result = self.action.execute(client, context)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['equipment_coverage']['total_equipped'], 2)
        self.assertAlmostEqual(result['equipment_coverage_percentage'], 16.0, places=0)  # 2/12 slots

    @patch('src.controller.actions.analyze_equipment.get_character_api')
    def test_upgrade_recommendations(self, mock_get_character):
        """Test upgrade recommendations generation."""
        character_data = MockCharacterData(name="test_character", level=10)
        character_data.weapon_slot = "wooden_stick"  # Low-tier weapon
        
        mock_get_character.return_value = mock_character_response(character_data)
        client = create_mock_client()
        
        context = MockActionContext(
            character_name="test_character",
            analysis_type="comprehensive",
            knowledge_base=MockKnowledgeBase()
        )
        result = self.action.execute(client, context)
        
        self.assertTrue(result['success'])
        self.assertTrue(result['need_equipment'])
        self.assertIn('upgrade_priorities', result)


if __name__ == '__main__':
    unittest.main()