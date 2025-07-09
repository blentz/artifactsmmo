# Configuration Guide

This guide explains how to work with the simple, declarative YAML configuration system in the ArtifactsMMO AI Player.

## Configuration Overview

The system uses YAML files for:
- Action class registration
- GOAP action definitions (conditions, reactions, weights)
- Goal templates with simple target states
- Default state values

All configuration is **declarative** - no complex logic, templating, or operators. The system uses a **UnifiedStateContext** with flattened properties for direct access.

## Configuration Files

```
config/
├── action_configurations.yaml     # Action class registry
├── default_actions.yaml          # GOAP action definitions
├── goal_templates.yaml           # Goal definitions
└── consolidated_state_defaults.yaml  # Default state values
```

## Action Configuration

### 1. Register Action Classes

Add new actions to `config/action_configurations.yaml`:

```yaml
action_classes:
  move: "src.controller.actions.move.MoveAction"
  attack: "src.controller.actions.attack.AttackAction"
  rest: "src.controller.actions.rest.RestAction"
  gather_resources: "src.controller.actions.gather_resources.GatherResourcesAction"
```

### 2. Define GOAP Actions

Add GOAP definitions to `config/default_actions.yaml`:

```yaml
actions:
  move:
    conditions:
      character_alive: true
      character_cooldown_active: false
    reactions:
      at_target: true
    weight: 1.0
    description: "Move character to target location"
    
  attack:
    conditions:
      character_alive: true
        cooldown_active: false
      combat_context:
        status: 'ready'
    reactions:
      combat_context:
        status: 'engaged'
      goal_progress:
        has_gained_xp: true
    weight: 3.0
    description: "Attack target monster"
```

### 3. Implement Action Class

Create the action class inheriting from ActionBase:

```python
from src.controller.actions.base import ActionBase, ActionResult

class MoveAction(ActionBase):
    # GOAP metadata matches YAML configuration
    conditions = {
        'character_status': {'alive': True, 'cooldown_active': False}
    }
    reactions = {
        'location_context': {'at_target': True}
    }
    weight = 1.0
    
    def execute(self, client, context):
        # Implementation here
        target_x = getattr(context, 'target_x', 0)
        target_y = getattr(context, 'target_y', 0)
        
        # Make API call
        response = move_character(client, target_x, target_y)
        
        if response.status_code == 200:
            return ActionResult(
                success=True,
                message=f"Moved to ({target_x}, {target_y})"
            )
        else:
            return ActionResult(
                success=False,
                error="Move failed"
            )
```

## Goal Configuration

### Define Goals

Add goal templates to `config/goal_templates.yaml`:

```yaml
goal_templates:
  hunt_monsters:
    description: "Hunt monsters for experience"
    objective_type: "combat"
    target_state:
      goal_progress:
        has_gained_xp: true
    strategy:
      search_radius: 4
      max_search_attempts: 5
      
  upgrade_weapon:
    description: "Craft and equip better weapon"
    objective_type: "equipment_progression"
    target_state:
      equipment_status:
        upgrade_status: "completed"
    strategy:
      equipment_type: "weapon"
      search_radius: 4
      
  get_to_safety:
    description: "Rest to restore HP"
    objective_type: "maintenance" 
    target_state:
      character_status:
        safe: true
      healing_context:
        healing_status: "complete"
    strategy:
      max_iterations: 5
```

### Goal Template Structure

- **target_state**: Simple boolean/string values defining success
- **strategy**: Configuration values (no complex logic)
- **objective_type**: Category for organization

## State Configuration

### Default State Values

Configure initial state in `config/consolidated_state_defaults.yaml`:

```yaml
state_defaults:
  equipment_status:
    weapon: null
    upgrade_status: "needs_analysis"
    target_slot: null
    equipped: false
    
  location_context:
    current: {x: 0, y: 0}
    at_target: false
    at_workshop: false
    workshop_known: false
    
  materials:
    status: "unknown"
    gathered: false
    ready_to_craft: false
    requirements_determined: false
    
  combat_context:
    status: "idle"
    recent_win_rate: 1.0
    low_win_rate: false
    
  character_status:
    alive: true
    cooldown_active: false
    safe: true
    hp_percentage: 100.0
    
  goal_progress:
    has_gained_xp: false
    monsters_hunted: 0
```

### State Structure Rules

- Use simple nested dictionaries
- Boolean, string, and numeric values only
- No complex calculations in configuration
- All fields used by actions must have defaults

## Configuration Rules

### 1. GOAP Conditions

Conditions are simple equality checks:

```yaml
conditions:
  character_status:
    alive: true              # Must be exactly true
    cooldown_active: false   # Must be exactly false
  equipment_status:
    upgrade_status: "ready"  # Must be exactly "ready"
```

### 2. GOAP Reactions

Reactions are direct value assignments:

```yaml
reactions:
  location_context:
    at_target: true         # Set to true
  combat_context:
    status: "engaged"       # Set to "engaged"
```

### 3. Goal Target States

Target states use same simple equality:

```yaml
target_state:
  equipment_status:
    upgrade_status: "completed"
  character_status:
    safe: true
```

## Development Workflow

### Adding a New Action

1. **Register the class**:
```yaml
# config/action_configurations.yaml
action_classes:
  my_action: "src.controller.actions.my_action.MyAction"
```

2. **Define GOAP behavior**:
```yaml
# config/default_actions.yaml
actions:
  my_action:
    conditions:
      some_status:
        ready: true
    reactions:
      some_status:
        completed: true
    weight: 2.0
```

3. **Implement the class**:
```python
# src/controller/actions/my_action.py
class MyAction(ActionBase):
    conditions = {'some_status': {'ready': True}}
    reactions = {'some_status': {'completed': True}}
    weight = 2.0
    
    def execute(self, client, context):
        # Implementation
        return ActionResult(success=True)
```

### Adding a New Goal

1. **Define the goal**:
```yaml
# config/goal_templates.yaml
goal_templates:
  my_goal:
    target_state:
      some_status:
        completed: true
```

### Testing Configuration

The system validates configuration on startup:
- All action classes must be importable
- GOAP conditions/reactions must reference valid state fields
- Goal target states must use defined state structure

### Configuration Hot-Reloading

Reload configuration without restarting:
```python
controller.reload_action_configurations()
```

## Best Practices

### 1. Keep It Simple
- Use only boolean, string, and numeric values
- Avoid complex nested logic
- One clear purpose per action

### 2. Consistent Naming
- Use snake_case for all configuration keys
- Be descriptive with action and state names
- Group related state fields together

### 3. State Design
- Design state fields for clear true/false decisions
- Use string enums for status fields ("idle", "ready", "completed")
- Keep state structure flat where possible

### 4. Action Design
- Each action should have a single, clear purpose
- Conditions should be minimal and specific
- Reactions should be direct state updates

This simple, declarative approach makes the system easy to understand, modify, and extend without complex configuration syntax or logic.