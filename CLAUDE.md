# Claude.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **artifactsmmo AI player** project. This project is an AI player used for operating a character in a role-playing game played through an API. This is a python v3.13 project.

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
- `run.sh` - Run application. This command can only be used after all unit tests pass with no errors.

### Utilities
- `ag` - Silver Searcher, a grep alternative
- `jq` - JSON query tool
- `lsd` - an ls alternative

## Architecture

### Core Components

**Core application** (`src/`):
- `main.py` - Application entrypoint

**Controller** (`src/controller/`):
- `actions/` - Action classes with GOAP parameters (used for class defaults only)
- `action_factory.py` - **Dynamic action instantiation from YAML configuration**
- `action_executor.py` - **YAML-driven action execution with composite action support**
- `ai_player_controller.py` - **Main AI controller using metaprogramming architecture**
- `world/` - World state management
- `knowledge/` - Learning and knowledge management

**Game state** (`src/game/`):
- `character/` - Character state
- `map/` - Map state

**Libraries** (`src/lib/`):
- `goap.py` - Goal-oriented Action Planner base library ("GOAP")
- `goap_data.py` - YAML-backed state storage for Goal-oriented Action Planner base library
- `state_loader.py` - **Object-oriented YAML-driven state management with dependency injection**
- `httpstatus.py` - Custom HTTP status codes used by the ArtifactsMMO API
- `log.py` - Logging facilities
- `yaml_data.py` - YAML-backed file storage

**Configuration** (`data/`):
- `action_configurations.yaml` - **YAML-driven action definitions and composite workflows**
- `state_configurations.yaml` - **Object-oriented state class configuration**
- `actions.yaml` - GOAP action configurations for planning
- `world.yaml` - World state persistence
- `knowledge.yaml` - Learning and knowledge persistence

**ArtifactsMMO API Client Library** (`artifactsmmo-api-client/`):
- `artifactsmmo-api-client/` - API Client library files for connecting to the ArtifactsMMO API

### Key Design Patterns

1. **Metaprogramming Architecture**: The system uses YAML-driven metaprogramming for action execution
   - Actions are created dynamically through ActionFactory based on YAML configuration
   - No hardcoded if-elif blocks - all action logic is configuration-driven
   - Supports composite actions and parameter template resolution

2. **Factory Pattern**: ActionFactory creates action instances dynamically from configuration

3. **Strategy Pattern**: ActionExecutor handles different action types (simple, composite, special) 

4. **Dependency Injection**: StateLoader manages object creation with YAML-defined dependencies

5. **GOAP Integration**: Goal-Oriented Action Planning with action class defaults and config overrides

6. **Learning System**: Automatic learning callbacks integrated into metaprogramming execution flow

## Development Notes

- The system uses Python 3.13 with type checking
- The virtualenv must be enabled before running any python commands
- Most command-line utilities have a `-h` or `--help` flag
- **IMPORTANT**: The system uses metaprogramming - actions are NOT created directly but through ActionFactory
- **IMPORTANT**: All new functionality should be added via YAML configuration, not hardcoded logic
- Configuration changes can be hot-reloaded without code changes

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
- **IMPORTANT**: You must maintain as close to 100% test coverage as possible.
- **IMPORTANT**: Use metaprogramming test patterns, not direct action mocking

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

## Debugging and Troubleshooting

### Common Issues

1. **"Missing required parameter" errors**: Check action factory parameter mappings
2. **"Unknown action" errors**: Verify action is registered in `action_configurations.yaml`
3. **Tests bypassing metaprogramming**: Ensure tests use ActionExecutor, not direct action mocking
4. **GOAP integration issues**: Check action class has proper `conditions`, `reactions`, and `weights`

### Debug Commands

- Check available actions: `controller.get_available_actions()`
- Reload configurations: `controller.reload_action_configurations()`
- Verify factory registration: `controller.action_executor.factory.is_action_registered('action_name')`