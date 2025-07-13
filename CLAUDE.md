# Claude.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **artifactsmmo AI player** project - an AI player for operating a character in a role-playing game through an API. Uses Python 3.13.

## Core Project Principles

1. **Prioritize general-case solutions** over special-case handling
2. **ALWAYS avoid code duplication** - maximize code reuse
3. **NEVER add backward compatibility** - refactor freely for better solutions
4. **NEVER hard-code values or mappings** - use configuration and dynamic discovery
5. **Behavior-based solutions** over hard-coded logic
6. **API responses are authoritative** - the only source for data
7. **Test-driven development** - all changes must have tests and all tests must pass
8. **Business logic goes in actions** - controllers and managers only orchestrate

## Architecture

### Key Design Patterns

1. **Modular Manager Architecture**
   - AIPlayerController: Orchestration only (no business logic)
   - Specialized managers handle specific concerns not suitable for Actions

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
- `goal_templates.yaml` - Goal definitions and selection rules

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

**MANDATORY STANDARDS** (Zero Tolerance):
- **100% code coverage** - no exceptions
- **0 test failures** - all tests must pass
- **0 warnings** - clean test output required  
- **0 skipped tests** - all tests must run

**ALWAYS verify changes with:**
1. Unit tests: `python -m pytest` (must pass 100%)
2. Runtime test: `./run.sh` (minimum 15-30 seconds)
3. Check data persistence in YAML files
4. Verify no test data contaminates production files
5. **Architectural compliance review** - ensure business logic stays in actions

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

## Recent Architectural Improvements

### Goal Manager Refactor (Major Success)

Successfully transformed goal manager from complex business logic container to simple YAML template provider:

**Problem Solved**: "No suitable goal found for current state" error caused by over-complex goal selection logic.

**Solution**: Complete architectural refactor following principle "business logic goes in actions."

**Before vs After**:
- **Code Reduction**: 761 → 127 lines (83% reduction)
- **Business Logic**: Removed ALL character analysis, viability checks, state computation
- **Categories**: Removed hardcoded categories, moved to YAML
- **Selection**: Simplified to priority-based boolean condition checking

**Key Architectural Insights**:
1. **Simplicity wins**: Complex logic was causing failures, simple logic works reliably
2. **Separation of concerns**: Goal manager should only load templates and check boolean flags
3. **Declarative configuration**: All selection logic moved to YAML configuration
4. **Actions handle business logic**: Character viability, crafting requirements, etc.

### Current Goal Manager Architecture

**Role**: Simple YAML-driven goal template provider
- Load goal templates from `config/goal_templates.yaml`
- Load goal selection rules with priorities
- Check simple boolean conditions against state flags
- Return goal templates for GOAP planning
- **NO business logic whatsoever**

**Example Goal Selection**:
```yaml
# In goal_templates.yaml
goal_selection_rules:
  emergency:
    - condition: {'character_status.healthy': false}
      goal: 'get_healthy'
      priority: 100
  progression:
    - condition: {'character_status.healthy': true}
      goal: 'hunt_monsters'
      priority: 70
```

**Simple Goal Selection Pattern**:
```python
def select_goal(self, current_state):
    # Collect all rules with priorities from YAML
    all_rules = []
    for category, rules in self.goal_selection_rules.items():
        for rule in rules:
            all_rules.append({
                'priority': rule.get('priority', 0),
                'goal_name': rule.get('goal'),
                'condition': rule.get('condition', {})
            })
    
    # Sort by priority and check simple boolean conditions
    all_rules.sort(key=lambda x: x['priority'], reverse=True)
    for rule_data in all_rules:
        if self._check_simple_condition(rule_data['condition'], current_state):
            return (rule_data['goal_name'], self.goal_templates[rule_data['goal_name']])
    
    return None
```

### Architectural Compliance Checklist

**✅ DO** (Compliant Patterns):
- Simple boolean condition checking in goal manager
- All business logic in actions
- Declarative YAML configuration
- Priority-based rule iteration
- State flags computed by UnifiedStateContext

**❌ DON'T** (Violation Patterns):
- Character state analysis in goal manager
- Hardcoded categories or selection algorithms
- Complex state computation outside actions
- If-elif blocks for goal selection
- Business logic in controllers or managers

## Common Issues & Solutions

1. **"Missing required parameter"** → Check ActionContext preservation
2. **"Unknown action"** → Verify registration in action_configurations.yaml
3. **Data not persisting** → Check learning callbacks are set
4. **Test data contamination** → Ensure tests use temp directories
5. **Cooldown issues** → Verify character state refresh before detection
6. **Goal parsing errors** → Check compound operators handled first
7. **Action context lost** → Ensure actions use `set_result()`
8. **"No suitable goal found"** → Check boolean flags in state, ensure goal_selection_rules in YAML match state format

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
- Architecture overview: `docs/ARCHITECTURE.md`
- Subgoal patterns and best practices: `docs/SUBGOAL_PATTERNS.md`

## Important Notes

- Python 3.13 with type checking
- Configuration hot-reloadable without code changes
- System uses discovery over hard-coding
- All new features via YAML configuration
- **Maintain exactly 100% test coverage** - no exceptions
- Production data files must stay clean of test data
- **Business logic MUST go in actions** - never in controllers or managers
- Goal manager is architecturally compliant (simple YAML template provider)
- Use boolean flags for state conditions, not complex computations
