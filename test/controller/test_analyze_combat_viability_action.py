"""Test module for AnalyzeCombatViabilityAction."""

import unittest
from unittest.mock import patch

from src.controller.actions.analyze_combat_viability import AnalyzeCombatViabilityAction

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


class TestAnalyzeCombatViabilityAction(unittest.TestCase):
    """Test cases for AnalyzeCombatViabilityAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir, self.original_data_prefix = create_test_environment()
        
        self.action = AnalyzeCombatViabilityAction()

    def tearDown(self):
        """Clean up test fixtures."""
        cleanup_test_environment(self.temp_dir, self.original_data_prefix)

    def test_analyze_combat_viability_action_initialization(self):
        """Test AnalyzeCombatViabilityAction initialization."""
        # Action should have no parameters stored as instance variables
        self.assertIsInstance(self.action, AnalyzeCombatViabilityAction)
        self.assertFalse(hasattr(self.action, 'analysis_radius'))

    def test_analyze_combat_viability_action_initialization_defaults(self):
        """Test AnalyzeCombatViabilityAction initialization with defaults."""
        action = AnalyzeCombatViabilityAction()
        # Action should have no parameters stored as instance variables
        self.assertIsInstance(action, AnalyzeCombatViabilityAction)
        self.assertFalse(hasattr(action, 'analysis_radius'))

    def test_analyze_combat_viability_action_repr(self):
        """Test AnalyzeCombatViabilityAction string representation."""
        expected = "AnalyzeCombatViabilityAction()"
        self.assertEqual(repr(self.action), expected)

    def test_execute_no_client(self):
        """Test execute succeeds without client when character_state is available in context."""
        context = MockActionContext(character_name="test_character")
        result = self.action.execute(None, context)
        # AnalyzeCombatViabilityAction can work without client if character_state is in context
        self.assertTrue(result.success)
        self.assertTrue(result.data.get("combat_viability_known"))
        self.assertIn("combat_viable", result.data)
        self.assertIn("ready_for_combat", result.data)

    @patch('src.controller.actions.analyze_combat_viability.get_character_api')
    def test_execute_no_character_data(self, mock_get_character):
        """Test execute fails when character data unavailable."""
        mock_get_character.return_value = None
        client = create_mock_client()
        context = MockActionContext(character_name="test_character", character_state="no_state")
        
        result = self.action.execute(client, context)
        self.assertFalse(result.success)
        self.assertIn('Could not get character data', result.error)

    @patch('src.controller.actions.analyze_combat_viability.get_character_api')
    def test_execute_successful_basic_analysis(self, mock_get_character):
        """Test successful combat viability analysis execution."""
        character_data = MockCharacterData(
            name="test_character",
            level=5,
            hp=80,
            max_hp=100,
            x=10,
            y=15
        )
        
        mock_get_character.return_value = mock_character_response(character_data)
        client = create_mock_client()
        context = MockActionContext(character_name="test_character")
        
        result = self.action.execute(client, context)
        
        self.assertTrue(result.success)
        self.assertTrue(result.data['combat_viability_known'])
        self.assertIn('character_x', result.data)
        self.assertIn('character_y', result.data)

    @patch('src.controller.actions.analyze_combat_viability.get_character_api')
    def test_execute_with_knowledge_base(self, mock_get_character):
        """Test execute with knowledge base integration."""
        character_data = MockCharacterData(name="test_character", level=3, x=5, y=10)
        mock_get_character.return_value = mock_character_response(character_data)
        
        # Create knowledge base with monster data
        knowledge_base = MockKnowledgeBase()
        knowledge_base.data['monsters'] = {
            'chicken': {
                'name': 'Chicken',
                'level': 1,
                'locations': [{'x': 6, 'y': 10}],
                'combat_results': [
                    {'result': 'win', 'hp_lost': 5},
                    {'result': 'win', 'hp_lost': 3},
                    {'result': 'loss', 'hp_lost': 50}
                ]
            }
        }
        
        map_state = MockMapState()
        map_state.data = {
            '5,10': {'x': 5, 'y': 10, 'content': {'type': 'monster', 'code': 'chicken'}},
            '6,10': {'x': 6, 'y': 10, 'content': {'type': 'monster', 'code': 'chicken'}}
        }
        
        client = create_mock_client()
        context = MockActionContext(
            character_name="test_character",
            knowledge_base=knowledge_base,
            map_state=map_state
        )
        result = self.action.execute(client, context)
        
        self.assertTrue(result.success)
        self.assertTrue(result.data['combat_viability_known'])
        self.assertIn('analysis_radius', result.data)

    @patch('src.controller.actions.analyze_combat_viability.get_character_api')
    def test_execute_low_hp_character(self, mock_get_character):
        """Test analysis with low HP character."""
        character_data = MockCharacterData(
            name="test_character",
            level=5,
            hp=15,  # Low HP
            max_hp=100
        )
        
        mock_get_character.return_value = mock_character_response(character_data)
        client = create_mock_client()
        context = MockActionContext(character_name="test_character", character_state="no_state")
        
        result = self.action.execute(client, context)
        
        self.assertTrue(result.success)
        self.assertFalse(result.data['ready_for_combat'])  # Should not be combat ready with low HP

    @patch('src.controller.actions.analyze_combat_viability.get_character_api')
    def test_execute_exception_handling(self, mock_get_character):
        """Test exception handling during execution."""
        mock_get_character.side_effect = Exception("API Error")
        client = create_mock_client()
        context = MockActionContext(character_name="test_character", character_state="no_state")
        
        result = self.action.execute(client, context)
        self.assertFalse(result.success)
        self.assertIn('Combat viability analysis failed: API Error', result.error)

    def test_goap_attributes(self):
        """Test that AnalyzeCombatViabilityAction has expected GOAP attributes."""
        self.assertTrue(hasattr(AnalyzeCombatViabilityAction, 'conditions'))
        self.assertTrue(hasattr(AnalyzeCombatViabilityAction, 'reactions'))
        self.assertTrue(hasattr(AnalyzeCombatViabilityAction, 'weight'))

    def test_goap_conditions(self):
        """Test GOAP conditions are properly defined."""
        self.assertIsInstance(AnalyzeCombatViabilityAction.conditions, dict)
        self.assertIn('character_status', AnalyzeCombatViabilityAction.conditions)
        self.assertTrue(AnalyzeCombatViabilityAction.conditions['character_status']['alive'])

    def test_goap_reactions(self):
        """Test GOAP reactions are properly defined."""
        self.assertIsInstance(AnalyzeCombatViabilityAction.reactions, dict)
        self.assertIn('combat_viability_known', AnalyzeCombatViabilityAction.reactions)
        self.assertIn('combat_not_viable', AnalyzeCombatViabilityAction.reactions)
        self.assertIn('combat_context', AnalyzeCombatViabilityAction.reactions)
        self.assertIn('goal_progress', AnalyzeCombatViabilityAction.reactions)

    def test_goap_weights(self):
        """Test GOAP weights are properly defined."""
        self.assertIsInstance(AnalyzeCombatViabilityAction.weight, (int, float))

    @patch('src.controller.actions.analyze_combat_viability.get_character_api')
    def test_character_readiness_healthy_character(self, mock_get_character):
        """Test character readiness calculation for healthy character."""
        character_data = MockCharacterData(
            name="test_character",
            level=5,
            hp=100,
            max_hp=100
        )
        
        mock_get_character.return_value = mock_character_response(character_data)
        client = create_mock_client()
        context = MockActionContext(character_name="test_character")
        
        result = self.action.execute(client, context)
        
        self.assertTrue(result.success)
        self.assertTrue(result.data['ready_for_combat'])
        self.assertEqual(result.data['hp_percentage'], 1.0)

    @patch('src.controller.actions.analyze_combat_viability.get_character_api')
    def test_combat_recommendation_generation(self, mock_get_character):
        """Test combat recommendation generation."""
        character_data = MockCharacterData(name="test_character", level=3, x=0, y=0)
        mock_get_character.return_value = mock_character_response(character_data)
        
        knowledge_base = MockKnowledgeBase()
        knowledge_base.data['monsters'] = {
            'chicken': {
                'name': 'Chicken',
                'level': 1,
                'locations': [{'x': 1, 'y': 1}],
                'combat_results': [
                    {'result': 'win', 'hp_lost': 2},
                    {'result': 'win', 'hp_lost': 3}
                ]
            }
        }
        
        map_state = MockMapState()
        client = create_mock_client()
        
        context = MockActionContext(
            character_name="test_character",
            knowledge_base=knowledge_base,
            map_state=map_state
        )
        result = self.action.execute(client, context)
        
        self.assertTrue(result.success)
        self.assertIn('primary_recommendation', result.data)
        self.assertIn('specific_actions', result.data)

    @patch('src.controller.actions.analyze_combat_viability.get_character_api') 
    def test_win_rate_analysis(self, mock_get_character):
        """Test win rate analysis from combat history."""
        character_data = MockCharacterData(name="test_character", level=5)
        mock_get_character.return_value = mock_character_response(character_data)
        
        knowledge_base = MockKnowledgeBase()
        knowledge_base.data['monsters'] = {
            'goblin': {
                'combat_results': [
                    {'result': 'win'},
                    {'result': 'win'},
                    {'result': 'loss'},
                    {'result': 'win'}
                ]
            }
        }
        
        client = create_mock_client()
        context = MockActionContext(
            character_name="test_character",
            knowledge_base=knowledge_base
        )
        result = self.action.execute(client, context)
        
        self.assertTrue(result.success)
        # Should calculate win rate as 75% (3 wins out of 4 fights)


if __name__ == '__main__':
    unittest.main()