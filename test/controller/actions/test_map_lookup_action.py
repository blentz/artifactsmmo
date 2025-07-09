import unittest
from unittest.mock import Mock, patch

from artifactsmmo_api_client.models.map_content_schema import MapContentSchema
from artifactsmmo_api_client.models.map_content_type import MapContentType
from artifactsmmo_api_client.models.map_response_schema import MapResponseSchema
from artifactsmmo_api_client.models.map_schema import MapSchema
from src.controller.actions.map_lookup import MapLookupAction
from src.controller.actions.base import ActionResult

from test.base_test import BaseTest
from test.fixtures import MockActionContext, create_mock_client


class TestMapLookupAction(BaseTest):
    def setUp(self):
        self.client = create_mock_client()
        self.x = 5
        self.y = 10
        self.action = MapLookupAction()
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up mock objects
        self.client = None
        self.action = None
        
        # Clear any patches that might be active
        patch.stopall()

    def test_map_lookup_action_initialization(self):
        action = MapLookupAction()
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(action, 'x'))
        self.assertFalse(hasattr(action, 'y'))

    def test_map_lookup_action_repr(self):
        action = MapLookupAction()
        expected_repr = "MapLookupAction()"
        self.assertEqual(repr(action), expected_repr)

    @patch('src.controller.actions.map_lookup.get_map_api')
    def test_map_lookup_action_execute(self, mock_get_map_api):
        # Mock the API response to avoid making actual API calls
        mock_response = Mock()
        mock_response.data = Mock()
        mock_get_map_api.return_value = mock_response
        
        action = MapLookupAction()
        context = MockActionContext(x=self.x, y=self.y)
        response = action.execute(client=self.client, context=context)
        
        # Verify the API was called with correct parameters
        mock_get_map_api.assert_called_once_with(
            x=self.x,
            y=self.y,
            client=self.client
        )
        
        # Verify response is returned
        self.assertIsNotNone(response)
        self.assertTrue(response.success)

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
        
        action = MapLookupAction()
        context = MockActionContext(x=self.x, y=self.y)
        response = action.execute(client=self.client, context=context)
        
        # Verify the response contains expected data
        self.assertIsInstance(response, ActionResult)
        self.assertTrue(response.success)
        self.assertEqual(response.data['x'], self.x)
        self.assertEqual(response.data['y'], self.y)
        if 'content' in response.data:
            self.assertEqual(response.data['content']['type'], 'monster')
            self.assertEqual(response.data['content']['code'], 'chicken')

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
        
        action = MapLookupAction()
        context = MockActionContext(x=self.x, y=self.y)
        response = action.execute(client=self.client, context=context)
        
        # Verify the response handles empty content correctly
        self.assertIsInstance(response, ActionResult)
        self.assertTrue(response.success)
        self.assertEqual(response.data['x'], self.x)
        self.assertEqual(response.data['y'], self.y)
        if 'content' in response.data:
            self.assertIsNone(response.data['content'])

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
                
                action = MapLookupAction()
                context = MockActionContext(x=self.x, y=self.y)
                response = action.execute(client=self.client, context=context)
                
                self.assertTrue(response.success)
                if 'content' in response.data and response.data['content']:
                    self.assertEqual(response.data['content']['type'], content_type.value)
                    self.assertEqual(response.data['content']['code'], code)

    def test_map_lookup_action_class_attributes(self):
        # Test that the action has the expected GOAP-related attributes
        action = MapLookupAction()
        
        # Check that class attributes exist (following the pattern from MoveAction)
        self.assertIsInstance(action.conditions, dict)
        self.assertIsInstance(action.reactions, dict)
        self.assertIsInstance(action.weight, (int, float))

    def test_map_lookup_action_no_client(self):
        # Test that execute fails gracefully without a client
        action = MapLookupAction()
        context = MockActionContext(x=self.x, y=self.y)
        response = action.execute(client=None, context=context)
        
        self.assertFalse(response.success)
        self.assertIn('failed', response.error)

    def test_map_lookup_action_missing_coordinates(self):
        # Test that execute fails when coordinates are missing
        action = MapLookupAction()
        context = MockActionContext()  # No x, y coordinates
        response = action.execute(client=self.client, context=context)
        
        self.assertFalse(response.success)
        self.assertIn('coordinates', response.error.lower())
    
    @patch('src.controller.actions.map_lookup.get_map_api')
    def test_map_lookup_action_no_data_in_response(self, mock_get_map_api):
        # Test when API returns response but data is None
        mock_response = Mock()
        mock_response.data = None
        mock_get_map_api.return_value = mock_response
        
        action = MapLookupAction()
        context = MockActionContext(x=self.x, y=self.y)
        response = action.execute(client=self.client, context=context)
        
        # Should return error when no map data
        self.assertFalse(response.success)
        self.assertEqual(response.error, "No map data returned")
        self.assertEqual(response.data['x'], self.x)
        self.assertEqual(response.data['y'], self.y)

if __name__ == '__main__':
    unittest.main()
