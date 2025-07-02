"""Test module for AnalyzeCraftingRequirementsAction."""

import unittest
from unittest.mock import patch

from src.controller.actions.analyze_crafting_requirements import AnalyzeCraftingRequirementsAction

from test.fixtures import (
    MockActionContext,
    MockCharacterData,
    MockCraftData,
    MockCraftItem,
    MockInventoryItem,
    MockItemData,
    MockKnowledgeBase,
    cleanup_test_environment,
    create_mock_client,
    create_test_environment,
    mock_character_response,
    mock_item_response,
)


class TestAnalyzeCraftingRequirementsAction(unittest.TestCase):
    """Test cases for AnalyzeCraftingRequirementsAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir, self.original_data_prefix = create_test_environment()
        
        self.action = AnalyzeCraftingRequirementsAction()

    def tearDown(self):
        """Clean up test fixtures."""
        cleanup_test_environment(self.temp_dir, self.original_data_prefix)

    def test_analyze_crafting_requirements_action_initialization(self):
        """Test AnalyzeCraftingRequirementsAction initialization."""
        # Action no longer has attributes since it uses ActionContext
        self.assertIsInstance(self.action, AnalyzeCraftingRequirementsAction)

    def test_analyze_crafting_requirements_action_goap_params(self):
        """Test AnalyzeCraftingRequirementsAction GOAP parameters."""
        self.assertEqual(self.action.conditions["character_status"]["alive"], True)
        self.assertTrue("crafting_requirements_known" in self.action.reactions)

    def test_analyze_crafting_requirements_action_repr(self):
        """Test AnalyzeCraftingRequirementsAction string representation."""
        expected = "AnalyzeCraftingRequirementsAction()"
        self.assertEqual(repr(self.action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        context = MockActionContext(character_name="test_character")
        result = self.action.execute(None, context)
        # With centralized validation, None client triggers validation error
        self.assertFalse(result["success"])
        # Direct action execution bypasses centralized validation
        self.assertIn('error', result)

    @patch('src.controller.actions.analyze_crafting_requirements.get_character_api')
    def test_execute_no_character_data(self, mock_get_character):
        """Test execute fails when character data unavailable."""
        mock_get_character.return_value = None
        client = create_mock_client()
        
        context = MockActionContext(character_name="test_character")
        result = self.action.execute(client, context)
        self.assertFalse(result['success'])
        self.assertIn('Could not get character data', result['error'])

    @patch('src.controller.actions.analyze_crafting_requirements.get_item_api')
    @patch('src.controller.actions.analyze_crafting_requirements.get_character_api')
    def test_execute_successful_basic_analysis(self, mock_get_character, mock_get_item):
        """Test successful crafting requirements analysis execution."""
        # Set up character with inventory
        character_data = MockCharacterData(
            name="test_character",
            level=3,
            inventory=[
                MockInventoryItem("copper_ore", 5),
                MockInventoryItem("coal", 2)
            ]
        )
        
        # Set up item data with crafting recipe
        craft_data = MockCraftData(
            skill="weaponcrafting",
            level=1,
            items=[MockCraftItem("copper_ore", 2), MockCraftItem("coal", 1)]
        )
        item_data = MockItemData(
            code="copper_dagger",
            name="Copper Dagger",
            type="weapon",
            craft=craft_data
        )
        
        mock_get_character.return_value = mock_character_response(character_data)
        mock_get_item.return_value = mock_item_response(item_data)
        
        client = create_mock_client()
        context = MockActionContext(
            character_name="test_character",
            target_items=["copper_dagger"],
            crafting_goal="equipment",
            knowledge_base=MockKnowledgeBase()
        )
        result = self.action.execute(client, context)
        
        self.assertTrue(result['success'])
        self.assertTrue(result['crafting_requirements_known'])
        self.assertIn('craftable_items', result)
        self.assertIn('total_materials_needed', result)

    @patch('src.controller.actions.analyze_crafting_requirements.get_character_api')
    def test_execute_with_knowledge_base(self, mock_get_character):
        """Test execute with knowledge base integration."""
        character_data = MockCharacterData(name="test_character", level=3)
        mock_get_character.return_value = mock_character_response(character_data)
        
        # Create knowledge base with crafting data
        knowledge_base = MockKnowledgeBase()
        knowledge_base.data['items'] = {
            'copper_dagger': {
                'name': 'Copper Dagger',
                'craft_data': {
                    'skill': 'weaponcrafting',
                    'level': 1,
                    'materials': [
                        {'code': 'copper_ore', 'quantity': 2},
                        {'code': 'coal', 'quantity': 1}
                    ]
                }
            }
        }
        
        client = create_mock_client()
        context = MockActionContext(
            character_name="test_character",
            target_items=["copper_dagger"],
            crafting_goal="equipment",
            knowledge_base=knowledge_base
        )
        result = self.action.execute(client, context)
        
        self.assertTrue(result['success'])
        self.assertTrue(result['crafting_requirements_known'])
        self.assertIn('copper_dagger', result['craftable_items'])

    @patch('src.controller.actions.analyze_crafting_requirements.get_character_api')
    def test_execute_auto_target_determination(self, mock_get_character):
        """Test automatic target item determination."""
        action = AnalyzeCraftingRequirementsAction()  # No target items
        character_data = MockCharacterData(name="test_character", level=2)
        character_data.weapon_slot = "wooden_stick"  # Poor equipment
        
        mock_get_character.return_value = mock_character_response(character_data)
        
        # Create MockKnowledgeBase with items data so filtering doesn't remove all items
        knowledge_base = MockKnowledgeBase()
        knowledge_base.data['items'] = {
            'copper_dagger': {'name': 'Copper Dagger', 'type': 'weapon'},
            'wooden_staff': {'name': 'Wooden Staff', 'type': 'weapon'},
            'leather_helmet': {'name': 'Leather Helmet', 'type': 'helmet'},
            'leather_boots': {'name': 'Leather Boots', 'type': 'boots'}
        }
        
        client = create_mock_client()
        context = MockActionContext(
            character_name="test_character",
            target_items=[],  # No target items - will auto-determine
            crafting_goal="equipment",
            knowledge_base=knowledge_base
        )
        result = action.execute(client, context)
        
        self.assertTrue(result['success'])
        self.assertGreater(len(result['target_items']), 0)  # Should determine some items

    @patch('src.controller.actions.analyze_crafting_requirements.get_character_api')
    def test_execute_exception_handling(self, mock_get_character):
        """Test exception handling during execution."""
        mock_get_character.side_effect = Exception("API Error")
        client = create_mock_client()
        
        context = MockActionContext(
            character_name="test_character",
            target_items=["copper_dagger"],
            crafting_goal="equipment",
            knowledge_base=MockKnowledgeBase()
        )
        result = self.action.execute(client, context)
        self.assertFalse(result['success'])
        self.assertIn('Crafting requirements analysis failed: API Error', result['error'])

    def test_goap_attributes(self):
        """Test that AnalyzeCraftingRequirementsAction has expected GOAP attributes."""
        self.assertTrue(hasattr(AnalyzeCraftingRequirementsAction, 'conditions'))
        self.assertTrue(hasattr(AnalyzeCraftingRequirementsAction, 'reactions'))
        self.assertTrue(hasattr(AnalyzeCraftingRequirementsAction, 'weights'))

    def test_goap_conditions(self):
        """Test GOAP conditions are properly defined."""
        self.assertIsInstance(AnalyzeCraftingRequirementsAction.conditions, dict)
        self.assertIn('character_status', AnalyzeCraftingRequirementsAction.conditions)
        self.assertTrue(AnalyzeCraftingRequirementsAction.conditions['character_status']['alive'])

    def test_goap_reactions(self):
        """Test GOAP reactions are properly defined."""
        self.assertIsInstance(AnalyzeCraftingRequirementsAction.reactions, dict)
        expected_reactions = [
            'crafting_requirements_known', 'need_crafting_materials',
            'has_crafting_materials', 'materials_sufficient'
        ]
        for reaction in expected_reactions:
            self.assertIn(reaction, AnalyzeCraftingRequirementsAction.reactions)

    def test_goap_weights(self):
        """Test GOAP weights are properly defined."""
        self.assertIsInstance(AnalyzeCraftingRequirementsAction.weights, dict)
        self.assertIn('crafting_requirements_known', AnalyzeCraftingRequirementsAction.weights)

    @patch('src.controller.actions.analyze_crafting_requirements.get_character_api')
    def test_material_sufficiency_analysis(self, mock_get_character):
        """Test material sufficiency analysis."""
        character_data = MockCharacterData(
            name="test_character",
            level=3,
            inventory=[
                MockInventoryItem("copper_ore", 10),  # Plenty
                MockInventoryItem("coal", 1)  # Just enough for one craft
            ]
        )
        
        mock_get_character.return_value = mock_character_response(character_data)
        
        knowledge_base = MockKnowledgeBase()
        knowledge_base.data['items'] = {
            'copper_dagger': {
                'craft_data': {
                    'materials': [
                        {'code': 'copper_ore', 'quantity': 2},
                        {'code': 'coal', 'quantity': 1}
                    ]
                }
            }
        }
        
        client = create_mock_client()
        context = MockActionContext(
            character_name="test_character",
            target_items=["copper_dagger"],
            crafting_goal="equipment",
            knowledge_base=knowledge_base
        )
        result = self.action.execute(client, context)
        
        self.assertTrue(result['success'])
        self.assertIn('copper_dagger', result['ready_to_craft'])
        self.assertGreaterEqual(result['total_sufficiency_score'], 0.5)

    @patch('src.controller.actions.analyze_crafting_requirements.get_character_api')
    def test_skill_requirements_analysis(self, mock_get_character):
        """Test skill requirements analysis."""
        character_data = MockCharacterData(
            name="test_character",
            level=5,
            weaponcrafting_level=1  # Low skill level
        )
        
        mock_get_character.return_value = mock_character_response(character_data)
        
        knowledge_base = MockKnowledgeBase()
        knowledge_base.data['items'] = {
            'iron_sword': {
                'craft_data': {
                    'skill': 'weaponcrafting',
                    'level': 5,  # High skill requirement
                    'materials': [{'code': 'iron', 'quantity': 3}]
                }
            }
        }
        
        action = AnalyzeCraftingRequirementsAction()
        client = create_mock_client()
        context = MockActionContext(
            character_name="test_character",
            target_items=["iron_sword"],
            crafting_goal="equipment",
            knowledge_base=knowledge_base
        )
        result = action.execute(client, context)
        
        self.assertTrue(result['success'])
        self.assertFalse(result['skills_sufficient'])
        self.assertIn('weaponcrafting', result['skill_gaps'])

    @patch('src.controller.actions.analyze_crafting_requirements.get_character_api')
    def test_gathering_strategy_generation(self, mock_get_character):
        """Test gathering strategy generation for missing materials."""
        character_data = MockCharacterData(
            name="test_character",
            level=3,
            inventory=[]  # No materials
        )
        
        mock_get_character.return_value = mock_character_response(character_data)
        
        knowledge_base = MockKnowledgeBase()
        knowledge_base.data['items'] = {
            'copper_dagger': {
                'craft_data': {
                    'materials': [
                        {'code': 'copper_ore', 'quantity': 2},
                        {'code': 'coal', 'quantity': 1}
                    ]
                }
            }
        }
        
        client = create_mock_client()
        context = MockActionContext(
            character_name="test_character",
            target_items=["copper_dagger"],
            crafting_goal="equipment",
            knowledge_base=knowledge_base
        )
        result = self.action.execute(client, context)
        
        self.assertTrue(result['success'])
        self.assertIn('gathering_priorities', result)
        self.assertIn('resource_sources', result)
        self.assertIn(result['primary_strategy'], ['material_gathering_focus', 'skill_development_first'])

    @patch('src.controller.actions.analyze_crafting_requirements.get_character_api')
    def test_consumables_crafting_goal(self, mock_get_character):
        """Test analysis with consumables crafting goal."""
        action = AnalyzeCraftingRequirementsAction()
        character_data = MockCharacterData(name="test_character", level=3)
        
        mock_get_character.return_value = mock_character_response(character_data)
        
        client = create_mock_client()
        context = MockActionContext(
            character_name="test_character",
            crafting_goal="consumables",
            knowledge_base=MockKnowledgeBase()
        )
        result = action.execute(client, context)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['crafting_goal'], 'consumables')


if __name__ == '__main__':
    unittest.main()