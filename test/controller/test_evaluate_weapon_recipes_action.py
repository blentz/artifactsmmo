"""Test module for EvaluateWeaponRecipesAction."""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.controller.actions.evaluate_weapon_recipes import EvaluateWeaponRecipesAction
from src.lib.state_parameters import StateParameters

from test.fixtures import create_mock_client
from test.test_base import UnifiedContextTestBase


class TestEvaluateWeaponRecipesAction(UnifiedContextTestBase):
    """Test cases for EvaluateWeaponRecipesAction."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_prefix = os.environ.get('DATA_PREFIX', '')
        os.environ['DATA_PREFIX'] = self.temp_dir
        
        self.character_name = "test_character"
        # Mock knowledge base with simplified structure
        self.mock_knowledge_base = Mock()
        self.mock_knowledge_base.data = {
            'items': {
                'wooden_staff': {
                    'name': 'Wooden Staff',
                    'level': 5,
                    'type': 'weapon',
                    'craft_data': {
                        'skill': 'weaponcrafting',
                        'level': 3,
                        'items': [{'code': 'ash_wood', 'quantity': 2}]
                    }
                }
            }
        }
        
        self.action = EvaluateWeaponRecipesAction()
        
        # Set up context using StateParameters
        self.context.set(StateParameters.CHARACTER_NAME, self.character_name)
        self.context.set(StateParameters.CHARACTER_LEVEL, 5)
        self.context.knowledge_base = self.mock_knowledge_base

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['DATA_PREFIX'] = self.original_data_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_evaluate_weapon_recipes_action_initialization(self):
        """Test EvaluateWeaponRecipesAction initialization."""
        self.assertIsNotNone(self.action)

    def test_evaluate_weapon_recipes_action_initialization_defaults(self):
        """Test EvaluateWeaponRecipesAction initialization with defaults."""
        action = EvaluateWeaponRecipesAction()
        self.assertIsNotNone(action)

    def test_evaluate_weapon_recipes_action_repr(self):
        """Test EvaluateWeaponRecipesAction string representation."""
        # Simplified action doesn't store character_name or current_weapon
        result = str(self.action)
        self.assertIn("EvaluateWeaponRecipesAction", result)

    def test_evaluate_weapon_recipes_action_repr_no_current_weapon(self):
        """Test EvaluateWeaponRecipesAction string representation without current weapon."""
        # Simplified action doesn't store current_weapon
        result = str(self.action)
        self.assertIn("EvaluateWeaponRecipesAction", result)

    def test_execute_character_api_fails(self):
        """Test execute when character API fails."""
        # Simplified action doesn't call character API
        client = create_mock_client()
        result = self.action.execute(client, self.context)
        # Should succeed since it doesn't depend on character API
        self.assertTrue(result.success)

    def test_execute_character_api_no_data(self):
        """Test execute when character API returns no data."""
        # Simplified action doesn't call character API
        client = create_mock_client()
        result = self.action.execute(client, self.context)
        # Should succeed since it doesn't depend on character API
        self.assertTrue(result.success)

    def test_execute_exception_handling(self):
        """Test execute with exception handling."""
        client = create_mock_client()
        # Cause an exception by removing knowledge base
        self.context.knowledge_base = None
        
        result = self.action.execute(client, self.context)
        self.assertFalse(result.success)
        self.assertIn("No knowledge base available", result.error)

    def test_execute_has_goap_attributes(self):
        """Test that action has GOAP attributes."""
        self.assertTrue(hasattr(self.action, 'conditions'))
        self.assertTrue(hasattr(self.action, 'reactions'))
        self.assertTrue(hasattr(self.action, 'weight'))

    def test_execute_no_client(self):
        """Test execute without client."""
        result = self.action.execute(None, self.context)
        # Should succeed since simplified action doesn't require client
        self.assertTrue(result.success)

    def test_execute_no_weapons_data(self):
        """Test execute when no weapons data is available."""
        client = create_mock_client()
        # Remove weapons from knowledge base
        self.mock_knowledge_base.data = {'items': {}}
        
        result = self.action.execute(client, self.context)
        self.assertFalse(result.success)
        self.assertIn("No suitable weapons found", result.error)

    def test_execute_success_basic(self):
        """Test successful execution with basic setup."""
        client = create_mock_client()
        
        result = self.action.execute(client, self.context)
        self.assertTrue(result.success)
        self.assertIn('selected_weapon', result.data)
        self.assertEqual(result.data['selected_weapon'], 'wooden_staff')
        self.assertEqual(result.data['target_item'], 'wooden_staff')
        self.assertEqual(result.data['item_code'], 'wooden_staff')

    def test_execute_knowledge_base_fails(self):
        """Test execute when knowledge base is not available."""
        client = create_mock_client()
        self.context.knowledge_base = None
        
        result = self.action.execute(client, self.context)
        self.assertFalse(result.success)
        self.assertIn("No knowledge base available", result.error)