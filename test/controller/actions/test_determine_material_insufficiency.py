"""Test determine material insufficiency action."""

import pytest
from unittest.mock import Mock, patch

from src.controller.actions.determine_material_insufficiency import DetermineMaterialInsufficiencyAction
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters


class TestDetermineMaterialInsufficiencyAction:
    """Test the DetermineMaterialInsufficiencyAction class."""
    
    def setup_method(self):
        """Set up test dependencies."""
        self.action = DetermineMaterialInsufficiencyAction()
        self.mock_client = Mock()
        self.context = ActionContext()
        self.context.set(StateParameters.CHARACTER_NAME, "TestChar")
        
        # Mock knowledge base for context
        self.context.knowledge_base = Mock()
        
    def test_execute_with_target_recipe(self):
        """Test execution with target recipe."""
        # Set up context with TARGET_RECIPE
        self.context.set_result(StateParameters.TARGET_RECIPE, 'copper_dagger')
        
        # Mock character with empty inventory
        mock_character_data = Mock()
        mock_character_data.inventory = []
        
        mock_response = Mock()
        mock_response.data = mock_character_data
        
        # Mock knowledge base
        with patch.object(self.context.knowledge_base, 'get_material_requirements') as mock_get_requirements:
            mock_get_requirements.return_value = {'copper_ore': 60}  # 6 bars * 10 ore each
            
            with patch('src.controller.actions.determine_material_insufficiency.get_character_api') as mock_get_char:
                mock_get_char.return_value = mock_response
                
                # Execute
                result = self.action.execute(self.mock_client, self.context)
                
        # Verify
        assert result.success is True
        
        # Check that current gathering goal is set
        gathering_goal = self.context.get(StateParameters.CURRENT_GATHERING_GOAL)
        assert gathering_goal['material'] == 'copper_ore'
        assert gathering_goal['quantity'] == 60
        
        # Verify the subgoal request parameters
        assert hasattr(result, 'subgoal_request')
        assert result.subgoal_request['goal_name'] == 'gather_resource'
        assert result.subgoal_request['parameters']['resource'] == 'copper_ore'
        assert result.subgoal_request['parameters']['quantity'] == 60
        
    def test_execute_no_target_recipe(self):
        """Test execution with no target recipe."""
        # Clear any existing target recipe
        self.context._state.reset()
        self.context.set(StateParameters.CHARACTER_NAME, "TestChar")
        
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify
        assert result.success is False
        assert "No target recipe" in result.error
        
    def test_sufficient_materials_with_target_recipe(self):
        """Test when character has sufficient materials for target recipe."""
        # Set up context
        self.context.set_result(StateParameters.TARGET_RECIPE, 'copper_dagger')
        
        # Mock character with sufficient inventory
        mock_inventory_item = Mock()
        mock_inventory_item.code = 'copper_ore'
        mock_inventory_item.quantity = 70  # More than required 60
        
        mock_character_data = Mock()
        mock_character_data.inventory = [mock_inventory_item]
        
        mock_response = Mock()
        mock_response.data = mock_character_data
        
        # Mock knowledge base
        with patch.object(self.context.knowledge_base, 'get_material_requirements') as mock_get_requirements:
            mock_get_requirements.return_value = {'copper_ore': 60}  # 6 bars * 10 ore each
            
            with patch('src.controller.actions.determine_material_insufficiency.get_character_api') as mock_get_char:
                mock_get_char.return_value = mock_response
                
                # Execute
                result = self.action.execute(self.mock_client, self.context)
                
        # Verify
        assert result.success is True
        
        # Should have no missing materials - gathering goal should be None
        gathering_goal = self.context.get(StateParameters.CURRENT_GATHERING_GOAL)
        assert gathering_goal['material'] is None
        assert gathering_goal['quantity'] == 0
        
        # Should not request subgoal when materials are sufficient
        assert not hasattr(result, 'subgoal_request') or result.subgoal_request is None