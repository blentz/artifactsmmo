"""Test module for AnalyzeCraftingChainAction."""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.controller.actions.analyze_crafting_chain import AnalyzeCraftingChainAction

from test.fixtures import create_mock_client


class TestAnalyzeCraftingChainAction(unittest.TestCase):
    """Test cases for AnalyzeCraftingChainAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_prefix = os.environ.get('DATA_PREFIX', '')
        os.environ['DATA_PREFIX'] = self.temp_dir
        
        self.character_name = "test_character"
        self.target_item = "iron_sword"
        self.action = AnalyzeCraftingChainAction()

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['DATA_PREFIX'] = self.original_data_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_analyze_crafting_chain_action_initialization(self):
        """Test AnalyzeCraftingChainAction initialization."""
        # Action should have no parameters stored as instance variables
        self.assertIsInstance(self.action, AnalyzeCraftingChainAction)
        self.assertFalse(hasattr(self.action, 'character_name'))
        self.assertFalse(hasattr(self.action, 'target_item'))
        # analyzed_items is a valid instance variable for the action's functionality
        self.assertTrue(hasattr(self.action, 'analyzed_items'))

    def test_analyze_crafting_chain_action_initialization_defaults(self):
        """Test AnalyzeCraftingChainAction initialization with defaults."""
        action = AnalyzeCraftingChainAction()
        # Action should have no parameters stored as instance variables
        self.assertIsInstance(action, AnalyzeCraftingChainAction)
        self.assertFalse(hasattr(action, 'character_name'))
        self.assertFalse(hasattr(action, 'target_item'))

    def test_analyze_crafting_chain_action_repr(self):
        """Test AnalyzeCraftingChainAction string representation."""
        expected = "AnalyzeCraftingChainAction()"
        self.assertEqual(repr(self.action), expected)

    def test_analyze_crafting_chain_action_repr_no_target(self):
        """Test AnalyzeCraftingChainAction string representation without target."""
        action = AnalyzeCraftingChainAction()
        expected = "AnalyzeCraftingChainAction()"
        self.assertEqual(repr(action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name="test_character", target_item="iron_sword")
        result = self.action.execute(None, context)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    def test_execute_no_target_item(self):
        """Test execute fails without target item."""
        from test.fixtures import MockActionContext
        action = AnalyzeCraftingChainAction()
        client = create_mock_client()
        context = MockActionContext(character_name="player")
        
        result = action.execute(client, context)
        self.assertFalse(result['success'])
        self.assertIn('No target item specified', result['error'])

    def test_execute_knowledge_base_fails(self):
        """Test execute when knowledge base fails to load."""
        # Create a knowledge base that raises an exception when accessing data
        mock_knowledge_base = Mock()
        mock_knowledge_base.data.side_effect = Exception("Knowledge base error")
        
        client = create_mock_client()
        
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name="test_character", target_item="iron_sword", knowledge_base=mock_knowledge_base)
        result = self.action.execute(client, context)
        self.assertFalse(result['success'])
        self.assertIn('Crafting chain analysis failed:', result['error'])

    def test_execute_no_knowledge_data(self):
        """Test execute when knowledge base has no data."""
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {}
        
        client = create_mock_client()
        
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name="test_character", target_item="iron_sword", knowledge_base=mock_knowledge_base)
        result = self.action.execute(client, context)
        self.assertFalse(result['success'])
        self.assertIn('Crafting chain analysis failed:', result['error'])

    @patch('src.controller.actions.analyze_crafting_chain.get_item_api')
    def test_execute_item_not_found(self, mock_get_item_api):
        """Test execute when target item not found."""
        # Mock knowledge base with some data
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'items': {'other_item': {'name': 'Other Item'}}
        }
        
        # Mock item API failure
        mock_get_item_api.return_value = None
        
        client = create_mock_client()
        
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name="test_character", target_item="iron_sword", knowledge_base=mock_knowledge_base)
        result = self.action.execute(client, context)
        self.assertFalse(result['success'])
        self.assertIn('Could not analyze crafting chain', result['error'])

    @patch('src.controller.actions.analyze_crafting_chain.get_item_api')
    def test_execute_successful_basic_analysis(self, mock_get_item_api):
        """Test successful crafting chain analysis for a simple item."""
        # Mock knowledge base with item data
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'items': {
                'iron_sword': {
                    'name': 'Iron Sword',
                    'type': 'weapon',
                    'level': 10,
                    'craft': {
                        'skill': 'weaponcrafting',
                        'level': 10,
                        'items': [
                            {'code': 'iron', 'quantity': 3},
                            {'code': 'ash_wood', 'quantity': 1}
                        ]
                    }
                },
                'iron': {'name': 'Iron', 'type': 'resource'},
                'ash_wood': {'name': 'Ash Wood', 'type': 'resource'}
            },
            'resources': {
                'iron_rocks': {'code': 'iron_rocks', 'drop': [{'code': 'iron', 'quantity': 1}]},
                'ash_tree': {'code': 'ash_tree', 'drop': [{'code': 'ash_wood', 'quantity': 1}]}
            }
        }
        
        # Mock item API response
        mock_item_data = Mock()
        mock_item_data.name = 'Iron Sword'
        mock_item_data.type_ = 'weapon'
        mock_item_response = Mock()
        mock_item_response.data = mock_item_data
        mock_get_item_api.return_value = mock_item_response
        
        client = create_mock_client()
        
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name="test_character", target_item="iron_sword", knowledge_base=mock_knowledge_base)
        result = self.action.execute(client, context)
        self.assertTrue(result['success'])
        self.assertEqual(result['target_item'], 'iron_sword')
        self.assertIn('chain_analysis', result)
        self.assertIn('raw_materials_needed', result)
        self.assertIn('workshops_required', result)

    def test_action_initialization_attributes(self):
        """Test that action has expected attributes after initialization."""
        # Test that the action properly initializes its tracking attributes
        self.assertIsInstance(self.action.analyzed_items, set)
        self.assertIsInstance(self.action.resource_nodes, dict)
        self.assertIsInstance(self.action.workshops, dict)
        self.assertIsInstance(self.action.crafting_dependencies, dict)
        self.assertIsInstance(self.action.transformation_chains, list)

    def test_execute_exception_handling(self):
        """Test exception handling during execution."""
        client = create_mock_client()
        
        # Create a knowledge base that will raise an exception when accessed
        mock_knowledge_base = Mock()
        mock_knowledge_base.data.side_effect = Exception("Unexpected Error")
        
        from test.fixtures import MockActionContext
        context = MockActionContext(character_name="test_character", target_item="iron_sword", knowledge_base=mock_knowledge_base)
        result = self.action.execute(client, context)
        self.assertFalse(result['success'])
        self.assertIn('Crafting chain analysis failed:', result['error'])

    def test_execute_has_goap_attributes(self):
        """Test that AnalyzeCraftingChainAction has expected GOAP attributes."""
        self.assertTrue(hasattr(AnalyzeCraftingChainAction, 'conditions'))
        self.assertTrue(hasattr(AnalyzeCraftingChainAction, 'reactions'))
        self.assertTrue(hasattr(AnalyzeCraftingChainAction, 'weights'))
        self.assertTrue(hasattr(AnalyzeCraftingChainAction, 'g'))

    def test_goap_conditions(self):
        """Test GOAP conditions are properly defined."""
        expected_conditions = {"character_alive": True}
        self.assertEqual(AnalyzeCraftingChainAction.conditions, expected_conditions)

    def test_goap_reactions(self):
        """Test GOAP reactions are properly defined."""
        expected_reactions = {"craft_plan_available": True, "material_requirements_known": True, "crafting_opportunities_known": True}
        self.assertEqual(AnalyzeCraftingChainAction.reactions, expected_reactions)

    def test_goap_weights(self):
        """Test GOAP weights are properly defined."""
        expected_weights = {"craft_plan_available": 20}
        self.assertEqual(AnalyzeCraftingChainAction.weights, expected_weights)

    def test_calculate_total_resource_requirements(self):
        """Test _calculate_total_resource_requirements aggregates quantities."""
        # This tests a method that should exist for aggregating resource requirements
        chain_data = {
            'iron_sword': [{'code': 'iron', 'quantity': 3}, {'code': 'ash_wood', 'quantity': 1}],
            'iron_helmet': [{'code': 'iron', 'quantity': 2}]
        }
        
        # Test basic functionality if the method exists
        if hasattr(self.action, '_calculate_total_resource_requirements'):
            totals = self.action._calculate_total_resource_requirements(chain_data)
            self.assertEqual(totals.get('iron', 0), 5)  # 3 + 2
            self.assertEqual(totals.get('ash_wood', 0), 1)


if __name__ == '__main__':
    unittest.main()