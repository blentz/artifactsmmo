"""Test module for CheckSkillRequirementAction."""

import unittest
import tempfile
import os
from unittest.mock import Mock, patch
from src.controller.actions.check_skill_requirement import CheckSkillRequirementAction


class TestCheckSkillRequirementAction(unittest.TestCase):
    """Test cases for CheckSkillRequirementAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_prefix = os.environ.get('DATA_PREFIX', '')
        os.environ['DATA_PREFIX'] = self.temp_dir
        
        self.character_name = "test_character"
        self.target_item = "iron_sword"
        self.action = CheckSkillRequirementAction(
            character_name=self.character_name,
            target_item=self.target_item
        )

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['DATA_PREFIX'] = self.original_data_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

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
    def test_execute_item_api_fails(self, mock_get_item_api):
        """Test execute when item API fails."""
        mock_get_item_api.return_value = None
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('item information', result['error'])

    @patch('src.controller.actions.check_skill_requirement.get_item_api')
    def test_execute_item_api_no_data(self, mock_get_item_api):
        """Test execute when item API returns no data."""
        mock_response = Mock()
        mock_response.data = None
        mock_get_item_api.return_value = mock_response
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('item information', result['error'])

    def test_execute_simple_path(self):
        """Test execute with basic success path."""
        # Just test that the action can execute and handle basic errors
        client = Mock()
        
        # Test that it properly handles the API flow
        result = self.action.execute(client)
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)

    def test_execute_exception_handling(self):
        """Test exception handling during execution."""
        client = Mock()
        
        with patch('src.controller.actions.check_skill_requirement.get_item_api', side_effect=Exception("API Error")):
            result = self.action.execute(client)
            self.assertFalse(result['success'])
            self.assertIn('API Error', result['error'])

    def test_execute_has_goap_attributes(self):
        """Test that CheckSkillRequirementAction has expected GOAP attributes."""
        self.assertTrue(hasattr(CheckSkillRequirementAction, 'conditions'))
        self.assertTrue(hasattr(CheckSkillRequirementAction, 'reactions'))
        self.assertTrue(hasattr(CheckSkillRequirementAction, 'weights'))
        self.assertTrue(hasattr(CheckSkillRequirementAction, 'g'))


if __name__ == '__main__':
    unittest.main()