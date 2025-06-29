"""Test module for FindCorrectWorkshopAction."""

import unittest
import tempfile
import os
from unittest.mock import Mock, patch
from src.controller.actions.find_correct_workshop import FindCorrectWorkshopAction


class TestFindCorrectWorkshopAction(unittest.TestCase):
    """Test cases for FindCorrectWorkshopAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_prefix = os.environ.get('DATA_PREFIX', '')
        os.environ['DATA_PREFIX'] = self.temp_dir
        
        self.item_code = "copper_sword"
        self.character_name = "test_character"
        self.action = FindCorrectWorkshopAction(
            item_code=self.item_code,
            character_name=self.character_name,
            search_radius=5
        )

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['DATA_PREFIX'] = self.original_data_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_find_correct_workshop_action_initialization(self):
        """Test FindCorrectWorkshopAction initialization."""
        self.assertEqual(self.action.item_code, "copper_sword")
        self.assertEqual(self.action.character_name, "test_character")
        self.assertEqual(self.action.search_radius, 5)

    def test_find_correct_workshop_action_initialization_defaults(self):
        """Test FindCorrectWorkshopAction initialization with defaults."""
        action = FindCorrectWorkshopAction(item_code="iron_dagger")
        self.assertEqual(action.item_code, "iron_dagger")
        self.assertEqual(action.search_radius, 10)

    def test_find_correct_workshop_action_repr(self):
        """Test FindCorrectWorkshopAction string representation."""
        expected = "FindCorrectWorkshopAction(0, 0, radius=5, item=copper_sword)"
        self.assertEqual(repr(self.action), expected)

    def test_find_correct_workshop_action_repr_no_character(self):
        """Test FindCorrectWorkshopAction string representation without character."""
        action = FindCorrectWorkshopAction(item_code="iron_dagger")
        expected = "FindCorrectWorkshopAction(0, 0, radius=10, item=iron_dagger)"
        self.assertEqual(repr(action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        result = self.action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    @patch('src.controller.actions.find_correct_workshop.get_item_api')
    def test_execute_item_api_fails(self, mock_get_item_api):
        """Test execute when item API fails."""
        mock_get_item_api.return_value = None
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Could not get details for item', result['error'])

    @patch('src.controller.actions.find_correct_workshop.get_item_api')
    def test_execute_item_api_no_data(self, mock_get_item_api):
        """Test execute when item API returns no data."""
        mock_response = Mock()
        mock_response.data = None
        mock_get_item_api.return_value = mock_response
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Could not get details for item', result['error'])

    @patch('src.controller.actions.find_correct_workshop.get_item_api')
    def test_execute_no_craft_requirements(self, mock_get_item_api):
        """Test execute when item has no craft requirements."""
        # Mock item without craft requirements
        mock_item_data = Mock()
        mock_item_data.craft = None
        mock_item_response = Mock()
        mock_item_response.data = mock_item_data
        mock_get_item_api.return_value = mock_item_response
        
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('does not have crafting information', result['error'])

    @patch('src.controller.actions.find_correct_workshop.get_character_api')
    @patch('src.controller.actions.find_correct_workshop.get_item_api')
    def test_execute_character_api_fails(self, mock_get_item_api, mock_get_character_api):
        """Test execute when character API fails."""
        # Mock item with craft requirements
        mock_craft = Mock()
        mock_craft.skill = 'weaponcrafting'
        mock_item_data = Mock()
        mock_item_data.craft = mock_craft
        mock_item_response = Mock()
        mock_item_response.data = mock_item_data
        mock_get_item_api.return_value = mock_item_response
        
        # Mock character API failure
        mock_get_character_api.return_value = None
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Could not retrieve character location', result['error'])

    @patch('src.controller.actions.find_correct_workshop.FindWorkshopsAction')
    @patch('src.controller.actions.find_correct_workshop.get_character_api')
    @patch('src.controller.actions.find_correct_workshop.get_item_api')
    def test_execute_success_workshop_found(self, mock_get_item_api, mock_get_character_api, mock_find_workshops_action_class):
        """Test successful execution when workshop is found."""
        # Mock item with craft requirements
        mock_craft = Mock()
        mock_craft.skill = 'weaponcrafting'
        mock_item_data = Mock()
        mock_item_data.craft = mock_craft
        mock_item_response = Mock()
        mock_item_response.data = mock_item_data
        mock_get_item_api.return_value = mock_item_response
        
        # Mock character location
        mock_character_data = Mock()
        mock_character_data.x = 10
        mock_character_data.y = 15
        mock_character_response = Mock()
        mock_character_response.data = mock_character_data
        mock_get_character_api.return_value = mock_character_response
        
        # Mock FindWorkshopsAction success
        mock_find_workshops_action = Mock()
        mock_find_workshops_action.execute.return_value = {
            'success': True,
            'workshop_code': 'weaponcrafting',
            'location': (12, 15)
        }
        mock_find_workshops_action_class.return_value = mock_find_workshops_action
        
        client = Mock()
        
        result = self.action.execute(client)
        self.assertTrue(result['success'])
        self.assertEqual(result['item_code'], 'copper_sword')
        self.assertEqual(result['required_skill'], 'weaponcrafting')
        self.assertEqual(result['workshop_type'], 'weaponcrafting')
        self.assertEqual(result['workshop_location'], (12, 15))

    @patch('src.controller.actions.find_correct_workshop.FindWorkshopsAction')
    @patch('src.controller.actions.find_correct_workshop.get_character_api')
    @patch('src.controller.actions.find_correct_workshop.get_item_api')
    def test_execute_workshop_not_found(self, mock_get_item_api, mock_get_character_api, mock_find_workshops_action_class):
        """Test execution when workshop is not found."""
        # Mock item with craft requirements
        mock_craft = Mock()
        mock_craft.skill = 'weaponcrafting'
        mock_item_data = Mock()
        mock_item_data.craft = mock_craft
        mock_item_response = Mock()
        mock_item_response.data = mock_item_data
        mock_get_item_api.return_value = mock_item_response
        
        # Mock character location
        mock_character_data = Mock()
        mock_character_data.x = 10
        mock_character_data.y = 15
        mock_character_response = Mock()
        mock_character_response.data = mock_character_data
        mock_get_character_api.return_value = mock_character_response
        
        # Mock FindWorkshopsAction failure
        mock_find_workshops_action = Mock()
        mock_find_workshops_action.execute.return_value = {
            'success': False,
            'error': 'No workshop found'
        }
        mock_find_workshops_action_class.return_value = mock_find_workshops_action
        
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Workshop search failed', result['error'])

    def test_execute_exception_handling(self):
        """Test exception handling during execution."""
        client = Mock()
        
        with patch('src.controller.actions.find_correct_workshop.get_item_api', side_effect=Exception("API Error")):
            result = self.action.execute(client)
            self.assertFalse(result['success'])
            self.assertIn('Workshop search failed: API Error', result['error'])

    def test_execute_has_goap_attributes(self):
        """Test that FindCorrectWorkshopAction has expected GOAP attributes."""
        self.assertTrue(hasattr(FindCorrectWorkshopAction, 'conditions'))
        self.assertTrue(hasattr(FindCorrectWorkshopAction, 'reactions'))
        self.assertTrue(hasattr(FindCorrectWorkshopAction, 'weights'))
        self.assertTrue(hasattr(FindCorrectWorkshopAction, 'g'))


if __name__ == '__main__':
    unittest.main()