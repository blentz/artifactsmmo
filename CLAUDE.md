# Claude.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **artifactsmmo AI player** project. This project is an AI player used for operating a character in a role-playing game played through an API. This is a python v3.13 project.

## Project Principles

- Backward compatibility is not a priority and should not be factored into your solutions.
- General case solutions must be preferred over special-case handling.
- Behavior-based solutions must be preferred over hard-coded solutions.
- The API responses are authoritative and the only source for data.
- Use object-oriented strategies, function pointer passing, and callback methods to execute behaviors to minimize complex if-else logic.
- Use test-driven development strategies to ensure that all changes have tests that confirm their correctness.

### State Engine Integration Patterns
- **StateCalculationEngine integration**: Add computed state variables to world state calculation
- **Preserve existing functionality**: Don't override critical calculations like cooldown detection
- **Integration pattern**: Apply state engine AFTER base calculations, with selective overrides
```python
# Preserve existing cooldown calculation when integrating state engine
current_cooldown_state = state.get('is_on_cooldown')
computed_state = self.state_engine.calculate_derived_state(state, self.thresholds)
if 'is_on_cooldown' in computed_state and current_cooldown_state is not None:
    computed_state['is_on_cooldown'] = current_cooldown_state
```

### Critical Testing & Validation Requirements
**ALWAYS verify changes with both unit tests AND real API execution:**
1. Run full test suite: `python -m unittest` (all 480+ tests must pass)
2. Run real application: `./run.sh` (minimum 15-30 seconds to observe behavior)
3. Verify goal selection, GOAP planning, action execution, and learning system
4. Check data persistence to YAML files (world.yaml, knowledge.yaml, map.yaml)

## Development Commands

### Build & Development
- `workon artifactsmmo` - Enable python virtualenv.
- `deactivate artifactsmmo` - Disable python virtualenv
- `generate_openapi_client.sh` - Generate API Client files

### Testing
- `python -m unittest` - Run all unit tests (preferred method)
- `python -m unittest test.controller.test_action_factory -v` - Run specific test module with verbose output
- `python -m unittest test.controller.test_ai_player_controller_metaprogramming.TestAIPlayerControllerMetaprogramming.test_execute_action_through_metaprogramming -v` - Run specific test method
- `pytest --tb=short` - Alternative test runner (legacy)
- `pytest --tb=short --cov=artifactsmmo` - Run tests with coverage reporting

### Code Quality
- `pylint` - Run Pylint

### Execution
- `run.sh` - Run application. This command can only be used after all unit tests pass with no errors. This command writes to session.log. No additional output redirection or piping is needed to follow the output.

### Additional Command-Line Utilities
- `jq` - JSON query tool
- `yq` - YAML query tool

## Architecture

### Core Components

**Core application** (`src/`):
- `main.py` - Application entrypoint

**Controller** (`src/controller/`):
- `actions/` - Action classes with GOAP parameters (used for class defaults only)
- `action_factory.py` - Dynamic action instantiation from YAML configuration
- `action_executor.py` - YAML-driven action execution with composite action support
- `ai_player_controller.py` - Main AI controller for manager coordination (830 lines)
- `cooldown_manager.py` - Character state caching and cooldown handling
- `goap_execution_manager.py` - Centralized GOAP planning and execution
- `skill_goal_manager.py` - Skill-specific progression goals (9 skills supported)
- `mission_executor.py` - Level progression and autonomous mission execution
- `learning_manager.py` - Learning callbacks and knowledge management
- `goal_manager.py` - YAML-driven goal template management
- `state_engine.py` - State calculation engine
- `world/` - World state management
- `knowledge/` - Learning and knowledge management

**Game state** (`src/game/`):
- `character/` - Character state
- `map/` - Map state

**Libraries** (`src/lib/`):
- `goap.py` - Goal-oriented Action Planner base library ("GOAP")
- `goap_data.py` - YAML-backed state storage for Goal-oriented Action Planner base library
- `state_loader.py` - Object-oriented YAML-driven state management with dependency injection
- `httpstatus.py` - Custom HTTP status codes used by the ArtifactsMMO API
- `log.py` - Logging facilities
- `yaml_data.py` - YAML-backed file storage

**Configuration** (`config/`):
- `action_configurations.yaml` - YAML-driven action definitions and composite workflows
- `state_configurations.yaml` - Object-oriented state class configuration
- `actions.yaml` - GOAP action configurations for planning
- `skill_goals.yaml` - Skill progression templates and strategies (9 skills)
- `goal_templates.yaml` - Goal template definitions
- `state_engine.yaml` - State calculation rules
- `default_actions.yaml` - Default action configurations
- `ai_player.yaml` - AI player configuration

**Data** (`data/`):
- `world.yaml` - World state persistence (runtime)
- `knowledge.yaml` - Learning and combat data persistence (runtime)
- `map.yaml` - Map exploration data persistence (runtime)

**ArtifactsMMO API Client Library** (`artifactsmmo-api-client/`):
- `artifactsmmo-api-client/` - API Client library files for connecting to the ArtifactsMMO API

### Key Design Patterns

1. **Modular Manager Architecture**: The system uses specialized managers for different concerns
   - **AIPlayerController**: Coordinates between managers (830 lines, focused on orchestration)
   - **GOAPExecutionManager**: Handles all GOAP planning and execution
   - **SkillGoalManager**: Manages skill-specific progression (9 skills: combat, woodcutting, mining, fishing, weaponcrafting, gearcrafting, jewelrycrafting, cooking, alchemy)
   - **MissionExecutor**: Handles level progression and autonomous missions
   - **CooldownManager**: Manages character state caching and cooldown handling
   - **LearningManager**: Handles learning callbacks and knowledge management

2. **Metaprogramming Architecture**: The system uses YAML-driven metaprogramming for action execution
   - Actions are created dynamically through ActionFactory based on YAML configuration
   - No hardcoded if-elif blocks - all action logic is configuration-driven
   - Supports composite actions and parameter template resolution

3. **Factory Pattern**: ActionFactory creates action instances dynamically from configuration

4. **Strategy Pattern**: ActionExecutor handles different action types (simple, composite, special)

5. **Dependency Injection**: StateLoader manages object creation with YAML-defined dependencies

6. **GOAP Integration**: Goal-Oriented Action Planning with centralized execution management

7. **Learning System**: Automatic learning callbacks integrated into metaprogramming execution flow

8. **Data Persistence**: YAML-backed state persistence with automatic API data capture

9. **Skill Progression System**: Template-driven skill advancement with YAML-configurable progression rules

## Development Notes

- The system uses Python 3.13 with type checking
- The virtualenv must be enabled before running any python commands
- Most command-line utilities have a `-h` or `--help` flag
- **IMPORTANT**: The system uses modular manager architecture - functionality is NOT added to the controller directly but through specialized managers
- **IMPORTANT**: The system uses metaprogramming - actions are NOT created directly but through ActionFactory
- **IMPORTANT**: All new functionality should be added via YAML configuration, not hardcoded logic
- **IMPORTANT**: GOAP functionality is handled by GOAPExecutionManager, not the controller directly
- **IMPORTANT**: Skill progression is handled by SkillGoalManager with YAML-configurable templates
- Configuration changes can be hot-reloaded without code changes

## Data Persistence System

The system automatically persists game data from API responses to YAML files:

### Core Data Files

1. **`data/world.yaml`** - GOAP world state
   - Updated by GOAP planner during goal execution
   - Contains boolean flags like `monsters_available`, `character_alive`, etc.

2. **`data/map.yaml`** - Map exploration data
   - Updated when MapState.scan() discovers new locations
   - Contains location data: coordinates, content, terrain types
   - Learning callbacks trigger when content (monsters, resources) is discovered

3. **`data/knowledge.yaml`** - Learning and combat data
   - Updated by learning callbacks during gameplay
   - Contains monster combat statistics, resource discovery data
   - Updated when: fighting monsters, discovering content, learning from exploration

### Learning System Integration

The learning system automatically captures data during gameplay:

```python
# Learning callbacks are triggered automatically during:
# 1. Map exploration (content discovery)
map_state.set_learning_callback(controller.learn_from_map_exploration)

# 2. Combat (via action executor)
controller.learn_from_combat(monster_code, result, pre_combat_hp)

# 3. Action execution (integrated into metaprogramming flow)
action_executor._handle_learning_callbacks(action_name, response, context)
```

### Data Flow Architecture

```
API Response → Action Execution → Learning Callbacks → YAML Persistence
     ↓              ↓                   ↓                    ↓
Game Data → ActionExecutor → learn_from_* methods → save() to files
```

**Key Points**:
- Data files repopulate automatically from API on each run
- No manual data management required
- Learning happens in real-time during gameplay
- Files contain only real game data, never test data

### Adding New Actions

**DO NOT** create new actions by:
- Adding if-elif blocks to the controller
- Hardcoding action instantiation

**DO** create new actions by:
1. Adding action class in `src/controller/actions/` with GOAP parameters
2. Registering in `data/action_configurations.yaml`
3. Writing tests for the action class

Example new action registration:
```yaml
action_configurations:
  new_action:
    type: "builtin"
    description: "Description of new action"
```

### Creating Composite Actions

Define multi-step workflows in YAML:
```yaml
composite_actions:
  gather_and_craft:
    description: "Gather resources then craft items"
    steps:
      - name: "find_resources"
        action: "find_resources"
        required: true
        params:
          resource_type: "${action_data.resource_type}"
      - name: "gather"
        action: "gather_resources"
        required: true
        conditions:
          resource_found: true
      - name: "craft"
        action: "craft_item"
        required: false
        params:
          item_type: "${action_data.target_item}"
```

## Testing Philosophy

- Tests should validate functional correctness based on APIs presented by client library
- All tests should be created under the `test/` directory
- Do not create demo files
- Do not create summary reports
- You must run unit tests after every code change to validate your changes.
- The `run.sh` script creates a `session.log` with a log of the play session.
- **IMPORTANT**: You must maintain as close to 100% test coverage as possible.
- **IMPORTANT**: Use metaprogramming test patterns, not direct action mocking

### Verification Requirements

**CRITICAL**: Before reporting any task as complete, you MUST:

1. **Run unit tests** to verify code correctness:
   ```bash
   python -m unittest
   ```
   - All tests must pass
   - No new test failures introduced
   - Verify relevant test modules specifically

2. **Run the application** to verify real-world functionality:
   ```bash
   ./run.sh
   ```
   - Test for at least 10-15 seconds
   - Verify expected behavior occurs
   - Check that data files are created/updated correctly
   - Ensure no runtime errors

3. **Verify data persistence** (if applicable):
   - Check that `data/world.yaml`, `data/map.yaml`, `data/knowledge.yaml` are updated
   - Confirm no test data contaminates production files
   - Verify files contain real game data, not mock/test data

**NEVER** report success based solely on:
- Code compilation
- Static analysis
- Theoretical correctness
- System reminders about file changes

**ALWAYS** verify with both unit tests AND actual application execution.

### Test Structure
```
test/
├── controller/
│   ├── test_action_factory.py                    # Factory pattern tests
│   ├── test_action_executor.py                   # Executor tests
│   ├── test_ai_player_controller_metaprogramming.py  # Controller integration
│   └── test_learning_metaprogramming.py          # Learning integration
├── lib/
│   └── test_state_loader.py                     # State management tests
└── [action_tests]/                              # Individual action class tests
```

### Writing Metaprogramming Tests

**DO NOT** mock action classes directly:
```python
# WRONG - Old approach
@patch('src.controller.ai_player_controller.MoveAction')
def test_move_action(self, mock_move_action):
    # This bypasses metaprogramming
```

**DO** test through ActionExecutor:
```python
# CORRECT - Metaprogramming approach
@patch('src.controller.ai_player_controller.ActionExecutor')
def test_move_action(self, mock_executor_class):
    mock_executor_instance = Mock()
    mock_executor_class.return_value = mock_executor_instance
    # Test through metaprogramming system
```

### Test Data Isolation

**CRITICAL**: Tests must NEVER write to production data files.

**WRONG** - Writing to production files:
```python
# This will contaminate production data
knowledge_base = KnowledgeBase(filename='knowledge.yaml')
```

**CORRECT** - Use temporary files:
```python
# Tests must use temporary directories
self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
knowledge_base = KnowledgeBase(filename=self.temp_file.name)
```

**Production data files** that must stay clean:
- `data/world.yaml` - GOAP state persistence
- `data/map.yaml` - Map exploration data
- `data/knowledge.yaml` - Learning and combat data

These files should only contain real game data from API responses, never test data.

## Critical Bug Prevention Patterns

### Runtime Stability Issues

**CRITICAL BUG PATTERNS** that have been identified and fixed:

#### 1. Cooldown Handling

**Problem**: Actions continuing despite active cooldowns causing 499 API errors
```
🕐 Cooldown detected before {action} - skipping action
```

**Prevention**:
- **ALWAYS** check for cooldowns before non-wait actions: `_is_character_on_cooldown()`
- **ALLOW** rest and wait actions during cooldowns: `action_name not in ['wait', 'rest']`
- **EXTEND** wait duration for long cooldowns: maximum 65 seconds (not 30)
- **REFRESH** character state before cooldown detection to get current status

#### 2. Combat Results Recording

**Problem**: Combat data not persisting to `knowledge.yaml` despite learning callbacks
```python
# WRONG - Missing fight_data parameter
knowledge_base.record_combat_result(monster_code, result, character_data)

# CORRECT - Include fight_data for detailed recording
knowledge_base.record_combat_result(monster_code, result, character_data, fight_data)
```

**Prevention**:
- **EXTRACT** fight_data in action_executor learning callbacks
- **PASS** fight_data as 4th parameter to `learn_from_combat()` method
- **CONVERT** response objects to dict format for knowledge base storage
- **VERIFY** `total_combats` increases and `combat_results` arrays populate

#### 3. Action Parameter Passing

**Problem**: "Missing required parameter X for action Y" in action sequences
```
Missing required parameter x for action move
```

**Prevention**:
- **PRESERVE** action context between plan iterations: `self.action_context = preserved_data`
- **EXTRACT** location data from successful find_monsters actions
- **STORE** target coordinates in action context for subsequent move actions
- **MAINTAIN** data flow: find_monsters → action_context → move action

#### 4. HTTP Request Optimization

**Problem**: Excessive API requests during monster search
```
⚠️ Cache miss for (10,5) - requesting from API
```

**Prevention**:
- **IMPLEMENT** timestamp-based caching: 5-minute cache duration
- **CHECK** cache freshness before API requests: `is_cache_fresh(x, y)`
- **LIMIT** HTTP requests to once per grid square per hunt iteration
- **STORE** last_scanned timestamp with location data

#### 5. Test Data Contamination

**Problem**: Unit tests writing mock data to production YAML files
```
# WRONG - Contaminates production data
knowledge_base = KnowledgeBase(filename='knowledge.yaml')

# CORRECT - Isolated test data
temp_file = tempfile.NamedTemporaryFile(suffix='.yaml', delete=False)
knowledge_base = KnowledgeBase(filename=temp_file.name)
```

**Prevention**:
- **PATCH** DATA_PREFIX in tests: `@patch('src.game.map.state.DATA_PREFIX', temp_dir)`
- **USE** temporary directories for all test state files
- **VERIFY** no test files appear in `data/` directory after test runs
- **ISOLATE** test configurations from production configurations

### Validation Requirements

**MANDATORY** verification steps before claiming any fix is complete:

#### 1. Unit Test Verification
```bash
python -m unittest  # Must pass 100%
```
- **ALL** tests must pass without failures
- **NEW** tests must be created for fixed bugs to prevent regressions
- **METHOD** signatures updated if parameters change (e.g., fight_data addition)

#### 2. Runtime Validation
```bash
./run.sh  # Run for at least 30 seconds
```
- **MONITOR** for expected behavior (combat, movement, learning)
- **CHECK** log messages indicate fixes are working:
  - `🕐 Cooldown detected` for cooldown handling
  - `⚔️ Combat vs {monster}: {result}` for combat logging
  - `🧠 Combat learning` for combat results recording
  - `💰 XP gained from {monster}: {amount}` for detailed combat data

#### 3. Data Persistence Verification
```bash
# Check that data files are being updated with real game data
ls -la data/*.yaml
cat data/knowledge.yaml | grep -A5 "combat_results"
```
- **VERIFY** `total_combats` increases during gameplay
- **CONFIRM** `combat_results` arrays contain combat records
- **CHECK** no test data in production files

### Emergency Debugging

**When fixes don't work as expected:**

1. **Check character state refresh**: Logs should show "Updated character cooldown expiration"
2. **Monitor action execution flow**: Look for "Action {name} executed successfully" vs "Action {name} failed"
3. **Trace learning callbacks**: Search logs for "🔍 Processing attack learning" and fight data extraction
4. **Verify action context preservation**: Check that target coordinates persist between actions
5. **Confirm cache behavior**: Look for cache hit/miss messages during map exploration

**Common fix validation failures:**
- Tests pass but runtime fails → Check action parameter mappings and context passing
- Runtime works but data not persisting → Verify learning callbacks and save() calls
- Cooldowns still causing issues → Check character state refresh timing
- Combat data missing specific fields → Verify fight_data extraction and conversion

## Debugging and Troubleshooting

### Common Issues

1. **"Missing required parameter" errors**: Check action factory parameter mappings and action context preservation
2. **"Unknown action" errors**: Verify action is registered in `action_configurations.yaml`
3. **Tests bypassing metaprogramming**: Ensure tests use ActionExecutor, not direct action mocking
4. **GOAP integration issues**: Check action class has proper `conditions`, `reactions`, and `weights`
5. **Data persistence not working**:
   - Check that learning callbacks are set: `map_state.set_learning_callback()`
   - Verify YAML data structure loading: check for nested `data:` keys
   - Confirm files are being created in `data/` directory, not test directories
   - Verify fight_data parameter is passed to record_combat_result()
6. **Test data contaminating production files**:
   - Check that tests use `tempfile.mkdtemp()` or `tempfile.NamedTemporaryFile()`
   - Ensure test state configurations point to temp directories
   - Verify no hardcoded paths to `data/` directory in tests
7. **Cooldown handling issues**:
   - Check that character state is refreshed before cooldown detection
   - Verify wait actions can execute up to 65 seconds duration
   - Ensure rest actions are allowed during cooldowns
8. **Combat results not recording**:
   - Check that action_executor extracts fight_data from API responses
   - Verify learn_from_combat() signature includes fight_data parameter
   - Confirm knowledge_base.record_combat_result() receives fight_data

### Debug Commands

- Check available actions: `controller.get_available_actions()`
- Reload configurations: `controller.reload_action_configurations()`
- Verify factory registration: `controller.action_executor.factory.is_action_registered('action_name')`
- Check data file modification times: `ls -la data/*.yaml`
- Verify learning callback setup: `map_state._learning_callback is not None`
- Check YAML data structure: `knowledge_base.data` (should not contain nested `data:` keys)
- Monitor learning during gameplay: Look for "🧠 Learned:" log messages
- Check cooldown status: `controller._is_character_on_cooldown()`
- Verify combat data recording: `grep "combat_results" data/knowledge.yaml`
- Monitor action context: `controller.action_context` for preserved coordinates
- Check cache behavior: Look for "Cache hit/miss" messages in map exploration

