# YAML Configuration Guide

This guide documents the YAML configuration file formats used by the ArtifactsMMO AI Player system.

## Overview

The ArtifactsMMO AI Player uses simple, declarative YAML files for configuration:

- **Configuration Files** (`config/`): Define behavior and rules  
- **Data Files** (`data/`): Store runtime state and learned information

## Configuration Files

### Action Class Registry

**File**: `config/action_configurations.yaml`

Maps action names to Python implementation classes.

```yaml
action_classes:
  move: "src.controller.actions.move.MoveAction"
  attack: "src.controller.actions.attack.AttackAction"
  rest: "src.controller.actions.rest.RestAction"
  gather_resources: "src.controller.actions.gather_resources.GatherResourcesAction"
  find_monsters: "src.controller.actions.find_monsters.FindMonstersAction"
```

### GOAP Actions

**File**: `config/default_actions.yaml`

Defines actions for Goal-Oriented Action Planning with simple conditions and reactions.

#### Structure

```yaml
actions:
  action_name:
    conditions:
      field_name: required_value
    reactions:
      field_name: new_value
    weight: 1.0
    description: "What this action does"
```

**Note**: The system now uses flattened property names instead of nested state groups. For example, instead of `character_status.alive`, use `character_alive`.

#### Example

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
      character_cooldown_active: false
      combat_status: 'ready'
    reactions:
      combat_status: 'engaged'
      has_gained_xp: true
    weight: 3.0
    description: "Attack target monster"
    
  rest:
    conditions:
      character_alive: true
      healing_status: 'needed'
    reactions:
      healing_status: 'complete'
      character_safe: true
    weight: 1.0
    description: "Rest to restore HP"
```

**Note**: The system now uses flattened property names. Instead of nested groups like `character_status.alive`, use direct properties like `character_alive`.

### Goal Templates

**File**: `config/goal_templates.yaml`

Defines reusable goal templates with simple target states.

#### Structure

```yaml
goal_templates:
  goal_name:
    description: "What this goal achieves"
    objective_type: "category"
    target_state:
      state_group:
        field_name: target_value
    strategy:
      parameter: value
```

#### Example

```yaml
goal_templates:
  hunt_monsters:
    description: "Hunt monsters for experience and loot"
    objective_type: "combat"
    target_state:
      goal_progress:
        has_gained_xp: true
    strategy:
      search_radius: 4
      max_search_attempts: 5
      
  upgrade_weapon:
    description: "Craft and equip a better weapon"
    objective_type: "equipment_progression"
    target_state:
      equipment_status:
        upgrade_status: "completed"
    strategy:
      equipment_type: "weapon"
      search_radius: 4
      
  get_to_safety:
    description: "Rest to restore HP when in danger"
    objective_type: "maintenance"
    target_state:
      character_status:
        safe: true
      healing_context:
        healing_status: "complete"
    strategy:
      max_iterations: 5
```

### State Defaults

**File**: `config/consolidated_state_defaults.yaml`

Defines the default initial state structure for the GOAP system.

#### Structure

```yaml
state_defaults:
  state_group:
    field_name: default_value
```

#### Example

```yaml
state_defaults:
  equipment_status:
    weapon: null
    upgrade_status: "needs_analysis"
    target_slot: null
    equipped: false
    
  location_context:
    current:
      x: 0
      y: 0
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

## Data Files

### World State

**File**: `data/world.yaml`

Persists the current GOAP world state between runs.

#### Structure

Simple nested dictionaries with boolean, string, and numeric values:

```yaml
equipment_status:
  weapon: "iron_sword"
  upgrade_status: "ready"
  equipped: true
  
location_context:
  current:
    x: 5
    y: 10
  at_target: false
  
character_status:
  alive: true
  cooldown_active: false
  hp_percentage: 85.0
  level: 12
```

### Knowledge Base

**File**: `data/knowledge.yaml`

Stores learned information from API interactions.

```yaml
monsters:
  chicken:
    locations:
      - x: 0
        y: 1
    combat_data:
      win_rate: 0.95
      avg_damage: 15
      
resources:
  copper_ore:
    locations:
      - x: 2
        y: 0
    quantity_available: 50
```

### Map Data

**File**: `data/map.yaml`

Caches explored map locations and their contents.

```yaml
"0,0":
  content:
    type: "spawn"
    name: "spawn"
"2,0":
  content:
    type: "resource"
    code: "copper_ore"
```

## Configuration Rules

### Value Types

All configuration uses simple value types:

- **Boolean**: `true`, `false`
- **String**: `"value"`, `'value'`
- **Number**: `123`, `45.6`
- **Null**: `null`

### No Complex Logic

Configuration files contain **only data**, no logic:

- ❌ No complex operators (`>=`, `<`, `!=`)
- ❌ No templating (`${variable}`)
- ❌ No conditional expressions
- ❌ No computed values

### State Structure

State is organized in nested groups:

```yaml
state_group:
  field1: value1
  field2: value2
  nested_group:
    field3: value3
```

Common state groups:
- `character_status`: Character health, level, cooldown
- `equipment_status`: Equipment and upgrade status
- `location_context`: Position and location states
- `combat_context`: Combat status and statistics
- `materials`: Crafting materials and inventory
- `goal_progress`: Progress tracking for current goals

## Best Practices

### 1. Naming Conventions
- Use `snake_case` for all field names
- Use descriptive names that clearly indicate purpose
- Group related fields under common state groups

### 2. State Design
- Design fields for clear true/false decisions
- Use string enums for status fields (`"idle"`, `"ready"`, `"completed"`)
- Keep numeric values simple (avoid complex calculations)

### 3. Action Design
- Each action should have minimal, specific conditions
- Reactions should be direct state updates
- Use appropriate weights (higher = more preferred by GOAP)

### 4. Goal Design
- Target states should be specific and achievable
- Use boolean flags for completion status
- Keep strategy parameters simple

### 5. Configuration Management
- Validate YAML syntax before committing
- Use version control for all configuration files
- Test configuration changes before deployment
- Keep data files backed up

## Common Patterns

### Simple State Flags

```yaml
# Boolean state flags
character_status:
  alive: true
  safe: false
  
# String status values  
materials:
  status: "insufficient"  # or "gathered", "ready"
```

### Equipment Workflows

```yaml
equipment_status:
  upgrade_status: "needs_analysis"  # → "ready" → "completed"
  target_slot: "weapon"
  selected_item: "iron_sword"
```

### Location Tracking

```yaml
location_context:
  at_target: false
  at_workshop: false
  workshop_known: true
```

## Troubleshooting

### Common Issues

- **Actions not executing**: Check that conditions match current state exactly
- **Goals not achieved**: Verify target state uses correct field names and values
- **State not persisting**: Ensure data files have write permissions
- **Planning failures**: Check that all state fields referenced in conditions have defaults

### Debugging Tips

1. Use logging to see current state values
2. Check that action conditions match exactly (case-sensitive)
3. Verify all referenced state fields exist in defaults
4. Ensure boolean values are `true`/`false`, not `True`/`False`

This simple, declarative approach makes the system predictable and easy to modify without complex configuration syntax.