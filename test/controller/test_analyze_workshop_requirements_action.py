"""Test module for AnalyzeWorkshopRequirementsAction."""

import unittest
import tempfile
import os
from unittest.mock import Mock, patch
from src.controller.actions.analyze_workshop_requirements import AnalyzeWorkshopRequirementsAction
from test.fixtures import (
    create_mock_client, MockCharacterData, MockKnowledgeBase, MockMapState,
    mock_character_response, create_test_environment, cleanup_test_environment
)


class TestAnalyzeWorkshopRequirementsAction(unittest.TestCase):
    """Test cases for AnalyzeWorkshopRequirementsAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir, self.original_data_prefix = create_test_environment()
        
        self.action = AnalyzeWorkshopRequirementsAction(
            character_name="test_character",
            goal_type="general"
        )

    def tearDown(self):
        """Clean up test fixtures."""
        cleanup_test_environment(self.temp_dir, self.original_data_prefix)

    def test_analyze_workshop_requirements_action_initialization(self):
        """Test AnalyzeWorkshopRequirementsAction initialization."""
        self.assertEqual(self.action.character_name, "test_character")
        self.assertEqual(self.action.goal_type, "general")

    def test_analyze_workshop_requirements_action_initialization_defaults(self):
        """Test AnalyzeWorkshopRequirementsAction initialization with defaults."""
        action = AnalyzeWorkshopRequirementsAction("test")
        self.assertEqual(action.character_name, "test")
        self.assertEqual(action.goal_type, "general")

    def test_analyze_workshop_requirements_action_repr(self):
        """Test AnalyzeWorkshopRequirementsAction string representation."""
        expected = "AnalyzeWorkshopRequirementsAction(test_character, general)"
        self.assertEqual(repr(self.action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        result = self.action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    @patch('src.controller.actions.analyze_workshop_requirements.get_character_api')
    def test_execute_no_character_data(self, mock_get_character):
        """Test execute fails when character data unavailable."""
        mock_get_character.return_value = None
        client = create_mock_client()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Could not get character data', result['error'])

    @patch('src.controller.actions.analyze_workshop_requirements.get_character_api')
    def test_execute_successful_basic_analysis(self, mock_get_character):
        """Test successful workshop requirements analysis execution."""
        character_data = MockCharacterData(
            name="test_character",
            level=3,
            x=10,
            y=15
        )
        
        mock_get_character.return_value = mock_character_response(character_data)
        client = create_mock_client()
        
        result = self.action.execute(client)
        
        self.assertTrue(result['success'])
        self.assertTrue(result['workshop_requirements_known'])
        self.assertIn('required_workshops', result)
        self.assertIn('discovery_needed', result)

    @patch('src.controller.actions.analyze_workshop_requirements.get_character_api')
    def test_execute_with_knowledge_base(self, mock_get_character):
        """Test execute with knowledge base integration."""
        character_data = MockCharacterData(name="test_character", level=5)
        mock_get_character.return_value = mock_character_response(character_data)
        
        # Create knowledge base with workshop data
        knowledge_base = MockKnowledgeBase()
        knowledge_base.data['workshops'] = {
            'weaponcrafting_workshop': {
                'name': 'Weaponcrafting Workshop',
                'skill': 'weaponcrafting',
                'level': 1
            },
            'gearcrafting_workshop': {
                'name': 'Gearcrafting Workshop',
                'skill': 'gearcrafting',
                'level': 1
            }
        }
        knowledge_base.data['maps'] = {
            '5,10': {
                'x': 5, 'y': 10,
                'content': {'type': 'workshop', 'code': 'weaponcrafting_workshop'}
            }
        }
        
        map_state = MockMapState()
        
        client = create_mock_client()
        result = self.action.execute(client, knowledge_base=knowledge_base, map_state=map_state)
        
        self.assertTrue(result['success'])
        self.assertTrue(result['workshop_requirements_known'])
        self.assertIn('known_workshops', result)
        self.assertEqual(result['total_workshops_known'], 2)

    @patch('src.controller.actions.analyze_workshop_requirements.get_character_api')
    def test_execute_weaponcrafting_goal(self, mock_get_character):
        """Test analysis with weaponcrafting-specific goal."""
        action = AnalyzeWorkshopRequirementsAction("test_character", "weaponcrafting")
        character_data = MockCharacterData(name="test_character", level=5, weaponcrafting_level=3)
        mock_get_character.return_value = mock_character_response(character_data)
        
        client = create_mock_client()
        result = action.execute(client)
        
        self.assertTrue(result['success'])
        self.assertIn('weaponcrafting', result['required_workshop_types'])
        self.assertIn('goal_specific_needs', result)

    @patch('src.controller.actions.analyze_workshop_requirements.get_character_api')
    def test_execute_exception_handling(self, mock_get_character):
        """Test exception handling during execution."""
        mock_get_character.side_effect = Exception("API Error")
        client = create_mock_client()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Workshop requirements analysis failed: API Error', result['error'])

    def test_goap_attributes(self):
        """Test that AnalyzeWorkshopRequirementsAction has expected GOAP attributes."""
        self.assertTrue(hasattr(AnalyzeWorkshopRequirementsAction, 'conditions'))
        self.assertTrue(hasattr(AnalyzeWorkshopRequirementsAction, 'reactions'))
        self.assertTrue(hasattr(AnalyzeWorkshopRequirementsAction, 'weights'))

    def test_goap_conditions(self):
        """Test GOAP conditions are properly defined."""
        self.assertIsInstance(AnalyzeWorkshopRequirementsAction.conditions, dict)
        self.assertIn('character_alive', AnalyzeWorkshopRequirementsAction.conditions)

    def test_goap_reactions(self):
        """Test GOAP reactions are properly defined."""
        self.assertIsInstance(AnalyzeWorkshopRequirementsAction.reactions, dict)
        expected_reactions = [
            'workshop_requirements_known', 'need_workshop_discovery',
            'workshops_discovered', 'at_correct_workshop'
        ]
        for reaction in expected_reactions:
            self.assertIn(reaction, AnalyzeWorkshopRequirementsAction.reactions)

    def test_goap_weights(self):
        """Test GOAP weights are properly defined."""
        self.assertIsInstance(AnalyzeWorkshopRequirementsAction.weights, dict)
        self.assertIn('workshop_requirements_known', AnalyzeWorkshopRequirementsAction.weights)

    @patch('src.controller.actions.analyze_workshop_requirements.get_character_api')
    def test_discovery_needs_high_level_character(self, mock_get_character):
        """Test workshop discovery needs for high-level character."""
        character_data = MockCharacterData(name="test_character", level=8)
        mock_get_character.return_value = mock_character_response(character_data)
        
        # No knowledge base - should need discovery
        client = create_mock_client()
        result = self.action.execute(client)
        
        self.assertTrue(result['success'])
        self.assertTrue(result['discovery_needed'])
        self.assertIn('discovery_priority', result)

    @patch('src.controller.actions.analyze_workshop_requirements.get_character_api')
    def test_workshop_location_analysis(self, mock_get_character):
        """Test current location workshop analysis."""
        character_data = MockCharacterData(name="test_character", level=3, x=5, y=10)
        mock_get_character.return_value = mock_character_response(character_data)
        
        knowledge_base = MockKnowledgeBase()
        knowledge_base.data['workshops'] = {
            'weaponcrafting_workshop': {
                'name': 'Weaponcrafting Workshop',
                'skill': 'weaponcrafting'
            }
        }
        knowledge_base.data['maps'] = {
            '5,10': {
                'x': 5, 'y': 10,
                'content': {'type': 'workshop', 'code': 'weaponcrafting_workshop'}
            }
        }
        
        map_state = MockMapState()
        
        client = create_mock_client()
        result = self.action.execute(client, knowledge_base=knowledge_base, map_state=map_state)
        
        self.assertTrue(result['success'])
        self.assertTrue(result['at_workshop'])
        self.assertEqual(result['current_workshop_code'], 'weaponcrafting_workshop')

    @patch('src.controller.actions.analyze_workshop_requirements.get_character_api')
    def test_missing_workshop_identification(self, mock_get_character):
        """Test identification of missing workshops."""
        character_data = MockCharacterData(name="test_character", level=5)
        mock_get_character.return_value = mock_character_response(character_data)
        
        # Knowledge base with only one workshop type
        knowledge_base = MockKnowledgeBase()
        knowledge_base.data['workshops'] = {
            'cooking_workshop': {
                'name': 'Cooking Workshop',
                'skill': 'cooking'
            }
        }
        
        client = create_mock_client()
        result = self.action.execute(client, knowledge_base=knowledge_base)
        
        self.assertTrue(result['success'])
        # Should identify weaponcrafting and gearcrafting as missing for level 5 character
        self.assertIn('missing_workshop_types', result)
        self.assertIn('weaponcrafting', result['missing_workshop_types'])

    @patch('src.controller.actions.analyze_workshop_requirements.get_character_api')
    def test_workshop_recommendations(self, mock_get_character):
        """Test workshop recommendation generation."""
        character_data = MockCharacterData(name="test_character", level=3)
        mock_get_character.return_value = mock_character_response(character_data)
        
        client = create_mock_client()
        result = self.action.execute(client)
        
        self.assertTrue(result['success'])
        self.assertIn('primary_recommendation', result)
        self.assertIn('specific_actions', result)
        self.assertIn('immediate_steps', result)


if __name__ == '__main__':
    unittest.main()