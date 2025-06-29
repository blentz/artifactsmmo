"""Test module for TransformRawMaterialsAction."""

import unittest
import tempfile
import os
from unittest.mock import Mock, patch
from src.controller.actions.transform_raw_materials import TransformRawMaterialsAction


class TestTransformRawMaterialsAction(unittest.TestCase):
    """Test cases for TransformRawMaterialsAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_prefix = os.environ.get('DATA_PREFIX', '')
        os.environ['DATA_PREFIX'] = self.temp_dir
        
        self.character_name = "test_character"
        self.target_item = "copper_sword"
        self.action = TransformRawMaterialsAction(
            character_name=self.character_name,
            target_item=self.target_item
        )

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['DATA_PREFIX'] = self.original_data_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_transform_raw_materials_action_initialization(self):
        """Test TransformRawMaterialsAction initialization."""
        self.assertEqual(self.action.character_name, "test_character")
        self.assertEqual(self.action.target_item, "copper_sword")

    def test_transform_raw_materials_action_initialization_defaults(self):
        """Test TransformRawMaterialsAction initialization with defaults."""
        action = TransformRawMaterialsAction("player")
        self.assertEqual(action.character_name, "player")
        self.assertIsNone(action.target_item)

    def test_transform_raw_materials_action_repr(self):
        """Test TransformRawMaterialsAction string representation."""
        expected = "TransformRawMaterialsAction(test_character, target=copper_sword)"
        self.assertEqual(repr(self.action), expected)

    def test_transform_raw_materials_action_repr_no_target(self):
        """Test TransformRawMaterialsAction string representation without target."""
        action = TransformRawMaterialsAction("player")
        expected = "TransformRawMaterialsAction(player, target=None)"
        self.assertEqual(repr(action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        result = self.action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    @patch('src.controller.actions.transform_raw_materials.get_character_api')
    def test_execute_character_api_fails(self, mock_get_character_api):
        """Test execute when character API fails."""
        mock_get_character_api.return_value = None
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Could not get character data', result['error'])

    @patch('src.controller.actions.transform_raw_materials.get_character_api')
    def test_execute_character_api_no_data(self, mock_get_character_api):
        """Test execute when character API returns no data."""
        mock_response = Mock()
        mock_response.data = None
        mock_get_character_api.return_value = mock_response
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Could not get character data', result['error'])

    @patch('src.controller.actions.transform_raw_materials.get_character_api')
    def test_execute_no_inventory(self, mock_get_character_api):
        """Test execute when character has no inventory."""
        mock_character_data = Mock()
        mock_character_data.x = 5
        mock_character_data.y = 10
        mock_character_data.inventory = None
        
        mock_response = Mock()
        mock_response.data = mock_character_data
        mock_get_character_api.return_value = mock_response
        
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('No inventory data available', result['error'])

    @patch('src.controller.actions.transform_raw_materials.get_character_api')
    def test_execute_empty_inventory(self, mock_get_character_api):
        """Test execute when character has empty inventory."""
        mock_character_data = Mock()
        mock_character_data.x = 5
        mock_character_data.y = 10
        mock_character_data.inventory = []
        
        mock_response = Mock()
        mock_response.data = mock_character_data
        mock_get_character_api.return_value = mock_response
        
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('No raw materials found in inventory', result['error'])

    @patch('src.controller.actions.transform_raw_materials.get_map_api')
    @patch('src.controller.actions.transform_raw_materials.get_character_api')
    def test_execute_map_api_fails(self, mock_get_character_api, mock_get_map_api):
        """Test execute when map API fails."""
        # Mock character with inventory
        mock_item = Mock()
        mock_item.code = 'copper_ore'
        mock_item.quantity = 5
        
        mock_character_data = Mock()
        mock_character_data.x = 5
        mock_character_data.y = 10
        mock_character_data.inventory = [mock_item]
        
        mock_response = Mock()
        mock_response.data = mock_character_data
        mock_get_character_api.return_value = mock_response
        
        # Mock map API failure
        mock_get_map_api.return_value = None
        
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Could not get map information', result['error'])

    @patch('src.controller.actions.transform_raw_materials.get_map_api')
    @patch('src.controller.actions.transform_raw_materials.get_character_api')
    def test_execute_no_workshop_at_location(self, mock_get_character_api, mock_get_map_api):
        """Test execute when no workshop at character location."""
        # Mock character with inventory
        mock_item = Mock()
        mock_item.code = 'copper_ore'
        mock_item.quantity = 5
        
        mock_character_data = Mock()
        mock_character_data.x = 5
        mock_character_data.y = 10
        mock_character_data.inventory = [mock_item]
        
        mock_character_response = Mock()
        mock_character_response.data = mock_character_data
        mock_get_character_api.return_value = mock_character_response
        
        # Mock map data without workshop
        mock_map_data = Mock()
        mock_map_data.content = None
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map_api.return_value = mock_map_response
        
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('No workshop available at current location', result['error'])

    @patch('src.controller.actions.transform_raw_materials.crafting_api')
    @patch('src.controller.actions.transform_raw_materials.get_map_api')
    @patch('src.controller.actions.transform_raw_materials.get_character_api')
    def test_execute_successful_transformation(self, mock_get_character_api, mock_get_map_api, mock_crafting_api):
        """Test successful raw material transformation."""
        # Mock character with raw materials
        mock_item = Mock()
        mock_item.code = 'copper_ore'
        mock_item.quantity = 5
        
        mock_character_data = Mock()
        mock_character_data.x = 5
        mock_character_data.y = 10
        mock_character_data.inventory = [mock_item]
        
        mock_character_response = Mock()
        mock_character_response.data = mock_character_data
        mock_get_character_api.return_value = mock_character_response
        
        # Mock map data with workshop
        mock_content = Mock()
        mock_content.type_ = 'workshop'
        mock_content.code = 'mining'
        
        mock_map_data = Mock()
        mock_map_data.content = mock_content
        
        mock_map_response = Mock()
        mock_map_response.data = mock_map_data
        mock_get_map_api.return_value = mock_map_response
        
        # Mock successful crafting response
        mock_crafting_data = Mock()
        mock_crafting_data.xp = 25
        mock_crafting_data.skill = 'mining'
        
        mock_crafting_response = Mock()
        mock_crafting_response.data = mock_crafting_data
        mock_crafting_api.return_value = mock_crafting_response
        
        client = Mock()
        
        result = self.action.execute(client)
        self.assertTrue(result['success'])
        self.assertIn('transformations_completed', result)
        self.assertIn('total_xp_gained', result)

    def test_execute_exception_handling(self):
        """Test exception handling during execution."""
        client = Mock()
        
        with patch('src.controller.actions.transform_raw_materials.get_character_api', side_effect=Exception("API Error")):
            result = self.action.execute(client)
            self.assertFalse(result['success'])
            self.assertIn('Raw material transformation failed: API Error', result['error'])

    def test_execute_has_goap_attributes(self):
        """Test that TransformRawMaterialsAction has expected GOAP attributes."""
        self.assertTrue(hasattr(TransformRawMaterialsAction, 'conditions'))
        self.assertTrue(hasattr(TransformRawMaterialsAction, 'reactions'))
        self.assertTrue(hasattr(TransformRawMaterialsAction, 'weights'))
        self.assertTrue(hasattr(TransformRawMaterialsAction, 'g'))

    def test_goap_conditions(self):
        """Test GOAP conditions are properly defined."""
        expected_conditions = {"character_alive": True, "has_raw_materials": True, "character_safe": True}
        self.assertEqual(TransformRawMaterialsAction.conditions, expected_conditions)

    def test_goap_reactions(self):
        """Test GOAP reactions are properly defined."""
        expected_reactions = {"has_refined_materials": True, "materials_sufficient": True}
        self.assertEqual(TransformRawMaterialsAction.reactions, expected_reactions)

    def test_goap_weights(self):
        """Test GOAP weights are properly defined."""
        expected_weights = {"has_refined_materials": 15}
        self.assertEqual(TransformRawMaterialsAction.weights, expected_weights)


if __name__ == '__main__':
    unittest.main()