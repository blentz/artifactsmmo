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
    
    def test_execute_no_item_data(self):
        """Test execution when item data not found"""
        # Mock knowledge base to return None for item data
        self.mock_knowledge_base.get_item_data.return_value = None
        
        context = MockActionContext(
            character_name=self.character_name,
            target_item='nonexistent_item',
            knowledge_base=self.mock_knowledge_base
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertIn('Could not find item data for nonexistent_item', result.error)
    
    def test_execute_no_materials_required(self):
        """Test execution when item has no required materials"""
        # Mock item data with empty materials list
        self.mock_knowledge_base.get_item_data.return_value = {
            'name': 'Test Item',
            'craft_data': {
                'skill': 'crafting',
                'items': []  # Empty materials list
            }
        }
        
        context = MockActionContext(
            character_name=self.character_name,
            target_item='test_item',
            knowledge_base=self.mock_knowledge_base
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertIn('No materials required for test_item', result.error)
    
    @patch('src.controller.actions.plan_crafting_materials.get_character_api')
    def test_get_character_inventory_api_fails(self, mock_get_character):
        """Test _get_character_inventory when character API returns None"""
        # Mock character API to return None
        mock_get_character.return_value = None
        
        result = self.action._get_character_inventory(self.mock_client, self.character_name)
        
        self.assertEqual(result, {})
    
    def test_plan_includes_craft_material_step(self):
        """Test execute includes craft step for craftable materials"""
        # Mock knowledge base to return item with craftable material
        self.mock_knowledge_base.get_item_data.return_value = {
            'name': 'Test Item',
            'craft_data': {
                'skill': 'crafting',
                'items': [
                    {'code': 'refined_material', 'quantity': 5}
                ]
            }
        }
        
        # Mock character with no materials
        with patch('src.controller.actions.plan_crafting_materials.get_character_api') as mock_get_char:
            mock_char = Mock()
            mock_char.data = Mock()
            mock_char.data.inventory = []  # No materials
            mock_get_char.return_value = mock_char
            
            # Mock material as craftable
            self.mock_knowledge_base.get_material_info.return_value = {
                'craftable': True,
                'craft_skill': 'smithing',
                'craft_materials': [{'code': 'raw_material', 'quantity': 5}]
            }
            
            context = MockActionContext(
                character_name=self.character_name,
                target_item='test_item',
                knowledge_base=self.mock_knowledge_base
            )
            
            result = self.action.execute(self.mock_client, context)
            
            # Check that the plan includes craft_material step
            self.assertTrue(result.success)
            self.assertIn('crafting_plan', result.data)
            plan = result.data['crafting_plan']
            
            # Find the craft_material step
            craft_steps = [s for s in plan['steps'] if s['action'] == 'craft_material']
            self.assertEqual(len(craft_steps), 1)
            self.assertEqual(craft_steps[0]['item'], 'refined_material')
            self.assertEqual(craft_steps[0]['quantity'], 5)
    
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
        self.assertTrue(result.success)
        self.assertEqual(result.data['target_item'], 'wooden_staff')
        self.assertTrue(result.data['materials_sufficient'])
        self.assertEqual(len(result.data['missing_materials']), 0)
        self.assertEqual(result.data['materials_available'], 2)
    
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
        self.assertTrue(result.success)
        self.assertEqual(result.data['target_item'], 'wooden_staff')
        self.assertFalse(result.data['materials_sufficient'])
        self.assertTrue(result.data['need_resources'])
        self.assertEqual(len(result.data['missing_materials']), 2)  # Missing both materials
    
    def test_execute_no_target_item(self):
        """Test execution when no target item is specified"""
        context = MockActionContext(
            character_name=self.character_name,
            knowledge_base=self.mock_knowledge_base,
            action_context={}  # No selected weapon
        )
        
        result = self.action.execute(self.mock_client, context)
        
        self.assertFalse(result.success)
        self.assertIn('No target item specified', result.error)
    
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
        
        self.assertFalse(result.success)
        self.assertIn('not craftable', result.error)
    
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
        self.assertTrue(result.success)
        self.assertTrue(result.data['materials_sufficient'])
        self.assertEqual(len(result.data['missing_materials']), 0)
    
    def test_repr(self):
        """Test string representation"""
        expected = "PlanCraftingMaterialsAction()"
        self.assertEqual(repr(self.action), expected)


if __name__ == '__main__':
    unittest.main()