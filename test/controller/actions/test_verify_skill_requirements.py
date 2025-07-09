"""Test module for VerifySkillRequirementsAction."""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.verify_skill_requirements import VerifySkillRequirementsAction
from src.controller.actions.base import ActionResult
from src.lib.action_context import ActionContext
from test.fixtures import MockActionContext, create_mock_client


class TestVerifySkillRequirementsAction(unittest.TestCase):
    """Test cases for VerifySkillRequirementsAction class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.action = VerifySkillRequirementsAction()
        self.mock_client = create_mock_client()
        self.character_name = "TestCharacter"
        
    def test_init(self):
        """Test initialization."""
        action = VerifySkillRequirementsAction()
        self.assertIsInstance(action, VerifySkillRequirementsAction)
        
        # Check GOAP parameters
        self.assertEqual(action.conditions['equipment_status']['has_selected_item'], True)
        self.assertEqual(action.conditions['materials']['status'], 'sufficient')
        self.assertEqual(action.reactions['skill_requirements']['verified'], True)
        self.assertEqual(action.weight, 1.0)
    
    def test_execute_no_selected_item(self):
        """Test execution when no selected item."""
        context = MockActionContext(character_name=self.character_name)
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "No selected item available")
    
    @patch('src.controller.actions.verify_skill_requirements.get_character_api')
    def test_execute_no_character_response(self, mock_get_character):
        """Test execution when character API returns no response."""
        mock_get_character.return_value = None
        
        context = MockActionContext(
            character_name=self.character_name,
            selected_item="copper_sword"
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Could not get character data")
    
    @patch('src.controller.actions.verify_skill_requirements.get_character_api')
    def test_execute_skill_sufficient(self, mock_get_character):
        """Test execution when skill is sufficient."""
        # Mock character data with weaponcrafting skill
        mock_char_data = Mock()
        mock_char_data.weaponcrafting_level = 5
        
        mock_response = Mock()
        mock_response.data = mock_char_data
        mock_get_character.return_value = mock_response
        
        context = MockActionContext(
            character_name=self.character_name,
            selected_item="copper_sword",
            selected_recipe={'workshop': 'weaponcrafting'}
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Skill verification completed: weaponcrafting 5/1")
        self.assertTrue(result.data['skill_sufficient'])
        self.assertEqual(result.data['current_level'], 5)
        self.assertEqual(result.data['required_level'], 1)
        self.assertEqual(result.data['shortfall'], 0)
        self.assertEqual(result.state_changes['skill_requirements']['sufficient'], True)
        
        # Check context was updated via set_result call
        # MockActionContext doesn't have get_result, but we can verify set_result was called
        # The actual context update happens in the action
    
    @patch('src.controller.actions.verify_skill_requirements.get_character_api')
    def test_execute_skill_insufficient(self, mock_get_character):
        """Test execution when skill is insufficient."""
        # Mock character data with low skill level
        mock_char_data = Mock()
        mock_char_data.mining_level = 2
        
        mock_response = Mock()
        mock_response.data = mock_char_data
        mock_get_character.return_value = mock_response
        
        # Mock recipe that requires level 5
        context = MockActionContext(
            character_name=self.character_name,
            selected_item="iron_ore",
            selected_recipe={'workshop': 'mining'}
        )
        
        # Override the skill requirements method to return higher level
        with patch.object(self.action, '_get_skill_requirements', return_value={'skill': 'mining', 'level': 5}):
            result = self.action.execute(self.mock_client, context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Skill verification completed: mining 2/5")
        self.assertFalse(result.data['skill_sufficient'])
        self.assertEqual(result.data['shortfall'], 3)
        self.assertEqual(result.state_changes['skill_requirements']['sufficient'], False)
    
    @patch('src.controller.actions.verify_skill_requirements.get_character_api')
    def test_execute_no_skill_requirements(self, mock_get_character):
        """Test execution when can't determine skill requirements."""
        mock_char_data = Mock()
        mock_response = Mock()
        mock_response.data = mock_char_data
        mock_get_character.return_value = mock_response
        
        context = MockActionContext(
            character_name=self.character_name,
            selected_item="unknown_item"
        )
        
        # Mock _get_skill_requirements to return None
        with patch.object(self.action, '_get_skill_requirements', return_value=None):
            result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Could not determine skill requirements for unknown_item")
    
    def test_execute_with_exception(self):
        """Test execution with exception handling."""
        context = MockActionContext(
            character_name=self.character_name,
            selected_item="copper_sword"
        )
        
        # Mock exception in get_character_api
        with patch('src.controller.actions.verify_skill_requirements.get_character_api', side_effect=Exception("API error")):
            result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Skill verification failed: API error")
    
    def test_get_skill_requirements_from_recipe(self):
        """Test _get_skill_requirements with recipe data."""
        recipe = {'workshop': 'weaponcrafting'}
        context = MockActionContext()
        
        result = self.action._get_skill_requirements(recipe, 'copper_sword', context)
        
        self.assertEqual(result['skill'], 'weaponcrafting')
        self.assertEqual(result['level'], 1)
    
    def test_get_skill_requirements_from_knowledge_base(self):
        """Test _get_skill_requirements with knowledge base."""
        # Mock knowledge base
        mock_kb = Mock()
        mock_kb.get_item_data.return_value = {
            'craft': {
                'skill': 'jewelcrafting',
                'level': 3
            }
        }
        
        context = MockActionContext()
        context.knowledge_base = mock_kb
        
        result = self.action._get_skill_requirements({}, 'ruby_ring', context)
        
        self.assertEqual(result['skill'], 'jewelcrafting')
        self.assertEqual(result['level'], 3)
    
    def test_get_skill_requirements_no_craft_info(self):
        """Test _get_skill_requirements when no craft info available."""
        mock_kb = Mock()
        mock_kb.get_item_data.return_value = {'name': 'Item'}  # No craft info
        
        context = MockActionContext()
        context.knowledge_base = mock_kb
        
        result = self.action._get_skill_requirements({}, 'some_item', context)
        
        self.assertIsNone(result)
    
    def test_get_skill_requirements_exception(self):
        """Test _get_skill_requirements with exception."""
        recipe = {'workshop': 'broken'}
        context = MockActionContext()
        
        # Mock workshop_to_skill to raise exception
        with patch.object(self.action, '_workshop_to_skill', side_effect=Exception("Error")):
            result = self.action._get_skill_requirements(recipe, 'item', context)
        
        self.assertIsNone(result)
    
    def test_workshop_to_skill(self):
        """Test _workshop_to_skill method."""
        self.assertEqual(self.action._workshop_to_skill('WeaponCrafting'), 'weaponcrafting')
        self.assertEqual(self.action._workshop_to_skill('MINING'), 'mining')
        self.assertEqual(self.action._workshop_to_skill('cooking'), 'cooking')
    
    def test_get_fallback_skill(self):
        """Test _get_fallback_skill method."""
        result = self.action._get_fallback_skill('any_item')
        self.assertIsNone(result)
    
    def test_get_character_skill_level_direct_attribute(self):
        """Test _get_character_skill_level with direct attribute."""
        mock_char = Mock()
        mock_char.mining_level = 7
        
        level = self.action._get_character_skill_level(mock_char, 'mining')
        self.assertEqual(level, 7)
    
    def test_get_character_skill_level_camel_case(self):
        """Test _get_character_skill_level with camelCase attribute."""
        mock_char = Mock()
        mock_char.miningLevel = 8
        
        level = self.action._get_character_skill_level(mock_char, 'mining')
        self.assertEqual(level, 8)
    
    def test_get_character_skill_level_plain_attribute(self):
        """Test _get_character_skill_level with plain attribute name."""
        mock_char = Mock()
        mock_char.woodcutting = 10
        
        level = self.action._get_character_skill_level(mock_char, 'woodcutting')
        self.assertEqual(level, 10)
    
    def test_get_character_skill_level_from_skills_dict(self):
        """Test _get_character_skill_level from skills dictionary."""
        mock_char = Mock()
        mock_char.skills = {'fishing': 15}
        
        # Need to ensure hasattr returns False for direct attributes
        mock_char.fishing_level = Mock()  # This will be non-integer
        del mock_char.fishingLevel  # Remove camelCase
        del mock_char.fishing  # Remove plain
        
        level = self.action._get_character_skill_level(mock_char, 'fishing')
        self.assertEqual(level, 15)
    
    def test_get_character_skill_level_not_found(self):
        """Test _get_character_skill_level when skill not found."""
        mock_char = Mock()
        # No matching attributes
        
        level = self.action._get_character_skill_level(mock_char, 'unknown_skill')
        self.assertEqual(level, 1)  # Default
    
    def test_get_character_skill_level_non_integer(self):
        """Test _get_character_skill_level with non-integer attribute."""
        mock_char = Mock()
        mock_char.cooking_level = "not_an_int"
        mock_char.cookingLevel = None
        mock_char.cooking = 5.5  # Float
        
        level = self.action._get_character_skill_level(mock_char, 'cooking')
        self.assertEqual(level, 1)  # Default when no valid integer found
    
    def test_get_character_skill_level_exception(self):
        """Test _get_character_skill_level with exception."""
        # Create a class that raises exception when accessing skill attributes
        class ExceptionChar:
            def __getattr__(self, name):
                if name in ['mining_level', 'miningLevel', 'mining', 'skills']:
                    raise Exception("Error accessing attribute")
                raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
            
            def __hasattr__(self, name):
                # Make hasattr return True for the attributes we want to test
                return name in ['mining_level', 'miningLevel', 'mining', 'skills']
        
        # Create instance that will raise exception
        mock_char = ExceptionChar()
        
        # Override hasattr to return True for our test attributes
        with patch('builtins.hasattr', side_effect=lambda obj, name: name in ['mining_level', 'miningLevel', 'mining', 'skills']):
            level = self.action._get_character_skill_level(mock_char, 'mining')
        
        self.assertEqual(level, 1)  # Default on error
    
    def test_repr(self):
        """Test __repr__ method."""
        self.assertEqual(repr(self.action), "VerifySkillRequirementsAction()")
    
    @patch('src.controller.actions.verify_skill_requirements.get_character_api')
    def test_reactions_update_sufficient(self, mock_get_character):
        """Test that reactions are updated when skill is sufficient."""
        mock_char_data = Mock()
        mock_char_data.crafting_level = 10
        
        mock_response = Mock()
        mock_response.data = mock_char_data
        mock_get_character.return_value = mock_response
        
        context = MockActionContext(
            character_name=self.character_name,
            selected_item="item",
            selected_recipe={'workshop': 'crafting'}
        )
        
        # Check initial reactions
        initial_reactions = dict(self.action.reactions)
        
        result = self.action.execute(self.mock_client, context)
        
        # Reactions should be updated
        self.assertEqual(self.action.reactions['skill_requirements']['sufficient'], True)
    
    @patch('src.controller.actions.verify_skill_requirements.get_character_api')
    def test_reactions_update_insufficient(self, mock_get_character):
        """Test that reactions are updated when skill is insufficient."""
        mock_char_data = Mock()
        mock_char_data.crafting_level = 1
        
        mock_response = Mock()
        mock_response.data = mock_char_data
        mock_get_character.return_value = mock_response
        
        context = MockActionContext(
            character_name=self.character_name,
            selected_item="item",
            selected_recipe={'workshop': 'crafting'}
        )
        
        # Mock higher requirement
        with patch.object(self.action, '_get_skill_requirements', return_value={'skill': 'crafting', 'level': 5}):
            result = self.action.execute(self.mock_client, context)
        
        # Reactions should be updated
        self.assertEqual(self.action.reactions['skill_requirements']['sufficient'], False)


if __name__ == '__main__':
    unittest.main()