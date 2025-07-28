# Plan: One Class Per File Refactoring

## Overview
Refactor the codebase to follow the "one class per file" convention for better code organization and maintainability.

## Priority Classification

### High Priority (Core Business Logic)
These files contain multiple classes that are core to the application:

1. **`src/ai_player/goal_manager.py`** (2 classes)
   - `CooldownAwarePlanner`
   - `GoalManager`
   - **Action**: Split into `cooldown_aware_planner.py` and `goal_manager.py`

2. **`src/ai_player/state/game_state.py`** (3 classes)
   - `GameState` (enum)
   - `ActionResult`
   - `CharacterGameState`
   - **Action**: Split into `game_state.py`, `action_result.py`, `character_game_state.py`

3. **`src/ai_player/actions/__init__.py`** (3 classes)
   - `ActionFactory`
   - `ActionRegistry`
   - `ParameterizedActionFactory`
   - **Action**: Split into separate files, update `__init__.py` to re-export

4. **`src/ai_player/actions/movement_action.py`** (2 classes)
   - `MovementAction`
   - `MovementActionFactory`
   - **Action**: Split into `movement_action.py` and `movement_action_factory.py`

5. **`src/game_data/api_client.py`** (3 classes)
   - `TokenConfig`
   - `APIClientWrapper`
   - `CooldownManager`
   - **Action**: Split into `token_config.py`, `api_client_wrapper.py`, `cooldown_manager.py`

6. **`src/game_data/models.py`** (6 classes)
   - Multiple Pydantic models
   - **Action**: Split each model into its own file

### Medium Priority (Complex Modules)
These files have many classes but are more self-contained:

7. **`src/ai_player/pathfinding.py`** (8 classes)
   - **Action**: Split into logical groups (nodes, algorithms, services, config)

8. **`src/ai_player/inventory_optimizer.py`** (12 classes)
   - **Action**: Split into logical groups (enums, models, optimizers, managers)

9. **`src/ai_player/economic_intelligence.py`** (12 classes)
   - **Action**: Split into logical groups (enums, models, analyzers, strategies)

10. **`src/ai_player/task_manager.py`** (10 classes)
    - **Action**: Split into logical groups (enums, models, managers, optimizers)

### Low Priority (Library/Model Files)
These are less critical but should be addressed for consistency:

11. **`src/lib/goap.py`** (3 classes)
12. **`src/lib/throttled_transport.py`** (2 classes)
13. **`src/ai_player/models/*.py`** (Multiple model files with 2-4 classes each)

## Implementation Strategy

### Phase 1: Core State Management (High Impact)
1. **`src/ai_player/state/game_state.py`**
   - Create `src/ai_player/state/game_state_enum.py` for `GameState`
   - Create `src/ai_player/state/action_result.py` for `ActionResult`
   - Create `src/ai_player/state/character_game_state.py` for `CharacterGameState`
   - Update imports throughout codebase

### Phase 2: Action System (High Impact)
2. **`src/ai_player/actions/__init__.py`**
   - Create `src/ai_player/actions/action_factory.py`
   - Create `src/ai_player/actions/action_registry.py`
   - Create `src/ai_player/actions/parameterized_action_factory.py`
   - Update `__init__.py` to re-export all classes

3. **`src/ai_player/actions/movement_action.py`**
   - Split into `movement_action.py` and `movement_action_factory.py`

### Phase 3: Goal Management (High Impact)
4. **`src/ai_player/goal_manager.py`**
   - Create `src/ai_player/cooldown_aware_planner.py`
   - Keep `GoalManager` in `goal_manager.py`

### Phase 4: API Layer (High Impact)
5. **`src/game_data/api_client.py`**
   - Create `src/game_data/token_config.py`
   - Create `src/game_data/api_client_wrapper.py`
   - Create `src/game_data/cooldown_manager.py`

6. **`src/game_data/models.py`**
   - Split each model into its own file
   - Create descriptive filenames (e.g., `cooldown_info.py`, `game_item.py`)

### Phase 5: Complex Modules (Medium Impact)
7. **Large multi-class modules** - Split into logical groups:
   - `pathfinding.py` → multiple files by functionality
   - `inventory_optimizer.py` → multiple files by responsibility
   - `economic_intelligence.py` → multiple files by component
   - `task_manager.py` → multiple files by component

## File Naming Conventions

- Use snake_case for filenames
- Make filenames descriptive of the single class they contain
- For factories, use `{class_name}_factory.py`
- For enums, use `{domain}_enum.py` or keep descriptive name
- For managers, use `{domain}_manager.py`

## Import Update Strategy

1. **Update `__init__.py` files** to re-export classes from new locations
2. **Use relative imports** within packages
3. **Update external imports** systematically
4. **Test imports** after each phase

## Testing Strategy

1. **Run diagnostic commands** after each phase to ensure functionality
2. **Test import statements** in Python REPL
3. **Run existing test suite** to catch breaking changes
4. **Update test imports** as needed

## Risk Mitigation

1. **Work in phases** to isolate potential issues
2. **Test thoroughly** after each file split
3. **Keep git commits atomic** for easy rollback
4. **Update imports systematically** to avoid missing references

## Success Criteria

- Each Python file contains only one class definition
- All imports work correctly
- Diagnostic commands continue to function
- Test suite passes
- Code organization is improved and more maintainable