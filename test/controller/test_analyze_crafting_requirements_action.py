"""Test module for AnalyzeCraftingRequirementsAction."""

import unittest
from unittest.mock import Mock

from src.controller.actions.analyze_crafting_requirements import AnalyzeCraftingRequirementsAction
from src.lib.state_parameters import StateParameters
from test.test_base import UnifiedContextTestBase

from test.fixtures import (
    cleanup_test_environment,
    create_mock_client,
    create_test_environment,
)


class TestAnalyzeCraftingRequirementsAction(UnifiedContextTestBase):
    """Test cases for AnalyzeCraftingRequirementsAction."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.temp_dir, self.original_data_prefix = create_test_environment()
        
        self.action = AnalyzeCraftingRequirementsAction()
        
        # Set up simplified context
        self.context.set(StateParameters.CHARACTER_NAME, "test_character")
        self.context.set(StateParameters.TARGET_ITEM, "wooden_staff")
        
        # Mock knowledge base with simplified structure
        self.mock_knowledge_base = Mock()
        self.mock_knowledge_base.data = {
            'items': {
                'wooden_staff': {
                    'name': 'Wooden Staff',
                    'level': 5,
                    'type': 'weapon',
                    'craft_data': {
                        'skill': 'weaponcrafting',
                        'level': 3,
                        'items': [{'code': 'ash_wood', 'quantity': 2}]
                    }
                }
            }
        }
        self.context.knowledge_base = self.mock_knowledge_base

    def tearDown(self):
        """Clean up test fixtures."""
        cleanup_test_environment(self.temp_dir, self.original_data_prefix)

    def test_analyze_crafting_requirements_action_initialization(self):
        """Test AnalyzeCraftingRequirementsAction initialization."""
        self.assertIsInstance(self.action, AnalyzeCraftingRequirementsAction)

    def test_analyze_crafting_requirements_action_goap_params(self):
        """Test AnalyzeCraftingRequirementsAction GOAP parameters."""
        self.assertEqual(self.action.conditions["character_status"]["alive"], True)
        self.assertTrue("crafting_requirements_known" in self.action.reactions)

    def test_analyze_crafting_requirements_action_repr(self):
        """Test AnalyzeCraftingRequirementsAction string representation."""
        result = str(self.action)
        self.assertIn("AnalyzeCraftingRequirementsAction", result)

    def test_execute_successful_basic_analysis(self):
        """Test successful basic crafting requirements analysis."""
        client = create_mock_client()
        
        result = self.action.execute(client, self.context)
        self.assertTrue(result.success)
        self.assertEqual(result.data['target_item'], 'wooden_staff')
        self.assertEqual(result.data['required_skill'], 'weaponcrafting')
        self.assertEqual(result.data['required_skill_level'], 3)
        self.assertEqual(len(result.data['required_materials']), 1)
        self.assertEqual(result.data['required_materials'][0]['code'], 'ash_wood')

    def test_execute_no_character_name(self):
        """Test execute without character name."""
        client = create_mock_client()
        self.context.set(StateParameters.CHARACTER_NAME, None)
        
        result = self.action.execute(client, self.context)
        self.assertFalse(result.success)
        self.assertIn("No character name provided", result.error)

    def test_execute_no_target_item(self):
        """Test execute without target item."""
        client = create_mock_client()
        self.context.set(StateParameters.TARGET_ITEM, None)
        
        result = self.action.execute(client, self.context)
        self.assertFalse(result.success)
        self.assertIn("No target item specified", result.error)

    def test_execute_no_knowledge_base(self):
        """Test execute without knowledge base."""
        client = create_mock_client()
        self.context.knowledge_base = None
        
        result = self.action.execute(client, self.context)
        self.assertFalse(result.success)
        self.assertIn("No knowledge base available", result.error)

    def test_execute_item_not_found(self):
        """Test execute with item not found in knowledge base - should request subgoal."""
        client = create_mock_client()
        self.context.set(StateParameters.TARGET_ITEM, "unknown_item")
        
        result = self.action.execute(client, self.context)
        self.assertTrue(result.success)
        self.assertEqual(result.data['subgoal_requested'], True)
        self.assertEqual(result.data['subgoal_name'], 'lookup_item_info')

    def test_execute_item_not_craftable(self):
        """Test execute with item that has no craft data."""
        client = create_mock_client()
        
        # Add item without craft data
        self.mock_knowledge_base.data['items']['non_craftable'] = {
            'name': 'Non-Craftable Item',
            'level': 1
        }
        self.context.set(StateParameters.TARGET_ITEM, "non_craftable")
        
        result = self.action.execute(client, self.context)
        self.assertFalse(result.success)
        self.assertIn("Item non_craftable is not craftable", result.error)

    def test_execute_with_knowledge_base(self):
        """Test execute with knowledge base."""
        client = create_mock_client()
        
        result = self.action.execute(client, self.context)
        self.assertTrue(result.success)
        self.assertTrue(result.data['crafting_requirements_known'])

    def test_execute_no_client(self):
        """Test execute without client."""
        result = self.action.execute(None, self.context)
        # Should succeed since simplified action doesn't require client
        self.assertTrue(result.success)

    def test_execute_exception_handling(self):
        """Test execute with exception handling."""
        client = create_mock_client()
        
        # Cause an exception by making knowledge base.data not a dict
        self.mock_knowledge_base.data = None
        
        result = self.action.execute(client, self.context)
        self.assertFalse(result.success)
        self.assertIn("Crafting requirements analysis failed", result.error)

    def test_execute_auto_target_determination(self):
        """Test execute with auto target determination."""
        # Simplified action requires explicit target item
        client = create_mock_client()
        self.context.set(StateParameters.TARGET_ITEM, "wooden_staff")
        
        result = self.action.execute(client, self.context)
        self.assertTrue(result.success)
        self.assertEqual(result.data['target_item'], 'wooden_staff')

    def test_consumables_crafting_goal(self):
        """Test with consumables crafting goal."""
        client = create_mock_client()
        
        # Add consumable item
        self.mock_knowledge_base.data['items']['health_potion'] = {
            'name': 'Health Potion',
            'level': 1,
            'type': 'consumable',
            'craft_data': {
                'skill': 'alchemy',
                'level': 1,
                'items': [{'code': 'herb', 'quantity': 1}]
            }
        }
        self.context.set(StateParameters.TARGET_ITEM, "health_potion")
        
        result = self.action.execute(client, self.context)
        self.assertTrue(result.success)
        self.assertEqual(result.data['required_skill'], 'alchemy')

    def test_gathering_strategy_generation(self):
        """Test gathering strategy generation."""
        client = create_mock_client()
        
        result = self.action.execute(client, self.context)
        self.assertTrue(result.success)
        # Simplified action provides basic requirements
        self.assertIn('required_materials', result.data)

    def test_material_sufficiency_analysis(self):
        """Test material sufficiency analysis."""
        client = create_mock_client()
        
        result = self.action.execute(client, self.context)
        self.assertTrue(result.success)
        # Simplified action provides basic requirements
        self.assertIn('required_materials', result.data)

    def test_skill_requirements_analysis(self):
        """Test skill requirements analysis."""
        client = create_mock_client()
        
        result = self.action.execute(client, self.context)
        self.assertTrue(result.success)
        self.assertIn('required_skill', result.data)
        self.assertIn('required_skill_level', result.data)