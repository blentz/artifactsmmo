"""Test for PlanCraftingMaterialsAction"""

import unittest
from unittest.mock import Mock, patch

from src.controller.actions.plan_crafting_materials import PlanCraftingMaterialsAction
from test.fixtures import MockActionContext, create_mock_client


class TestPlanCraftingMaterialsAction(unittest.TestCase):
    """Test cases for PlanCraftingMaterialsAction"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.character_name = "TestCharacter"
        self.action = PlanCraftingMaterialsAction()
        self.mock_client = create_mock_client()
        
        # Create mock knowledge base
        self.mock_knowledge_base = Mock()
    
    def test_initialization(self):
        """Test action initialization"""
        self.assertIsInstance(self.action, PlanCraftingMaterialsAction)
        # Action should have no parameters stored as instance variables
        self.assertFalse(hasattr(self.action, 'character_name'))
        self.assertFalse(hasattr(self.action, 'target_item'))
    
    @patch('src.controller.actions.plan_crafting_materials.get_character_api')
    def test_execute_success_all_materials_available(self, mock_get_character):
        """Test successful execution when all materials are available"""
        # Mock character data with inventory
        mock_character = Mock()
        mock_character.data = Mock()
        mock_character.data.inventory = [
            Mock(code='wooden_stick', quantity=1),
            Mock(code='ash_wood', quantity=10)
        ]
        mock_character.data.weapon_slot = 'wooden_stick'
        mock_get_character.return_value = mock_character
        
        # Mock knowledge base responses
        self.mock_knowledge_base.get_item_data.side_effect = lambda code, **kwargs: {
            'wooden_staff': {
                'name': 'Wooden Staff',
                'craft_data': {
                    'skill': 'weaponcrafting',
                    'items': [
                        {'code': 'wooden_stick', 'quantity': 1},
                        {'code': 'ash_wood', 'quantity': 4}
                    ]
                }
            },
            'wooden_stick': {'name': 'Wooden Stick', 'type': 'weapon'},
            'ash_wood': {'name': 'Ash Wood', 'type': 'resource', 'sources': ['ash_tree']}
        }.get(code, {})
        
        # Create context with selected_weapon
        context = MockActionContext(
            character_name=self.character_name,
            knowledge_base=self.mock_knowledge_base,
            selected_weapon='wooden_staff'
        )
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify success
        self.assertTrue(result['success'])
        self.assertEqual(result['target_item'], 'wooden_staff')
        self.assertTrue(result['materials_sufficient'])
        self.assertEqual(len(result['missing_materials']), 0)
        self.assertEqual(result['materials_available'], 2)
    
    @patch('src.controller.actions.plan_crafting_materials.get_character_api')
    def test_execute_missing_materials(self, mock_get_character):
        """Test execution when materials are missing"""
        # Mock character data with insufficient inventory
        mock_character = Mock()
        mock_character.data = Mock()
        mock_character.data.inventory = [
            Mock(code='ash_wood', quantity=2)  # Not enough ash_wood
        ]
        mock_character.data.weapon_slot = ''  # No weapon equipped
        mock_get_character.return_value = mock_character
        
        # Mock knowledge base responses
        self.mock_knowledge_base.get_item_data.side_effect = lambda code, **kwargs: {
            'wooden_staff': {
                'name': 'Wooden Staff',
                'craft_data': {
                    'skill': 'weaponcrafting',
                    'items': [
                        {'code': 'wooden_stick', 'quantity': 1},
                        {'code': 'ash_wood', 'quantity': 4}
                    ]
                }
            },
            'wooden_stick': {'name': 'Wooden Stick', 'type': 'weapon'},
            'ash_wood': {'name': 'Ash Wood', 'type': 'resource', 'sources': ['ash_tree']}
        }.get(code, {})
        
        # Create context
        context = MockActionContext(
            character_name=self.character_name,
            knowledge_base=self.mock_knowledge_base,
            selected_weapon='wooden_staff'
        )
        
        # Execute action
        result = self.action.execute(self.mock_client, context)
        
        # Verify success with missing materials
        self.assertTrue(result['success'])
        self.assertEqual(result['target_item'], 'wooden_staff')
        self.assertFalse(result['materials_sufficient'])
        self.assertTrue(result['need_resources'])
        self.assertEqual(len(result['missing_materials']), 2)  # Missing both materials
    
    def test_execute_no_target_item(self):
        """Test execution when no target item is specified"""
        context = MockActionContext(
            character_name=self.character_name,
            knowledge_base=self.mock_knowledge_base,
            action_context={}  # No selected weapon
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result['success'])
        self.assertIn('No target item specified', result['error'])
    
    def test_execute_item_not_craftable(self):
        """Test execution when item is not craftable"""
        # Mock knowledge base response for non-craftable item
        self.mock_knowledge_base.get_item_data.return_value = {
            'name': 'Wooden Stick',
            'type': 'weapon'
            # No craft_data
        }
        
        context = MockActionContext(
            character_name=self.character_name,
            knowledge_base=self.mock_knowledge_base,
            selected_weapon='wooden_staff'
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result['success'])
        self.assertIn('not craftable', result['error'])
    
    @patch('src.controller.actions.plan_crafting_materials.get_character_api')
    def test_equipped_items_counted(self, mock_get_character):
        """Test that equipped items are considered when checking materials"""
        # Mock character data with equipped weapon
        mock_character = Mock()
        mock_character.data = Mock()
        mock_character.data.inventory = [
            Mock(code='ash_wood', quantity=4)
        ]
        mock_character.data.weapon_slot = 'wooden_stick'  # Equipped weapon
        mock_get_character.return_value = mock_character
        
        # Mock knowledge base responses
        self.mock_knowledge_base.get_item_data.side_effect = lambda code, **kwargs: {
            'wooden_staff': {
                'name': 'Wooden Staff',
                'craft_data': {
                    'skill': 'weaponcrafting',
                    'items': [
                        {'code': 'wooden_stick', 'quantity': 1},
                        {'code': 'ash_wood', 'quantity': 4}
                    ]
                }
            },
            'wooden_stick': {'name': 'Wooden Stick', 'type': 'weapon'},
            'ash_wood': {'name': 'Ash Wood', 'type': 'resource'}
        }.get(code, {})
        
        context = MockActionContext(
            character_name=self.character_name,
            knowledge_base=self.mock_knowledge_base,
            selected_weapon='wooden_staff'
        )
        
        result = self.action.execute(self.mock_client, context)
        
        # Should have all materials (equipped wooden_stick + inventory ash_wood)
        self.assertTrue(result['success'])
        self.assertTrue(result['materials_sufficient'])
        self.assertEqual(len(result['missing_materials']), 0)
    
    def test_repr(self):
        """Test string representation"""
        expected = "PlanCraftingMaterialsAction()"
        self.assertEqual(repr(self.action), expected)


if __name__ == '__main__':
    unittest.main()