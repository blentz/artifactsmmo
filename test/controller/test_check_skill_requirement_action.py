"""Test module for CheckSkillRequirementAction."""

import unittest
from unittest.mock import patch
from test.fixtures import (
    create_test_environment, cleanup_test_environment, create_mock_client,
    mock_character_response, mock_item_response, MockCharacterData, MockItemData,
    MockCraftData, MockCraftItem
)
from src.controller.actions.check_skill_requirement import CheckSkillRequirementAction


class TestCheckSkillRequirementAction(unittest.TestCase):
    """Test cases for CheckSkillRequirementAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir, self.original_data_prefix = create_test_environment()
        
        self.character_name = "test_character"
        self.target_item = "iron_sword"
        self.action = CheckSkillRequirementAction(
            character_name=self.character_name,
            target_item=self.target_item
        )
        self.client = create_mock_client()

    def tearDown(self):
        """Clean up test fixtures."""
        cleanup_test_environment(self.temp_dir, self.original_data_prefix)

    def test_check_skill_requirement_action_initialization(self):
        """Test CheckSkillRequirementAction initialization."""
        self.assertEqual(self.action.character_name, "test_character")
        self.assertEqual(self.action.target_item, "iron_sword")

    def test_check_skill_requirement_action_initialization_defaults(self):
        """Test CheckSkillRequirementAction initialization with defaults."""
        action = CheckSkillRequirementAction("player")
        self.assertEqual(action.character_name, "player")
        self.assertEqual(action.task_type, "crafting")
        self.assertIsNone(action.target_item)

    def test_check_skill_requirement_action_repr(self):
        """Test CheckSkillRequirementAction string representation."""
        expected = "CheckSkillRequirementAction(test_character, crafting, iron_sword)"
        self.assertEqual(repr(self.action), expected)

    def test_check_skill_requirement_action_repr_no_target(self):
        """Test CheckSkillRequirementAction string representation without target."""
        action = CheckSkillRequirementAction("player")
        expected = "CheckSkillRequirementAction(player, crafting, None)"
        self.assertEqual(repr(action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        result = self.action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    @patch('src.controller.actions.check_skill_requirement.get_item_api')
    @patch('src.controller.actions.check_skill_requirement.get_character_api')
    def test_execute_simple_path(self, mock_get_character_api, mock_get_item_api):
        """Test execute with basic success path."""
        # Mock character with sufficient skill level
        character = MockCharacterData(
            name=self.character_name,
            weaponcrafting_level=10
        )
        mock_get_character_api.return_value = mock_character_response(character)
        
        # Mock item with lower skill requirement
        craft_item = MockCraftItem(code="iron", quantity=2)
        craft_data = MockCraftData(skill="weaponcrafting", level=5, items=[craft_item])
        item = MockItemData(
            code=self.target_item,
            name="Iron Sword",
            type="weapon",
            craft=craft_data
        )
        mock_get_item_api.return_value = mock_item_response(item)
        
        result = self.action.execute(self.client)
        
        self.assertTrue(result['success'])
        # Check the actual keys returned by the action
        self.assertTrue(result.get('skill_level_sufficient'))
        self.assertEqual(result.get('current_skill_level'), 10)
        self.assertEqual(result.get('required_skill_level'), 5)

    @patch('src.controller.actions.check_skill_requirement.get_item_api')
    @patch('src.controller.actions.check_skill_requirement.get_character_api')
    def test_execute_insufficient_skill(self, mock_get_character_api, mock_get_item_api):
        """Test execute when skill level is insufficient."""
        # Mock character with low skill level
        character = MockCharacterData(
            name=self.character_name,
            weaponcrafting_level=2
        )
        mock_get_character_api.return_value = mock_character_response(character)
        
        # Mock item with higher skill requirement
        craft_item = MockCraftItem(code="iron", quantity=2)
        craft_data = MockCraftData(skill="weaponcrafting", level=5, items=[craft_item])
        item = MockItemData(
            code=self.target_item,
            name="Iron Sword",
            type="weapon",
            craft=craft_data
        )
        mock_get_item_api.return_value = mock_item_response(item)
        
        result = self.action.execute(self.client)
        
        self.assertTrue(result['success'])
        self.assertFalse(result.get('skill_level_sufficient'))
        self.assertEqual(result.get('current_skill_level'), 2)
        self.assertEqual(result.get('required_skill_level'), 5)
        self.assertEqual(result.get('skill_gap'), 3)

    @patch('src.controller.actions.check_skill_requirement.get_item_api')
    @patch('src.controller.actions.check_skill_requirement.get_character_api')  
    def test_execute_item_not_craftable(self, mock_get_character_api, mock_get_item_api):
        """Test execute when item is not craftable."""
        # Mock character
        character = MockCharacterData(name=self.character_name)
        mock_get_character_api.return_value = mock_character_response(character)
        
        # Mock item without craft data
        item = MockItemData(
            code=self.target_item,
            name="Special Item",
            type="consumable",
            craft=None
        )
        mock_get_item_api.return_value = mock_item_response(item)
        
        result = self.action.execute(self.client)
        
        self.assertFalse(result['success'])
        self.assertIn('Could not determine skill requirements', result['error'])

    @patch('src.controller.actions.check_skill_requirement.get_item_api')
    @patch('src.controller.actions.check_skill_requirement.get_character_api')
    def test_execute_item_api_fails(self, mock_get_character_api, mock_get_item_api):
        """Test execute when item API fails."""
        # Mock character
        character = MockCharacterData(name=self.character_name)
        mock_get_character_api.return_value = mock_character_response(character)
        
        # Mock item API failure
        mock_get_item_api.return_value = None
        
        result = self.action.execute(self.client)
        
        self.assertFalse(result['success'])
        self.assertIn('Could not determine skill requirements', result['error'])

    @patch('src.controller.actions.check_skill_requirement.get_item_api')
    @patch('src.controller.actions.check_skill_requirement.get_character_api')
    def test_execute_item_api_no_data(self, mock_get_character_api, mock_get_item_api):
        """Test execute when item API returns no data."""
        # Mock character
        character = MockCharacterData(name=self.character_name)
        mock_get_character_api.return_value = mock_character_response(character)
        
        # Mock item API with no data
        mock_get_item_api.return_value = mock_item_response(None)
        
        result = self.action.execute(self.client)
        
        self.assertFalse(result['success'])
        self.assertIn('Could not determine skill requirements', result['error'])

    @patch('src.controller.actions.check_skill_requirement.get_character_api')
    def test_execute_character_api_fails(self, mock_get_character_api):
        """Test execute when character API fails."""
        mock_get_character_api.return_value = None
        
        result = self.action.execute(self.client)
        
        self.assertFalse(result['success'])
        self.assertIn('Could not get character data', result['error'])

    @patch('src.controller.actions.check_skill_requirement.get_item_api')
    @patch('src.controller.actions.check_skill_requirement.get_character_api')
    def test_execute_exception_handling(self, mock_get_character_api, mock_get_item_api):
        """Test exception handling during execution."""
        mock_get_character_api.side_effect = Exception("API Error")
        
        result = self.action.execute(self.client)
        
        self.assertFalse(result['success'])
        self.assertIn('Skill requirement check failed', result['error'])
        self.assertIn('API Error', result['error'])

    def test_execute_has_goap_attributes(self):
        """Test that CheckSkillRequirementAction has expected GOAP attributes."""
        self.assertTrue(hasattr(CheckSkillRequirementAction, 'conditions'))
        self.assertTrue(hasattr(CheckSkillRequirementAction, 'reactions'))
        self.assertTrue(hasattr(CheckSkillRequirementAction, 'weights'))

    def test_goap_conditions(self):
        """Test GOAP conditions are properly defined."""
        expected_conditions = {"character_alive": True}
        self.assertEqual(CheckSkillRequirementAction.conditions, expected_conditions)

    def test_goap_reactions(self):
        """Test GOAP reactions are properly defined."""
        expected_reactions = {
            "skill_requirements_checked": True,
            "skill_level_sufficient": True,
            "required_skill_level_known": True,
            "need_skill_upgrade": True
        }
        self.assertEqual(CheckSkillRequirementAction.reactions, expected_reactions)

    def test_goap_weights(self):
        """Test GOAP weights are properly defined."""
        expected_weights = {"skill_requirements_checked": 10}
        self.assertEqual(CheckSkillRequirementAction.weights, expected_weights)


if __name__ == '__main__':
    unittest.main()