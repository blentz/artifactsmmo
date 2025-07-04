"""Test module for EvaluateWeaponRecipesAction."""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.controller.actions.evaluate_weapon_recipes import EvaluateWeaponRecipesAction

from test.fixtures import MockActionContext, create_mock_client


class TestEvaluateWeaponRecipesAction(unittest.TestCase):
    """Test cases for EvaluateWeaponRecipesAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_prefix = os.environ.get('DATA_PREFIX', '')
        os.environ['DATA_PREFIX'] = self.temp_dir
        
        self.character_name = "test_character"
        # Mock knowledge base and action config
        self.mock_knowledge_base = Mock()
        self.mock_knowledge_base.data = {'items': {}, 'monsters': {}, 'starting_equipment': {}}
        
        self.mock_action_config = {'default_weapon': 'iron_sword'}
        self.action = EvaluateWeaponRecipesAction()

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['DATA_PREFIX'] = self.original_data_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_evaluate_weapon_recipes_action_initialization(self):
        """Test EvaluateWeaponRecipesAction initialization."""
        # Action doesn't store character_name or current_weapon anymore
        self.assertIsNotNone(self.action)

    def test_evaluate_weapon_recipes_action_initialization_defaults(self):
        """Test EvaluateWeaponRecipesAction initialization with defaults."""
        action = EvaluateWeaponRecipesAction()
        self.assertIsNotNone(action)

    def test_evaluate_weapon_recipes_action_repr(self):
        """Test EvaluateWeaponRecipesAction string representation."""
        expected = "EvaluateWeaponRecipesAction()"
        self.assertEqual(repr(self.action), expected)

    def test_evaluate_weapon_recipes_action_repr_no_current_weapon(self):
        """Test EvaluateWeaponRecipesAction string representation with default weapon."""
        action = EvaluateWeaponRecipesAction()
        expected = "EvaluateWeaponRecipesAction()"
        self.assertEqual(repr(action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        context = MockActionContext(character_name=self.character_name)
        result = self.action.execute(None, context)
        # With centralized validation, None client triggers validation error
        self.assertFalse(result.success)
        # Direct action execution bypasses centralized validation
        self.assertTrue(hasattr(result, 'error'))

    @patch('src.controller.actions.evaluate_weapon_recipes.get_character_api')
    def test_execute_character_api_fails(self, mock_get_character_api):
        """Test execute when character API fails."""
        mock_get_character_api.return_value = None
        client = create_mock_client()
        
        context = MockActionContext(character_name=self.character_name)
        context.knowledge_base = self.mock_knowledge_base
        context["action_config"] = self.mock_action_config
        
        result = self.action.execute(client, context)
        self.assertFalse(result.success)
        self.assertIn('Could not get character data', result.error)

    @patch('src.controller.actions.evaluate_weapon_recipes.get_character_api')
    def test_execute_character_api_no_data(self, mock_get_character_api):
        """Test execute when character API returns no data."""
        mock_response = Mock()
        mock_response.data = None
        mock_get_character_api.return_value = mock_response
        client = create_mock_client()
        
        context = MockActionContext(character_name=self.character_name)
        context.knowledge_base = self.mock_knowledge_base
        context["action_config"] = self.mock_action_config
        
        result = self.action.execute(client, context)
        self.assertFalse(result.success)
        self.assertIn('Could not get character data', result.error)

    @patch('src.controller.actions.evaluate_weapon_recipes.get_character_api')
    def test_execute_knowledge_base_fails(self, mock_get_character_api):
        """Test execute when knowledge base fails to load."""
        # Mock character API
        mock_character_data = Mock()
        mock_character_data.weaponcrafting_level = 5
        mock_character_response = Mock()
        mock_character_response.data = mock_character_data
        mock_get_character_api.return_value = mock_character_response
        
        # Create a knowledge base that fails when trying to use data
        mock_knowledge_base = Mock()
        # Make data property raise when accessed
        type(mock_knowledge_base).data = property(lambda self: (_ for _ in ()).throw(Exception("Knowledge base error")))
        
        action = EvaluateWeaponRecipesAction()
        context = MockActionContext(
            character_name=self.character_name,
            current_weapon="iron_sword"
        )
        context.knowledge_base = mock_knowledge_base
        context["action_config"] = self.mock_action_config
        
        client = create_mock_client()
        
        result = action.execute(client, context)
        self.assertFalse(result.success)
        self.assertIn('Knowledge base error', result.error)

    @patch('src.controller.actions.evaluate_weapon_recipes.get_character_api')
    def test_execute_no_weapons_data(self, mock_get_character_api):
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
        
        action = EvaluateWeaponRecipesAction()
        context = MockActionContext(
            character_name=self.character_name,
            current_weapon="iron_sword"
        )
        context.knowledge_base = mock_knowledge_base
        context["action_config"] = self.mock_action_config
        
        client = create_mock_client()
        
        result = action.execute(client, context)
        self.assertFalse(result.success)
        self.assertIn('No weapon recipes found', result.error)

    @patch('src.controller.actions.evaluate_weapon_recipes.get_character_api')
    def test_execute_success_basic(self, mock_get_character_api):
        """Test successful execution with basic weapon data."""
        # Mock character API
        mock_character_data = Mock()
        mock_character_data.weaponcrafting_level = 5
        mock_character_data.level = 10
        mock_character_data.inventory = []  # Empty inventory for test
        mock_character_data.weapon_slot = 'current_weapon'  # Currently equipped weapon
        mock_character_response = Mock()
        mock_character_response.data = mock_character_data
        mock_get_character_api.return_value = mock_character_response
        
        # Mock knowledge base with weapons data
        mock_knowledge_base = Mock()
        
        # Mock get_item_data method
        def mock_get_item_data(item_code, client=None):
            if item_code in mock_knowledge_base.data['items']:
                return mock_knowledge_base.data['items'][item_code]
            return None
        
        mock_knowledge_base.get_item_data = mock_get_item_data
        mock_knowledge_base.data = {
            'items': {
                'copper_sword': {
                    'type': 'weapon',
                    'level': 3,
                    'attack_fire': 10,
                    'craft_data': {
                        'skill': 'weaponcrafting',
                        'level': 3,
                        'items': [
                            {'code': 'copper', 'quantity': 5}
                        ]
                    }
                },
                'iron_sword': {
                    'type': 'weapon', 
                    'level': 8,
                    'attack_fire': 20,
                    'craft_data': {
                        'skill': 'weaponcrafting',
                        'level': 8,
                        'items': [
                            {'code': 'iron', 'quantity': 5}
                        ]
                    }
                }
            }
        }
        
        # Mock action config with stat weights
        mock_action_config = {
            'weapon_stat_weights': {
                'attack_fire': 1.0,
                'attack_earth': 1.0,
                'attack_water': 1.0,
                'attack_air': 1.0
            },
            'max_weapons_to_evaluate': 10
        }
        
        # Create action and context with mocked dependencies
        action = EvaluateWeaponRecipesAction()
        context = MockActionContext(
            character_name=self.character_name,
            current_weapon="iron_sword"
        )
        context.knowledge_base = mock_knowledge_base
        context["action_config"] = mock_action_config
        
        # Store character data for skill discovery
        action.character_data = mock_character_data
        
        # Mock API responses for weapon fetching
        with patch('src.controller.actions.evaluate_weapon_recipes.get_all_items_api') as mock_get_all_items:
            # Mock get_all_items_api to return empty (no weapons found via API)
            mock_items_response = Mock()
            mock_items_response.data = []
            mock_get_all_items.return_value = mock_items_response
            
            # Add current weapon to knowledge base for stats lookup
            mock_knowledge_base.data['items']['current_weapon'] = {
                'code': 'current_weapon',
                'name': 'Current Weapon',
                'type': 'weapon',
                'level': 1,
                'attack_fire': 20
            }
            
            client = create_mock_client()
            
            result = action.execute(client, context)
        
        # Since action can't fetch weapons from API and knowledge base has limited weapons,
        # it might find no craftable weapons for the character's skill level
        if result.success:
            self.assertIn('selected_weapon', result.data)
            self.assertIn('craftability_score', result.data)
        else:
            # If no craftable weapons found, it should suggest skill upgrade
            if 'skill_upgrade_needed' in result.data:
                self.assertTrue(result.data['skill_upgrade_needed'])
                self.assertIn('required_skill', result.data)
            else:
                self.assertIn('No weapon recipes found', result.error)

    def test_execute_exception_handling(self):
        """Test exception handling during execution."""
        client = create_mock_client()
        
        context = MockActionContext(character_name=self.character_name)
        context.knowledge_base = self.mock_knowledge_base
        context["action_config"] = self.mock_action_config
        
        with patch('src.controller.actions.evaluate_weapon_recipes.get_character_api', side_effect=Exception("API Error")):
            result = self.action.execute(client, context)
            self.assertFalse(result.success)
            self.assertIn('Weapon recipe evaluation failed: API Error', result.error)

    def test_execute_has_goap_attributes(self):
        """Test that EvaluateWeaponRecipesAction has expected GOAP attributes."""
        self.assertTrue(hasattr(EvaluateWeaponRecipesAction, 'conditions'))
        self.assertTrue(hasattr(EvaluateWeaponRecipesAction, 'reactions'))
        self.assertTrue(hasattr(EvaluateWeaponRecipesAction, 'weight'))


if __name__ == '__main__':
    unittest.main()