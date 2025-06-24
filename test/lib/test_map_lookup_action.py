import unittest
from unittest.mock import Mock, patch

from artifactsmmo_api_client.client import AuthenticatedClient
from artifactsmmo_api_client.models.map_response_schema import MapResponseSchema
from artifactsmmo_api_client.models.map_schema import MapSchema
from artifactsmmo_api_client.models.map_content_schema import MapContentSchema
from artifactsmmo_api_client.models.map_content_type import MapContentType
from src.controller.actions.map_lookup import MapLookupAction

class TestMapLookupAction(unittest.TestCase):
    def setUp(self):
        self.client = AuthenticatedClient(base_url="https://api.artifactsmmo.com", token="test_token")
        self.x = 5
        self.y = 10

    def test_map_lookup_action_initialization(self):
        action = MapLookupAction(x=self.x, y=self.y)
        self.assertEqual(action.x, self.x)
        self.assertEqual(action.y, self.y)

    def test_map_lookup_action_repr(self):
        action = MapLookupAction(x=self.x, y=self.y)
        expected_repr = f"MapLookupAction({self.x}, {self.y})"
        self.assertEqual(repr(action), expected_repr)

    @patch('src.controller.actions.map_lookup.get_map_api')
    def test_map_lookup_action_execute(self, mock_get_map_api):
        # Mock the API response to avoid making actual API calls
        mock_response = Mock()
        mock_get_map_api.return_value = mock_response
        
        action = MapLookupAction(x=self.x, y=self.y)
        response = action.execute(client=self.client)
        
        # Verify the API was called with correct parameters
        mock_get_map_api.assert_called_once_with(
            x=self.x,
            y=self.y,
            client=self.client
        )
        
        # Verify response is returned
        self.assertIsNotNone(response)
        self.assertEqual(response, mock_response)

    @patch('src.controller.actions.map_lookup.get_map_api')
    def test_map_lookup_action_execute_with_real_map_data(self, mock_get_map_api):
        # Create a realistic mock response
        mock_content = MapContentSchema(
            type_=MapContentType.MONSTER,
            code="chicken"
        )
        mock_map_data = MapSchema(
            name="Forest",
            skin="forest",
            x=self.x,
            y=self.y,
            content=mock_content
        )
        mock_response = MapResponseSchema(data=mock_map_data)
        mock_get_map_api.return_value = mock_response
        
        action = MapLookupAction(x=self.x, y=self.y)
        response = action.execute(client=self.client)
        
        # Verify the response contains expected data
        self.assertIsInstance(response, MapResponseSchema)
        self.assertEqual(response.data.name, "Forest")
        self.assertEqual(response.data.skin, "forest")
        self.assertEqual(response.data.x, self.x)
        self.assertEqual(response.data.y, self.y)
        self.assertEqual(response.data.content.type_, MapContentType.MONSTER)
        self.assertEqual(response.data.content.code, "chicken")

    @patch('src.controller.actions.map_lookup.get_map_api')
    def test_map_lookup_action_execute_with_empty_map(self, mock_get_map_api):
        # Create a mock response for an empty map location
        mock_map_data = MapSchema(
            name="Empty Field",
            skin="grass",
            x=self.x,
            y=self.y,
            content=None
        )
        mock_response = MapResponseSchema(data=mock_map_data)
        mock_get_map_api.return_value = mock_response
        
        action = MapLookupAction(x=self.x, y=self.y)
        response = action.execute(client=self.client)
        
        # Verify the response handles empty content correctly
        self.assertIsInstance(response, MapResponseSchema)
        self.assertEqual(response.data.name, "Empty Field")
        self.assertEqual(response.data.skin, "grass")
        self.assertIsNone(response.data.content)

    @patch('src.controller.actions.map_lookup.get_map_api')
    def test_map_lookup_different_content_types(self, mock_get_map_api):
        # Test different content types
        content_types = [
            (MapContentType.BANK, "bank_1"),
            (MapContentType.RESOURCE, "iron_ore"),
            (MapContentType.NPC, "merchant"),
            (MapContentType.WORKSHOP, "workshop_1"),
            (MapContentType.GRAND_EXCHANGE, "ge_1"),
            (MapContentType.TASKS_MASTER, "tasks_master_1")
        ]
        
        for content_type, code in content_types:
            with self.subTest(content_type=content_type, code=code):
                mock_content = MapContentSchema(
                    type_=content_type,
                    code=code
                )
                mock_map_data = MapSchema(
                    name=f"Test Location {content_type.value}",
                    skin="test",
                    x=self.x,
                    y=self.y,
                    content=mock_content
                )
                mock_response = MapResponseSchema(data=mock_map_data)
                mock_get_map_api.return_value = mock_response
                
                action = MapLookupAction(x=self.x, y=self.y)
                response = action.execute(client=self.client)
                
                self.assertEqual(response.data.content.type_, content_type)
                self.assertEqual(response.data.content.code, code)

    def test_map_lookup_action_class_attributes(self):
        # Test that the action has the expected GOAP-related attributes
        action = MapLookupAction(x=self.x, y=self.y)
        
        # Check that class attributes exist (following the pattern from MoveAction)
        self.assertIsInstance(action.conditions, dict)
        self.assertIsInstance(action.reactions, dict)
        self.assertIsInstance(action.weights, dict)
        self.assertIsNone(action.g)  # goal attribute

if __name__ == '__main__':
    unittest.main()
