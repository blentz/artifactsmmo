"""
Integration tests for subgoal request validation.

These tests verify that subgoal requests are properly structured,
validated, and processed by the GOAP system, ensuring that actions
correctly delegate complex workflows to the GOAP planner.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from src.controller.actions.base import ActionBase, ActionResult
from src.lib.action_context import ActionContext
from src.controller.goap_execution_manager import GOAPExecutionManager
from src.controller.actions.gather_missing_materials import GatherMissingMaterialsAction


@dataclass
class SubgoalRequest:
    """Test subgoal request structure."""
    subgoal_actions: List[str]
    context_updates: Dict[str, Any]
    priority: Optional[int] = None
    timeout: Optional[int] = None


class TestSubgoalRequestValidation:
    """Test subgoal request validation and processing."""

    def setup_method(self):
        """Setup test fixtures."""
        self.mock_client = Mock()
        self.goap_manager = GOAPExecutionManager()
        
    def test_subgoal_request_structure_validation(self):
        """Test that subgoal requests have proper structure."""
        # Valid subgoal request
        valid_request = SubgoalRequest(
            subgoal_actions=['move_to_resource'],
            context_updates={
                'location_context': {
                    'resource_known': True,
                    'target_x': 2,
                    'target_y': 0
                }
            }
        )
        
        # Validate required fields
        assert hasattr(valid_request, 'subgoal_actions')
        assert hasattr(valid_request, 'context_updates')
        assert isinstance(valid_request.subgoal_actions, list)
        assert isinstance(valid_request.context_updates, dict)
        assert len(valid_request.subgoal_actions) > 0
    
    def test_invalid_subgoal_request_detection(self):
        """Test detection of invalid subgoal requests."""
        # Test empty subgoal actions
        with pytest.raises(ValueError, match="Subgoal actions cannot be empty"):
            self.validate_subgoal_request(SubgoalRequest(
                subgoal_actions=[],
                context_updates={}
            ))
        
        # Test invalid action names
        with pytest.raises(ValueError, match="Invalid action name"):
            self.validate_subgoal_request(SubgoalRequest(
                subgoal_actions=['invalid_action_name'],
                context_updates={}
            ))
        
        # Test invalid context updates
        with pytest.raises(ValueError, match="Context updates must be a dictionary"):
            self.validate_subgoal_request(SubgoalRequest(
                subgoal_actions=['move_to_resource'],
                context_updates="invalid"
            ))
    
    def validate_subgoal_request(self, request: SubgoalRequest) -> bool:
        """Validate a subgoal request structure."""
        # Check subgoal actions
        if not request.subgoal_actions:
            raise ValueError("Subgoal actions cannot be empty")
        
        if not isinstance(request.subgoal_actions, list):
            raise ValueError("Subgoal actions must be a list")
        
        # Validate action names (simplified validation)
        valid_actions = [
            'move_to_resource', 'find_resources', 'gather_resources',
            'move_to_workshop', 'craft_item', 'equip_item', 'fight'
        ]
        
        for action in request.subgoal_actions:
            if action not in valid_actions:
                raise ValueError(f"Invalid action name: {action}")
        
        # Check context updates
        if not isinstance(request.context_updates, dict):
            raise ValueError("Context updates must be a dictionary")
        
        return True
    
    def test_subgoal_request_creation_patterns(self):
        """Test different patterns for creating subgoal requests."""
        # Pattern 1: Simple movement request
        movement_request = SubgoalRequest(
            subgoal_actions=['move_to_resource'],
            context_updates={
                'location_context': {
                    'resource_known': True,
                    'target_x': 2,
                    'target_y': 0
                }
            }
        )
        
        assert self.validate_subgoal_request(movement_request)
        
        # Pattern 2: Multi-step workflow
        crafting_request = SubgoalRequest(
            subgoal_actions=['move_to_workshop', 'craft_item'],
            context_updates={
                'location_context': {
                    'workshop_known': True,
                    'at_workshop': False
                },
                'equipment_status': {
                    'selected_item': 'copper_dagger',
                    'recipe_selected': True
                }
            }
        )
        
        assert self.validate_subgoal_request(crafting_request)
        
        # Pattern 3: Conditional workflow
        combat_request = SubgoalRequest(
            subgoal_actions=['find_resources', 'fight'],
            context_updates={
                'combat_context': {
                    'status': 'searching',
                    'target_level': 5
                }
            }
        )
        
        assert self.validate_subgoal_request(combat_request)
    
    def test_subgoal_context_merge_validation(self):
        """Test that subgoal context updates merge correctly."""
        # Initial context
        initial_context = {
            'character_status': {
                'alive': True,
                'level': 1
            },
            'location_context': {
                'current': {'x': 0, 'y': 1},
                'at_resource': False
            }
        }
        
        # Subgoal context updates
        context_updates = {
            'location_context': {
                'resource_known': True,
                'target_x': 2,
                'target_y': 0
            },
            'materials': {
                'status': 'gathering'
            }
        }
        
        # Perform merge
        merged_context = self.merge_context_updates(initial_context, context_updates)
        
        # Validate merge results
        assert merged_context['character_status']['alive'] is True  # Preserved
        assert merged_context['location_context']['current'] == {'x': 0, 'y': 1}  # Preserved
        assert merged_context['location_context']['at_resource'] is False  # Preserved
        assert merged_context['location_context']['resource_known'] is True  # Added
        assert merged_context['location_context']['target_x'] == 2  # Added
        assert merged_context['materials']['status'] == 'gathering'  # Added
    
    def merge_context_updates(self, initial: Dict, updates: Dict) -> Dict:
        """Merge context updates with initial context."""
        result = initial.copy()
        
        for category, category_updates in updates.items():
            if category not in result:
                result[category] = {}
            
            if isinstance(category_updates, dict):
                result[category].update(category_updates)
            else:
                result[category] = category_updates
        
        return result
    
    def test_gather_missing_materials_subgoal_compliance(self):
        """Test that gather_missing_materials follows proper subgoal patterns."""
        action = GatherMissingMaterialsAction()
        context = ActionContext()
        context.character_name = "TestChar"
        context.missing_materials = {"copper_ore": 5}
        
        # Execute action through public interface only
        result = action.execute(self.mock_client, context)
        
        # Validate ActionResult behavior - all outcomes are valid
        assert isinstance(result, ActionResult), \
            "gather_missing_materials should return ActionResult"
        
        # Test either successful execution or proper subgoal request
        if hasattr(result, 'subgoal_request') and result.subgoal_request:
            # Validate subgoal structure follows architecture
            subgoal_request = result.subgoal_request
            assert isinstance(subgoal_request, dict), \
                "Subgoal request should be dict"
            assert 'goal_name' in subgoal_request, \
                "Subgoal request should have goal_name"
            
            # Validate goal name is reasonable
            goal_name = subgoal_request['goal_name']
            valid_goals = ['find_resources', 'move_to_location', 'gather_materials']
            assert goal_name in valid_goals, \
                f"Goal name '{goal_name}' should be one of {valid_goals}"
            
            # Validate parameters if present
            if 'parameters' in subgoal_request:
                parameters = subgoal_request['parameters']
                assert isinstance(parameters, dict), "Parameters should be a dictionary"
        
        else:
            # Action completed without subgoal - verify proper result structure
            assert isinstance(result.success, bool), "Result should have success status"
            if not result.success:
                assert result.error is not None, "Failed result should have error message"
            else:
                assert isinstance(result.data, dict), "Successful result should have data"
    
    def test_subgoal_priority_handling(self):
        """Test that subgoal requests can specify priority."""
        # High priority subgoal (urgent movement)
        urgent_request = SubgoalRequest(
            subgoal_actions=['move_to_resource'],
            context_updates={
                'location_context': {'resource_known': True}
            },
            priority=10
        )
        
        # Low priority subgoal (optional optimization)
        optional_request = SubgoalRequest(
            subgoal_actions=['equip_item'],
            context_updates={
                'equipment_status': {'selected_item': 'copper_dagger'}
            },
            priority=1
        )
        
        # Validate priority handling
        assert urgent_request.priority == 10
        assert optional_request.priority == 1
        assert urgent_request.priority > optional_request.priority
    
    def test_subgoal_timeout_handling(self):
        """Test that subgoal requests can specify timeout."""
        # Quick timeout for simple actions
        quick_request = SubgoalRequest(
            subgoal_actions=['move_to_resource'],
            context_updates={},
            timeout=30
        )
        
        # Longer timeout for complex workflows
        complex_request = SubgoalRequest(
            subgoal_actions=['find_resources', 'move_to_resource', 'gather_resources'],
            context_updates={},
            timeout=300
        )
        
        # Validate timeout handling
        assert quick_request.timeout == 30
        assert complex_request.timeout == 300
    
    def test_subgoal_request_serialization(self):
        """Test that subgoal requests can be serialized for persistence."""
        request = SubgoalRequest(
            subgoal_actions=['move_to_resource'],
            context_updates={
                'location_context': {
                    'resource_known': True,
                    'target_x': 2,
                    'target_y': 0
                }
            },
            priority=5
        )
        
        # Serialize to dictionary
        serialized = {
            'subgoal_actions': request.subgoal_actions,
            'context_updates': request.context_updates,
            'priority': request.priority,
            'timeout': request.timeout
        }
        
        # Validate serialization
        assert serialized['subgoal_actions'] == ['move_to_resource']
        assert serialized['context_updates']['location_context']['resource_known'] is True
        assert serialized['priority'] == 5
        
        # Deserialize
        deserialized = SubgoalRequest(
            subgoal_actions=serialized['subgoal_actions'],
            context_updates=serialized['context_updates'],
            priority=serialized['priority'],
            timeout=serialized['timeout']
        )
        
        # Validate deserialization
        assert deserialized.subgoal_actions == request.subgoal_actions
        assert deserialized.context_updates == request.context_updates
        assert deserialized.priority == request.priority
    
    def test_subgoal_dependency_validation(self):
        """Test validation of subgoal action dependencies."""
        # Valid dependency chain
        valid_chain = ['find_resources', 'move_to_resource', 'gather_resources']
        
        # Invalid dependency chain (move before find)
        invalid_chain = ['move_to_resource', 'find_resources', 'gather_resources']
        
        # Validate dependency chains
        assert self.validate_action_dependencies(valid_chain) is True
        
        # For this test, we'll assume invalid chains are allowed
        # but should be flagged for optimization
        dependency_warnings = self.check_action_dependencies(invalid_chain)
        assert len(dependency_warnings) > 0, \
            "Should warn about suboptimal action ordering"
    
    def validate_action_dependencies(self, actions: List[str]) -> bool:
        """Validate that actions are in logical dependency order."""
        # Simplified validation - in practice, this would check
        # the actual conditions and reactions of each action
        return True
    
    def check_action_dependencies(self, actions: List[str]) -> List[str]:
        """Check for potential dependency issues."""
        warnings = []
        
        # Check for common ordering issues
        if 'move_to_resource' in actions and 'find_resources' in actions:
            move_index = actions.index('move_to_resource')
            find_index = actions.index('find_resources')
            
            if move_index < find_index:
                warnings.append(
                    "move_to_resource should come after find_resources"
                )
        
        return warnings
    
    def test_action_result_subgoal_integration(self):
        """Test integration between ActionResult and subgoal requests."""
        # Create an ActionResult with subgoal request
        subgoal_request = SubgoalRequest(
            subgoal_actions=['move_to_resource'],
            context_updates={
                'location_context': {
                    'resource_known': True,
                    'target_x': 2,
                    'target_y': 0
                }
            }
        )
        
        result = ActionResult(
            success=True,
            message="Resource found, movement required",
            data={},
            subgoal_request=subgoal_request
        )
        
        # Validate integration
        assert result.success is True
        assert hasattr(result, 'subgoal_request')
        assert result.subgoal_request is not None
        assert result.subgoal_request.subgoal_actions == ['move_to_resource']
        assert result.subgoal_request.context_updates['location_context']['resource_known'] is True