"""Test module for CheckSkillRequirementAction."""

import unittest
from unittest.mock import patch

from src.controller.actions.check_skill_requirement import CheckSkillRequirementAction

from test.fixtures import (
    MockActionContext,
    MockCharacterData,
    MockCraftData,
    MockCraftItem,
    MockItemData,
    MockKnowledgeBase,
    cleanup_test_environment,
    create_mock_client,
    create_test_environment,
    mock_character_response,
    mock_item_response,
)


class TestCheckSkillRequirementAction(unittest.TestCase):
    """Test cases for CheckSkillRequirementAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir, self.original_data_prefix = create_test_environment()
        
        self.character_name = "test_character"
        self.target_item = "iron_sword"
        self.action = CheckSkillRequirementAction()
        self.client = create_mock_client()

    def tearDown(self):
        """Clean up test fixtures."""
        cleanup_test_environment(self.temp_dir, self.original_data_prefix)

    def test_check_skill_requirement_action_initialization(self):
        """Test CheckSkillRequirementAction initialization."""
        # Action no longer has attributes since it uses ActionContext
        self.assertIsInstance(self.action, CheckSkillRequirementAction)

    def test_check_skill_requirement_action_repr(self):
        """Test CheckSkillRequirementAction string representation."""
        expected = "CheckSkillRequirementAction()"
        self.assertEqual(repr(self.action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        context = MockActionContext(character_name=self.character_name)
        result = self.action.execute(None, context)
        # With centralized validation, None client triggers validation error
        self.assertFalse(result.success)
        # Direct action execution bypasses centralized validation
        self.assertTrue(hasattr(result, 'error'))

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
        
        context = MockActionContext(
            character_name=self.character_name,
            task_type="crafting",
            target_item=self.target_item,
            knowledge_base=MockKnowledgeBase()
        )
        result = self.action.execute(self.client, context)
        
        self.assertTrue(result.success)
        # Check the actual keys returned by the action
        self.assertTrue(result.data.get('skill_level_sufficient'))
        self.assertEqual(result.data.get('current_skill_level'), 10)
        self.assertEqual(result.data.get('required_skill_level'), 5)

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
        
        context = MockActionContext(
            character_name=self.character_name,
            task_type="crafting",
            target_item=self.target_item,
            knowledge_base=MockKnowledgeBase()
        )
        result = self.action.execute(self.client, context)
        
        self.assertTrue(result.success)
        self.assertFalse(result.data.get('skill_level_sufficient'))
        self.assertEqual(result.data.get('current_skill_level'), 2)
        self.assertEqual(result.data.get('required_skill_level'), 5)
        self.assertEqual(result.data.get('skill_gap'), 3)

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
        
        context = MockActionContext(
            character_name=self.character_name,
            task_type="crafting",
            target_item=self.target_item,
            knowledge_base=MockKnowledgeBase()
        )
        result = self.action.execute(self.client, context)
        
        self.assertFalse(result.success)
        self.assertIn('Could not determine skill requirements', result.error)

    @patch('src.controller.actions.check_skill_requirement.get_item_api')
    @patch('src.controller.actions.check_skill_requirement.get_character_api')
    def test_execute_item_api_fails(self, mock_get_character_api, mock_get_item_api):
        """Test execute when item API fails."""
        # Mock character
        character = MockCharacterData(name=self.character_name)
        mock_get_character_api.return_value = mock_character_response(character)
        
        # Mock item API failure
        mock_get_item_api.return_value = None
        
        context = MockActionContext(
            character_name=self.character_name,
            task_type="crafting",
            target_item=self.target_item,
            knowledge_base=MockKnowledgeBase()
        )
        result = self.action.execute(self.client, context)
        
        self.assertFalse(result.success)
        self.assertIn('Could not determine skill requirements', result.error)

    @patch('src.controller.actions.check_skill_requirement.get_item_api')
    @patch('src.controller.actions.check_skill_requirement.get_character_api')
    def test_execute_item_api_no_data(self, mock_get_character_api, mock_get_item_api):
        """Test execute when item API returns no data."""
        # Mock character
        character = MockCharacterData(name=self.character_name)
        mock_get_character_api.return_value = mock_character_response(character)
        
        # Mock item API with no data
        mock_get_item_api.return_value = mock_item_response(None)
        
        context = MockActionContext(
            character_name=self.character_name,
            task_type="crafting",
            target_item=self.target_item,
            knowledge_base=MockKnowledgeBase()
        )
        result = self.action.execute(self.client, context)
        
        self.assertFalse(result.success)
        self.assertIn('Could not determine skill requirements', result.error)

    @patch('src.controller.actions.check_skill_requirement.get_character_api')
    def test_execute_character_api_fails(self, mock_get_character_api):
        """Test execute when character API fails."""
        mock_get_character_api.return_value = None
        
        context = MockActionContext(
            character_name=self.character_name,
            task_type="crafting",
            target_item=self.target_item,
            knowledge_base=MockKnowledgeBase()
        )
        result = self.action.execute(self.client, context)
        
        self.assertFalse(result.success)
        self.assertIn('Could not get character data', result.error)

    @patch('src.controller.actions.check_skill_requirement.get_item_api')
    @patch('src.controller.actions.check_skill_requirement.get_character_api')
    def test_execute_exception_handling(self, mock_get_character_api, mock_get_item_api):
        """Test exception handling during execution."""
        mock_get_character_api.side_effect = Exception("API Error")
        
        context = MockActionContext(
            character_name=self.character_name,
            task_type="crafting",
            target_item=self.target_item,
            knowledge_base=MockKnowledgeBase()
        )
        result = self.action.execute(self.client, context)
        
        self.assertFalse(result.success)
        self.assertIn('Skill requirement check failed', result.error)
        self.assertIn('API Error', result.error)

    def test_execute_has_goap_attributes(self):
        """Test that CheckSkillRequirementAction has expected GOAP attributes."""
        self.assertTrue(hasattr(CheckSkillRequirementAction, 'conditions'))
        self.assertTrue(hasattr(CheckSkillRequirementAction, 'reactions'))
        self.assertTrue(hasattr(CheckSkillRequirementAction, 'weight'))

    def test_goap_conditions(self):
        """Test GOAP conditions are properly defined."""
        self.assertIn('character_status', CheckSkillRequirementAction.conditions)
        self.assertTrue(CheckSkillRequirementAction.conditions['character_status']['alive'])

    def test_goap_reactions(self):
        """Test GOAP reactions are properly defined."""
        expected_reactions = {
            'skill_status': {
                'checked': True,
                'sufficient': True
            }
        }
        self.assertEqual(CheckSkillRequirementAction.reactions, expected_reactions)

    def test_goap_weights(self):
        """Test GOAP weights are properly defined."""
        expected_weight = CheckSkillRequirementAction.weight
        self.assertIsInstance(expected_weight, (int, float))

    @patch('src.controller.actions.check_skill_requirement.get_item_api')
    @patch('src.controller.actions.check_skill_requirement.get_character_api')
    def test_weaponcrafting_skill_states_set_correctly(self, mock_get_character_api, mock_get_item_api):
        """Test that weaponcrafting-specific states are set correctly."""
        # Create character with weaponcrafting level 2
        character_data = MockCharacterData(name=self.character_name)
        character_data.weaponcrafting_level = 2
        mock_get_character_api.return_value = mock_character_response(character_data)
        
        # Create item that requires weaponcrafting level 5
        item_data = MockItemData(code=self.target_item, name="Iron Sword", type="weapon", level=5)
        craft_data = MockCraftData(
            skill="weaponcrafting", 
            level=5,
            items=[MockCraftItem(code="iron", quantity=3)]
        )
        item_data.craft = craft_data
        mock_get_item_api.return_value = mock_item_response(item_data)
        
        context = MockActionContext(
            character_name=self.character_name,
            task_type="crafting",
            target_item=self.target_item,
            knowledge_base=MockKnowledgeBase()
        )
        result = self.action.execute(self.client, context)
        
        # Verify the result
        self.assertTrue(result.success)
        
        # Check weaponcrafting-specific states
        self.assertTrue(result.data['need_weaponcrafting_upgrade'])
        self.assertFalse(result.data['weaponcrafting_level_sufficient'])
        self.assertEqual(result.data['required_weaponcrafting_level'], 5)
        self.assertEqual(result.data['current_weaponcrafting_level'], 2)
        
        # Check general skill states
        self.assertFalse(result.data['skill_level_sufficient'])
        self.assertTrue(result.data['need_skill_upgrade'])
        self.assertEqual(result.data['required_skill'], 'weaponcrafting')
        self.assertEqual(result.data['required_skill_level'], 5)
        self.assertEqual(result.data['current_skill_level'], 2)
        self.assertEqual(result.data['skill_gap'], 3)

    @patch('src.controller.actions.check_skill_requirement.get_item_api')
    @patch('src.controller.actions.check_skill_requirement.get_character_api')
    def test_weaponcrafting_skill_sufficient(self, mock_get_character_api, mock_get_item_api):
        """Test when weaponcrafting skill is sufficient."""
        # Create character with weaponcrafting level 5
        character_data = MockCharacterData(name=self.character_name)
        character_data.weaponcrafting_level = 5
        mock_get_character_api.return_value = mock_character_response(character_data)
        
        # Create item that requires weaponcrafting level 3
        item_data = MockItemData(code=self.target_item, name="Iron Sword", type="weapon", level=5)
        craft_data = MockCraftData(
            skill="weaponcrafting", 
            level=3,
            items=[MockCraftItem(code="iron", quantity=3)]
        )
        item_data.craft = craft_data
        mock_get_item_api.return_value = mock_item_response(item_data)
        
        context = MockActionContext(
            character_name=self.character_name,
            task_type="crafting",
            target_item=self.target_item,
            knowledge_base=MockKnowledgeBase()
        )
        result = self.action.execute(self.client, context)
        
        # Verify the result
        self.assertTrue(result.success)
        
        # Check weaponcrafting-specific states
        self.assertFalse(result.data['need_weaponcrafting_upgrade'])
        self.assertTrue(result.data['weaponcrafting_level_sufficient'])
        self.assertEqual(result.data['required_weaponcrafting_level'], 3)
        self.assertEqual(result.data['current_weaponcrafting_level'], 5)
        
        # Check general skill states
        self.assertTrue(result.data['skill_level_sufficient'])
        self.assertFalse(result.data['need_skill_upgrade'])
        self.assertEqual(result.data['skill_gap'], 0)


if __name__ == '__main__':
    unittest.main()