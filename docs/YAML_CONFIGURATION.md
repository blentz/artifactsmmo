# ArtifactsMMO AI Player - YAML Configuration Guide

This guide documents the YAML configuration file formats used by the ArtifactsMMO AI Player system.

## Table of Contents
- [Overview](#overview)
- [Action Configurations](#action-configurations)
- [GOAP Actions](#goap-actions)
- [Goal Templates](#goal-templates)
- [Skill Goals](#skill-goals)
- [State Engine](#state-engine)
- [World State](#world-state)
- [State Configurations](#state-configurations)

## Overview

The ArtifactsMMO AI Player uses YAML files for configuration and data persistence:

- **Configuration Files** (`config/`): Define behavior and rules
- **Data Files** (`data/`): Store runtime state and learned information

## Action Configurations

**File**: `config/action_configurations.yaml`

Defines how actions are executed, including both simple and composite actions.

### Structure

```yaml
# Action definitions
action_configurations:
  action_name:
    type: "builtin"  # or "composite"
    description: "What this action does"
    # Additional action-specific parameters

# Composite action workflows
composite_actions:
  workflow_name:
    description: "Multi-step action sequence"
    steps:
      - name: "step_identifier"
        action: "action_to_execute"
        required: true/false
        params:
          param_name: "${template_variable}"
        conditions:
          condition_key: expected_value
```

### Example

```yaml
action_configurations:
  move:
    type: "builtin"
    description: "Move character to specified coordinates"
  
  gather_resources:
    type: "builtin"
    description: "Gather resources at current location"

composite_actions:
  find_and_gather:
    description: "Find resources and gather them"
    steps:
      - name: "search"
        action: "find_resources"
        required: true
        params:
          resource_type: "${action_data.target_resource}"
      - name: "move_to_resource"
        action: "move"
        required: true
        params:
          x: "${steps.search.result.x}"
          y: "${steps.search.result.y}"
      - name: "gather"
        action: "gather_resources"
        required: true
```

## GOAP Actions

**File**: `config/actions.yaml`

Defines actions for the Goal-Oriented Action Planner with conditions, reactions, and weights.

### Structure

```yaml
actions:
  action_name:
    conditions:
      state_variable: required_value
      # Special operators:
      # variable_ge: value  # Greater than or equal
      # variable_lt: value  # Less than
    reactions:
      state_variable: new_value
    weight: 1.0  # Cost of this action (lower is preferred)
```

### Example

```yaml
actions:
  attack:
    conditions:
      character_alive: true
      has_target: true
      character_hp_ge: 20
    reactions:
      has_xp: true
      has_target: false
      need_rest: true
    weight: 2.0
  
  rest:
    conditions:
      character_alive: true
      need_rest: true
    reactions:
      need_rest: false
      character_hp: 100
    weight: 1.0
  
  find_monsters:
    conditions:
      need_combat: true
      monsters_available: false
      can_attack: true
    reactions:
      monsters_available: true
      has_target: true
    weight: 3.0
```

## Goal Templates

**File**: `config/goal_templates.yaml`

Defines reusable goal templates for common objectives.

### Structure

```yaml
goal_templates:
  template_name:
    description: "What this goal achieves"
    goal_state:
      state_variable: target_value
    priority: 1-10  # Higher = more important
    prerequisites:
      - prerequisite_state: value
```

### Example

```yaml
goal_templates:
  gain_combat_xp:
    description: "Gain XP through combat"
    goal_state:
      has_xp: true
      combat_skill_increased: true
    priority: 8
    prerequisites:
      - character_level_lt: 40
  
  reach_level_10:
    description: "Reach character level 10"
    goal_state:
      character_level_ge: 10
    priority: 10
  
  gather_iron:
    description: "Gather iron ore"
    goal_state:
      has_iron_ore: true
    priority: 5
    prerequisites:
      - mining_skill_ge: 5
```

## Skill Goals

**File**: `config/skill_goals.yaml`

Defines skill progression strategies and goals for each skill.

### Structure

```yaml
skill_goals:
  skill_name:
    description: "Skill description"
    max_level: 30
    progression:
      - level: 1
        goals:
          - goal_template: "template_name"
            priority: 1-10
            conditions:
              condition_key: value
      - level: 10
        goals:
          - goal_template: "advanced_template"
            priority: 8
```

### Example

```yaml
skill_goals:
  mining:
    description: "Extract minerals and ores"
    max_level: 30
    progression:
      - level: 1
        goals:
          - goal_template: "gather_copper"
            priority: 7
            conditions:
              has_pickaxe: true
      - level: 5
        goals:
          - goal_template: "gather_iron"
            priority: 8
          - goal_template: "craft_iron_pickaxe"
            priority: 6
      - level: 10
        goals:
          - goal_template: "gather_gold"
            priority: 9
  
  combat:
    description: "Fighting and warfare skills"
    max_level: 30
    progression:
      - level: 1
        goals:
          - goal_template: "fight_chickens"
            priority: 5
      - level: 5
        goals:
          - goal_template: "fight_wolves"
            priority: 7
            conditions:
              has_weapon: true
```

## State Engine

**File**: `config/state_engine.yaml`

Defines state calculation rules and derived state computation.

### Structure

```yaml
state_engine:
  rules:
    - name: "rule_name"
      conditions:
        state_var: value
      derived_states:
        new_state_var: computed_value
      priority: 1-10  # Order of rule evaluation

  thresholds:
    variable_name:
      low: 20
      medium: 50
      high: 80
```

### Example

```yaml
state_engine:
  rules:
    - name: "low_health_detection"
      conditions:
        character_hp_lt: 30
      derived_states:
        need_rest: true
        can_attack: false
      priority: 10
    
    - name: "combat_readiness"
      conditions:
        character_hp_ge: 50
        has_weapon: true
      derived_states:
        can_attack: true
        combat_ready: true
      priority: 5
  
  thresholds:
    character_hp:
      critical: 10
      low: 30
      healthy: 70
    character_level:
      beginner: 5
      intermediate: 15
      advanced: 25
```

## World State

**File**: `data/world.yaml`

Persists the current GOAP world state between runs.

### Structure

```yaml
# Boolean flags and state variables
state_variable: true/false
numeric_variable: 123
string_variable: "value"

# Special variables:
character_alive: true
character_level: 15
character_hp: 85
monsters_available: false
resources_available: true
```

### Example

```yaml
character_alive: true
character_level: 12
character_hp: 75
character_xp: 45000
combat_skill: 8
mining_skill: 5
has_weapon: true
has_pickaxe: true
has_iron_ore: false
monsters_available: true
resources_available: true
need_rest: false
can_attack: true
is_on_cooldown: false
last_combat_result: "victory"
```

## State Configurations

**File**: `config/state_configurations.yaml`

Defines object-oriented state class configurations with dependency injection.

### Structure

```yaml
state_configurations:
  class_name:
    module: "src.module.path"
    class: "ClassName"
    singleton: true/false
    dependencies:
      - name: "dependency_name"
        type: "DependencyClass"
        config:
          param: value
    config:
      parameter: value
```

### Example

```yaml
state_configurations:
  CharacterState:
    module: "src.game.character.state"
    class: "CharacterState"
    singleton: true
    config:
      name: "default_character"
  
  MapState:
    module: "src.game.map.state"
    class: "MapState"
    singleton: false
    dependencies:
      - name: "client"
        type: "APIClient"
    config:
      cache_duration: 300  # 5 minutes
  
  KnowledgeBase:
    module: "src.controller.knowledge.base"
    class: "KnowledgeBase"
    singleton: true
    config:
      filename: "knowledge.yaml"
      max_combat_records: 1000
```

## Best Practices

1. **Use Descriptive Names**: Action and state names should clearly indicate their purpose
2. **Document Complex Logic**: Add description fields to explain non-obvious behavior
3. **Version Control**: Track changes to configuration files in git
4. **Validate Syntax**: Use a YAML validator before committing changes
5. **Backup Data Files**: Keep backups of world.yaml and other runtime data
6. **Use Templates**: Leverage template variables in composite actions for reusability
7. **Set Appropriate Weights**: Action weights affect GOAP planning efficiency
8. **Test Changes**: Use `--goal-planner` and `--evaluate-plan` CLI options to test

## Common Patterns

### Conditional Actions
```yaml
actions:
  conditional_action:
    conditions:
      prerequisite_met: true
      resource_available: true
    reactions:
      action_completed: true
      resource_available: false
```

### Progressive Goals
```yaml
goal_templates:
  level_progression:
    goal_state:
      character_level_ge: "${params.target_level}"
    priority: "${params.priority}"
```

### Multi-Step Workflows
```yaml
composite_actions:
  complete_quest:
    steps:
      - name: "accept"
        action: "accept_quest"
      - name: "complete_objectives"
        action: "do_quest_objectives"
      - name: "turn_in"
        action: "turn_in_quest"
```

## Troubleshooting

- **Actions not executing**: Check conditions in actions.yaml
- **Goals not being selected**: Verify goal templates and priorities
- **State not persisting**: Ensure world.yaml has write permissions
- **Composite actions failing**: Check step dependencies and parameter templates
- **Planning failures**: Use CLI debugging tools to analyze state and conditions