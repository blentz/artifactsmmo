# Subgoal Patterns and Best Practices

## Overview

The ArtifactsMMO AI Player uses recursive subgoal execution to handle complex multi-step workflows. This document provides comprehensive guidance for implementing actions that use subgoals correctly.

## Core Concepts

### Subgoal Execution Flow

1. **Action Request**: Action calls `result.request_subgoal()` to delegate work
2. **Recursive Planning**: GOAP system creates plan for subgoal
3. **Subgoal Execution**: Subgoal plan executes completely
4. **Context Preservation**: Essential data preserved across subgoal execution
5. **Continuation**: Original action re-executes to continue workflow
6. **Completion**: Process repeats until no more subgoals needed

### Key Architecture Components

- **ActionResult.request_subgoal()**: Method to request recursive subgoal execution
- **UnifiedStateContext**: Singleton context that preserves data across subgoals
- **GOAPExecutionManager**: Handles recursive subgoal execution and continuation
- **Goal Stack**: Manages nested goal state during recursive execution

## Implementation Patterns

### Pattern 1: Simple Movement Subgoal

For actions that need character movement:

```python
from src.controller.actions.base import ActionBase, ActionResult
from src.controller.actions.subgoal_mixins import MovementSubgoalMixin
from src.lib.unified_state_context import UnifiedStateContext

class GatherResourceAction(ActionBase, MovementSubgoalMixin):
    """Action that gathers resources at a specific location."""
    
    def execute(self, client, context: UnifiedStateContext) -> ActionResult:
        # Check for continuation from previous execution
        if self.is_at_target_location(client, context):
            # We're at the target - proceed with gathering
            return self._perform_gathering(client, context)
        
        # Initial execution - find resource and request movement
        resource_location = self._find_resource_location(client, context)
        if not resource_location:
            return self.create_error_result("No resource location found")
        
        # Request movement subgoal
        return self.request_movement_subgoal(
            context, 
            resource_location['x'], 
            resource_location['y'],
            preserve_keys=['target_resource', 'quantity_needed']
        )
    
    def _perform_gathering(self, client, context):
        """Perform the actual resource gathering."""
        # Implementation for gathering
        return self.create_success_result("Resource gathered successfully")
```

### Pattern 2: Multi-Step Workflow

For complex workflows with multiple sequential subgoals:

```python
from src.controller.actions.subgoal_mixins import CombinedSubgoalMixin

class ComplexCraftingAction(ActionBase, CombinedSubgoalMixin):
    """Action that implements a complete crafting workflow."""
    
    def execute(self, client, context: ActionContext) -> ActionResult:
        step = self.get_workflow_step(context, 'initial')
        
        if step == 'initial':
            # Step 1: Gather required materials
            materials = {'copper_ore': 5, 'ash_wood': 3}
            return self.request_workflow_subgoal(
                context,
                goal_name="gather_materials",
                parameters={"missing_materials": materials},
                next_step="materials_gathered",
                preserve_keys=['target_item', 'craft_quantity']
            )
            
        elif step == 'materials_gathered':
            # Step 2: Move to workshop
            workshop_location = self._find_workshop(client, context)
            return self.request_workflow_subgoal(
                context,
                goal_name="move_to_location", 
                parameters={"target_x": workshop_location['x'], "target_y": workshop_location['y']},
                next_step="at_workshop",
                preserve_keys=['target_item', 'craft_quantity']
            )
            
        elif step == 'at_workshop':
            # Step 3: Perform crafting
            return self._perform_crafting(client, context)
            
        else:
            return self.create_error_result(f"Unknown workflow step: {step}")
```

### Pattern 3: Conditional Subgoals

For actions that conditionally request subgoals based on state:

```python
class ConditionalAction(ActionBase, MovementSubgoalMixin):
    """Action that conditionally requests subgoals based on current state."""
    
    def execute(self, client, context: ActionContext) -> ActionResult:
        # Check current character state
        char_data = self._get_character_data(client, context)
        
        # Check if we need to move first
        if not self._is_at_required_location(char_data, context):
            target_location = self._determine_target_location(context)
            return self.request_movement_subgoal(
                context, 
                target_location['x'], 
                target_location['y'],
                preserve_keys=['action_state', 'required_items']
            )
        
        # Check if we need materials
        if not self._has_required_materials(char_data, context):
            materials = self._determine_required_materials(context)
            return self.request_material_gathering_subgoal(
                context, 
                materials,
                preserve_keys=['action_state', 'target_location']
            )
        
        # All prerequisites met - perform main action
        return self._perform_main_action(client, context)
```

## Common Subgoal Types

### Movement Subgoals

**Goal Name**: `move_to_location`  
**Parameters**: `target_x`, `target_y`  
**Use Case**: When action needs character at specific coordinates

```python
result.request_subgoal(
    goal_name="move_to_location",
    parameters={"target_x": 10, "target_y": 5},
    preserve_context=["target_resource", "quantity_needed"]
)
```

### Material Gathering Subgoals

**Goal Name**: `gather_materials`  
**Parameters**: `missing_materials`  
**Use Case**: When action needs specific materials in inventory

```python
result.request_subgoal(
    goal_name="gather_materials", 
    parameters={"missing_materials": {"copper_ore": 5, "ash_wood": 3}},
    preserve_context=["target_item", "craft_location"]
)
```

### Resource Collection Subgoals

**Goal Name**: `gather_resource`  
**Parameters**: `resource_type`, `quantity`  
**Use Case**: When action needs specific quantity of single resource

```python
result.request_subgoal(
    goal_name="gather_resource",
    parameters={"resource_type": "copper_ore", "quantity": 10},
    preserve_context=["crafting_plan", "workshop_location"]
)
```

## Context Preservation

### Critical Context Keys

Always preserve these keys when requesting subgoals:

- **Target coordinates**: `target_x`, `target_y`
- **Workflow state**: `workflow_step`, `action_state` 
- **Material requirements**: `missing_materials`, `required_items`
- **Target entities**: `target_resource`, `target_monster`, `target_item`
- **Quantities**: `quantity_needed`, `craft_quantity`

### Context Best Practices

1. **Preserve Essential Data**: Include all keys needed for continuation
2. **Use Descriptive Names**: Make context keys self-documenting
3. **Avoid Overwriting**: Don't reuse context keys for different purposes
4. **Clean Up**: Remove temporary context when action completes

## Error Handling

### Subgoal Failure Handling

When subgoals fail, the original action is re-executed:

```python
def execute(self, client, context: ActionContext) -> ActionResult:
    # Check if subgoal failed (action will be re-executed)
    subgoal_failed = context.get('subgoal_failed', False)
    
    if subgoal_failed:
        # Handle subgoal failure - maybe try alternative approach
        context.set_result('subgoal_failed', False)  # Clear flag
        return self._handle_subgoal_failure(client, context)
    
    # Normal execution flow
    return self._normal_execution(client, context)
```

### Infinite Loop Prevention

Prevent infinite subgoal loops:

```python
def execute(self, client, context: ActionContext) -> ActionResult:
    # Track attempt count to prevent infinite loops
    attempts = context.get('movement_attempts', 0)
    
    if attempts >= 3:
        return self.create_error_result("Maximum movement attempts exceeded")
    
    if not self.is_at_target_location(client, context):
        context.set_result('movement_attempts', attempts + 1)
        return self.request_movement_subgoal(context, target_x, target_y)
    
    # Success - clear attempt counter
    context.set_result('movement_attempts', 0)
    return self._perform_work(client, context)
```

## Testing Subgoal Actions

### Unit Test Patterns

Test both initial execution and continuation:

```python
def test_action_initial_execution(self):
    """Test action's initial execution that requests subgoal."""
    context = ActionContext.from_controller(mock_controller, {})
    
    result = action.execute(mock_client, context)
    
    assert result.success
    assert result.subgoal_request is not None
    assert result.subgoal_request['goal_name'] == 'move_to_location'

def test_action_continuation(self):
    """Test action's continuation after subgoal completion."""
    context = ActionContext.from_controller(mock_controller, {
        'target_x': 10,
        'target_y': 5
    })
    mock_character_at_location(10, 5)
    
    result = action.execute(mock_client, context)
    
    assert result.success
    assert result.subgoal_request is None  # No more subgoals needed
```

### Integration Testing

Test complete subgoal workflows:

```python
def test_complete_subgoal_workflow(self):
    """Test complete workflow from initial request through continuation."""
    # This would test the full GOAP execution with subgoals
    goal_state = {'materials': {'status': 'gathered'}}
    
    success = goap_manager.achieve_goal_with_goap(goal_state, controller)
    
    assert success
    assert_materials_gathered()
    assert_character_at_expected_location()
```

## Migration Guide

### Converting Existing Actions

For actions currently using direct synchronous calls:

**Before** (❌ Incorrect):
```python
def execute(self, client, context):
    # Direct synchronous execution
    move_action = MoveAction()
    move_result = move_action.execute(client, context)
    
    if move_result.success:
        # Continue with work
        return self._perform_work(client, context)
```

**After** (✅ Correct):
```python
def execute(self, client, context: UnifiedStateContext):
    # Check for continuation
    if self.is_at_target_location(client, context):
        return self._perform_work(client, context)
    
    # Request movement subgoal
    location = self._find_target_location(client, context)
    context.target_x = location['x']
    context.target_y = location['y']
    return self.request_movement_subgoal(context, location['x'], location['y'])
```

### High-Priority Actions to Convert

Based on QA analysis, these actions need immediate conversion:

1. **ExecuteCraftingPlanAction** - Replace workshop movement with subgoals
2. **NavigateToWorkshopAction** - Replace direct movement with subgoal request  
3. **FindCorrectWorkshopAction** - Add subgoal pattern for movement
4. **TransformMaterialsCoordinatorAction** - Break complex workflow into subgoals

## Performance Considerations

### Subgoal Overhead

- Each subgoal adds planning overhead
- Use subgoals judiciously for complex workflows
- Simple actions shouldn't use subgoals unnecessarily

### Context Size

- Keep preserved context minimal
- Remove unused context keys when possible
- Use descriptive but concise key names

### Planning Depth

- Limit subgoal nesting depth (recommended max: 3 levels)
- Complex workflows should be broken into simpler goals
- Use workflow patterns for linear sequences

## Debugging Subgoals

### Logging Patterns

Add comprehensive logging for subgoal debugging:

```python
def execute(self, client, context: ActionContext) -> ActionResult:
    stored_coords = self.get_stored_target_coordinates(context)
    
    if stored_coords:
        self.logger.info(f"Continuing execution, target: {stored_coords}")
        if self.is_at_target_location(client, context):
            self.logger.info("At target location, proceeding with work")
            return self._perform_work(client, context)
    else:
        self.logger.info("Initial execution, finding target location")
    
    location = self._find_location(client, context)
    self.logger.info(f"Requesting movement subgoal to {location}")
    return self.request_movement_subgoal(context, location['x'], location['y'])
```

### Common Issues

1. **Context Not Preserved**: Check `preserve_context` parameter
2. **Infinite Loops**: Add attempt counters and maximum retry limits
3. **Wrong Continuation Logic**: Verify stored state checks
4. **State Conflicts**: Ensure context keys don't conflict between actions

This comprehensive guide provides the foundation for implementing robust, maintainable actions that use the subgoal system effectively.