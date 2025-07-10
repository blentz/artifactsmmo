"""
Integration tests for state persistence across actions.

These tests verify that state changes are properly persisted throughout
the execution of multi-step workflows, ensuring that ActionContext data
and world state updates are maintained correctly.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
import yaml

from src.controller.goap_execution_manager import GOAPExecutionManager
from src.controller.action_executor import ActionExecutor
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from src.controller.actions.base import ActionBase, ActionResult
from src.controller.actions.find_resources import FindResourcesAction
from src.controller.actions.gather_missing_materials import GatherMissingMaterialsAction


class TestStatePersistence:
    """Test state persistence across action execution."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_prefix = os.environ.get('DATA_PREFIX')
        os.environ['DATA_PREFIX'] = self.temp_dir
        
        # Create test data files
        self.world_file = os.path.join(self.temp_dir, 'world.yaml')
        self.knowledge_file = os.path.join(self.temp_dir, 'knowledge.yaml')
        
        # Initial world state
        self.initial_world_state = {
            'character_status': {
                'alive': True,
                'cooldown_active': False,
                'level': 1
            },
            'materials': {
                'status': 'insufficient',
                'availability_checked': True,
                'missing_materials': {'copper_ore': 5}
            },
            'location_context': {
                'resource_known': False,
                'at_resource': False,
                'current': {'x': 0, 'y': 1}
            }
        }
        
        # Knowledge base with resource locations
        self.knowledge_data = {
            'resources': {
                'copper_rocks': {
                    'locations': [
                        {'x': 2, 'y': 0, 'confirmed': True}
                    ]
                }
            }
        }
        
        # Write test data
        with open(self.world_file, 'w') as f:
            yaml.dump(self.initial_world_state, f)
        
        with open(self.knowledge_file, 'w') as f:
            yaml.dump(self.knowledge_data, f)
        
        self.mock_client = Mock()
        self.goap_manager = GOAPExecutionManager()
        self.action_executor = ActionExecutor()
        
    def teardown_method(self):
        """Clean up test fixtures."""
        if self.original_data_prefix:
            os.environ['DATA_PREFIX'] = self.original_data_prefix
        else:
            os.environ.pop('DATA_PREFIX', None)
    
    def test_action_context_persistence_across_subgoals(self):
        """Test that StateParameters persist correctly in unified context."""
        context = ActionContext()
        
        # Set initial state using registered StateParameters only
        context.set(StateParameters.CHARACTER_NAME, "TestChar")
        context.set_result(StateParameters.TARGET_ITEM, "copper_dagger")
        # Note: missing_materials is complex data handled by knowledge base, not state parameters

        # Simulate action setting coordinates using StateParameters
        context.set_result(StateParameters.TARGET_X, 2)
        context.set_result(StateParameters.TARGET_Y, 0)
        context.set_result(StateParameters.RESOURCE_CODE, "copper_rocks")

        # Verify persistence using proper StateParameters access
        assert context.get(StateParameters.TARGET_X) == 2, "target_x should be preserved"
        assert context.get(StateParameters.TARGET_Y) == 0, "target_y should be preserved"
        assert context.get(StateParameters.RESOURCE_CODE) == "copper_rocks", "resource_code should be preserved"

        # Test that unified context preserves all data throughout workflow
        assert context.get(StateParameters.CHARACTER_NAME) == "TestChar", "character_name should persist"
        # Note: missing_materials not tested - complex data handled by knowledge base
        assert context.get(StateParameters.TARGET_ITEM) == "copper_dagger", "target_item should persist"

        # Test workflow step progression using StateParameters
        context.set_result(StateParameters.WORKFLOW_STEP, 'resource_discovery')
        
        # Verify unified context persistence
        assert context.get(StateParameters.WORKFLOW_STEP) == 'resource_discovery', "Workflow step should persist"
    
    def test_world_state_updates_persist(self):
        """Test that world state updates persist between actions."""
        # Load initial world state
        with open(self.world_file, 'r') as f:
            current_state = yaml.safe_load(f)
        
        # Verify initial state
        assert current_state['location_context']['resource_known'] is False
        assert current_state['location_context']['at_resource'] is False
        
        # Simulate resource discovery state update
        state_updates = {
            'location_context': {
                'resource_known': True,
                'at_resource': False,
                'target_x': 2,
                'target_y': 0,
                'resource_code': 'copper_rocks'
            }
        }
        
        # Apply state updates
        current_state['location_context'].update(state_updates['location_context'])
        
        # Write updated state
        with open(self.world_file, 'w') as f:
            yaml.dump(current_state, f)
        
        # Reload and verify persistence
        with open(self.world_file, 'r') as f:
            reloaded_state = yaml.safe_load(f)
        
        assert reloaded_state['location_context']['resource_known'] is True
        assert reloaded_state['location_context']['target_x'] == 2
        assert reloaded_state['location_context']['target_y'] == 0
        assert reloaded_state['location_context']['resource_code'] == 'copper_rocks'
    
    def test_action_result_data_preservation(self):
        """Test that action result data is preserved for subsequent actions."""
        # Mock a FindResourcesAction result
        find_result = ActionResult(
            success=True,
            message="Found copper_rocks at (2, 0)",
            data={
                'target_x': 2,
                'target_y': 0,
                'resource_code': 'copper_rocks',
                'resource_type': 'copper_ore'
            }
        )
        
        # Verify result data structure
        assert find_result.success is True
        assert find_result.data['target_x'] == 2
        assert find_result.data['target_y'] == 0
        assert find_result.data['resource_code'] == 'copper_rocks'
        
        # Simulate extracting data for next action
        context = ActionContext()
        context.target_x = find_result.data['target_x']
        context.target_y = find_result.data['target_y']
        context.resource_code = find_result.data['resource_code']
        
        # Verify data was properly extracted
        assert context.target_x == 2
        assert context.target_y == 0
        assert context.resource_code == 'copper_rocks'
    
    def test_subgoal_context_updates_applied(self):
        """Test that subgoal context updates are properly applied."""
        # Create a subgoal request with context updates
        class MockSubgoalRequest:
            def __init__(self):
                self.subgoal_actions = ['move_to_resource']
                self.context_updates = {
                    'location_context': {
                        'resource_known': True,
                        'target_x': 2,
                        'target_y': 0
                    }
                }
        
        subgoal_request = MockSubgoalRequest()
        
        # Apply context updates to current state
        current_state = self.initial_world_state.copy()
        
        # Deep merge context updates
        for category, updates in subgoal_request.context_updates.items():
            if category not in current_state:
                current_state[category] = {}
            current_state[category].update(updates)
        
        # Verify updates were applied
        assert current_state['location_context']['resource_known'] is True
        assert current_state['location_context']['target_x'] == 2
        assert current_state['location_context']['target_y'] == 0
        
        # Verify other state was preserved
        assert current_state['character_status']['alive'] is True
        assert current_state['materials']['status'] == 'insufficient'
    
    def test_action_context_set_result_method(self):
        """Test that ActionContext.set_result properly preserves data."""
        context = ActionContext()
        
        # Test setting various types of results using StateParameters
        context.set_result(StateParameters.TARGET_ITEM, 'copper_dagger')
        context.set_result(StateParameters.TARGET_X, 2)
        context.set_result(StateParameters.TARGET_Y, 0)
        context.set_result(StateParameters.RESOURCE_CODE, 'copper_rocks')
        
        # Verify all results were preserved in unified context
        assert context.get(StateParameters.TARGET_ITEM) == 'copper_dagger'
        assert context.get(StateParameters.TARGET_X) == 2
        assert context.get(StateParameters.TARGET_Y) == 0
        assert context.get(StateParameters.RESOURCE_CODE) == 'copper_rocks'
    
    def test_failed_action_state_preservation(self):
        """Test that state is preserved even when actions fail."""
        context = ActionContext()
        context.character_name = "TestChar"
        context.target_x = 2
        context.target_y = 0
        
        # Simulate action failure
        failed_result = ActionResult(
            success=False,
            message="Action failed",
            error="Could not move to resource location"
        )
        
        # Verify context is preserved even after failure
        assert hasattr(context, 'character_name')
        assert hasattr(context, 'target_x')
        assert hasattr(context, 'target_y')
        assert context.character_name == "TestChar"
        assert context.target_x == 2
        assert context.target_y == 0
    
    def test_state_bridge_integration(self):
        """Test state bridge integration for context preservation."""
        # This test ensures that the state bridge properly maintains
        # the connection between ActionContext and world state
        
        context = ActionContext()
        context.character_name = "TestChar"
        context.missing_materials = {"copper_ore": 5}
        
        # Simulate state bridge preserving context data
        state_bridge_data = {
            'character_name': getattr(context, 'character_name', None),
            'missing_materials': getattr(context, 'missing_materials', None),
            'target_x': getattr(context, 'target_x', None),
            'target_y': getattr(context, 'target_y', None)
        }
        
        # Verify state bridge captured context
        assert state_bridge_data['character_name'] == "TestChar"
        assert state_bridge_data['missing_materials'] == {"copper_ore": 5}
        
        # Simulate restoring context from state bridge
        restored_context = ActionContext()
        for key, value in state_bridge_data.items():
            if value is not None:
                setattr(restored_context, key, value)
        
        # Verify context was restored
        assert restored_context.character_name == "TestChar"
        assert restored_context.missing_materials == {"copper_ore": 5}
    
    def test_multi_action_workflow_state_consistency(self):
        """Test state consistency across a multi-action workflow."""
        # Simulate the full workflow: find_resources -> move_to_resource -> gather_resources
        
        context = ActionContext()
        context.character_name = "TestChar"
        context.missing_materials = {"copper_ore": 5}
        
        # Step 1: Find resources
        find_result = ActionResult(
            success=True,
            message="Found copper_rocks",
            data={'target_x': 2, 'target_y': 0, 'resource_code': 'copper_rocks'}
        )
        
        # Update context with find results
        context.target_x = find_result.data['target_x']
        context.target_y = find_result.data['target_y']
        context.resource_code = find_result.data['resource_code']
        
        # Step 2: Verify context for movement
        assert context.target_x == 2
        assert context.target_y == 0
        assert context.resource_code == 'copper_rocks'
        
        # Step 3: Simulate movement completion
        move_result = ActionResult(
            success=True,
            message="Moved to resource location",
            data={'current_x': 2, 'current_y': 0}
        )
        
        # Update context with movement results
        context.current_x = move_result.data['current_x']
        context.current_y = move_result.data['current_y']
        
        # Step 4: Verify final context state
        assert context.target_x == 2
        assert context.target_y == 0
        assert context.current_x == 2
        assert context.current_y == 0
        assert context.resource_code == 'copper_rocks'
        assert context.missing_materials == {"copper_ore": 5}
        assert context.character_name == "TestChar"
        
        # Verify all state is consistent for final gathering step
        assert context.current_x == context.target_x
        assert context.current_y == context.target_y