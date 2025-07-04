"""Test module for FindCorrectWorkshopAction."""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.find_correct_workshop import FindCorrectWorkshopAction

from test.fixtures import (
    MockActionContext,
    MockKnowledgeBase,
    MockMapState,
    cleanup_test_environment,
    create_mock_client,
    create_test_environment,
)


class TestFindCorrectWorkshopAction(unittest.TestCase):
    """Test cases for FindCorrectWorkshopAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir, self.original_data_prefix = create_test_environment()
        
        self.item_code = "copper_sword"
        self.character_name = "test_character"
        self.action = FindCorrectWorkshopAction()
        self.client = create_mock_client()

    def tearDown(self):
        """Clean up test fixtures."""
        cleanup_test_environment(self.temp_dir, self.original_data_prefix)

    def test_find_correct_workshop_action_initialization(self):
        """Test FindCorrectWorkshopAction initialization."""
        # Action no longer has attributes since it uses ActionContext
        self.assertIsInstance(self.action, FindCorrectWorkshopAction)

    def test_find_correct_workshop_action_initialization_defaults(self):
        """Test FindCorrectWorkshopAction initialization with defaults."""
        action = FindCorrectWorkshopAction()
        self.assertIsInstance(action, FindCorrectWorkshopAction)

    def test_find_correct_workshop_action_repr(self):
        """Test FindCorrectWorkshopAction string representation."""
        expected = "FindCorrectWorkshopAction()"
        self.assertEqual(repr(self.action), expected)

    def test_find_correct_workshop_action_repr_no_character(self):
        """Test FindCorrectWorkshopAction string representation without character."""
        action = FindCorrectWorkshopAction()
        expected = "FindCorrectWorkshopAction()"
        self.assertEqual(repr(action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        context = MockActionContext(
            character_name=self.character_name,
            item_code=self.item_code
        )
        result = self.action.execute(None, context)
        # With centralized validation, None client triggers validation error
        self.assertFalse(result.success)
        # Direct action execution bypasses centralized validation
        self.assertTrue(hasattr(result, 'error'))

    def test_execute_no_item_code(self):
        """Test execute fails without item_code."""
        context = MockActionContext(
            character_name=self.character_name
            # No item_code provided
        )
        result = self.action.execute(self.client, context)
        self.assertFalse(result.success)
        self.assertIn('No item code specified', result.error)

    @patch('src.controller.actions.find_correct_workshop.get_item_api')
    def test_execute_item_api_fails(self, mock_get_item_api):
        """Test execute when item API fails."""
        mock_get_item_api.return_value = None
        
        context = MockActionContext(
            character_name=self.character_name,
            item_code=self.item_code,
            search_radius=5
        )
        result = self.action.execute(self.client, context)
        self.assertFalse(result.success)
        self.assertIn('Could not get details for item', result.error)

    @patch('src.controller.actions.find_correct_workshop.get_item_api')
    def test_execute_item_api_no_data(self, mock_get_item_api):
        """Test execute when item API returns no data."""
        mock_response = Mock()
        mock_response.data = None
        mock_get_item_api.return_value = mock_response
        
        context = MockActionContext(
            character_name=self.character_name,
            item_code=self.item_code,
            search_radius=5
        )
        result = self.action.execute(self.client, context)
        self.assertFalse(result.success)
        self.assertIn('Could not get details for item', result.error)

    @patch('src.controller.actions.find_correct_workshop.get_item_api')
    def test_execute_no_craft_requirements(self, mock_get_item_api):
        """Test execute when item has no craft requirements."""
        # Mock item without craft requirements
        mock_item_data = Mock()
        mock_item_data.craft = None
        mock_item_response = Mock()
        mock_item_response.data = mock_item_data
        mock_get_item_api.return_value = mock_item_response
        
        context = MockActionContext(
            character_name=self.character_name,
            item_code=self.item_code,
            search_radius=5
        )
        result = self.action.execute(self.client, context)
        self.assertFalse(result.success)
        self.assertIn('does not have crafting information', result.error)

    @patch('src.controller.actions.find_correct_workshop.get_item_api')
    def test_execute_item_api_no_craft_data(self, mock_get_item_api):
        """Test execute when item has no craft data."""
        # Mock item without craft requirements
        mock_item_data = Mock()
        mock_item_data.craft = None
        mock_item_response = Mock()
        mock_item_response.data = mock_item_data
        mock_get_item_api.return_value = mock_item_response
        
        context = MockActionContext(
            character_name=self.character_name,
            item_code=self.item_code,
            search_radius=5
        )
        result = self.action.execute(self.client, context)
        self.assertFalse(result.success)
        self.assertIn('does not have crafting information', result.error)

    @patch('src.controller.actions.find_correct_workshop.get_item_api')
    def test_execute_success_workshop_found(self, mock_get_item_api):
        """Test successful execution when workshop is found."""
        # Mock item with craft requirements
        mock_craft = Mock()
        mock_craft.skill = 'weaponcrafting'
        mock_item_data = Mock()
        mock_item_data.craft = mock_craft
        mock_item_response = Mock()
        mock_item_response.data = mock_item_data
        mock_get_item_api.return_value = mock_item_response
        
        # Mock unified_search to return success
        with patch.object(self.action, 'unified_search') as mock_unified_search:
            from src.controller.actions.base import ActionResult
            mock_result = ActionResult(success=True)
            mock_result.data = {
                'workshop_code': 'weaponcrafting',
                'workshop_type': 'weaponcrafting',
                'location': (12, 15),
                'target_x': 12,
                'target_y': 15,
                'required_skill': 'weaponcrafting',
                'item_code': 'copper_sword'
            }
            mock_unified_search.return_value = mock_result
            
            context = MockActionContext(
                character_name=self.character_name,
                item_code=self.item_code,
                search_radius=5,
                knowledge_base=MockKnowledgeBase(),
                map_state=MockMapState()
            )
            result = self.action.execute(self.client, context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.data['item_code'], 'copper_sword')
        self.assertEqual(result.data['required_skill'], 'weaponcrafting')
        self.assertEqual(result.data['workshop_type'], 'weaponcrafting')
        self.assertEqual(result.data['location'], (12, 15))

    @patch('src.controller.actions.find_correct_workshop.get_item_api')
    def test_execute_workshop_not_found(self, mock_get_item_api):
        """Test execution when workshop is not found."""
        # Mock item with craft requirements
        mock_craft = Mock()
        mock_craft.skill = 'weaponcrafting'
        mock_item_data = Mock()
        mock_item_data.craft = mock_craft
        mock_item_response = Mock()
        mock_item_response.data = mock_item_data
        mock_get_item_api.return_value = mock_item_response
        
        # Mock unified_search to return failure
        with patch.object(self.action, 'unified_search') as mock_unified_search:
            mock_unified_search.return_value = None  # unified_search returns None when no workshop found
            
            context = MockActionContext(
                character_name=self.character_name,
                item_code=self.item_code,
                search_radius=5,
                knowledge_base=MockKnowledgeBase(),
                map_state=MockMapState()
            )
            result = self.action.execute(self.client, context)
        self.assertFalse(result.success)
        self.assertIn('No weaponcrafting workshop found', result.error)

    def test_execute_exception_handling(self):
        """Test exception handling during execution."""
        context = MockActionContext(
            character_name=self.character_name,
            item_code=self.item_code,
            search_radius=5
        )
        
        with patch('src.controller.actions.find_correct_workshop.get_item_api', side_effect=Exception("API Error")):
            result = self.action.execute(self.client, context)
            self.assertFalse(result.success)
            self.assertIn('Workshop search failed: API Error', result.error)

    def test_execute_has_goap_attributes(self):
        """Test that FindCorrectWorkshopAction has expected GOAP attributes."""
        self.assertTrue(hasattr(FindCorrectWorkshopAction, 'conditions'))
        self.assertTrue(hasattr(FindCorrectWorkshopAction, 'reactions'))
        self.assertTrue(hasattr(FindCorrectWorkshopAction, 'weight'))
    
    def test_goap_conditions(self):
        """Test GOAP conditions are properly defined."""
        self.assertIn('character_status', FindCorrectWorkshopAction.conditions)
        self.assertTrue(FindCorrectWorkshopAction.conditions['character_status']['alive'])
        self.assertFalse(FindCorrectWorkshopAction.conditions['character_status']['cooldown_active'])
    
    def test_goap_reactions(self):
        """Test GOAP reactions are properly defined."""
        self.assertIsInstance(FindCorrectWorkshopAction.reactions, dict)
    
    def test_goap_weights(self):
        """Test GOAP weights are properly defined."""
        expected_weight = FindCorrectWorkshopAction.weight
        self.assertIsInstance(expected_weight, (int, float))


if __name__ == '__main__':
    unittest.main()