"""Test module for CraftItemAction."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from src.controller.actions.craft_item import CraftItemAction


class TestCraftItemAction(unittest.TestCase):
    """Test cases for CraftItemAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.character_name = "TestCharacter"
        self.item_code = "copper_sword"
        self.quantity = 2
        self.action = CraftItemAction(self.character_name, self.item_code, self.quantity)
        
        # Mock client
        self.mock_client = Mock()
        
        # Mock character response
        self.mock_character_data = Mock()
        self.mock_character_data.x = 5
        self.mock_character_data.y = 3
        
        self.mock_character_response = Mock()
        self.mock_character_response.data = self.mock_character_data
        self.mock_client._character_cache = self.mock_character_response

    def test_craft_item_action_initialization(self):
        """Test CraftItemAction initialization."""
        self.assertEqual(self.action.character_name, self.character_name)
        self.assertEqual(self.action.item_code, self.item_code)
        self.assertEqual(self.action.quantity, self.quantity)

    def test_craft_item_action_initialization_default_quantity(self):
        """Test CraftItemAction initialization with default quantity."""
        action = CraftItemAction(self.character_name, self.item_code)
        self.assertEqual(action.quantity, 1)

    def test_craft_item_action_repr(self):
        """Test CraftItemAction string representation."""
        expected = f"CraftItemAction({self.character_name}, {self.item_code}, qty={self.quantity})"
        self.assertEqual(repr(self.action), expected)

    def test_execute_no_client(self):
        """Test crafting fails without client."""
        result = self.action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    @patch('src.controller.actions.craft_item.get_character_api')
    def test_execute_no_character_cache(self, mock_get_character_api):
        """Test crafting fails without character data."""
        mock_client = Mock()
        mock_client._character_cache = None
        mock_get_character_api.return_value = None
        
        result = self.action.execute(mock_client)
        self.assertFalse(result['success'])
        self.assertIn('No character data available', result['error'])

    @patch('src.controller.actions.craft_item.get_map_api')
    def test_execute_map_api_fails(self, mock_get_map_api):
        """Test crafting fails when map API fails."""
        mock_get_map_api.return_value = None
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn('Could not get map information', result['error'])
        self.assertEqual(result['location'], (5, 3))

    @patch('src.controller.actions.craft_item.get_map_api')
    def test_execute_map_api_no_data(self, mock_get_map_api):
        """Test crafting fails when map API returns no data."""
        mock_response = Mock()
        mock_response.data = None
        mock_get_map_api.return_value = mock_response
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn('Could not get map information', result['error'])

    @patch('src.controller.actions.craft_item.get_map_api')
    def test_execute_no_workshop_at_location(self, mock_get_map_api):
        """Test crafting fails when no workshop at location."""
        # Mock map data without workshop
        mock_map_data = Mock()
        mock_map_data.content = None
        
        mock_response = Mock()
        mock_response.data = mock_map_data
        mock_get_map_api.return_value = mock_response
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn('No workshop available at current location', result['error'])

    @patch('src.controller.actions.craft_item.get_character_api')
    @patch('src.controller.actions.craft_item.get_map_api')
    def test_execute_wrong_content_type(self, mock_get_map_api, mock_get_character_api):
        """Test crafting fails when location has wrong content type."""
        # Mock character API response
        mock_character_data = Mock()
        mock_character_data.x = 5
        mock_character_data.y = 3
        
        mock_character_response = Mock()
        mock_character_response.data = mock_character_data
        mock_get_character_api.return_value = mock_character_response
        
        # Mock map data with non-workshop content
        mock_content = Mock()
        mock_content.type_ = 'bank'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_response = Mock()
        mock_response.data = mock_map_data
        mock_get_map_api.return_value = mock_response
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn('No workshop available at current location', result['error'])

    @patch('src.controller.actions.craft_item.get_item_api')
    @patch('src.controller.actions.craft_item.get_map_api')
    def test_execute_item_api_fails(self, mock_get_map_api, mock_get_item_api):
        """Test crafting fails when item API fails."""
        # Mock map data with workshop
        mock_content = Mock()
        mock_content.type_ = 'workshop'
        mock_content.code = 'weaponcrafting'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map_api.return_value = mock_map_response
        
        # Mock item API failure
        mock_get_item_api.return_value = None
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn(f'Could not get details for item {self.item_code}', result['error'])

    @patch('src.controller.actions.craft_item.get_item_api')
    @patch('src.controller.actions.craft_item.get_map_api')
    def test_execute_item_api_no_data(self, mock_get_map_api, mock_get_item_api):
        """Test crafting fails when item API returns no data."""
        # Mock map data with workshop
        mock_content = Mock()
        mock_content.type_ = 'workshop'
        mock_content.code = 'weaponcrafting'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map_api.return_value = mock_map_response
        
        # Mock item API with no data
        mock_item_response = Mock()
        mock_item_response.data = None
        mock_get_item_api.return_value = mock_item_response
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn(f'Could not get details for item {self.item_code}', result['error'])

    @patch('src.controller.actions.craft_item.crafting_api')
    @patch('src.controller.actions.craft_item.get_item_api')
    @patch('src.controller.actions.craft_item.get_map_api')
    def test_execute_crafting_api_fails(self, mock_get_map_api, mock_get_item_api, mock_crafting_api):
        """Test crafting fails when crafting API fails."""
        self._setup_successful_mocks(mock_get_map_api, mock_get_item_api)
        
        # Mock crafting API failure
        mock_crafting_api.return_value = None
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn('Crafting action failed - no response data', result['error'])

    @patch('src.controller.actions.craft_item.crafting_api')
    @patch('src.controller.actions.craft_item.get_item_api')
    @patch('src.controller.actions.craft_item.get_map_api')
    def test_execute_crafting_api_no_data(self, mock_get_map_api, mock_get_item_api, mock_crafting_api):
        """Test crafting fails when crafting API returns no data."""
        self._setup_successful_mocks(mock_get_map_api, mock_get_item_api)
        
        # Mock crafting API with no data
        mock_crafting_response = Mock()
        mock_crafting_response.data = None
        mock_crafting_api.return_value = mock_crafting_response
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn('Crafting action failed - no response data', result['error'])

    @patch('src.controller.actions.craft_item.crafting_api')
    @patch('src.controller.actions.craft_item.get_item_api')
    @patch('src.controller.actions.craft_item.get_map_api')
    def test_execute_success_minimal_data(self, mock_get_map_api, mock_get_item_api, mock_crafting_api):
        """Test successful crafting with minimal response data."""
        self._setup_successful_mocks(mock_get_map_api, mock_get_item_api)
        
        # Mock crafting response with minimal data using spec to control attributes
        mock_skill_data = Mock(spec=[])
        # Set only the attributes we want to exist
        mock_skill_data.xp = 0
        mock_skill_data.skill = 'unknown'
        
        mock_crafting_response = Mock()
        mock_crafting_response.data = mock_skill_data
        mock_crafting_api.return_value = mock_crafting_response
        
        result = self.action.execute(self.mock_client)
        self.assertTrue(result['success'])
        self.assertEqual(result['item_code'], self.item_code)
        self.assertEqual(result['quantity_crafted'], self.quantity)
        self.assertEqual(result['workshop_code'], 'weaponcrafting')
        self.assertEqual(result['location'], (5, 3))

    @patch('src.controller.actions.craft_item.crafting_api')
    @patch('src.controller.actions.craft_item.get_item_api')
    @patch('src.controller.actions.craft_item.get_map_api')
    def test_execute_success_full_data(self, mock_get_map_api, mock_get_item_api, mock_crafting_api):
        """Test successful crafting with full response data."""
        self._setup_successful_mocks(mock_get_map_api, mock_get_item_api)
        
        # Mock crafting response with full data
        mock_cooldown = Mock()
        mock_cooldown.total_seconds = 30
        
        mock_character = Mock()
        mock_character.level = 15
        mock_character.hp = 80
        mock_character.max_hp = 100
        
        mock_produced_item = Mock()
        mock_produced_item.code = 'copper_sword'
        mock_produced_item.quantity = 1
        
        mock_consumed_item = Mock()
        mock_consumed_item.code = 'copper'
        mock_consumed_item.quantity = 2
        
        mock_details = Mock()
        mock_details.items = [mock_produced_item]
        mock_details.consumed = [mock_consumed_item]
        
        mock_skill_data = Mock()
        mock_skill_data.cooldown = mock_cooldown
        mock_skill_data.xp = 25
        mock_skill_data.skill = 'weaponcrafting'
        mock_skill_data.character = mock_character
        mock_skill_data.details = mock_details
        
        mock_crafting_response = Mock()
        mock_crafting_response.data = mock_skill_data
        mock_crafting_api.return_value = mock_crafting_response
        
        result = self.action.execute(self.mock_client)
        self.assertTrue(result['success'])
        self.assertEqual(result['cooldown'], 30)
        self.assertEqual(result['xp_gained'], 25)
        self.assertEqual(result['skill'], 'weaponcrafting')
        self.assertEqual(result['character_level'], 15)
        self.assertEqual(result['character_hp'], 80)
        self.assertEqual(result['character_max_hp'], 100)
        self.assertEqual(len(result['items_produced']), 1)
        self.assertEqual(result['items_produced'][0]['code'], 'copper_sword')
        self.assertEqual(len(result['materials_consumed']), 1)
        self.assertEqual(result['materials_consumed'][0]['code'], 'copper')

    @patch('src.controller.actions.craft_item.get_map_api')
    def test_execute_exception_handling(self, mock_get_map_api):
        """Test exception handling during crafting."""
        mock_get_map_api.side_effect = Exception("Network error")
        
        result = self.action.execute(self.mock_client)
        self.assertFalse(result['success'])
        self.assertIn('Crafting action failed: Network error', result['error'])

    def test_execute_has_goap_attributes(self):
        """Test that CraftItemAction has expected GOAP attributes."""
        self.assertTrue(hasattr(CraftItemAction, 'conditions'))
        self.assertTrue(hasattr(CraftItemAction, 'reactions'))
        self.assertTrue(hasattr(CraftItemAction, 'weights'))
        self.assertTrue(hasattr(CraftItemAction, 'g'))

    def _setup_successful_mocks(self, mock_get_map_api, mock_get_item_api):
        """Helper method to setup successful mock responses."""
        # Mock map data with workshop
        mock_content = Mock()
        mock_content.type_ = 'workshop'
        mock_content.code = 'weaponcrafting'  # Must match the required skill
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map_api.return_value = mock_map_response
        
        # Mock item data with matching craft skill
        mock_craft = Mock()
        mock_craft.skill = 'weaponcrafting'  # Must match workshop code
        
        mock_item_data = Mock()
        mock_item_data.name = 'Copper Sword'
        mock_item_data.craft = mock_craft
        
        mock_item_response = Mock()
        mock_item_response.data = mock_item_data
        mock_get_item_api.return_value = mock_item_response


if __name__ == '__main__':
    unittest.main()