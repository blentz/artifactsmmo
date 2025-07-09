"""Test determine material requirements action."""

import pytest
from unittest.mock import Mock, patch

from src.controller.actions.determine_material_requirements import DetermineMaterialRequirementsAction
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from test.fixtures import MockActionContext
from test.test_base import UnifiedContextTestBase


class TestDetermineMaterialRequirementsAction(UnifiedContextTestBase):
    """Test the DetermineMaterialRequirementsAction class."""
    
    def setUp(self):
        """Set up test dependencies."""
        super().setUp()
        self.action = DetermineMaterialRequirementsAction()
        self.mock_client = Mock()
        self.context.set(StateParameters.CHARACTER_NAME, "TestChar")
        
    def test_init(self):
        """Test initialization."""
        action = DetermineMaterialRequirementsAction()
        self.assertTrue(hasattr(action, 'knowledge_base'))
        
        # Check GOAP parameters
        self.assertEqual(action.conditions['equipment_status']['upgrade_status'], 'ready')
        self.assertTrue(action.conditions['equipment_status']['has_selected_item'])
        self.assertTrue(action.reactions['materials']['requirements_determined'])
        self.assertEqual(action.reactions['materials']['status'], 'checking')
        self.assertEqual(action.weight, 1.0)
        
    def test_execute_no_selected_item(self):
        """Test execution when no selected item is available."""
        # Use unified context - don't set selected_item, it should be None
        # Clear any selected item that might be set from previous tests
        self.context.set(StateParameters.EQUIPMENT_SELECTED_ITEM, None)
        
        result = self.action.execute(self.mock_client, self.context)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "No selected item available")
        
    def test_execute_material_requirements_empty(self):
        """Test execution when material requirements calculation returns empty."""
        self.context.set(StateParameters.EQUIPMENT_SELECTED_ITEM, 'unknown_item')
        
        # Mock to return None/empty requirements
        with patch.object(self.action, '_calculate_material_requirements_with_quantities', return_value={}):
            result = self.action.execute(self.mock_client, self.context)
            
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Could not determine materials for unknown_item")
        
    def test_execute_with_exception(self):
        """Test execution with exception handling."""
        self.context.set(StateParameters.EQUIPMENT_SELECTED_ITEM, 'copper_dagger')
        
        # Mock to raise exception
        with patch.object(self.action, '_calculate_material_requirements_with_quantities', side_effect=Exception("Calculation error")):
            result = self.action.execute(self.mock_client, self.context)
            
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Material requirements determination failed: Calculation error")
        
    def test_calculate_material_requirements_copper_dagger(self):
        """Test calculation for copper_dagger showing correct recursive quantities."""
        # Set up context
        self.context.set_result(StateParameters.EQUIPMENT_SELECTED_ITEM, 'copper_dagger')
        
        # Mock knowledge base to return copper_dagger -> 6 copper_bars -> 60 copper_ore
        with patch.object(self.action.knowledge_base, 'get_item_data') as mock_get_item:
            mock_get_item.side_effect = lambda item, client=None: {
                'copper_dagger': {
                    'craft': {
                        'items': [
                            {'code': 'copper_bar', 'quantity': 6}
                        ]
                    }
                },
                'copper_bar': {
                    'craft': {
                        'items': [
                            {'code': 'copper_ore', 'quantity': 10}
                        ]
                    }
                },
                'copper_ore': {}  # Raw material
            }.get(item, {})
            
            # Execute
            result = self.action.execute(self.mock_client, self.context)
            
        # Verify
        self.assertTrue(result.success)
        
        # Check that we get 60 copper_ore (6 bars * 10 ore each)
        material_requirements = result.data.get('material_requirements', {})
        self.assertEqual(material_requirements, {'copper_ore': 60})
        
        # Verify context updates
        self.assertEqual(self.context.get(StateParameters.MATERIAL_REQUIREMENTS), {'copper_ore': 60})
        self.assertEqual(self.context.get(StateParameters.REQUIRED_MATERIALS), ['copper_ore'])
        
    def test_calculate_material_requirements_with_quantities_directly(self):
        """Test the recursive calculation method directly."""
        # Mock knowledge base
        with patch.object(self.action.knowledge_base, 'get_item_data') as mock_get_item:
            mock_get_item.side_effect = lambda item, client=None: {
                'copper_dagger': {
                    'craft': {
                        'items': [
                            {'code': 'copper_bar', 'quantity': 6}
                        ]
                    }
                },
                'copper_bar': {
                    'craft': {
                        'items': [
                            {'code': 'copper_ore', 'quantity': 10}
                        ]
                    }
                },
                'copper_ore': {}  # Raw material
            }.get(item, {})
            
            # Test direct method call
            requirements = self.action._calculate_material_requirements_with_quantities('copper_dagger', self.context)
            
        self.assertEqual(requirements, {'copper_ore': 60})
        
    def test_calculate_requirements_raw_material(self):
        """Test calculation for raw material (no crafting recipe)."""
        # Mock knowledge base to return no data
        with patch.object(self.action.knowledge_base, 'get_item_data', return_value=None):
            requirements = self.action._calculate_material_requirements_with_quantities('iron_ore', self.context, quantity=5)
            
        self.assertEqual(requirements, {'iron_ore': 5})
        
    def test_calculate_requirements_no_craft_info(self):
        """Test calculation when item has no craft info."""
        # Mock knowledge base to return item without craft info
        with patch.object(self.action.knowledge_base, 'get_item_data', return_value={'name': 'Iron Ore'}):
            requirements = self.action._calculate_material_requirements_with_quantities('iron_ore', self.context, quantity=3)
            
        self.assertEqual(requirements, {'iron_ore': 3})
        
    def test_calculate_requirements_multiple_materials(self):
        """Test calculation with multiple materials that sum up."""
        with patch.object(self.action.knowledge_base, 'get_item_data') as mock_get_item:
            mock_get_item.side_effect = lambda item, client=None: {
                'complex_item': {
                    'craft': {
                        'items': [
                            {'code': 'component_a', 'quantity': 2},
                            {'code': 'component_b', 'quantity': 3}
                        ]
                    }
                },
                'component_a': {
                    'craft': {
                        'items': [
                            {'code': 'raw_material', 'quantity': 5}
                        ]
                    }
                },
                'component_b': {
                    'craft': {
                        'items': [
                            {'code': 'raw_material', 'quantity': 4}
                        ]
                    }
                },
                'raw_material': {}  # Raw material
            }.get(item, {})
            
            requirements = self.action._calculate_material_requirements_with_quantities('complex_item', self.context)
            
        # Should be 2*5 + 3*4 = 22 raw_material
        self.assertEqual(requirements, {'raw_material': 22})
        
    def test_get_recipe_materials(self):
        """Test _get_recipe_materials method."""
        recipe = {'materials': ['iron_ore', 'copper_ore']}
        context = MockActionContext(character_name="TestChar")
        
        materials = self.action._get_recipe_materials(recipe, 'test_item', context)
        
        self.assertEqual(materials, ['iron_ore', 'copper_ore'])
        
    def test_get_recipe_materials_exception(self):
        """Test _get_recipe_materials with exception."""
        recipe = {}
        context = MockActionContext(character_name="TestChar")
        
        with patch.object(self.action, '_get_direct_materials', side_effect=Exception("Direct materials error")):
            materials = self.action._get_recipe_materials(recipe, 'test_item', context)
            
        self.assertEqual(materials, [])
        
    def test_get_recipe_materials_empty_direct_materials(self):
        """Test _get_recipe_materials when _get_direct_materials returns empty."""
        recipe = {}
        context = MockActionContext(character_name="TestChar")
        
        with patch.object(self.action, '_get_direct_materials', return_value=[]):
            materials = self.action._get_recipe_materials(recipe, 'test_item', context)
            
        self.assertEqual(materials, [])
        
    def test_get_direct_materials_from_recipe(self):
        """Test _get_direct_materials from recipe data."""
        recipe = {'materials': ['iron_ore', 'copper_ore']}
        context = MockActionContext(character_name="TestChar")
        
        materials = self.action._get_direct_materials(recipe, 'test_item', context)
        
        self.assertEqual(materials, ['iron_ore', 'copper_ore'])
        
    def test_get_direct_materials_from_knowledge_base(self):
        """Test _get_direct_materials from knowledge base."""
        recipe = {}
        mock_kb = Mock()
        mock_kb.get_item_data.return_value = {
            'craft': {
                'items': [
                    {'code': 'iron_ore'},
                    {'code': 'copper_ore'}
                ]
            }
        }
        
        context = MockActionContext(character_name="TestChar", knowledge_base=mock_kb)
        
        materials = self.action._get_direct_materials(recipe, 'test_item', context)
        
        self.assertEqual(materials, ['iron_ore', 'copper_ore'])
        
    def test_get_direct_materials_no_data(self):
        """Test _get_direct_materials when no data available."""
        recipe = {}
        mock_kb = Mock()
        mock_kb.get_item_data.return_value = None
        
        context = MockActionContext(character_name="TestChar", knowledge_base=mock_kb)
        
        materials = self.action._get_direct_materials(recipe, 'test_item', context)
        
        self.assertEqual(materials, [])
        
    def test_get_direct_materials_exception(self):
        """Test _get_direct_materials with exception."""
        recipe = {'materials': Mock(side_effect=Exception("Materials error"))}
        context = MockActionContext(character_name="TestChar")
        
        materials = self.action._get_direct_materials(recipe, 'test_item', context)
        
        self.assertEqual(materials, [])
        
    def test_resolve_to_raw_materials_recursive(self):
        """Test _resolve_to_raw_materials with recursion."""
        mock_kb = Mock()
        mock_kb.get_item_data.side_effect = lambda item: {
            'copper_bar': {
                'craft': {
                    'items': [{'code': 'copper_ore', 'quantity': 10}]
                }
            },
            'copper_ore': {}  # Raw material
        }.get(item, {})
        
        context = MockActionContext(character_name="TestChar")
        
        materials = self.action._resolve_to_raw_materials('copper_bar', context, mock_kb)
        
        self.assertEqual(materials, ['copper_ore'])
        
    def test_resolve_to_raw_materials_circular_reference(self):
        """Test _resolve_to_raw_materials with circular reference."""
        mock_kb = Mock()
        mock_kb.get_item_data.side_effect = lambda item: {
            'item_a': {
                'craft': {
                    'items': [{'code': 'item_b'}]
                }
            },
            'item_b': {
                'craft': {
                    'items': [{'code': 'item_a'}]
                }
            }
        }.get(item, {})
        
        context = MockActionContext(character_name="TestChar")
        
        # Should handle circular reference
        materials = self.action._resolve_to_raw_materials('item_a', context, mock_kb)
        
        # Should return the item itself when circular reference detected
        self.assertTrue('item_a' in materials or 'item_b' in materials)
        
    def test_resolve_to_raw_materials_exception(self):
        """Test _resolve_to_raw_materials with exception."""
        mock_kb = Mock()
        mock_kb.get_item_data.side_effect = Exception("KB error")
        
        context = MockActionContext(character_name="TestChar")
        
        materials = self.action._resolve_to_raw_materials('copper_bar', context, mock_kb)
        
        # Should return the material itself on error
        self.assertEqual(materials, ['copper_bar'])
        
    def test_repr(self):
        """Test __repr__ method."""
        self.assertEqual(repr(self.action), "DetermineMaterialRequirementsAction()")