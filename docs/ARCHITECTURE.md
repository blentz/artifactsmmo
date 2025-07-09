# ArtifactsMMO AI Player Architecture

## Overview

The ArtifactsMMO AI Player is an autonomous agent that operates a character in a role-playing game through an API. The system uses Goal-Oriented Action Planning (GOAP) with simple, declarative YAML configuration to create maintainable and extensible AI behavior.

## Core Architectural Principles

1. **Orchestration over Business Logic**: Controllers delegate to specialized managers
2. **Declarative Configuration**: Simple YAML files define behavior without complex logic
3. **GOAP Planning**: Goal-oriented planning with simple state conditions
4. **Recursive Subgoal Execution**: Actions request subgoals for complex workflows
5. **Learning Integration**: Automatic knowledge acquisition from API interactions
6. **State-Driven Behavior**: Actions based on simple boolean and string state values

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    AI Player Controller                 │
│              (Orchestration Only)                      │
└─────────────────────┬───────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
        ▼                           ▼
┌──────────────┐              ┌──────────────┐
│ GOAP System  │              │ Action System│
│              │              │              │
│ ┌──────────┐ │              │ ┌──────────┐ │
│ │   Goal   │ │              │ │ Action   │ │
│ │ Manager  │ │              │ │Executor  │ │
│ └──────────┘ │              │ └──────────┘ │
│              │              │              │
│ ┌──────────┐ │              │ ┌──────────┐ │
│ │   GOAP   │ │              │ │ Action   │ │
│ │Execution │ │              │ │ Factory  │ │
│ │ Manager  │ │              │ └──────────┘ │
│ └──────────┘ │              └──────────────┘
└──────────────┘
        │                           │
        └─────────────┬─────────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │     Specialized Managers    │
        │                             │
        │ • Learning Manager          │
        │ • Mission Executor          │  
        │ • Cooldown Manager          │
        └─────────────────────────────┘
```

## Core Components

### 1. AIPlayerController (src/controller/ai_player_controller.py)

**Role**: Main orchestrator that coordinates subsystems without implementing business logic.

**Key Responsibilities**:
- Delegates GOAP planning to GOAPExecutionManager
- Delegates action execution to ActionExecutor  
- Manages character, map, and knowledge state
- Coordinates learning through callbacks

**Design**:
- Uses ActionContext singleton for data flow
- No hardcoded action logic
- All behavior driven by YAML configuration

### 2. GOAP System

#### GOAPExecutionManager (src/controller/goap_execution_manager.py)

**Role**: Centralized Goal-Oriented Action Planning with recursive subgoal support.

**Key Features**:
- Creates GOAP worlds from declarative state
- Handles recursive subgoal execution with proper continuation
- Simple replanning based on action results
- Manages goal stack for nested goals
- Re-executes same action after subgoal completion for continuation

**Planning Process**:
1. Load current state from consolidated format
2. Load action conditions/reactions from YAML
3. Generate plan using GOAP algorithm
4. Execute actions with state updates
5. Handle subgoal requests recursively
6. Re-execute requesting action after subgoal completion
7. Replan when discovery actions provide new information

**Subgoal Execution Flow**:
1. Action requests subgoal via `result.request_subgoal()`
2. Current goal state pushed to goal stack
3. Subgoal executed recursively with new GOAP planning
4. Subgoal state changes merged back to parent world
5. Original action re-executed for continuation logic
6. Process repeats until no more subgoals needed

#### Goal Manager (src/controller/goal_manager.py)

**Role**: Simple goal definition and state calculation.

**Features**:
- Loads goal templates from `config/goal_templates.yaml`
- Calculates world state from character/map data
- Simple boolean flag calculations

### 3. Action System

#### ActionExecutor (src/controller/action_executor.py)

**Role**: Executes actions and applies state updates.

**Execution Pipeline**:
1. **Execution**: Run action through ActionFactory
2. **State Updates**: Apply GOAP reactions to world state
3. **Learning**: Trigger learning callbacks
4. **Persistence**: Save state changes

#### ActionFactory (src/controller/action_factory.py)

**Role**: Creates action instances from registry.

**Features**:
- Loads action classes from `config/action_configurations.yaml`
- Simple class name to implementation mapping
- No complex instantiation logic

#### ActionBase (src/controller/actions/base.py)

**Role**: Base class for all actions with subgoal support.

**Contract**:
- `execute()` method returning ActionResult
- Simple GOAP metadata (conditions, reactions, weight)
- Standardized result format
- ActionResult supports `request_subgoal()` for recursive workflows

**Subgoal Support**:
- Actions can request subgoals via `result.request_subgoal(goal_name, parameters, preserve_context)`
- System automatically handles recursive execution and continuation
- Actions should implement continuation logic for post-subgoal execution

### 4. ActionContext System

#### ActionContext (src/lib/action_context.py)

**Role**: Singleton context for action data flow.

**Features**:
- Persists data throughout plan execution
- Simple attribute access
- No complex templating or substitution

## State Management

### State Structure

The system uses a consolidated state structure with simple nested dictionaries:

```yaml
equipment_status:
  weapon: null
  upgrade_status: "needs_analysis"
  target_slot: null
  
location_context:
  current: {x: 0, y: 0}
  at_target: false
  at_workshop: false
  
materials:
  status: "unknown"
  gathered: false
  ready_to_craft: false
  
combat_context:
  status: "idle"
  recent_win_rate: 1.0
  
character_status:
  alive: true
  cooldown_active: false
  hp_percentage: 100.0
```

### State Updates

Actions update state through simple reactions:

```yaml
# In default_actions.yaml
move:
  reactions:
    location_context:
      at_target: true
      
attack:
  reactions:
    combat_context:
      status: "engaged"
```

## Configuration System

### YAML Files

#### Action Registry (`config/action_configurations.yaml`)
```yaml
action_classes:
  move: "src.controller.actions.move.MoveAction"
  attack: "src.controller.actions.attack.AttackAction"
```

#### GOAP Actions (`config/default_actions.yaml`)
```yaml
actions:
  move:
    conditions:
      character_status:
        alive: true
        cooldown_active: false
    reactions:
      location_context:
        at_target: true
    weight: 1.0
```

#### Goal Templates (`config/goal_templates.yaml`)
```yaml
goal_templates:
  hunt_monsters:
    target_state:
      goal_progress:
        has_gained_xp: true
    strategy:
      search_radius: 4
```

#### State Defaults (`config/consolidated_state_defaults.yaml`)
```yaml
state_defaults:
  equipment_status:
    upgrade_status: "needs_analysis"
    equipped: false
  combat_context:
    status: "idle"
    recent_win_rate: 1.0
```

### Configuration Characteristics

- **Declarative**: No complex logic in configuration files
- **Simple Values**: Boolean, string, and numeric values only
- **No Templating**: Direct value assignment without substitution
- **Hot Reloadable**: Configuration changes without restarts

## Learning System

### Learning Manager (src/controller/learning_manager.py)

**Role**: Manages learning from API interactions.

**Learning Sources**:
- Map exploration responses
- Combat result data
- Bulk API data loading
- Resource discovery

**Integration**:
- Learning callbacks triggered after action execution
- Knowledge stored in `data/knowledge.yaml`
- Map data cached in `data/map.yaml`

## Data Flow

### Execution Flow
```
YAML Config → Action Classes → GOAP Planning → Action Execution → Unified State Updates → Persistence
```

### State Flow
```
API Response → UnifiedStateContext → GOAP Planning → Action Selection → Direct Property Updates → File Storage
```

## Key Design Decisions

### 1. Unified State Management
- Single UnifiedStateContext with flattened properties
- Direct property access without nested dictionaries
- Singleton pattern ensures consistency across components

### 2. Simplified GOAP
- Actions have simple boolean/string conditions
- Reactions are direct state assignments
- No complex operators or logic in conditions

### 3. Declarative Configuration
- YAML files contain only data, not logic
- No templating or variable substitution
- Boolean flags and string values only

### 4. Action Simplicity
- Each action has a single, clear purpose
- No composite actions or complex workflows
- State changes through direct property updates

### 5. Learning Integration
- Automatic learning from all API interactions
- Knowledge stored in simple YAML format
- No complex learning algorithms

## File Structure

### Core Files
- `src/controller/ai_player_controller.py` - Main orchestrator
- `src/controller/goap_execution_manager.py` - GOAP planning
- `src/controller/action_executor.py` - Action execution
- `src/controller/actions/base.py` - Action base class

### Configuration Files
- `config/action_configurations.yaml` - Action class registry
- `config/default_actions.yaml` - GOAP action definitions
- `config/goal_templates.yaml` - Goal definitions
- `config/consolidated_state_defaults.yaml` - Default state values

### State Files
- `data/world.yaml` - Current GOAP state
- `data/knowledge.yaml` - Learned game data  
- `data/map.yaml` - Map exploration data

## Development Patterns

### Subgoal Handling Patterns

The system supports sophisticated recursive workflows through subgoals. Actions can delegate subtasks to the GOAP system and continue execution after completion.

#### Pattern 1: Movement-Based Actions

Actions that need character movement should use the movement subgoal pattern:

```python
class ResourceGatheringAction(ActionBase):
    def execute(self, client, context: ActionContext) -> ActionResult:
        # Check if continuing from previous execution
        target_x = context.get('target_x')
        target_y = context.get('target_y')
        
        if target_x is not None and target_y is not None:
            # Continuation: Check if at target location
            char_response = get_character_api(context.character_name, client=client)
            current_x = char_response.data.x
            current_y = char_response.data.y
            
            if current_x == target_x and current_y == target_y:
                # At target - proceed with actual work
                return self._perform_gathering(client, context)
        
        # Initial execution: Find target and request movement
        location = self._find_resource_location(client, context)
        context.set_result('target_x', location['x'])
        context.set_result('target_y', location['y'])
        
        result = self.create_success_result("Found resource location")
        result.request_subgoal(
            goal_name="move_to_location",
            parameters={"target_x": location['x'], "target_y": location['y']},
            preserve_context=["target_material", "target_x", "target_y"]
        )
        return result
```

#### Pattern 2: Multi-Step Workflow Actions

For complex workflows requiring multiple steps:

```python
class ComplexWorkflowAction(ActionBase):
    def execute(self, client, context: ActionContext) -> ActionResult:
        workflow_step = context.get('workflow_step', 'initial')
        
        if workflow_step == 'initial':
            # Step 1: Request first subgoal
            context.set_result('workflow_step', 'materials_gathered')
            result = self.create_success_result("Starting workflow")
            result.request_subgoal(
                goal_name="gather_materials",
                parameters={"materials": ["copper_ore", "ash_wood"]},
                preserve_context=["workflow_step", "target_item"]
            )
            return result
            
        elif workflow_step == 'materials_gathered':
            # Step 2: Request second subgoal
            context.set_result('workflow_step', 'at_workshop')
            result = self.create_success_result("Materials ready")
            result.request_subgoal(
                goal_name="move_to_location",
                parameters={"target_x": workshop_x, "target_y": workshop_y},
                preserve_context=["workflow_step", "target_item"]
            )
            return result
            
        elif workflow_step == 'at_workshop':
            # Final step: Complete the work
            return self._complete_workflow(client, context)
```

#### Subgoal Action Mixin

For actions requiring common subgoal patterns, use the movement mixin:

```python
class MovementSubgoalMixin:
    """Mixin for actions that need to request movement subgoals."""
    
    def request_movement_subgoal(self, context: ActionContext, target_x: int, target_y: int, 
                                preserve_keys: List[str] = None) -> ActionResult:
        """Request movement to target location with proper context preservation."""
        context.set_result('target_x', target_x)
        context.set_result('target_y', target_y)
        
        preserve_context = preserve_keys or []
        preserve_context.extend(['target_x', 'target_y'])
        
        result = self.create_success_result(f"Requesting movement to ({target_x}, {target_y})")
        result.request_subgoal(
            goal_name="move_to_location",
            parameters={"target_x": target_x, "target_y": target_y},
            preserve_context=preserve_context
        )
        return result
    
    def is_at_target_location(self, client, context: ActionContext) -> bool:
        """Check if character is at the stored target location."""
        target_x = context.get('target_x')
        target_y = context.get('target_y')
        
        if target_x is None or target_y is None:
            return False
            
        char_response = get_character_api(context.character_name, client=client)
        if not char_response.data:
            return False
            
        return (char_response.data.x == target_x and 
                char_response.data.y == target_y)

class GatherResourceAction(ActionBase, MovementSubgoalMixin):
    def execute(self, client, context: ActionContext) -> ActionResult:
        if self.is_at_target_location(client, context):
            # Continuation: Perform gathering
            return self._perform_gathering(client, context)
        else:
            # Initial: Find location and request movement
            location = self._find_resource_location(client, context)
            return self.request_movement_subgoal(
                context, location['x'], location['y'],
                preserve_keys=['target_resource', 'quantity_needed']
            )
```

### Subgoal Best Practices

1. **Always Check for Continuation**: Actions should check stored context to determine if they're continuing from a previous execution

2. **Preserve Essential Context**: Use `preserve_context` parameter to maintain critical data across subgoal execution

3. **Use Appropriate Subgoal Names**: Match existing goal templates (`move_to_location`, `gather_materials`, etc.)

4. **Store Progression State**: Use context to track workflow progress for multi-step actions

5. **Handle Failures Gracefully**: Subgoal failures will cause action re-execution, so handle partial completion states

### Adding New Actions

1. Create action class inheriting from ActionBase (and mixins if needed):
```python
class NewAction(ActionBase, MovementSubgoalMixin):
    conditions = {
        'character_alive': True,
        'character_cooldown_active': False
    }
    reactions = {
        'some_status': 'completed'
    }
    weight = 1.0
    
    def execute(self, client, context: UnifiedStateContext):
        # Check for continuation first
        if self.is_at_target_location(client, context):
            return self._perform_work(client, context)
        
        # Find target and request movement
        location = self._find_target(client, context)
        return self.request_movement_subgoal(context, location['x'], location['y'])
```

2. Register in `config/action_configurations.yaml`:
```yaml
action_classes:
  new_action: "src.controller.actions.new_action.NewAction"
```

3. Add GOAP definition in `config/default_actions.yaml`:
```yaml
actions:
  new_action:
    conditions:
      character_alive: true
      character_cooldown_active: false
    reactions:
      some_status: completed
    weight: 1.0
```

### Adding New Goals

1. Define in `config/goal_templates.yaml`:
```yaml
goal_templates:
  new_goal:
    target_state:
      some_status: completed
```

### State Management

- Use UnifiedStateContext with flattened properties
- Access state directly: `context.selected_item`, `context.character_alive`
- Update state through direct property assignment
- No complex state calculations in configuration

This architecture provides a clean, maintainable foundation for AI behavior through simple declarative configuration and proven GOAP planning algorithms.