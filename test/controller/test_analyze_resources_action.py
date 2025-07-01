"""Test module for AnalyzeResourcesAction."""

import unittest
from unittest.mock import patch

from src.controller.actions.analyze_resources import AnalyzeResourcesAction

from test.fixtures import (
    MockActionContext,
    MockKnowledgeBase,
    cleanup_test_environment,
    create_mock_client,
    create_test_environment,
)


class TestAnalyzeResourcesAction(unittest.TestCase):
    """Test cases for AnalyzeResourcesAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir, self.original_data_prefix = create_test_environment()
        
        self.action = AnalyzeResourcesAction()

    def tearDown(self):
        """Clean up test fixtures."""
        cleanup_test_environment(self.temp_dir, self.original_data_prefix)

    def test_analyze_resources_action_initialization(self):
        """Test AnalyzeResourcesAction initialization."""
        # Action no longer has attributes since it uses ActionContext
        self.assertIsInstance(self.action, AnalyzeResourcesAction)

    def test_analyze_resources_action_repr(self):
        """Test AnalyzeResourcesAction string representation."""
        expected = "AnalyzeResourcesAction()"
        self.assertEqual(repr(self.action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        context = MockActionContext(character_name="test_character")
        result = self.action.execute(None, context)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    @patch('src.controller.actions.analyze_resources.AnalyzeResourcesAction._find_nearby_resources')
    def test_execute_map_state_fails(self, mock_find_resources):
        """Test execute when finding resources fails."""
        mock_find_resources.return_value = []
        client = create_mock_client()
        
        context = MockActionContext(
            character_name="test_character",
            character_x=10,
            character_y=15,
            character_level=5,
            analysis_radius=8,
            equipment_types=['weapon', 'armor'],
            knowledge_base=MockKnowledgeBase()
        )
        result = self.action.execute(client, context)
        self.assertFalse(result['success'])
        self.assertIn('No resources found in analysis radius', result['error'])





    def test_execute_exception_handling(self):
        """Test exception handling during execution."""
        client = create_mock_client()
        
        context = MockActionContext(
            character_name="test_character",
            character_x=10,
            character_y=15,
            character_level=5,
            analysis_radius=8,
            equipment_types=['weapon', 'armor'],
            knowledge_base=MockKnowledgeBase()
        )
        
        with patch('src.controller.actions.analyze_resources.AnalyzeResourcesAction._find_nearby_resources', side_effect=Exception("Unexpected Error")):
            result = self.action.execute(client, context)
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