# ArtifactsMMO AI Player - CLI Usage Guide

This guide provides comprehensive documentation for using the ArtifactsMMO AI Player command-line interface.

## Table of Contents
- [Basic Usage](#basic-usage)
- [Command-Line Arguments](#command-line-arguments)
- [Diagnostic Tools](#diagnostic-tools)
- [Examples](#examples)
- [Advanced Usage](#advanced-usage)

## Basic Usage

The ArtifactsMMO AI Player can be run with various command-line options to control its behavior:

```bash
python -m src.main [OPTIONS]
```

### Environment Setup
Before running, ensure you have:
1. Python 3.13+ installed
2. Virtual environment activated: `workon artifactsmmo`
3. API token set: `export TOKEN=your_api_token`

### Quick Start
```bash
# Run with default settings (normal operation)
python -m src.main

# Run with debug logging
python -m src.main -l DEBUG

# Create a new character with random name
python -m src.main -c

# Test a goal plan (offline simulation)
python -m src.main -g "upgrade_weapon"

# Execute a goal plan with live API
python -m src.main -g "upgrade_weapon" --online
```

## Command-Line Arguments

### Logging Control

#### `-l, --log-level LEVEL`
Set the logging verbosity level.

**Options**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`  
**Default**: `INFO`

**Examples**:
```bash
# Run with debug logging for detailed information
python -m src.main -l DEBUG

# Run with minimal logging (errors only)
python -m src.main -l ERROR
```

### Character Management

#### `-c, --create-character`
Create a new character with a randomly generated 8-character name (a-zA-Z).

**Example**:
```bash
python -m src.main -c
```

#### `-d, --delete-character CHARACTER_NAME`
Delete an existing character.

**Example**:
```bash
python -m src.main -d "OldCharacter"
```

### Execution Modes

#### `-p, --parallel CHARACTER1,CHARACTER2,...`
Run multiple characters in parallel. Provide a comma-separated list of character names.

**Example**:
```bash
# Run three characters simultaneously
python -m src.main -p "Fighter1,Miner2,Crafter3"
```

#### `--daemon`
Run the AI player as a background daemon process. Sets up signal handlers for graceful shutdown.

**Example**:
```bash
# Start as daemon (responds to SIGTERM/SIGINT)
python -m src.main --daemon
```

### Data Management

#### `-n, --clean`
Clear all generated data files (`world.yaml`, `map.yaml`, `knowledge.yaml`). Useful for starting fresh or clearing corrupted data.

**Example**:
```bash
# Remove all learned data
python -m src.main --clean
```

### Planning and Debugging

#### `-g, --goal-planner GOAL_STRING`
Show the GOAP (Goal-Oriented Action Planning) plan for achieving a specified goal. Can run in offline simulation mode or execute with live API calls.

**Goal String Formats**:
- Goal templates: Predefined goals from goal_templates.yaml
- State expressions: `"property=value"` (e.g., `"character_level=5"`)
- Simple flags: `"flag_name"` (assumes true)
- Level patterns: `"reach level N"` or `"level_N"`

**Examples**:
```bash
# Show plan to reach level 5
python -m src.main -g "character_level=5"

# Show plan for combat readiness
python -m src.main -g "combat_status=ready"

# Use a goal template
python -m src.main -g "hunt_monsters"
```

**Note**: The system now uses flattened property names. Instead of nested paths like `character_status.level`, use direct properties like `character_level`.

#### `-e, --evaluate-plan PLAN_STRING`
Evaluate a user-defined sequence of actions to check if it's valid and executable. Shows step-by-step validation of conditions and state changes.

**Plan String Formats**:
- Arrow separator: `"action1->action2->action3"`
- Comma separator: `"action1,action2,action3"`
- Pipe separator: `"action1|action2|action3"`
- Semicolon separator: `"action1;action2;action3"`

**Examples**:
```bash
# Evaluate a combat sequence
python -m src.main -e "find_monsters->attack->rest"

# Evaluate a crafting workflow
python -m src.main -e "find_resources,gather_resources,craft_item"

# Evaluate a simple action
python -m src.main -e "rest"
```

### Other Options

#### `--version`
Display the program version and exit.

```bash
python -m src.main --version
```

#### `-h, --help`
Show help message with all available options.

```bash
python -m src.main --help
```

## Diagnostic Tools

The diagnostic tools provide powerful debugging capabilities for GOAP planning and action evaluation. They support both offline simulation and live API execution.

### Diagnostic Options

#### `--offline`
Run diagnostic tools in offline mode without API access (default). This simulates action execution without making real API calls.

#### `--online`
Execute diagnostic plans with live API calls (requires authentication). Actions are actually executed against the game API.

#### `--clean-state`
Start diagnostics with a clean default state instead of loading existing world data. Useful for testing from known conditions.

#### `--state STATE_JSON`
Initialize diagnostics with custom state (JSON format). Allows testing specific scenarios.

### Diagnostic Examples

#### Offline Goal Planning with Clean State
```bash
$ python -m src.main -g "character_status.level=5" --clean-state

=== GOAP Plan Analysis for Goal: character_status.level=5 ===
Mode: OFFLINE simulation
Loaded 29 available actions
Goal state: {character_status: {level: 5}}

Current state summary:
character_status:
  level: 1

Generating GOAP plan...

❌ No plan found!

Possible reasons:
- Goal is already satisfied in current state
- No action sequence can achieve the goal
- Missing prerequisite states
```

#### Goal Planning with Custom State
```bash
$ python -m src.main -g "combat_context.status=ready" --state '{"combat_context": {"status": "searching"}}'

=== GOAP Plan Analysis for Goal: combat_context.status=ready ===
Mode: OFFLINE simulation

✅ Plan found with 1 actions:

1. find_monsters (weight: 2)
   Requires:
     - combat_context:
         status: searching
     - character_status:
         alive: True
   Effects:
     - resource_availability:
         monsters: True
     - combat_context:
         status: ready
     - location_context:
         at_target: True

Total plan cost: 2.00
```

#### Plan Evaluation with Clean State
```bash
$ python -m src.main -e "rest" --clean-state

=== Evaluating User Plan: rest ===
Mode: OFFLINE simulation

Starting state summary:
Character: Level 1, HP: 100.0%, Alive: True
Combat: Status=idle, Win rate=1.0
Location: (0, 0) Type: spawn

1. Evaluating action: rest
   ❌ Conditions not met:
     - healing_context.healing_status: required=in_progress, current=idle

=== Plan Evaluation Summary ===
❌ Plan is INVALID and cannot be executed
Fix the issues above before the plan can work
```

#### Live Execution Mode
```bash
# Execute a goal plan with live API calls
python -m src.main -g "hunt_monsters" --online

# Evaluate and execute a plan with live API
python -m src.main -e "move->attack" --online

# Set TOKEN from file for authenticated API access
export TOKEN=$(cat TOKEN) && python -m src.main -g "upgrade_weapon" --online

# Test specific action sequences with real character state
export TOKEN=$(cat TOKEN) && python -m src.main -e "determine_material_requirements->determine_material_insufficiency" --online
```

#### Complex State Initialization
```bash
# Test with specific game state
python -m src.main -g "equipment_status.equipped=true" \
  --state '{
    "character_status": {"alive": true, "level": 5},
    "equipment_status": {"item_crafted": true, "equipped": false, "selected_item": "copper_dagger"},
    "location_context": {"at_workshop": true}
  }'
```

## Examples

### Common Usage Patterns

1. **Development/Testing**
   ```bash
   # Run with debug logging and clean data
   python -m src.main --clean -l DEBUG
   
   # Test with clean state and offline diagnostics
   python -m src.main -g "character_status.level=10" --clean-state -l DEBUG
   ```

2. **Planning Analysis**
   ```bash
   # Check what actions are needed to reach level 5
   python -m src.main -g "character_status.level=5" --clean-state
   
   # Verify a combat strategy is valid
   python -m src.main -e "find_monsters->attack->rest"
   
   # Test with custom initial state
   python -m src.main -g "combat_context.status=completed" \
     --state '{"combat_context": {"status": "ready"}}'
   ```

3. **Production Run**
   ```bash
   # Run as daemon with standard logging
   python -m src.main --daemon
   
   # Run multiple characters
   python -m src.main -p "MainChar,AltChar1,AltChar2"
   ```

4. **Troubleshooting**
   ```bash
   # Clear data and run with verbose logging
   python -m src.main --clean -l DEBUG
   
   # Debug why a plan isn't working
   python -m src.main -e "rest" --clean-state -l DEBUG
   
   # Test goal planning with existing world state
   python -m src.main -g "equipment_status.equipped=true"
   ```

## Advanced Usage

### Combining Options
Options can be combined, but some are mutually exclusive:
- Cannot use `--daemon` with planning options (`-g`, `-e`)
- Cannot use `--clean` with character management (`-c`, `-d`)
- Cannot use both `--offline` and `--online` modes
- `--online` mode requires either `--goal-planner` or `--evaluate-plan`
- `--state` requires either `--goal-planner` or `--evaluate-plan`
- Character management options (`-c`, `-d`) are mutually exclusive
- Planning options (`-g`, `-e`) are mutually exclusive

### Exit Codes
- `0`: Success
- `1`: Invalid arguments or configuration error
- Other: System or runtime errors

### Signal Handling
When running with `--daemon`, the program responds to:
- `SIGTERM`: Graceful shutdown
- `SIGINT` (Ctrl+C): Graceful shutdown

### API Authentication for Live Testing

The diagnostic tools support live API testing using a TOKEN file:

```bash
# The TOKEN file contains your API authentication token
# Set it as environment variable for live testing
export TOKEN=$(cat TOKEN)

# Now you can use --online mode with full API access
python -m src.main -g "upgrade_weapon" --online

# Test specific action behaviors with real character data
python -m src.main -e "check_material_availability" --online

# Combine with custom states to test edge cases
python -m src.main -g "upgrade_weapon" --online --state '{"equipment_status": {"selected_item": "copper_dagger"}}'
```

**Benefits of TOKEN-based testing:**
- Validates action behavior with real API responses
- Tests actual character inventory and game state
- Identifies issues that offline simulation might miss
- Allows prototyping complex action sequences safely

**Best practices:**
- Use `export TOKEN=$(cat TOKEN)` before diagnostic commands
- Start with simple single-action tests before complex goals
- Monitor session.log for detailed execution traces
- Use `--clean-state` to reset between tests when needed

### Performance Considerations
- The `-p` parallel mode creates separate async tasks for each character
- Each character maintains its own state and cooldown management
- API rate limiting (180 requests/minute) is shared across all characters

### Debugging Tips

1. **Use Diagnostic Tools for Planning Issues**
   - Use `--clean-state` to test from a known state
   - Use `--state` to set up specific test scenarios
   - Start with `--offline` mode to validate plans before live execution

2. **Understanding Plan Failures**
   - "No plan found" - The goal may be impossible from current state
   - "Conditions not met" - Check the action's required preconditions
   - Use `-l DEBUG` for detailed execution logs

3. **Common Diagnostic Workflows**
   ```bash
   # Test why a goal isn't achievable
   python -m src.main -g "your_goal" --clean-state
   
   # Validate a specific action sequence
   python -m src.main -e "action1->action2" --clean-state
   
   # Debug with custom state
   python -m src.main -g "goal" --state '{"key": "value"}' -l DEBUG
   
   # Test with real API data (requires TOKEN file)
   export TOKEN=$(cat TOKEN) && python -m src.main -g "upgrade_weapon" --online
   
   # Validate action execution with live character
   # Note: For ActionContext properties, place them in the appropriate state category
   export TOKEN=$(cat TOKEN) && python -m src.main -e "determine_material_insufficiency" --online --state '{"materials": {"requirements_determined": true, "status": "checking"}, "equipment_status": {"selected_item": "copper_dagger", "has_selected_item": true}}'
   ```

4. **Check State Files**
   - `data/world.yaml` - Current GOAP world state
   - `data/map.yaml` - Discovered map locations
   - `data/knowledge.yaml` - Learned game data

### State Format Reference

The `--state` parameter accepts JSON with the consolidated state structure. Note that ActionContext flattened properties should be placed in their appropriate state categories:

```json
{
  "character_status": {
    "alive": true,
    "level": 1,
    "hp_percentage": 100.0,
    "cooldown_active": false
  },
  "combat_context": {
    "status": "idle",
    "target": null,
    "recent_win_rate": 1.0
  },
  "equipment_status": {
    "equipped": false,
    "selected_item": "copper_dagger",    // ActionContext property
    "has_selected_item": true,             // Required for actions that check selected_item
    "target_slot": "weapon",               // ActionContext property
    "upgrade_status": "ready"              // ActionContext property
  },
  "location_context": {
    "at_target": false,
    "at_workshop": false,
    "current": {"x": 0, "y": 0, "type": "spawn"},
    "target_x": 2,                          // ActionContext property
    "target_y": 0,                          // ActionContext property
    "resource_code": "copper_rocks"        // ActionContext property
  },
  "materials": {
    "material_requirements": {              // ActionContext property
      "copper_ore": 5
    },
    "missing_materials": {                  // ActionContext property
      "copper_ore": 3
    }
  }
}
```