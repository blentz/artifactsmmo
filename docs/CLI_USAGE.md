# ArtifactsMMO AI Player - CLI Usage Guide

This guide provides comprehensive documentation for using the ArtifactsMMO AI Player command-line interface.

## Table of Contents
- [Basic Usage](#basic-usage)
- [Command-Line Arguments](#command-line-arguments)
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

#### `-c, --create-character CHARACTER_NAME`
Create a new character with the specified name.

**Note**: Currently not implemented - placeholder for future API integration.

**Example**:
```bash
python -m src.main -c "MyHeroChar"
```

#### `-d, --delete-character CHARACTER_NAME`
Delete an existing character.

**Note**: Currently not implemented - placeholder for future API integration.

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
Show the GOAP (Goal-Oriented Action Planning) plan for achieving a specified goal without executing it. This is useful for debugging planning issues.

**Goal String Formats**:
- Level goals: `"level_N"` where N is the target level
- XP goals: `"has_xp"` or `"xp"`
- Skill goals: `"SKILL_skill"` where SKILL is one of: combat, woodcutting, mining, fishing, weaponcrafting, gearcrafting, jewelrycrafting, cooking, alchemy
- State variables: `"variable_name=value"` or just `"variable_name"` (assumes true)

**Examples**:
```bash
# Show plan to reach level 10
python -m src.main -g "level_10"

# Show plan to gain XP
python -m src.main -g "has_xp"

# Show plan to advance mining skill
python -m src.main -g "mining_skill"

# Show plan for custom goal state
python -m src.main -g "has_iron_ore=true"
```

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
python -m src.main -e "wait"
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

## Examples

### Common Usage Patterns

1. **Development/Testing**
   ```bash
   # Run with debug logging and clean data
   python -m src.main --clean -l DEBUG
   ```

2. **Planning Analysis**
   ```bash
   # Check what actions are needed to reach level 20
   python -m src.main -g "level_20"
   
   # Verify a combat strategy is valid
   python -m src.main -e "find_monsters->move->attack->rest->move"
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
   
   # Test specific goal planning
   python -m src.main -g "combat_skill_ge"
   ```

## Advanced Usage

### Combining Options
Options can be combined, but some are mutually exclusive:
- Cannot use `--daemon` with planning options (`-g`, `-e`)
- Cannot use `--clean` with character management (`-c`, `-d`)
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

### Performance Considerations
- The `-p` parallel mode creates separate async tasks for each character
- Each character maintains its own state and cooldown management
- API rate limiting (180 requests/minute) is shared across all characters

### Debugging Tips
1. Use `-l DEBUG` to see detailed action execution
2. Use `-g` to understand why certain goals aren't being achieved
3. Use `-e` to validate custom action sequences before implementation
4. Check data files in `data/` directory for current world state