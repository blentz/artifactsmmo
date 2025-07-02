"""Tests for PlanCraftingMaterialsAction"""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.controller.actions.plan_crafting_materials import PlanCraftingMaterialsAction

from test.fixtures import MockActionContext


class TestPlanCraftingMaterialsAction(unittest.TestCase):
    """Test cases for PlanCraftingMaterialsAction"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.character_name = "test_character"
        self.client = Mock()
        
        # Create temporary file for knowledge base
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        self.temp_file.close()
        
    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_plan_crafting_materials_initialization(self):
        """Test PlanCraftingMaterialsAction initialization"""
        action = PlanCraftingMaterialsAction()
        self.assertIsNotNone(action)
        
    def test_plan_crafting_materials_initialization_defaults(self):
        """Test PlanCraftingMaterialsAction initialization with defaults"""
        action = PlanCraftingMaterialsAction()
        self.assertIsNotNone(action)
        
    def test_execute_no_client(self):
        """Test execute fails without client"""
        action = PlanCraftingMaterialsAction()
        context = MockActionContext(character_name=self.character_name)
        result = action.execute(None, context)
        # With centralized validation, None client triggers validation error
        self.assertFalse(result["success"])
        # Direct action execution bypasses centralized validation
        self.assertFalse(result.get('success', True))
        
    def test_execute_no_knowledge_base(self):
        """Test execute fails without knowledge base"""
        action = PlanCraftingMaterialsAction()
        context = MockActionContext(
            character_name=self.character_name,
            target_item="wooden_staff"
        )
        context.knowledge_base = None
        result = action.execute(self.client, context)
        self.assertFalse(result['success'])
        self.assertIn('No knowledge base available', result['error'])
        
    def test_execute_no_target_item(self):
        """Test execute fails without target item"""
        action = PlanCraftingMaterialsAction()
        context = MockActionContext(character_name=self.character_name)
        context.knowledge_base = Mock()
        # Don't set target_item in context
        result = action.execute(self.client, context)
        self.assertFalse(result['success'])
        self.assertIn('No target item specified', result['error'])
        
    def test_determine_target_item_from_context(self):
        """Test determining target item from action context"""
        action = PlanCraftingMaterialsAction()
        
        # Test selected_weapon
        context = MockActionContext(selected_weapon='wooden_staff')
        action._context = context  # Set internal context
        target = action._determine_target_item(context)
        self.assertEqual(target, 'wooden_staff')
        
        # Test item_code
        context = MockActionContext(item_code='copper_sword')
        action._context = context
        target = action._determine_target_item(context)
        self.assertEqual(target, 'copper_sword')
        
        # Test target_item in context
        context = MockActionContext(target_item='iron_axe')
        action._context = context
        target = action._determine_target_item(context)
        self.assertEqual(target, 'iron_axe')
        
        # Test no item found
        context = MockActionContext()
        action._context = context
        target = action._determine_target_item(context)
        self.assertIsNone(target)
        
    def test_execute_success_all_materials_available(self):
        """Test successful execution when all materials are available"""
        action = PlanCraftingMaterialsAction()
        
        # Mock knowledge base
        knowledge_base = Mock()
        knowledge_base.get_item_data.return_value = {
            'code': 'wooden_staff',
            'name': 'Wooden Staff',
            'craft_data': {
                'skill': 'weaponcrafting',
                'items': [
                    {'code': 'wooden_stick', 'quantity': 1},
                    {'code': 'ash_wood', 'quantity': 4}
                ]
            }
        }
        
        # Mock character data with all materials
        character_data = Mock()
        character_data.inventory = [
            Mock(code='wooden_stick', quantity=2),
            Mock(code='ash_wood', quantity=10)
        ]
        character_data.weapon_slot = ''  # No equipped weapon
        
        # Configure character API response
        self.client.configure_mock(**{
            'get_character_characters_name_get.return_value': Mock(data=character_data)
        })
        
        with patch('src.controller.actions.plan_crafting_materials.get_character_api') as mock_get_char:
            mock_get_char.return_value = Mock(data=character_data)
            
            context = MockActionContext(
                character_name=self.character_name,
                target_item="wooden_staff"
            )
            context.knowledge_base = knowledge_base
            
            result = action.execute(self.client, context)
            
        self.assertTrue(result['success'])
        self.assertEqual(result['target_item'], 'wooden_staff')
        self.assertTrue(result['materials_sufficient'])
        self.assertFalse(result.get('need_resources', False))
        self.assertEqual(len(result['missing_materials']), 0)
        
    def test_execute_success_missing_materials(self):
        """Test successful execution when materials are missing"""
        action = PlanCraftingMaterialsAction()
        
        # Mock knowledge base
        knowledge_base = Mock()
        knowledge_base.get_item_data.side_effect = lambda item, client=None: {
            'wooden_staff': {
                'code': 'wooden_staff',
                'name': 'Wooden Staff',
                'craft_data': {
                    'skill': 'weaponcrafting',
                    'items': [
                        {'code': 'wooden_stick', 'quantity': 1},
                        {'code': 'ash_wood', 'quantity': 4}
                    ]
                }
            },
            'ash_wood': {
                'code': 'ash_wood',
                'name': 'Ash Wood',
                'type': 'resource',
                'sources': ['ash_tree']
            }
        }.get(item, None)
        
        # Mock character data with only wooden_stick
        character_data = Mock()
        character_data.inventory = []
        character_data.weapon_slot = 'wooden_stick'  # Equipped
        
        # Configure mock to have required attributes
        for attr in ['shield_slot', 'helmet_slot', 'body_armor_slot']:
            setattr(character_data, attr, '')
        
        with patch('src.controller.actions.plan_crafting_materials.get_character_api') as mock_get_char:
            mock_get_char.return_value = Mock(data=character_data)
            
            context = MockActionContext(
                character_name=self.character_name,
                target_item="wooden_staff"
            )
            context.knowledge_base = knowledge_base
            
            result = action.execute(self.client, context)
            
        self.assertTrue(result['success'])
        self.assertEqual(result['target_item'], 'wooden_staff')
        self.assertFalse(result['materials_sufficient'])
        self.assertTrue(result['need_resources'])
        self.assertEqual(len(result['missing_materials']), 1)
        self.assertEqual(result['missing_materials'][0]['code'], 'ash_wood')
        self.assertEqual(result['missing_materials'][0]['missing'], 4)
        
    def test_has_goap_attributes(self):
        """Test that PlanCraftingMaterialsAction has expected GOAP attributes"""
        self.assertTrue(hasattr(PlanCraftingMaterialsAction, 'conditions'))
        self.assertTrue(hasattr(PlanCraftingMaterialsAction, 'reactions'))
        self.assertTrue(hasattr(PlanCraftingMaterialsAction, 'weights'))
        
        # Check specific conditions
        self.assertIn('character_status', PlanCraftingMaterialsAction.conditions)
        self.assertTrue(PlanCraftingMaterialsAction.conditions['character_status']['alive'])
        self.assertIn('best_weapon_selected', PlanCraftingMaterialsAction.conditions)
        
        # Check specific reactions
        self.assertIn('craft_plan_available', PlanCraftingMaterialsAction.reactions)
        self.assertIn('need_resources', PlanCraftingMaterialsAction.reactions)
        
    def test_plan_crafting_materials_repr(self):
        """Test PlanCraftingMaterialsAction string representation"""
        action = PlanCraftingMaterialsAction()
        repr_str = repr(action)
        self.assertEqual(repr_str, "PlanCraftingMaterialsAction()")
        
    def test_exception_handling(self):
        """Test exception handling during execution"""
        action = PlanCraftingMaterialsAction()
        
        # Mock knowledge base to raise exception
        knowledge_base = Mock()
        knowledge_base.get_item_data.side_effect = Exception("API Error")
        
        context = MockActionContext(
            character_name=self.character_name,
            target_item="wooden_staff"
        )
        context.knowledge_base = knowledge_base
        
        result = action.execute(self.client, context)
        
        self.assertFalse(result['success'])
        self.assertIn('Crafting planning failed', result['error'])
        self.assertIn('API Error', result['error'])


if __name__ == '__main__':
    unittest.main()