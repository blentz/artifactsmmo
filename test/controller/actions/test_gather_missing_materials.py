"""Test gather missing materials action."""
import pytest
from unittest.mock import Mock, patch

from src.controller.actions.gather_missing_materials import GatherMissingMaterialsAction
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters


class TestGatherMissingMaterialsAction:
    """Test cases for gather missing materials action."""

    def setup_method(self):
        """Set up test environment before each test."""
        self.action = GatherMissingMaterialsAction()
        self.mock_client = Mock()
        self.context = ActionContext()
        self.context.set(StateParameters.CHARACTER_NAME, "testchar")
        
        # Mock knowledge base for context
        self.context.knowledge_base = Mock()

    def test_execute_no_target_recipe(self):
        """Test execution with no target recipe specified."""
        # Ensure no target recipe is set
        self.context.set_result(StateParameters.TARGET_RECIPE, None)
        
        result = self.action.execute(self.mock_client, self.context)
        
        assert not result.success
        assert "No target recipe" in result.error

    def test_execute_with_target_recipe(self):
        """Test execution with target recipe."""
        # Set up context
        self.context.set_result(StateParameters.TARGET_RECIPE, 'copper_dagger')
        
        # Mock knowledge base
        self.context.knowledge_base.get_material_requirements.return_value = {'copper_ore': 60}
        
        # Mock inventory with insufficient materials
        self.context.inventory = [
            type('MockItem', (), {'code': 'copper_ore', 'quantity': 5})()
        ]
        
        # Execute
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify
        assert result.success is True
        assert "Need to find location for copper_ore" in result.message
        
        # Should request find_resources subgoal
        assert hasattr(result, 'subgoal_request')
        assert result.subgoal_request['goal_name'] == 'find_resources'
        assert result.subgoal_request['parameters']['resource_types'] == ['copper_ore']

    def test_execute_sufficient_materials(self):
        """Test execution when all materials are sufficient."""
        # Set up context
        self.context.set_result(StateParameters.TARGET_RECIPE, 'copper_dagger')
        
        # Mock knowledge base
        self.context.knowledge_base.get_material_requirements.return_value = {'copper_ore': 60}
        
        # Mock inventory with sufficient materials
        self.context.inventory = [
            type('MockItem', (), {'code': 'copper_ore', 'quantity': 70})()
        ]
        
        # Execute
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify
        assert result.success is True
        assert "All required materials gathered" in result.message
        
        # Should not request subgoal when materials are sufficient
        assert not hasattr(result, 'subgoal_request') or result.subgoal_request is None