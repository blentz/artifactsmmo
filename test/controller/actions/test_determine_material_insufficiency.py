"""Test determine material insufficiency action."""

import pytest
from unittest.mock import Mock, patch

from src.controller.actions.determine_material_insufficiency import DetermineMaterialInsufficencyAction
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters


class TestDetermineMaterialInsufficencyAction:
    """Test the DetermineMaterialInsufficencyAction class."""
    
    def setup_method(self):
        """Set up test dependencies."""
        self.action = DetermineMaterialInsufficencyAction()
        self.mock_client = Mock()
        self.context = ActionContext()
        self.context.set(StateParameters.CHARACTER_NAME, "TestChar")
        
    def test_execute_with_material_requirements_quantities(self):
        """Test execution with material_requirements containing quantities."""
        # Set up context with material requirements (the fixed format)
        self.context.set_result(StateParameters.SELECTED_ITEM, 'copper_dagger')
        self.context.set_result(StateParameters.MATERIAL_REQUIREMENTS, {'copper_ore': 60})  # Our fixed calculation
        self.context.set_result(StateParameters.REQUIRED_MATERIALS, ['copper_ore'])  # Legacy format
        
        # Mock character with empty inventory
        mock_character_data = Mock()
        mock_character_data.inventory = []
        
        mock_response = Mock()
        mock_response.data = mock_character_data
        
        with patch('src.controller.actions.determine_material_insufficiency.get_character_api') as mock_get_char:
            mock_get_char.return_value = mock_response
            
            # Execute
            result = self.action.execute(self.mock_client, self.context)
            
        # Verify
        assert result.success is True
        
        # Check that missing_materials uses the correct quantity (60, not 1)
        missing_materials = self.context.get(StateParameters.MISSING_MATERIALS)
        assert missing_materials == {'copper_ore': 60}
        
        # Verify the subgoal request parameters
        assert hasattr(result, 'subgoal_request')
        assert result.subgoal_request['goal_name'] == 'gather_materials'
        assert result.subgoal_request['parameters']['missing_materials'] == {'copper_ore': 60}
        
    def test_execute_fallback_to_required_materials(self):
        """Test fallback to required_materials when material_requirements not available."""
        # Set up context with only required_materials (legacy format)
        self.context.set_result(StateParameters.SELECTED_ITEM, 'copper_dagger')
        self.context.set_result(StateParameters.REQUIRED_MATERIALS, ['copper_ore'])
        # Explicitly clear material_requirements to ensure clean state
        self.context.set_result(StateParameters.MATERIAL_REQUIREMENTS, None)
        
        # Mock character with empty inventory
        mock_character_data = Mock()
        mock_character_data.inventory = []
        
        mock_response = Mock()
        mock_response.data = mock_character_data
        
        with patch('src.controller.actions.determine_material_insufficiency.get_character_api') as mock_get_char:
            mock_get_char.return_value = mock_response
            
            # Execute
            result = self.action.execute(self.mock_client, self.context)
            
        # Verify
        assert result.success is True
        
        # Should default to quantity 1 when using required_materials fallback
        missing_materials = self.context.get(StateParameters.MISSING_MATERIALS)
        assert missing_materials == {'copper_ore': 1}
        
    def test_sufficient_materials_with_quantities(self):
        """Test when character has sufficient materials (using quantities)."""
        # Set up context
        self.context.set_result(StateParameters.SELECTED_ITEM, 'copper_dagger')
        self.context.set_result(StateParameters.MATERIAL_REQUIREMENTS, {'copper_ore': 60})
        
        # Mock character with sufficient inventory
        mock_inventory_item = Mock()
        mock_inventory_item.code = 'copper_ore'
        mock_inventory_item.quantity = 70  # More than required 60
        
        mock_character_data = Mock()
        mock_character_data.inventory = [mock_inventory_item]
        
        mock_response = Mock()
        mock_response.data = mock_character_data
        
        with patch('src.controller.actions.determine_material_insufficiency.get_character_api') as mock_get_char:
            mock_get_char.return_value = mock_response
            
            # Execute
            result = self.action.execute(self.mock_client, self.context)
            
        # Verify
        assert result.success is True
        
        # Should have no missing materials
        missing_materials = self.context.get(StateParameters.MISSING_MATERIALS)
        assert missing_materials == {}
        
        # Should not request subgoal when materials are sufficient
        assert not hasattr(result, 'subgoal_request') or result.subgoal_request is None