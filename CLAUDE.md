# Claude.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **artifactsmmo AI player** project - an AI player for operating a character in a role-playing game through an API. Uses Python 3.13.

## Core Project Principles

1. **Prioritize general-case solutions** over special-case handling
2. **Avoid code duplication** - maximize code reuse
3. **Ignore backward compatibility** - refactor freely for better solutions
4. **No hard-coded values** - use configuration and dynamic discovery
5. **Behavior-based solutions** over hard-coded logic
6. **API responses are authoritative** - the only source for data
7. **Test-driven development** - all changes must have tests

## Architecture

### Key Design Patterns

1. **Modular Manager Architecture**
   - AIPlayerController: Orchestration only (no business logic)
   - Specialized managers handle specific concerns
   - Functionality added through managers, not the controller

2. **Metaprogramming & YAML-Driven Configuration**
   - Actions created dynamically via ActionFactory
   - No hard-coded if-elif blocks
   - All behavior configured through YAML

3. **ActionContext Pattern**
   - Actions communicate through ActionContext
   - Use `set_result()` to preserve data for subsequent actions
   - Context persists throughout plan execution
   - No hard-coded parameter mappings

4. **GOAP (Goal-Oriented Action Planning)**
   - Centralized through GOAPExecutionManager
   - Actions define conditions/reactions/weights
   - Dynamic replanning based on discoveries

5. **Learning System**
   - Automatic callbacks during action execution
   - Real-time data capture from API
   - Persisted to YAML files

### Core Components

**Controller** (`src/controller/`)
- `ai_player_controller.py` - Main orchestrator
- `goap_execution_manager.py` - GOAP planning/execution
- `action_executor.py` - YAML-driven action execution
- `action_factory.py` - Dynamic action instantiation
- Manager classes for specific domains

**Actions** (`src/controller/actions/`)
- Inherit from `ActionBase`
- Use ActionContext for parameters
- Define GOAP properties (conditions, reactions, weights)

**Configuration** (`config/`)
- `action_configurations.yaml` - Action definitions
- `goal_templates.yaml` - Goal definitions
- `state_engine.yaml` - State calculations

**Data Persistence** (`data/`)
- `world.yaml` - GOAP world state
- `knowledge.yaml` - Learning data
- `map.yaml` - Map exploration

## Development Workflow

### Commands
```bash
# Development
workon artifactsmmo           # Enable virtualenv
python -m pytest              # Run all tests
./run.sh                      # Run application (after tests pass)

# Utilities
jq                           # Query session.log (JSON format)
yq                           # Query YAML files
```

### Critical Testing Requirements

**ALWAYS verify changes with:**
1. Unit tests: `python -m pytest` (must pass 100%)
2. Runtime test: `./run.sh` (minimum 15-30 seconds)
3. Check data persistence in YAML files
4. Verify no test data contaminates production files

### Adding New Functionality

**DO NOT:**
- Add if-elif blocks to controllers
- Hard-code action instantiation
- Create special-case handlers
- Add business logic to the controller

**DO:**
1. Create action class in `src/controller/actions/`
2. Register in `config/action_configurations.yaml`
3. Write comprehensive tests
4. Use ActionContext for data flow

Example action registration:
```yaml
action_configurations:
  new_action:
    type: "builtin"
    description: "Description of new action"
```

### Writing Tests

**Test Patterns:**
```python
# CORRECT - Test through metaprogramming
@patch('src.controller.ai_player_controller.ActionExecutor')
def test_action(self, mock_executor_class):
    # Test through ActionExecutor

# WRONG - Direct action mocking
@patch('src.controller.ai_player_controller.MoveAction')
def test_action(self, mock_move_action):
    # Bypasses metaprogramming
```

**Test Isolation:**
- Use temporary files for test data
- Never write to production YAML files
- Patch DATA_PREFIX in tests

## Key Learnings

### ActionContext Usage
Actions must preserve information for subsequent actions:
```python
# In action - preserve data
if hasattr(self, '_context') and self._context:
    self._context.set_result('target_item', selected_item)
    
# In controller - context persists automatically
if not hasattr(self, 'action_context'):
    self.action_context = {}
```

### State Engine Integration
Apply state engine calculations after base calculations:
```python
current_state = state.get('is_on_cooldown')
computed_state = self.state_engine.calculate_derived_state(state)
if 'is_on_cooldown' in computed_state and current_state is not None:
    computed_state['is_on_cooldown'] = current_state
```

### Knowledge Base Fallback
Use API fallback for missing data:
```python
monster_data = knowledge_base.get_monster_data('chicken', client=api_client)
# Checks local cache first, then API if needed
```

## Common Issues & Solutions

1. **"Missing required parameter"** → Check ActionContext preservation
2. **"Unknown action"** → Verify registration in action_configurations.yaml
3. **Data not persisting** → Check learning callbacks are set
4. **Test data contamination** → Ensure tests use temp directories
5. **Cooldown issues** → Verify character state refresh before detection
6. **Goal parsing errors** → Check compound operators handled first
7. **Action context lost** → Ensure actions use `set_result()`

## Debug Commands

```python
# Check available actions
controller.get_available_actions()

# Reload configurations
controller.reload_action_configurations()

# Check action registration
controller.action_executor.factory.is_action_registered('action_name')

# Monitor action context
controller.action_context  # Should persist between actions
```

## Additional Documentation

- Bug prevention patterns: `docs/BUG_PREVENTION_PATTERNS.md`
- YAML configuration guide: `docs/YAML_CONFIGURATION.md`
- CLI usage: `docs/CLI_USAGE.md`

## Important Notes

- Python 3.13 with type checking
- Configuration hot-reloadable without code changes
- System uses discovery over hard-coding
- All new features via YAML configuration
- Maintain near 100% test coverage
- Production data files must stay clean of test data
