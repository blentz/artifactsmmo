"""Test module for UpgradeWeaponcraftingSkillAction."""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.upgrade_weaponcrafting_skill import UpgradeWeaponcraftingSkillAction

from test.fixtures import (
    MockActionContext,
    MockCharacterData,
    cleanup_test_environment,
    create_mock_client,
    create_test_environment,
    mock_character_response,
)


class TestUpgradeWeaponcraftingSkillAction(unittest.TestCase):
    """Test cases for UpgradeWeaponcraftingSkillAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir, self.original_data_prefix = create_test_environment()
        
        self.character_name = "test_character"
        self.action = UpgradeWeaponcraftingSkillAction()
        self.client = create_mock_client()

    def tearDown(self):
        """Clean up test fixtures."""
        cleanup_test_environment(self.temp_dir, self.original_data_prefix)

    def test_upgrade_weaponcrafting_skill_action_initialization(self):
        """Test UpgradeWeaponcraftingSkillAction initialization."""
        # Action no longer has attributes since it uses ActionContext
        self.assertIsInstance(self.action, UpgradeWeaponcraftingSkillAction)

    def test_upgrade_weaponcrafting_skill_action_repr(self):
        """Test UpgradeWeaponcraftingSkillAction string representation."""
        expected = "UpgradeWeaponcraftingSkillAction()"
        self.assertEqual(repr(self.action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        context = MockActionContext(
            character_name=self.character_name,
            target_level=2,
            current_level=0
        )
        result = self.action.execute(None, context)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    @patch('src.controller.actions.upgrade_weaponcrafting_skill.get_character_api')
    def test_execute_character_api_fails(self, mock_get_character_api):
        """Test execute when character API fails."""
        mock_get_character_api.return_value = None
        
        context = MockActionContext(
            character_name=self.character_name,
            target_level=2,
            current_level=0
        )
        result = self.action.execute(self.client, context)
        self.assertFalse(result['success'])
        self.assertIn('Could not get character data', result['error'])

    @patch('src.controller.actions.upgrade_weaponcrafting_skill.get_character_api')
    def test_execute_already_at_target_level(self, mock_get_character_api):
        """Test execute when character is already at target level."""
        # Mock character with target skill level already achieved
        character = MockCharacterData(
            name=self.character_name,
            weaponcrafting_level=5
        )
        mock_get_character_api.return_value = mock_character_response(character)
        
        context = MockActionContext(
            character_name=self.character_name,
            target_level=3,  # Target is lower than current
            current_level=0
        )
        result = self.action.execute(self.client, context)
        
        self.assertTrue(result['success'])
        self.assertTrue(result.get('skill_level_achieved'))
        self.assertEqual(result.get('current_weaponcrafting_level'), 5)

    @patch('src.controller.actions.upgrade_weaponcrafting_skill.craft_api')
    @patch('src.controller.actions.upgrade_weaponcrafting_skill.get_character_api')
    def test_execute_successful_craft(self, mock_get_character_api, mock_craft_api):
        """Test successful crafting execution."""
        # Mock character with low skill level and materials
        character = MockCharacterData(
            name=self.character_name,
            weaponcrafting_level=0
        )
        # Add inventory items for crafting
        inventory_item = Mock()
        inventory_item.code = 'ash_wood'
        inventory_item.quantity = 5
        character.inventory = [inventory_item]
        
        # Mock updated character with increased skill
        updated_character = MockCharacterData(
            name=self.character_name,
            weaponcrafting_level=1
        )
        
        # Setup API mocks
        mock_get_character_api.side_effect = [
            mock_character_response(character),  # Initial character data
            mock_character_response(updated_character)  # Updated character data
        ]
        
        mock_craft_response = Mock()
        mock_craft_response.data = {'item': 'wooden_stick'}
        mock_craft_api.return_value = mock_craft_response
        
        context = MockActionContext(
            character_name=self.character_name,
            target_level=1,
            current_level=0
        )
        result = self.action.execute(self.client, context)
        
        self.assertTrue(result['success'])
        self.assertEqual(result.get('item_crafted'), 'wooden_stick')
        self.assertTrue(result.get('skill_xp_gained'))

    @patch('src.controller.actions.upgrade_weaponcrafting_skill.get_character_api')
    def test_execute_no_suitable_items(self, mock_get_character_api):
        """Test execute when no suitable items can be crafted."""
        # Mock character with no materials
        character = MockCharacterData(
            name=self.character_name,
            weaponcrafting_level=0
        )
        character.inventory = []  # No materials
        
        mock_get_character_api.return_value = mock_character_response(character)
        
        context = MockActionContext(
            character_name=self.character_name,
            target_level=1,
            current_level=0
        )
        result = self.action.execute(self.client, context)
        
        self.assertFalse(result['success'])
        self.assertIn('No suitable items to craft', result['error'])

    def test_execute_exception_handling(self):
        """Test exception handling during execution."""
        context = MockActionContext(
            character_name=self.character_name,
            target_level=1,
            current_level=0
        )
        
        with patch('src.controller.actions.upgrade_weaponcrafting_skill.get_character_api', side_effect=Exception("API Error")):
            result = self.action.execute(self.client, context)
            self.assertFalse(result['success'])
            self.assertIn('Weaponcrafting skill upgrade failed: API Error', result['error'])

    def test_execute_has_goap_attributes(self):
        """Test that UpgradeWeaponcraftingSkillAction has expected GOAP attributes."""
        self.assertTrue(hasattr(UpgradeWeaponcraftingSkillAction, 'conditions'))
        self.assertTrue(hasattr(UpgradeWeaponcraftingSkillAction, 'reactions'))
        self.assertTrue(hasattr(UpgradeWeaponcraftingSkillAction, 'weights'))

    def test_goap_conditions(self):
        """Test GOAP conditions are properly defined."""
        expected_conditions = {
            "character_alive": True,
            "at_workshop": True,
            "has_materials": True
        }
        self.assertEqual(UpgradeWeaponcraftingSkillAction.conditions, expected_conditions)

    def test_goap_reactions(self):
        """Test GOAP reactions are properly defined."""
        expected_reactions = {
            "weaponcrafting_level_sufficient": True,
            "skill_xp_gained": True,
            "character_stats_improved": True
        }
        self.assertEqual(UpgradeWeaponcraftingSkillAction.reactions, expected_reactions)

    def test_goap_weights(self):
        """Test GOAP weights are properly defined."""
        expected_weights = {"weaponcrafting_level_sufficient": 30}
        self.assertEqual(UpgradeWeaponcraftingSkillAction.weights, expected_weights)


if __name__ == '__main__':
    unittest.main()