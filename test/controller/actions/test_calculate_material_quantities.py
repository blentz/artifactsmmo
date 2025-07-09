"""Test calculate material quantities action."""

import pytest
from unittest.mock import Mock, MagicMock, patch

from src.controller.actions.calculate_material_quantities import CalculateMaterialQuantitiesAction
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters


class TestCalculateMaterialQuantitiesAction:
    """Test the CalculateMaterialQuantitiesAction class."""
    
    def setup_method(self):
        """Set up test dependencies."""
        self.action = CalculateMaterialQuantitiesAction()
        self.mock_client = Mock()
        self.context = ActionContext()
        self.context.set(StateParameters.CHARACTER_NAME, "TestChar")
        
    def test_execute_success_copper_dagger(self):
        """Test successful calculation for copper_dagger."""
        # Set up context
        self.context.set_result(StateParameters.SELECTED_ITEM, 'copper_dagger')
        self.context.set_result(StateParameters.MISSING_MATERIALS, {'copper_ore': 1})  # Dict with shortage
        
        # Mock knowledge base
        with patch.object(self.action.knowledge_base, 'get_item_data') as mock_get_item:
            # Mock copper_dagger recipe (now handles client kwarg)
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
        assert result.success is True
        assert result.data['raw_material_needs'] == {'copper_ore': 60}  # 6 bars * 10 ore
        assert result.data['total_requirements'] == {'copper_ore': 60}
        
        # Check context updates
        assert self.context.get(StateParameters.RAW_MATERIAL_NEEDS) == {'copper_ore': 60}
        assert self.context.get(StateParameters.CURRENT_GATHERING_GOAL) == {
            'material': 'copper_ore',
            'quantity': 60
        }
        
    def test_execute_no_selected_item(self):
        """Test execution with no selected item."""
        # Clear any existing selected item
        self.context._state.reset()
        self.context.set(StateParameters.CHARACTER_NAME, "TestChar")
        result = self.action.execute(self.mock_client, self.context)
        
        assert result.success is False
        assert "No selected item" in result.error
        
    def test_execute_no_missing_materials(self):
        """Test execution with no missing materials."""
        # Clear state and set only selected item
        self.context._state.reset()
        self.context.set(StateParameters.CHARACTER_NAME, "TestChar")
        self.context.set_result(StateParameters.SELECTED_ITEM, 'copper_dagger')
        
        result = self.action.execute(self.mock_client, self.context)
        
        assert result.success is False
        assert "No missing materials" in result.error
        
    def test_calculate_full_requirements_recursive(self):
        """Test recursive calculation of material requirements."""
        # Mock knowledge base
        with patch.object(self.action.knowledge_base, 'get_item_data') as mock_get_item:
            mock_get_item.side_effect = lambda item, client=None: {
                'iron_sword': {
                    'craft': {
                        'items': [
                            {'code': 'iron_bar', 'quantity': 8}
                        ]
                    }
                },
                'iron_bar': {
                    'craft': {
                        'items': [
                            {'code': 'iron_ore', 'quantity': 12}
                        ]
                    }
                },
                'iron_ore': {}  # Raw material
            }.get(item, {})
            
            # Set up context for the action
            self.action._context = self.context
            requirements = self.action._calculate_full_requirements('iron_sword')
            
        assert requirements == {'iron_ore': 96}  # 8 bars * 12 ore
        
    def test_calculate_full_requirements_multiple_materials(self):
        """Test calculation with multiple material types."""
        # Mock knowledge base
        with patch.object(self.action.knowledge_base, 'get_item_data') as mock_get_item:
            mock_get_item.side_effect = lambda item, client=None: {
                'magic_staff': {
                    'craft': {
                        'items': [
                            {'code': 'wood_plank', 'quantity': 3},
                            {'code': 'magic_crystal', 'quantity': 2}
                        ]
                    }
                },
                'wood_plank': {
                    'craft': {
                        'items': [
                            {'code': 'wood', 'quantity': 5}
                        ]
                    }
                },
                'wood': {},  # Raw material
                'magic_crystal': {}  # Raw material (no sub-recipe)
            }.get(item, {})
            
            # Set up context for the action
            self.action._context = self.context
            requirements = self.action._calculate_full_requirements('magic_staff')
            
        assert requirements == {
            'wood': 15,  # 3 planks * 5 wood
            'magic_crystal': 2
        }
        
    def test_state_changes(self):
        """Test state changes are applied correctly."""
        self.context.set_result(StateParameters.SELECTED_ITEM, 'copper_dagger')
        self.context.set_result(StateParameters.MISSING_MATERIALS, {'copper_ore': 1})
        
        with patch.object(self.action.knowledge_base, 'get_item_data') as mock_get_item:
            mock_get_item.return_value = {}
            
            result = self.action.execute(self.mock_client, self.context)
            
        assert result.success is True
        assert result.state_changes == {
            'materials': {
                'quantities_calculated': True,
                'raw_materials_needed': True
            }
        }