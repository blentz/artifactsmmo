"""Test module for FindXpSourcesAction."""

import unittest
import tempfile
import os
from unittest.mock import Mock, patch
from src.controller.actions.find_xp_sources import FindXpSourcesAction
from test.fixtures import create_mock_client


class TestFindXpSourcesAction(unittest.TestCase):
    """Test cases for FindXpSourcesAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_prefix = os.environ.get('DATA_PREFIX', '')
        os.environ['DATA_PREFIX'] = self.temp_dir
        
        self.skill = "weaponcrafting"
        self.action = FindXpSourcesAction(self.skill, character_level=5)

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['DATA_PREFIX'] = self.original_data_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_find_xp_sources_action_initialization(self):
        """Test FindXpSourcesAction initialization."""
        self.assertEqual(self.action.skill, "weaponcrafting")
        self.assertEqual(self.action.kwargs.get('character_level'), 5)

    def test_find_xp_sources_action_initialization_defaults(self):
        """Test FindXpSourcesAction initialization with defaults."""
        action = FindXpSourcesAction("mining")
        self.assertEqual(action.skill, "mining")
        self.assertEqual(action.kwargs, {})

    def test_find_xp_sources_action_repr(self):
        """Test FindXpSourcesAction string representation."""
        expected = "FindXpSourcesAction(skill=weaponcrafting)"
        self.assertEqual(repr(self.action), expected)

    def test_find_xp_sources_action_repr_no_kwargs(self):
        """Test FindXpSourcesAction string representation without kwargs."""
        action = FindXpSourcesAction("cooking")
        expected = "FindXpSourcesAction(skill=cooking)"
        self.assertEqual(repr(action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        result = self.action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    def test_execute_no_knowledge_base(self):
        """Test execute fails when knowledge base is not provided."""
        client = create_mock_client()
        mock_learning_manager = Mock()
        
        # Execute with learning_manager but no knowledge_base
        result = self.action.execute(client, learning_manager=mock_learning_manager)
        self.assertFalse(result['success'])
        self.assertIn('Knowledge base not available', result['error'])

    def test_execute_no_learning_manager(self):
        """Test execute when learning manager is not provided."""
        client = create_mock_client()
        mock_knowledge_base = Mock()
        
        # Execute with knowledge_base but no learning_manager
        result = self.action.execute(client, knowledge_base=mock_knowledge_base)
        self.assertFalse(result['success'])
        self.assertIn('Learning manager not available', result['error'])

    def test_execute_no_skill_xp_effects(self):
        """Test execute when skill has no XP effects."""
        client = create_mock_client()
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {'effects': {}}
        
        mock_learning_manager = Mock()
        mock_learning_manager.find_xp_sources_for_skill.return_value = None
        
        result = self.action.execute(
            client,
            knowledge_base=mock_knowledge_base,
            learning_manager=mock_learning_manager
        )
        self.assertFalse(result['success'])
        self.assertIn("No XP sources found for skill 'weaponcrafting'", result['error'])

    def test_execute_success_basic(self):
        """Test successful execution with basic XP effects."""
        client = create_mock_client()
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'effects': {'weaponcrafting_xp': True},
            'items': {
                'copper_sword': {'name': 'Copper Sword', 'craft': {'skill': 'weaponcrafting'}},
                'iron_sword': {'name': 'Iron Sword', 'craft': {'skill': 'weaponcrafting'}}
            }
        }
        
        mock_learning_manager = Mock()
        mock_learning_manager.find_xp_sources_for_skill.return_value = [
            {'source': 'copper_sword', 'xp': 10},
            {'source': 'iron_sword', 'xp': 20}
        ]
        
        result = self.action.execute(
            client,
            knowledge_base=mock_knowledge_base,
            learning_manager=mock_learning_manager
        )
        self.assertTrue(result['success'])
        self.assertEqual(result['skill'], 'weaponcrafting')
        self.assertIn('xp_sources', result)
        self.assertIn('actionable_sources', result)
        self.assertGreater(result['total_sources_found'], 0)

    def test_execute_success_with_detailed_analysis(self):
        """Test successful execution with detailed effect analysis."""
        client = create_mock_client()
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'effects': {'weaponcrafting_xp': {'value': 25}},
            'items': {'copper_sword': {'craft': {'skill': 'weaponcrafting'}}}
        }
        
        mock_learning_manager = Mock()
        mock_learning_manager.find_xp_sources_for_skill.return_value = [
            {'source': 'crafting', 'effect': 'weaponcrafting_xp', 'value': 25}
        ]
        
        # Mock the _analyze_actionable_sources to return something
        with patch.object(self.action, '_analyze_actionable_sources', return_value=[{'item': 'copper_sword'}]):
            result = self.action.execute(
                client,
                knowledge_base=mock_knowledge_base,
                learning_manager=mock_learning_manager
            )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['total_sources_found'], 1)
        self.assertIsNotNone(result.get('actionable_sources'))

    def test_execute_missing_effect_details(self):
        """Test execution when effect details are missing but sources exist."""
        client = create_mock_client()
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {'effects': {}}
        
        mock_learning_manager = Mock()
        mock_learning_manager.find_xp_sources_for_skill.return_value = [
            {'source': 'unknown_source', 'xp': 5}
        ]
        
        result = self.action.execute(
            client,
            knowledge_base=mock_knowledge_base,
            learning_manager=mock_learning_manager
        )
        self.assertTrue(result['success'])
        self.assertEqual(result['total_sources_found'], 1)

    def test_execute_with_effects_learning(self):
        """Test execution triggers effects learning when data not available."""
        client = create_mock_client()
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {}  # No effects data
        
        mock_learning_manager = Mock()
        # First return None (no effects), then return effects after learning
        mock_learning_manager.find_xp_sources_for_skill.side_effect = [
            [{'source': 'learned_source', 'xp': 15}]
        ]
        mock_learning_manager.learn_all_effects_bulk.return_value = {'success': True}
        
        # Mock _check_effects_data_available to return False
        with patch.object(self.action, '_check_effects_data_available', return_value=False):
            result = self.action.execute(
                client,
                knowledge_base=mock_knowledge_base,
                learning_manager=mock_learning_manager
            )
        
        # Verify effects learning was called
        mock_learning_manager.learn_all_effects_bulk.assert_called_once_with(client)
        self.assertTrue(result['success'])

    def test_execute_has_goap_attributes(self):
        """Test that FindXpSourcesAction has expected GOAP attributes."""
        self.assertTrue(hasattr(FindXpSourcesAction, 'conditions'))
        self.assertTrue(hasattr(FindXpSourcesAction, 'reactions'))
        self.assertTrue(hasattr(FindXpSourcesAction, 'weights'))
        self.assertTrue(hasattr(FindXpSourcesAction, 'g'))

    def test_check_effects_data_available(self):
        """Test _check_effects_data_available method."""
        # Test when both effects and xp_effects_analysis exist
        mock_kb = Mock()
        mock_kb.data = {
            'effects': {'some_effect': {}},
            'xp_effects_analysis': {'skill': ['effect1']}
        }
        self.assertTrue(self.action._check_effects_data_available(mock_kb))
        
        # Test when effects data is empty
        mock_kb.data = {'effects': {}}
        self.assertFalse(self.action._check_effects_data_available(mock_kb))
        
        # Test when no effects key
        mock_kb.data = {}
        self.assertFalse(self.action._check_effects_data_available(mock_kb))

    def test_find_alternative_skill_names(self):
        """Test _find_alternative_skill_names method."""
        # Test that method returns a list
        alternatives = self.action._find_alternative_skill_names('weaponcrafting')
        self.assertIsInstance(alternatives, list)
        
        # Test skill with no variations
        alternatives = self.action._find_alternative_skill_names('mining')
        self.assertIsInstance(alternatives, list)


if __name__ == '__main__':
    unittest.main()