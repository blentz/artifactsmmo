"""Test check material availability action."""

import pytest
from unittest.mock import Mock, patch

from src.controller.actions.check_material_availability import CheckMaterialAvailabilityAction
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters


class TestCheckMaterialAvailabilityAction:
    """Test the CheckMaterialAvailabilityAction class."""
    
    def setup_method(self):
        """Set up test dependencies."""
        self.action = CheckMaterialAvailabilityAction()
        self.mock_client = Mock()
        self.context = ActionContext()
        self.context.set(StateParameters.CHARACTER_NAME, "TestChar")
        
        # Mock knowledge base for context
        self.context.knowledge_base = Mock()
        
    def test_execute_no_target_recipe(self):
        """Test execution with no target recipe."""
        result = self.action.execute(self.mock_client, self.context)
        
        assert result.success is False
        assert "No target recipe" in result.error
        
    def test_execute_sufficient_materials(self):
        """Test execution when all materials are sufficient."""
        # Set up context
        self.context.set_result(StateParameters.TARGET_RECIPE, 'copper_dagger')
        
        # Mock knowledge base
        self.context.knowledge_base.get_material_requirements.return_value = {'copper_ore': 60}
        
        # Mock character with sufficient inventory
        mock_inventory_item = Mock()
        mock_inventory_item.code = 'copper_ore'
        mock_inventory_item.quantity = 70
        
        mock_character_data = Mock()
        mock_character_data.inventory = [mock_inventory_item]
        
        mock_response = Mock()
        mock_response.data = mock_character_data
        
        with patch('src.controller.actions.check_material_availability.get_character_api') as mock_get_char:
            mock_get_char.return_value = mock_response
            
            result = self.action.execute(self.mock_client, self.context)
            
        # Verify
        assert result.success is True
        assert "All materials available" in result.message
        assert result.data['all_sufficient'] is True
        
    def test_execute_insufficient_materials(self):
        """Test execution when materials are insufficient."""
        # Set up context
        self.context.set_result(StateParameters.TARGET_RECIPE, 'copper_dagger')
        
        # Mock knowledge base
        self.context.knowledge_base.get_material_requirements.return_value = {'copper_ore': 60}
        
        # Mock character with insufficient inventory
        mock_inventory_item = Mock()
        mock_inventory_item.code = 'copper_ore'
        mock_inventory_item.quantity = 30
        
        mock_character_data = Mock()
        mock_character_data.inventory = [mock_inventory_item]
        
        mock_response = Mock()
        mock_response.data = mock_character_data
        
        with patch('src.controller.actions.check_material_availability.get_character_api') as mock_get_char:
            mock_get_char.return_value = mock_response
            
            result = self.action.execute(self.mock_client, self.context)
            
        # Verify
        assert result.success is True
        assert "materials missing" in result.message
        assert result.data['all_sufficient'] is False
        assert result.data['missing_materials'] == 1