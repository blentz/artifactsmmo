"""Test module for AnalyzeKnowledgeStateAction."""

import unittest
from unittest.mock import patch

from src.controller.actions.analyze_knowledge_state import AnalyzeKnowledgeStateAction

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


class TestAnalyzeKnowledgeStateAction(unittest.TestCase):
    """Test cases for AnalyzeKnowledgeStateAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir, self.original_data_prefix = create_test_environment()
        
        self.action = AnalyzeKnowledgeStateAction()

    def tearDown(self):
        """Clean up test fixtures."""
        cleanup_test_environment(self.temp_dir, self.original_data_prefix)

    def test_analyze_knowledge_state_action_initialization(self):
        """Test AnalyzeKnowledgeStateAction initialization."""
        # Action no longer has attributes since it uses ActionContext
        self.assertIsInstance(self.action, AnalyzeKnowledgeStateAction)

    def test_analyze_knowledge_state_action_goap_params(self):
        """Test AnalyzeKnowledgeStateAction GOAP parameters."""
        self.assertEqual(self.action.conditions["character_status"]["alive"], True)
        self.assertTrue("knowledge_state_analyzed" in self.action.reactions)
        self.assertTrue("exploration_data_available" in self.action.reactions)

    def test_analyze_knowledge_state_action_repr(self):
        """Test AnalyzeKnowledgeStateAction string representation."""
        expected = "AnalyzeKnowledgeStateAction()"
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

    @patch('src.controller.actions.analyze_knowledge_state.get_character_api')
    def test_execute_no_character_data(self, mock_get_character):
        """Test execute fails when character data unavailable."""
        mock_get_character.return_value = None
        client = create_mock_client()
        
        context = MockActionContext(
            character_name="test_character",
            analysis_scope="comprehensive",
            knowledge_base=MockKnowledgeBase(),
            map_state=MockMapState()
        )
        result = self.action.execute(client, context)
        self.assertFalse(result.success)
        self.assertIn('Could not get character data', result.error)

    @patch('src.controller.actions.analyze_knowledge_state.get_character_api')
    def test_execute_no_knowledge_base(self, mock_get_character):
        """Test execute fails without knowledge base."""
        character_data = MockCharacterData(name="test_character", level=3)
        mock_get_character.return_value = mock_character_response(character_data)
        
        client = create_mock_client()
        context = MockActionContext(
            character_name="test_character",
            analysis_scope="comprehensive",
            knowledge_base=None,
            map_state=MockMapState()
        )
        result = self.action.execute(client, context)  # No knowledge_base kwarg
        
        self.assertFalse(result.success)
        self.assertIn('No knowledge base available for analysis', result.error)

    @patch('src.controller.actions.analyze_knowledge_state.get_character_api')
    def test_execute_successful_basic_analysis(self, mock_get_character):
        """Test successful knowledge state analysis execution."""
        character_data = MockCharacterData(name="test_character", level=3)
        mock_get_character.return_value = mock_character_response(character_data)
        
        # Create minimal knowledge base
        knowledge_base = MockKnowledgeBase()
        knowledge_base.data = {
            'monsters': {
                'chicken': {'name': 'Chicken', 'level': 1, 'combat_results': []}
            },
            'items': {
                'copper_dagger': {'name': 'Copper Dagger', 'type': 'weapon'}
            },
            'resources': {
                'copper_rocks': {'locations': [{'x': 5, 'y': 10}]}
            },
            'workshops': {
                'weaponcrafting_workshop': {'skill': 'weaponcrafting'}
            }
        }
        
        client = create_mock_client()
        context = MockActionContext(
            character_name="test_character",
            analysis_scope="comprehensive",
            knowledge_base=knowledge_base,
            map_state=MockMapState()
        )
        result = self.action.execute(client, context)
        
        self.assertTrue(result.success)
        self.assertTrue(result.data['knowledge_state_analyzed'])
        self.assertIn('knowledge_completeness_score', result.data)
        self.assertIn('populated_categories', result.data)

    @patch('src.controller.actions.analyze_knowledge_state.get_character_api')
    def test_execute_combat_scope_analysis(self, mock_get_character):
        """Test analysis with combat scope."""
        action = AnalyzeKnowledgeStateAction()
        character_data = MockCharacterData(name="test_character", level=5)
        mock_get_character.return_value = mock_character_response(character_data)
        
        knowledge_base = MockKnowledgeBase()
        knowledge_base.data['monsters'] = {
            'chicken': {
                'name': 'Chicken',
                'level': 1,
                'combat_results': [
                    {'result': 'win', 'hp_lost': 5},
                    {'result': 'win', 'hp_lost': 3},
                    {'result': 'loss', 'hp_lost': 50}
                ],
                'drops': [{'code': 'feather', 'quantity': 1}]
            }
        }
        
        client = create_mock_client()
        context = MockActionContext(
            character_name="test_character",
            analysis_scope="combat",
            knowledge_base=knowledge_base,
            map_state=MockMapState()
        )
        result = action.execute(client, context)
        
        self.assertTrue(result.success)
        self.assertIn('combat_knowledge_score', result.data)
        self.assertIn('monsters_with_combat_data', result.data)

    @patch('src.controller.actions.analyze_knowledge_state.get_character_api')
    def test_execute_crafting_scope_analysis(self, mock_get_character):
        """Test analysis with crafting scope."""
        action = AnalyzeKnowledgeStateAction()
        character_data = MockCharacterData(name="test_character", level=3)
        mock_get_character.return_value = mock_character_response(character_data)
        
        knowledge_base = MockKnowledgeBase()
        knowledge_base.data = {
            'items': {
                'copper_dagger': {
                    'craft_data': {
                        'materials': [{'code': 'copper_ore', 'quantity': 2}]
                    }
                }
            },
            'workshops': {
                'weaponcrafting_workshop': {'skill': 'weaponcrafting'}
            },
            'resources': {
                'copper_rocks': {'locations': [{'x': 5, 'y': 10}]}
            }
        }
        
        client = create_mock_client()
        context = MockActionContext(
            character_name="test_character",
            analysis_scope="crafting",
            knowledge_base=knowledge_base,
            map_state=MockMapState()
        )
        result = action.execute(client, context)
        
        self.assertTrue(result.success)
        self.assertIn('crafting_knowledge_score', result.data)
        self.assertIn('items_with_recipes', result.data)
        self.assertIn('workshops_known', result.data)

    @patch('src.controller.actions.analyze_knowledge_state.get_character_api')
    def test_execute_exploration_scope_analysis(self, mock_get_character):
        """Test analysis with exploration scope."""
        action = AnalyzeKnowledgeStateAction()
        character_data = MockCharacterData(name="test_character", level=3)
        mock_get_character.return_value = mock_character_response(character_data)
        
        knowledge_base = MockKnowledgeBase()
        knowledge_base.data['maps'] = {
            '5,10': {'x': 5, 'y': 10, 'content': {'type': 'resource', 'code': 'copper_rocks'}},
            '6,10': {'x': 6, 'y': 10, 'content': {'type': 'monster', 'code': 'chicken'}},
            '7,10': {'x': 7, 'y': 10, 'content': {'type': 'unknown'}}
        }
        
        map_state = MockMapState()
        
        client = create_mock_client()
        context = MockActionContext(
            character_name="test_character",
            analysis_scope="exploration",
            knowledge_base=knowledge_base,
            map_state=map_state
        )
        result = action.execute(client, context)
        
        self.assertTrue(result.success)
        self.assertIn('exploration_knowledge_score', result.data)
        self.assertIn('locations_explored', result.data)
        self.assertIn('content_discovery_rate', result.data)

    @patch('src.controller.actions.analyze_knowledge_state.get_character_api')
    def test_execute_exception_handling(self, mock_get_character):
        """Test exception handling during execution."""
        mock_get_character.side_effect = Exception("API Error")
        client = create_mock_client()
        
        context = MockActionContext(
            character_name="test_character",
            analysis_scope="comprehensive",
            knowledge_base=MockKnowledgeBase(),
            map_state=MockMapState()
        )
        result = self.action.execute(client, context)
        self.assertFalse(result.success)
        self.assertIn('Knowledge state analysis failed: API Error', result.error)

    def test_goap_attributes(self):
        """Test that AnalyzeKnowledgeStateAction has expected GOAP attributes."""
        self.assertTrue(hasattr(AnalyzeKnowledgeStateAction, 'conditions'))
        self.assertTrue(hasattr(AnalyzeKnowledgeStateAction, 'reactions'))
        self.assertTrue(hasattr(AnalyzeKnowledgeStateAction, 'weight'))

    def test_goap_conditions(self):
        """Test GOAP conditions are properly defined."""
        self.assertIsInstance(AnalyzeKnowledgeStateAction.conditions, dict)
        self.assertIn('character_status', AnalyzeKnowledgeStateAction.conditions)
        self.assertTrue(AnalyzeKnowledgeStateAction.conditions['character_status']['alive'])

    def test_goap_reactions(self):
        """Test GOAP reactions are properly defined."""
        self.assertIsInstance(AnalyzeKnowledgeStateAction.reactions, dict)
        expected_reactions = [
            'knowledge_state_analyzed', 'map_explored', 'equipment_info_known',
            'recipe_known', 'exploration_data_available'
        ]
        for reaction in expected_reactions:
            self.assertIn(reaction, AnalyzeKnowledgeStateAction.reactions)

    def test_goap_weights(self):
        """Test GOAP weights are properly defined."""
        self.assertIsInstance(AnalyzeKnowledgeStateAction.weight, (int, float))

    @patch('src.controller.actions.analyze_knowledge_state.get_character_api')
    def test_knowledge_completeness_calculation(self, mock_get_character):
        """Test knowledge completeness score calculation."""
        character_data = MockCharacterData(name="test_character", level=5)
        mock_get_character.return_value = mock_character_response(character_data)
        
        # Create comprehensive knowledge base
        knowledge_base = MockKnowledgeBase()
        knowledge_base.data = {
            'monsters': {
                'chicken': {
                    'name': 'Chicken',
                    'level': 1,
                    'locations': [{'x': 5, 'y': 10}],
                    'combat_results': [{'result': 'win'}, {'result': 'win'}, {'result': 'loss'}],
                    'drops': [{'code': 'feather'}]
                }
            },
            'items': {
                'copper_dagger': {
                    'name': 'Copper Dagger',
                    'type': 'weapon',
                    'craft_data': {'materials': [{'code': 'copper_ore', 'quantity': 2}]}
                }
            },
            'resources': {
                'copper_rocks': {'locations': [{'x': 5, 'y': 10}, {'x': 6, 'y': 10}]}
            },
            'workshops': {
                'weaponcrafting_workshop': {'skill': 'weaponcrafting'}
            },
            'maps': {},
            'character_insights': {},
            'combat_performance': {},
            'exploration_patterns': {}
        }
        
        client = create_mock_client()
        context = MockActionContext(
            character_name="test_character",
            analysis_scope="comprehensive",
            knowledge_base=knowledge_base,
            map_state=MockMapState()
        )
        result = self.action.execute(client, context)
        
        self.assertTrue(result.success)
        self.assertGreater(result.data['knowledge_completeness_score'], 0.0)
        self.assertLessEqual(result.data['knowledge_completeness_score'], 1.0)

    @patch('src.controller.actions.analyze_knowledge_state.get_character_api')
    def test_information_gaps_identification(self, mock_get_character):
        """Test identification of information gaps."""
        character_data = MockCharacterData(name="test_character", level=5)
        mock_get_character.return_value = mock_character_response(character_data)
        
        # Create sparse knowledge base to trigger gaps
        knowledge_base = MockKnowledgeBase()
        knowledge_base.data = {
            'monsters': {},  # Empty - should trigger combat gap
            'items': {},     # Empty - should trigger crafting gap
            'resources': {}, # Empty
            'workshops': {}, # Empty
            'maps': {}       # Empty - should trigger exploration gap
        }
        
        client = create_mock_client()
        context = MockActionContext(
            character_name="test_character",
            analysis_scope="comprehensive",
            knowledge_base=knowledge_base,
            map_state=MockMapState()
        )
        result = self.action.execute(client, context)
        
        self.assertTrue(result.success)
        self.assertIn('priority_gaps', result.data)
        self.assertIn('learning_opportunities', result.data)
        self.assertIn('recommended_activities', result.data)
        self.assertGreater(result.data['information_gaps_score'], 0.5)  # Should have significant gaps

    @patch('src.controller.actions.analyze_knowledge_state.get_character_api')
    def test_learning_recommendations_generation(self, mock_get_character):
        """Test learning recommendations generation."""
        character_data = MockCharacterData(name="test_character", level=3)
        mock_get_character.return_value = mock_character_response(character_data)
        
        knowledge_base = MockKnowledgeBase()
        
        client = create_mock_client()
        context = MockActionContext(
            character_name="test_character",
            analysis_scope="comprehensive",
            knowledge_base=knowledge_base,
            map_state=MockMapState()
        )
        result = self.action.execute(client, context)
        
        self.assertTrue(result.success)
        self.assertIn('primary_learning_focus', result.data)
        self.assertIn('specific_learning_goals', result.data)
        self.assertIn('learning_strategy', result.data)
        self.assertIn('estimated_learning_time', result.data)


if __name__ == '__main__':
    unittest.main()