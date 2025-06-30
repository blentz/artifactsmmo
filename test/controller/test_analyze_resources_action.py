"""Test module for AnalyzeResourcesAction."""

import unittest
import tempfile
import os
from unittest.mock import Mock, patch
from src.controller.actions.analyze_resources import AnalyzeResourcesAction
from test.fixtures import create_mock_client


class TestAnalyzeResourcesAction(unittest.TestCase):
    """Test cases for AnalyzeResourcesAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_prefix = os.environ.get('DATA_PREFIX', '')
        os.environ['DATA_PREFIX'] = self.temp_dir
        
        self.action = AnalyzeResourcesAction(
            character_x=10,
            character_y=15,
            character_level=5,
            analysis_radius=8,
            equipment_types=['weapon', 'armor']
        )

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['DATA_PREFIX'] = self.original_data_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_analyze_resources_action_initialization(self):
        """Test AnalyzeResourcesAction initialization."""
        self.assertEqual(self.action.character_x, 10)
        self.assertEqual(self.action.character_y, 15)
        self.assertEqual(self.action.character_level, 5)
        self.assertEqual(self.action.analysis_radius, 8)
        self.assertEqual(self.action.equipment_types, ['weapon', 'armor'])

    def test_analyze_resources_action_initialization_defaults(self):
        """Test AnalyzeResourcesAction initialization with defaults."""
        action = AnalyzeResourcesAction()
        self.assertEqual(action.character_x, 0)
        self.assertEqual(action.character_y, 0)
        self.assertEqual(action.character_level, 1)
        self.assertEqual(action.analysis_radius, 10)
        self.assertEqual(action.equipment_types, ['weapon', 'armor', 'utility'])

    def test_analyze_resources_action_repr(self):
        """Test AnalyzeResourcesAction string representation."""
        expected = "AnalyzeResourcesAction(10, 15, level=5, radius=8)"
        self.assertEqual(repr(self.action), expected)

    def test_analyze_resources_action_repr_no_types(self):
        """Test AnalyzeResourcesAction string representation without equipment types."""
        action = AnalyzeResourcesAction(character_x=5, character_y=3)
        expected = "AnalyzeResourcesAction(5, 3, level=1, radius=10)"
        self.assertEqual(repr(action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        result = self.action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    @patch('src.controller.actions.analyze_resources.AnalyzeResourcesAction._find_nearby_resources')
    def test_execute_map_state_fails(self, mock_find_resources):
        """Test execute when finding resources fails."""
        mock_find_resources.return_value = []
        client = create_mock_client()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('No resources found in analysis radius', result['error'])





    def test_execute_exception_handling(self):
        """Test exception handling during execution."""
        client = create_mock_client()
        
        with patch('src.controller.actions.analyze_resources.AnalyzeResourcesAction._find_nearby_resources', side_effect=Exception("Unexpected Error")):
            result = self.action.execute(client)
            self.assertFalse(result['success'])
            self.assertIn('Resource analysis failed: Unexpected Error', result['error'])

    def test_execute_has_goap_attributes(self):
        """Test that AnalyzeResourcesAction has expected GOAP attributes."""
        self.assertTrue(hasattr(AnalyzeResourcesAction, 'conditions'))
        self.assertTrue(hasattr(AnalyzeResourcesAction, 'reactions'))
        self.assertTrue(hasattr(AnalyzeResourcesAction, 'weights'))
        self.assertTrue(hasattr(AnalyzeResourcesAction, 'g'))

    def test_goap_conditions(self):
        """Test GOAP conditions are properly defined."""
        self.assertTrue(hasattr(AnalyzeResourcesAction, 'conditions'))
        self.assertIsInstance(AnalyzeResourcesAction.conditions, dict)

    def test_goap_reactions(self):
        """Test GOAP reactions are properly defined."""
        self.assertTrue(hasattr(AnalyzeResourcesAction, 'reactions'))
        self.assertIsInstance(AnalyzeResourcesAction.reactions, dict)

    def test_goap_weights(self):
        """Test GOAP weights are properly defined."""
        self.assertTrue(hasattr(AnalyzeResourcesAction, 'weights'))
        self.assertIsInstance(AnalyzeResourcesAction.weights, dict)


if __name__ == '__main__':
    unittest.main()