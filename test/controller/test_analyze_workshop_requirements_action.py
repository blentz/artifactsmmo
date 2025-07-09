"""Test module for AnalyzeWorkshopRequirementsAction."""

import unittest
from unittest.mock import patch

from src.controller.actions.analyze_workshop_requirements import AnalyzeWorkshopRequirementsAction

from test.fixtures import (
    MockActionContext,
    MockCharacterData,
    MockKnowledgeBase,
    MockMapState,
    cleanup_test_environment,
    create_mock_client,
    create_test_environment,
    mock_character_response,
)


class TestAnalyzeWorkshopRequirementsAction(unittest.TestCase):
    """Test cases for AnalyzeWorkshopRequirementsAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir, self.original_data_prefix = create_test_environment()
        
        self.action = AnalyzeWorkshopRequirementsAction()

    def tearDown(self):
        """Clean up test fixtures."""
        cleanup_test_environment(self.temp_dir, self.original_data_prefix)

    def test_analyze_workshop_requirements_action_initialization(self):
        """Test AnalyzeWorkshopRequirementsAction initialization."""
        # Action no longer has attributes since it uses ActionContext
        self.assertIsInstance(self.action, AnalyzeWorkshopRequirementsAction)

    def test_analyze_workshop_requirements_action_repr(self):
        """Test AnalyzeWorkshopRequirementsAction string representation."""
        expected = "AnalyzeWorkshopRequirementsAction()"
        self.assertEqual(repr(self.action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        context = MockActionContext()
        context.character_name = "test_character"
        result = self.action.execute(None, context)
        # With centralized validation, None client triggers validation error
        self.assertFalse(result.success)
        # Direct action execution bypasses centralized validation
        self.assertTrue(hasattr(result, 'error'))

    @patch('src.controller.actions.analyze_workshop_requirements.get_character_api')
    def test_execute_no_character_data(self, mock_get_character):
        """Test execute fails when character data unavailable."""
        mock_get_character.return_value = None
        client = create_mock_client()
        
        context = MockActionContext(
            character_name="test_character",
            goal_type="general",
            knowledge_base=MockKnowledgeBase(),
            map_state=MockMapState()
        )
        result = self.action.execute(client, context)
        self.assertFalse(result.success)
        self.assertIn('Could not get character data', result.error)

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
        
        context = MockActionContext(
            character_name="test_character",
            goal_type="general",
            knowledge_base=MockKnowledgeBase(),
            map_state=MockMapState()
        )
        result = self.action.execute(client, context)
        
        self.assertTrue(result.success)
        self.assertTrue(result.data['workshop_requirements_known'])
        self.assertIn('required_workshops', result.data)
        self.assertIn('discovery_needed', result.data)

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
        context = MockActionContext(
            character_name="test_character",
            goal_type="general",
            knowledge_base=knowledge_base,
            map_state=map_state
        )
        result = self.action.execute(client, context)
        
        self.assertTrue(result.success)
        self.assertTrue(result.data['workshop_requirements_known'])
        self.assertIn('known_workshops', result.data)
        self.assertEqual(result.data['total_workshops_known'], 2)

    @patch('src.controller.actions.analyze_workshop_requirements.get_character_api')
    def test_execute_weaponcrafting_goal(self, mock_get_character):
        """Test analysis with weaponcrafting-specific goal."""
        action = AnalyzeWorkshopRequirementsAction()
        character_data = MockCharacterData(name="test_character", level=5, weaponcrafting_level=3)
        mock_get_character.return_value = mock_character_response(character_data)
        
        client = create_mock_client()
        context = MockActionContext(
            character_name="test_character",
            goal_type="weaponcrafting",
            knowledge_base=MockKnowledgeBase(),
            map_state=MockMapState()
        )
        result = action.execute(client, context)
        
        self.assertTrue(result.success)
        self.assertIn('weaponcrafting', result.data['required_workshop_types'])
        self.assertIn('goal_specific_needs', result.data)

    @patch('src.controller.actions.analyze_workshop_requirements.get_character_api')
    def test_execute_exception_handling(self, mock_get_character):
        """Test exception handling during execution."""
        mock_get_character.side_effect = Exception("API Error")
        client = create_mock_client()
        
        context = MockActionContext(
            character_name="test_character",
            goal_type="general",
            knowledge_base=MockKnowledgeBase(),
            map_state=MockMapState()
        )
        result = self.action.execute(client, context)
        self.assertFalse(result.success)
        self.assertIn('Workshop requirements analysis failed: API Error', result.error)

    def test_goap_attributes(self):
        """Test that AnalyzeWorkshopRequirementsAction has expected GOAP attributes."""
        self.assertTrue(hasattr(AnalyzeWorkshopRequirementsAction, 'conditions'))
        self.assertTrue(hasattr(AnalyzeWorkshopRequirementsAction, 'reactions'))
        self.assertTrue(hasattr(AnalyzeWorkshopRequirementsAction, 'weight'))

    def test_goap_conditions(self):
        """Test GOAP conditions are properly defined."""
        self.assertIsInstance(AnalyzeWorkshopRequirementsAction.conditions, dict)
        self.assertIn('character_status', AnalyzeWorkshopRequirementsAction.conditions)
        self.assertTrue(AnalyzeWorkshopRequirementsAction.conditions['character_status']['alive'])

    def test_goap_reactions(self):
        """Test GOAP reactions are properly defined."""
        self.assertIsInstance(AnalyzeWorkshopRequirementsAction.reactions, dict)
        expected_reactions = [
            'workshop_requirements_known',
            'workshops_discovered', 'at_correct_workshop'
        ]
        for reaction in expected_reactions:
            self.assertIn(reaction, AnalyzeWorkshopRequirementsAction.reactions)

    def test_goap_weights(self):
        """Test GOAP weights are properly defined."""
        self.assertIsInstance(AnalyzeWorkshopRequirementsAction.weight, (int, float))

    @patch('src.controller.actions.analyze_workshop_requirements.get_character_api')
    def test_discovery_needs_high_level_character(self, mock_get_character):
        """Test workshop discovery needs for high-level character."""
        character_data = MockCharacterData(name="test_character", level=8)
        mock_get_character.return_value = mock_character_response(character_data)
        
        # No knowledge base - should need discovery
        client = create_mock_client()
        context = MockActionContext(
            character_name="test_character",
            goal_type="general",
            knowledge_base=MockKnowledgeBase(),
            map_state=MockMapState()
        )
        result = self.action.execute(client, context)
        
        self.assertTrue(result.success)
        self.assertTrue(result.data['discovery_needed'])
        self.assertIn('discovery_priority', result.data)

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
        context = MockActionContext(
            character_name="test_character",
            goal_type="general",
            knowledge_base=knowledge_base,
            map_state=map_state
        )
        result = self.action.execute(client, context)
        
        self.assertTrue(result.success)
        self.assertTrue(result.data['at_workshop'])
        self.assertEqual(result.data['current_workshop_code'], 'weaponcrafting_workshop')

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
        context = MockActionContext(
            character_name="test_character",
            goal_type="general",
            knowledge_base=knowledge_base,
            map_state=MockMapState()
        )
        result = self.action.execute(client, context)
        
        self.assertTrue(result.success)
        # Should identify weaponcrafting and gearcrafting as missing for level 5 character
        self.assertIn('missing_workshop_types', result.data)
        self.assertIn('weaponcrafting', result.data['missing_workshop_types'])

    @patch('src.controller.actions.analyze_workshop_requirements.get_character_api')
    def test_workshop_recommendations(self, mock_get_character):
        """Test workshop recommendation generation."""
        character_data = MockCharacterData(name="test_character", level=3)
        mock_get_character.return_value = mock_character_response(character_data)
        
        client = create_mock_client()
        context = MockActionContext(
            character_name="test_character",
            goal_type="general",
            knowledge_base=MockKnowledgeBase(),
            map_state=MockMapState()
        )
        result = self.action.execute(client, context)
        
        self.assertTrue(result.success)
        self.assertIn('primary_recommendation', result.data)
        self.assertIn('specific_actions', result.data)
        self.assertIn('immediate_steps', result.data)


if __name__ == '__main__':
    unittest.main()