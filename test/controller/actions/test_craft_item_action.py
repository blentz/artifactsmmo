"""Test module for CraftItemAction."""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.craft_item import CraftItemAction

from test.fixtures import MockActionContext, create_mock_client


class TestCraftItemAction(unittest.TestCase):
    """Test cases for CraftItemAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.character_name = "TestCharacter"
        self.item_code = "copper_sword"
        self.quantity = 2
        self.action = CraftItemAction()
        
        # Mock client
        self.mock_client = create_mock_client()
        
        # Mock character response
        self.mock_character_data = Mock()
        self.mock_character_data.x = 5
        self.mock_character_data.y = 3
        
        self.mock_character_response = Mock()
        self.mock_character_response.data = self.mock_character_data
        self.mock_client._character_cache = self.mock_character_response

    def test_craft_item_action_initialization(self):
        """Test CraftItemAction initialization."""
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(self.action, 'character_name'))
        self.assertFalse(hasattr(self.action, 'item_code'))
        self.assertFalse(hasattr(self.action, 'quantity'))

    def test_craft_item_action_initialization_default_quantity(self):
        """Test CraftItemAction initialization with default quantity."""
        action = CraftItemAction()
        # Action no longer stores quantity as instance attribute
        self.assertFalse(hasattr(action, 'quantity'))

    def test_craft_item_action_repr(self):
        """Test CraftItemAction string representation."""
        # Repr is now simplified
        expected = "CraftItemAction()"
        self.assertEqual(repr(self.action), expected)

    def test_execute_no_client(self):
        """Test crafting fails without client."""
        context = MockActionContext(character_name=self.character_name, item_code=self.item_code, quantity=self.quantity)
        result = self.action.execute(None, context)
        # With centralized validation, None client triggers validation error
        self.assertFalse(result.success)
        # Direct action execution bypasses centralized validation
        self.assertIsNotNone(result.error)

    @patch('src.controller.actions.craft_item.get_character_api')
    def test_execute_no_character_cache(self, mock_get_character_api):
        """Test crafting fails without character data."""
        mock_client = create_mock_client()
        mock_client._character_cache = None
        mock_get_character_api.return_value = None
        
        context = MockActionContext(character_name=self.character_name, item_code=self.item_code, quantity=self.quantity, character_x=None, character_y=None)
        result = self.action.execute(mock_client, context)
        self.assertFalse(result.success)
        self.assertIn('No character data available', result.error)

    @patch('src.controller.actions.craft_item.get_map_api')
    def test_execute_map_api_fails(self, mock_get_map_api):
        """Test crafting fails when map API fails."""
        mock_get_map_api.return_value = None
        
        context = MockActionContext(character_name=self.character_name, item_code=self.item_code, quantity=self.quantity, character_x=5, character_y=3)
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result.success)
        self.assertIn('Could not get map information', result.error)
        self.assertEqual(result.data['target_x'], 5)
        self.assertEqual(result.data['target_y'], 3)

    @patch('src.controller.actions.craft_item.get_map_api')
    def test_execute_map_api_no_data(self, mock_get_map_api):
        """Test crafting fails when map API returns no data."""
        mock_response = Mock()
        mock_response.data = None
        mock_get_map_api.return_value = mock_response
        
        context = MockActionContext(character_name=self.character_name, item_code=self.item_code, quantity=self.quantity)
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result.success)
        self.assertIn('Could not get map information', result.error)

    @patch('src.controller.actions.craft_item.get_map_api')
    def test_execute_no_workshop_at_location(self, mock_get_map_api):
        """Test crafting fails when no workshop at location."""
        # Mock map data without workshop
        mock_map_data = Mock()
        mock_map_data.content = None
        
        mock_response = Mock()
        mock_response.data = mock_map_data
        mock_get_map_api.return_value = mock_response
        
        context = MockActionContext(character_name=self.character_name, item_code=self.item_code, quantity=self.quantity)
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result.success)
        self.assertIn('Crafting action failed', result.error)

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
        
        context = MockActionContext(character_name=self.character_name, item_code=self.item_code, quantity=self.quantity)
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result.success)
        self.assertIn('Crafting action failed', result.error)

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
        
        context = MockActionContext(character_name=self.character_name, item_code=self.item_code, quantity=self.quantity)
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result.success)
        self.assertIn(f'Could not get details for item {self.item_code}', result.error)

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
        
        context = MockActionContext(character_name=self.character_name, item_code=self.item_code, quantity=self.quantity)
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result.success)
        self.assertIn(f'Could not get details for item {self.item_code}', result.error)

    @patch('src.controller.actions.craft_item.crafting_api')
    @patch('src.controller.actions.craft_item.get_item_api')
    @patch('src.controller.actions.craft_item.get_map_api')
    def test_execute_crafting_api_fails(self, mock_get_map_api, mock_get_item_api, mock_crafting_api):
        """Test crafting fails when crafting API fails."""
        self._setup_successful_mocks(mock_get_map_api, mock_get_item_api)
        
        # Mock crafting API failure
        mock_crafting_api.return_value = None
        
        context = MockActionContext(character_name=self.character_name, item_code=self.item_code, quantity=self.quantity, character_x=5, character_y=3)
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result.success)
        self.assertIn('Crafting action failed - no response data', result.error)

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
        
        context = MockActionContext(character_name=self.character_name, item_code=self.item_code, quantity=self.quantity)
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result.success)
        self.assertIn('Crafting action failed - no response data', result.error)

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
        
        context = MockActionContext(character_name=self.character_name, item_code=self.item_code, quantity=self.quantity, character_x=5, character_y=3)
        result = self.action.execute(self.mock_client, context)
        self.assertTrue(result.success)
        self.assertEqual(result.data['item_code'], self.item_code)
        self.assertEqual(result.data['quantity_crafted'], self.quantity)
        self.assertEqual(result.data['workshop_code'], 'weaponcrafting')
        self.assertEqual(result.data['target_x'], 5)
        self.assertEqual(result.data['target_y'], 3)

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
        
        context = MockActionContext(character_name=self.character_name, item_code=self.item_code, quantity=self.quantity)
        result = self.action.execute(self.mock_client, context)
        self.assertTrue(result.success)
        self.assertEqual(result.data['cooldown'], 30)
        self.assertEqual(result.data['xp_gained'], 25)
        self.assertEqual(result.data['skill'], 'weaponcrafting')
        self.assertEqual(result.data['character_level'], 15)
        self.assertEqual(result.data['character_hp'], 80)
        self.assertEqual(result.data['character_max_hp'], 100)
        self.assertEqual(len(result.data['items_produced']), 1)
        self.assertEqual(result.data['items_produced'][0]['code'], 'copper_sword')
        self.assertEqual(len(result.data['materials_consumed']), 1)
        self.assertEqual(result.data['materials_consumed'][0]['code'], 'copper')

    @patch('src.controller.actions.craft_item.get_map_api')
    def test_execute_exception_handling(self, mock_get_map_api):
        """Test exception handling during crafting."""
        mock_get_map_api.side_effect = Exception("Network error")
        
        context = MockActionContext(character_name=self.character_name, item_code=self.item_code, quantity=self.quantity)
        result = self.action.execute(self.mock_client, context)
        self.assertFalse(result.success)
        self.assertIn('Crafting action failed: Network error', result.error)

    def test_execute_has_goap_attributes(self):
        """Test that CraftItemAction has expected GOAP attributes."""
        self.assertTrue(hasattr(CraftItemAction, 'conditions'))
        self.assertTrue(hasattr(CraftItemAction, 'reactions'))
        self.assertTrue(hasattr(CraftItemAction, 'weight'))

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