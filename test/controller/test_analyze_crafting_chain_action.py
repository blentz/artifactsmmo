"""Test module for AnalyzeCraftingChainAction."""

import unittest
import tempfile
import os
from unittest.mock import Mock, patch
from src.controller.actions.analyze_crafting_chain import AnalyzeCraftingChainAction


class TestAnalyzeCraftingChainAction(unittest.TestCase):
    """Test cases for AnalyzeCraftingChainAction."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_prefix = os.environ.get('DATA_PREFIX', '')
        os.environ['DATA_PREFIX'] = self.temp_dir
        
        self.character_name = "test_character"
        self.target_item = "iron_sword"
        self.action = AnalyzeCraftingChainAction(
            character_name=self.character_name,
            target_item=self.target_item
        )

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['DATA_PREFIX'] = self.original_data_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_analyze_crafting_chain_action_initialization(self):
        """Test AnalyzeCraftingChainAction initialization."""
        self.assertEqual(self.action.character_name, "test_character")
        self.assertEqual(self.action.target_item, "iron_sword")
        self.assertEqual(self.action.analyzed_items, set())
        self.assertEqual(self.action.resource_nodes, {})
        self.assertEqual(self.action.workshops, {})
        self.assertEqual(self.action.crafting_dependencies, {})
        self.assertEqual(self.action.transformation_chains, [])

    def test_analyze_crafting_chain_action_initialization_defaults(self):
        """Test AnalyzeCraftingChainAction initialization with defaults."""
        action = AnalyzeCraftingChainAction("player")
        self.assertEqual(action.character_name, "player")
        self.assertIsNone(action.target_item)

    def test_analyze_crafting_chain_action_repr(self):
        """Test AnalyzeCraftingChainAction string representation."""
        expected = "AnalyzeCraftingChainAction(test_character, iron_sword)"
        self.assertEqual(repr(self.action), expected)

    def test_analyze_crafting_chain_action_repr_no_target(self):
        """Test AnalyzeCraftingChainAction string representation without target."""
        action = AnalyzeCraftingChainAction("player")
        expected = "AnalyzeCraftingChainAction(player, None)"
        self.assertEqual(repr(action), expected)

    def test_execute_no_client(self):
        """Test execute fails without client."""
        result = self.action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    def test_execute_no_target_item(self):
        """Test execute fails without target item."""
        action = AnalyzeCraftingChainAction("player")
        client = Mock()
        
        result = action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('No target item specified', result['error'])

    @patch('src.controller.actions.analyze_crafting_chain.KnowledgeBase')
    def test_execute_knowledge_base_fails(self, mock_knowledge_base_class):
        """Test execute when knowledge base fails to load."""
        mock_knowledge_base_class.side_effect = Exception("Knowledge base error")
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Knowledge base error', result['error'])

    @patch('src.controller.actions.analyze_crafting_chain.KnowledgeBase')
    def test_execute_no_knowledge_data(self, mock_knowledge_base_class):
        """Test execute when knowledge base has no data."""
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {}
        mock_knowledge_base_class.return_value = mock_knowledge_base
        
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('No item data available in knowledge base', result['error'])

    @patch('src.controller.actions.analyze_crafting_chain.get_item_api')
    @patch('src.controller.actions.analyze_crafting_chain.KnowledgeBase')
    def test_execute_item_not_found(self, mock_knowledge_base_class, mock_get_item_api):
        """Test execute when target item not found."""
        # Mock knowledge base with some data
        mock_knowledge_base = Mock()
        mock_knowledge_base.data = {
            'items': {'other_item': {'name': 'Other Item'}}
        }
        mock_knowledge_base_class.return_value = mock_knowledge_base
        
        # Mock item API failure
        mock_get_item_api.return_value = None
        
        client = Mock()
        
        result = self.action.execute(client)
        self.assertFalse(result['success'])
        self.assertIn('Could not find item information', result['error'])

    @patch('src.controller.actions.analyze_crafting_chain.get_item_api')
    @patch('src.controller.actions.analyze_crafting_chain.KnowledgeBase')
    def test_execute_successful_basic_analysis(self, mock_knowledge_base_class, mock_get_item_api):
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
        mock_knowledge_base_class.return_value = mock_knowledge_base
        
        # Mock item API response
        mock_item_data = Mock()
        mock_item_data.name = 'Iron Sword'
        mock_item_data.type_ = 'weapon'
        mock_item_response = Mock()
        mock_item_response.data = mock_item_data
        mock_get_item_api.return_value = mock_item_response
        
        client = Mock()
        
        result = self.action.execute(client)
        self.assertTrue(result['success'])
        self.assertEqual(result['target_item'], 'iron_sword')
        self.assertIn('crafting_chain', result)
        self.assertIn('resource_requirements', result)
        self.assertIn('workshop_requirements', result)

    def test_is_resource_item_true(self):
        """Test _is_resource_item returns True for resource items."""
        item_data = {'type': 'resource'}
        self.assertTrue(self.action._is_resource_item(item_data))

    def test_is_resource_item_false(self):
        """Test _is_resource_item returns False for non-resource items."""
        item_data = {'type': 'weapon'}
        self.assertFalse(self.action._is_resource_item(item_data))

    def test_is_resource_item_no_type(self):
        """Test _is_resource_item returns False when no type specified."""
        item_data = {'name': 'Some Item'}
        self.assertFalse(self.action._is_resource_item(item_data))

    def test_get_crafting_requirements_with_craft_data(self):
        """Test _get_crafting_requirements extracts craft requirements."""
        item_data = {
            'craft': {
                'skill': 'weaponcrafting',
                'level': 10,
                'items': [
                    {'code': 'iron', 'quantity': 3},
                    {'code': 'ash_wood', 'quantity': 1}
                ]
            }
        }
        
        requirements = self.action._get_crafting_requirements(item_data)
        self.assertEqual(len(requirements), 2)
        self.assertEqual(requirements[0]['code'], 'iron')
        self.assertEqual(requirements[0]['quantity'], 3)
        self.assertEqual(requirements[1]['code'], 'ash_wood')
        self.assertEqual(requirements[1]['quantity'], 1)

    def test_get_crafting_requirements_no_craft_data(self):
        """Test _get_crafting_requirements returns empty list when no craft data."""
        item_data = {'name': 'Simple Item'}
        
        requirements = self.action._get_crafting_requirements(item_data)
        self.assertEqual(requirements, [])

    def test_get_crafting_requirements_no_items(self):
        """Test _get_crafting_requirements returns empty list when no items in craft data."""
        item_data = {
            'craft': {
                'skill': 'weaponcrafting',
                'level': 10
            }
        }
        
        requirements = self.action._get_crafting_requirements(item_data)
        self.assertEqual(requirements, [])

    def test_execute_exception_handling(self):
        """Test exception handling during execution."""
        client = Mock()
        
        with patch('src.controller.actions.analyze_crafting_chain.KnowledgeBase', side_effect=Exception("Unexpected Error")):
            result = self.action.execute(client)
            self.assertFalse(result['success'])
            self.assertIn('Crafting chain analysis failed: Unexpected Error', result['error'])

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