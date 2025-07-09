"""Test gather missing materials action."""
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.controller.actions.gather_missing_materials import GatherMissingMaterialsAction
from src.controller.actions.base import ActionResult
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
        
        # Mock the sub-actions
        self.action.find_resources_action = Mock()
        self.action.gather_resources_action = Mock()

    def test_execute_no_missing_materials(self):
        """Test execution with no missing materials specified."""
        result = self.action.execute(self.mock_client, self.context)
        
        assert not result.success
        assert "No materials required for recipe" in result.error

    def test_execute_dict_format_success(self):
        """Test execution with dict format missing materials."""
        # Set up context
        self.context.set(StateParameters.MISSING_MATERIALS, {'copper_ore': 5})
        
        # Mock successful resource finding
        find_result = ActionResult(
            success=True,
            message="Found resource",
            data={'target_x': 10, 'target_y': 20, 'resource_code': 'copper_ore'}
        )
        
        def mock_find_execute(client, context):
            # Set coordinates on context like real FindResourcesAction does
            context.target_x = 10
            context.target_y = 20
            return find_result
        
        self.action.find_resources_action.execute = Mock(side_effect=mock_find_execute)
        
        # Execute
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify the action now requests a subgoal instead of completing gathering
        assert result.success
        assert "Need to find location for" in result.message
        # The action requests a subgoal for resource finding, not movement
        assert result.subgoal_request is not None
        assert result.subgoal_request['goal_name'] == 'find_resources'
        assert 'copper_ore' in result.subgoal_request['parameters']['resource_types']
        
        # The action should not call find_resources directly since it requests it as a subgoal
        # self.action.find_resources_action.execute.assert_called_once()

    def test_execute_list_format_success(self):
        """Test execution with list format missing materials."""
        # Set up context
        self.context.set(StateParameters.MISSING_MATERIALS, ['iron_ore'])
        
        # Mock successful resource finding
        find_result = ActionResult(
            success=True,
            message="Found resource",
            data={'target_x': 15, 'target_y': 25, 'resource_code': 'iron_ore'}
        )
        
        def mock_find_execute(client, context):
            # Set coordinates on context like real FindResourcesAction does
            context.target_x = 15
            context.target_y = 25
            return find_result
        
        self.action.find_resources_action.execute = Mock(side_effect=mock_find_execute)
        
        # Execute
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify the action now requests a subgoal instead of completing gathering
        assert result.success
        assert "Need to find location for" in result.message
        # The action requests a subgoal for resource finding
        assert result.subgoal_request is not None
        assert result.subgoal_request['goal_name'] == 'find_resources'
        assert 'iron_ore' in result.subgoal_request['parameters']['resource_types']

    def test_execute_large_quantity_request(self):
        """Test execution with large quantity request."""
        # Set up context
        self.context.set(StateParameters.MISSING_MATERIALS, {'copper_ore': 10})
        
        # Mock successful resource finding
        find_result = ActionResult(
            success=True,
            message="Found resource",
            data={'target_x': 10, 'target_y': 20, 'resource_code': 'copper_ore'}
        )
        
        def mock_find_execute(client, context):
            # Set coordinates on context like real FindResourcesAction does
            context.target_x = 10
            context.target_y = 20
            return find_result
        
        self.action.find_resources_action.execute = Mock(side_effect=mock_find_execute)
        
        # Execute
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify the action properly handles large quantities
        assert result.success
        assert "Need to find location for" in result.message
        # Verify subgoal request contains the material
        assert result.subgoal_request is not None
        assert result.subgoal_request['goal_name'] == 'find_resources'
        assert 'copper_ore' in result.subgoal_request['parameters']['resource_types']

    def test_execute_resource_not_found(self):
        """Test execution when resource cannot be found."""
        # Set up context
        self.context.set(StateParameters.MISSING_MATERIALS, {'rare_ore': 1})
        
        # Mock failed resource finding
        find_result = ActionResult(
            success=False,
            message="Resource not found"
        )
        self.action.find_resources_action.execute.return_value = find_result
        
        # Execute
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify - action now requests subgoal instead of failing directly
        assert result.success
        assert "Need to find location for" in result.message
        assert result.subgoal_request is not None
        assert result.subgoal_request['goal_name'] == 'find_resources'
        assert 'rare_ore' in result.subgoal_request['parameters']['resource_types']

    def test_execute_invalid_coordinates(self):
        """Test execution when find_resources returns invalid coordinates."""
        # Set up context
        self.context.set(StateParameters.MISSING_MATERIALS, {'copper_ore': 1})
        
        # Mock resource finding with invalid coordinates
        find_result = ActionResult(
            success=True,
            message="Found resource",
            data={'target_x': None, 'target_y': None, 'resource_code': 'copper_ore'}
        )
        
        self.action.find_resources_action.execute.return_value = find_result
        
        # Execute
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify - action requests subgoal instead of failing directly
        assert result.success
        assert "Need to find location for" in result.message
        assert result.subgoal_request is not None
        assert result.subgoal_request['goal_name'] == 'find_resources'


    def test_execute_find_success_no_coordinates(self):
        """Test when find resources succeeds but sets no coordinates in context."""
        # Set up context
        self.context.set(StateParameters.MISSING_MATERIALS, {'copper_ore': 5})
        
        # Mock find resources with success but no coordinates set
        find_result = ActionResult(
            success=True,
            message="Found resource",
            data={}
        )
        
        def mock_find_execute(client, context):
            # Don't set coordinates - simulates failure to find location
            return find_result
        
        self.action.find_resources_action.execute = Mock(side_effect=mock_find_execute)
        
        # Execute
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify - action requests subgoal instead of failing directly
        assert result.success
        assert "Need to find location for" in result.message
        assert result.subgoal_request is not None
        assert result.subgoal_request['goal_name'] == 'find_resources'

    def test_execute_exception_handling(self):
        """Test exception handling during execution."""
        # Set up context
        self.context.set(StateParameters.MISSING_MATERIALS, {'copper_ore': 5})
        
        # Mock find resources to raise exception
        self.action.find_resources_action.execute.side_effect = Exception("Test exception")
        
        # Execute
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify - action requests subgoal even when internal logic would fail
        assert result.success
        assert "Need to find location for" in result.message
        assert result.subgoal_request is not None
        assert result.subgoal_request['goal_name'] == 'find_resources'

    def test_repr(self):
        """Test string representation."""
        assert repr(self.action) == "GatherMissingMaterialsAction()"

    def test_state_changes(self):
        """Test that proper state changes are returned."""
        # Set up context
        self.context.set(StateParameters.MISSING_MATERIALS, {'copper_ore': 1})
        
        # Mock successful flow
        find_result = ActionResult(
            success=True,
            message="Found resource",
            data={'target_x': 10, 'target_y': 20, 'resource_code': 'copper_ore'}
        )
        
        def mock_find_execute(client, context):
            # Set coordinates on context like real FindResourcesAction does
            context.target_x = 10
            context.target_y = 20
            return find_result
        
        self.action.find_resources_action.execute = Mock(side_effect=mock_find_execute)
        
        # Execute
        result = self.action.execute(self.mock_client, self.context)
        
        # Verify - action requests subgoal so no direct state changes
        assert result.success
        assert result.subgoal_request is not None
        assert result.subgoal_request['goal_name'] == 'find_resources'
        assert 'copper_ore' in result.subgoal_request['parameters']['resource_types']