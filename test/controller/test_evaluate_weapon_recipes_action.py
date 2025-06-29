"""Test module for EvaluateWeaponRecipesAction."""

import unittest
import tempfile
import os
from unittest.mock import Mock, patch
from src.controller.actions.evaluate_weapon_recipes import EvaluateWeaponRecipesAction


class TestEvaluateWeaponRecipesAction(unittest.TestCase):
    """Test cases for EvaluateWeaponRecipesAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_prefix = os.environ.get('DATA_PREFIX', '')
        os.environ['DATA_PREFIX'] = self.temp_dir
        
        self.character_name = "test_character"
        self.action = EvaluateWeaponRecipesAction(
            character_name=self.character_name,
            current_weapon="iron_sword"
        )

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['DATA_PREFIX'] = self.original_data_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_evaluate_weapon_recipes_action_initialization(self):
        """Test EvaluateWeaponRecipesAction initialization."""
        self.assertEqual(self.action.character_name, "test_character")
        self.assertEqual(self.action.current_weapon, "iron_sword")

    def test_evaluate_weapon_recipes_action_initialization_defaults(self):
        """Test EvaluateWeaponRecipesAction initialization with defaults."""
        action = EvaluateWeaponRecipesAction("player")
        self.assertEqual(action.character_name, "player")
        self.assertEqual(action.current_weapon, "wooden_stick")

    def test_evaluate_weapon_recipes_action_repr(self):
        """Test EvaluateWeaponRecipesAction string representation."""
        expected = "EvaluateWeaponRecipesAction(test_character, current=iron_sword)"
        self.assertEqual(repr(self.action), expected)

    def test_evaluate_weapon_recipes_action_repr_no_current_weapon(self):
        """Test EvaluateWeaponRecipesAction string representation with default weapon."""
        action = EvaluateWeaponRecipesAction("player")
        expected = "EvaluateWeaponRecipesAction(player, current=wooden_stick)"
        self.assertEqual(repr(action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        result = self.action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    @patch('src.controller.actions.evaluate_weapon_recipes.get_character_api')
    def test_execute_character_api_fails(self, mock_get_character_api):
        """Test execute when character API fails."""
        mock_get_character_api.return_value = None
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Could not retrieve character information', result['error'])

    @patch('src.controller.actions.evaluate_weapon_recipes.get_character_api')
    def test_execute_character_api_no_data(self, mock_get_character_api):
        """Test execute when character API returns no data."""
        mock_response = Mock()
        mock_response.data = None
        mock_get_character_api.return_value = mock_response
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Could not retrieve character information', result['error'])

    @patch('src.controller.actions.evaluate_weapon_recipes.KnowledgeBase')
    @patch('src.controller.actions.evaluate_weapon_recipes.get_character_api')
    def test_execute_knowledge_base_fails(self, mock_get_character_api, mock_knowledge_base_class):
        """Test execute when knowledge base fails to load."""
        # Mock character API
        mock_character_data = Mock()
        mock_character_data.weaponcrafting_level = 5
        mock_character_response = Mock()
        mock_character_response.data = mock_character_data
        mock_get_character_api.return_value = mock_character_response
        
        # Mock knowledge base failure
        mock_knowledge_base_class.side_effect = Exception("Knowledge base error")
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Knowledge base error', result['error'])

    @patch('src.controller.actions.evaluate_weapon_recipes.KnowledgeBase')
    @patch('src.controller.actions.evaluate_weapon_recipes.get_character_api')
    def test_execute_no_weapons_data(self, mock_get_character_api, mock_knowledge_base_class):
        """Test execute when no weapons data available."""
        # Mock character API
        mock_character_data = Mock()
        mock_character_data.weaponcrafting_level = 5
        mock_character_response = Mock()
        mock_character_response.data = mock_character_data
        mock_get_character_api.return_value = mock_character_response
        
        # Mock knowledge base without weapons data
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {}
        mock_knowledge_base_class.return_value = mock_knowledge_base
        
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('No weapons data available', result['error'])

    @patch('src.controller.actions.evaluate_weapon_recipes.ActionExecutor')
    @patch('src.controller.actions.evaluate_weapon_recipes.KnowledgeBase')
    @patch('src.controller.actions.evaluate_weapon_recipes.get_character_api')
    def test_execute_success_basic(self, mock_get_character_api, mock_knowledge_base_class, mock_action_executor_class):
        """Test successful execution with basic weapon data."""
        # Mock character API
        mock_character_data = Mock()
        mock_character_data.weaponcrafting_level = 5
        mock_character_data.level = 10
        mock_character_response = Mock()
        mock_character_response.data = mock_character_data
        mock_get_character_api.return_value = mock_character_response
        
        # Store character data for skill discovery
        self.action.character_data = mock_character_data
        
        # Mock knowledge base with weapons data
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'items': {
                'copper_sword': {
                    'type': 'weapon',
                    'level': 3,
                    'attack_fire': 10,
                    'craft': {
                        'skill': 'weaponcrafting',
                        'level': 3
                    }
                },
                'iron_sword': {
                    'type': 'weapon', 
                    'level': 8,
                    'attack_fire': 20,
                    'craft': {
                        'skill': 'weaponcrafting',
                        'level': 8
                    }
                }
            }
        }
        mock_knowledge_base_class.return_value = mock_knowledge_base
        
        # Mock action executor
        mock_action_executor = Mock()
        mock_action_executor.load_action_configurations.return_value = {
            'evaluate_weapon_recipes': {
                'weapon_stat_weights': {
                    'attack_fire': 1.0,
                    'attack_earth': 1.0,
                    'attack_water': 1.0,
                    'attack_air': 1.0
                }
            }
        }
        mock_action_executor_class.return_value = mock_action_executor
        
        client = Mock()
        
        result = self.action.execute(client)
        self.assertTrue(result['success'])
        self.assertIn('weapons_analyzed', result)
        self.assertIn('best_weapon', result)
        self.assertGreater(len(result['weapons_analyzed']), 0)

    def test_execute_exception_handling(self):
        """Test exception handling during execution."""
        client = Mock()
        
        with patch('src.controller.actions.evaluate_weapon_recipes.get_character_api', side_effect=Exception("API Error")):
            result = self.action.execute(client)
            self.assertFalse(result['success'])
            self.assertIn('Weapon recipe evaluation failed: API Error', result['error'])

    def test_execute_has_goap_attributes(self):
        """Test that EvaluateWeaponRecipesAction has expected GOAP attributes."""
        self.assertTrue(hasattr(EvaluateWeaponRecipesAction, 'conditions'))
        self.assertTrue(hasattr(EvaluateWeaponRecipesAction, 'reactions'))
        self.assertTrue(hasattr(EvaluateWeaponRecipesAction, 'weights'))
        self.assertTrue(hasattr(EvaluateWeaponRecipesAction, 'g'))


if __name__ == '__main__':
    unittest.main()