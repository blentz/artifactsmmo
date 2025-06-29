"""Test module for FindXpSourcesAction."""

import unittest
import tempfile
import os
from unittest.mock import Mock, patch
from src.controller.actions.find_xp_sources import FindXpSourcesAction


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

    @patch('src.controller.actions.find_xp_sources.KnowledgeBase')
    def test_execute_no_knowledge_base(self, mock_knowledge_base_class):
        """Test execute fails when knowledge base fails to load."""
        mock_knowledge_base_class.side_effect = Exception("Failed to load knowledge base")
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Failed to load knowledge base', result['error'])

    @patch('src.controller.actions.find_xp_sources.KnowledgeBase')
    def test_execute_no_xp_effects_data(self, mock_knowledge_base_class):
        """Test execute when no XP effects data available."""
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {}
        mock_knowledge_base_class.return_value = mock_knowledge_base
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('No XP effects analysis available', result['error'])

    @patch('src.controller.actions.find_xp_sources.KnowledgeBase')
    def test_execute_no_skill_xp_effects(self, mock_knowledge_base_class):
        """Test execute when skill has no XP effects."""
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'xp_effects_analysis': {
                'mining': ['some_effect'],
                'cooking': ['other_effect']
            }
        }
        mock_knowledge_base_class.return_value = mock_knowledge_base
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('No XP sources found for skill weaponcrafting', result['error'])

    @patch('src.controller.actions.find_xp_sources.KnowledgeBase')
    def test_execute_success_basic(self, mock_knowledge_base_class):
        """Test successful execution with basic XP effects."""
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'xp_effects_analysis': {
                'weaponcrafting': ['crafting_xp', 'weapon_smithing_xp']
            },
            'effects': {
                'crafting_xp': {
                    'name': 'crafting_xp',
                    'description': 'Grants crafting XP'
                },
                'weapon_smithing_xp': {
                    'name': 'weapon_smithing_xp', 
                    'description': 'Grants weapon smithing XP'
                }
            }
        }
        mock_knowledge_base_class.return_value = mock_knowledge_base
        client = Mock()
        
        result = self.action.execute(client)
        self.assertTrue(result['success'])
        self.assertEqual(result['skill'], 'weaponcrafting')
        self.assertEqual(len(result['xp_sources']), 2)
        self.assertIn('crafting_xp', result['xp_sources'])
        self.assertIn('weapon_smithing_xp', result['xp_sources'])

    @patch('src.controller.actions.find_xp_sources.KnowledgeBase')
    def test_execute_success_with_detailed_analysis(self, mock_knowledge_base_class):
        """Test successful execution with detailed effect analysis."""
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'xp_effects_analysis': {
                'weaponcrafting': ['crafting_xp']
            },
            'effects': {
                'crafting_xp': {
                    'name': 'crafting_xp',
                    'description': 'Grants crafting XP',
                    'value': 25
                }
            }
        }
        mock_knowledge_base_class.return_value = mock_knowledge_base
        client = Mock()
        
        result = self.action.execute(client)
        self.assertTrue(result['success'])
        self.assertEqual(result['total_sources_found'], 1)
        self.assertIn('effect_details', result)
        self.assertEqual(len(result['effect_details']), 1)
        self.assertEqual(result['effect_details'][0]['name'], 'crafting_xp')
        self.assertEqual(result['effect_details'][0]['value'], 25)

    @patch('src.controller.actions.find_xp_sources.KnowledgeBase')
    def test_execute_missing_effect_details(self, mock_knowledge_base_class):
        """Test execution when effect details are missing."""
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'xp_effects_analysis': {
                'weaponcrafting': ['missing_effect']
            },
            'effects': {}
        }
        mock_knowledge_base_class.return_value = mock_knowledge_base
        client = Mock()
        
        result = self.action.execute(client)
        self.assertTrue(result['success'])
        self.assertEqual(len(result['xp_sources']), 1)
        self.assertEqual(len(result['effect_details']), 0)  # No details available

    def test_execute_has_goap_attributes(self):
        """Test that FindXpSourcesAction has expected GOAP attributes."""
        self.assertTrue(hasattr(FindXpSourcesAction, 'conditions'))
        self.assertTrue(hasattr(FindXpSourcesAction, 'reactions'))
        self.assertTrue(hasattr(FindXpSourcesAction, 'weights'))
        self.assertTrue(hasattr(FindXpSourcesAction, 'g'))


if __name__ == '__main__':
    unittest.main()