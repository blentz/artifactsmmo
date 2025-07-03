# Bug Prevention Patterns

This document contains detailed bug patterns that have been identified and fixed in the artifactsmmo AI player project.

## Runtime Stability Issues

### 1. Cooldown Handling

**Problem**: Actions continuing despite active cooldowns causing 499 API errors
```
🕐 Cooldown detected before {action} - skipping action
```

**Prevention**:
- **ALWAYS** check for cooldowns before non-wait actions: `_is_character_on_cooldown()`
- **ALLOW** rest and wait actions during cooldowns: `action_name not in ['wait', 'rest']`
- **EXTEND** wait duration for long cooldowns: maximum 65 seconds (not 30)
- **REFRESH** character state before cooldown detection to get current status

### 2. Combat Results Recording

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

### 3. Action Parameter Passing

**Problem**: "Missing required parameter X for action Y" in action sequences
```
Missing required parameter x for action move
```

**Prevention**:
- **PRESERVE** action context between plan iterations
- **USE** ActionContext to pass information between actions
- **AVOID** hard-coded parameter mappings
- **MAINTAIN** data flow through ActionContext's `set_result()` method

### 4. HTTP Request Optimization

**Problem**: Excessive API requests during monster search
```
⚠️ Cache miss for (10,5) - requesting from API
```

**Prevention**:
- **IMPLEMENT** timestamp-based caching: 5-minute cache duration
- **CHECK** cache freshness before API requests: `is_cache_fresh(x, y)`
- **LIMIT** HTTP requests to once per grid square per hunt iteration
- **STORE** last_scanned timestamp with location data

### 5. Test Data Contamination

**Problem**: Unit tests writing mock data to production YAML files
```python
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

### 6. Goal Condition Parsing Errors

**Problem**: Goal selection conditions with compound operators causing parsing failures
```
Goal condition check failed: could not convert string to float: '=5'
Goal condition check failed: could not convert string to float: '=2'
```

**Root Cause**: The `_check_goal_condition` method in `goal_manager.py` only handles simple operators (`<`, `>`) and fails when parsing compound operators (`<=`, `>=`).

**Prevention**:
- **ORDER** compound operators before simple ones in parsing logic
- **HANDLE** `<=` and `>=` before `<` and `>` in condition evaluation
- **EXTRACT** numeric values correctly: `"<=5"` → `float("5")` not `float("=5")`
- **TEST** goal condition parsing with various operator combinations

**Fix Pattern**:
```python
# CORRECT - Handle compound operators first
if isinstance(expected_value, str) and expected_value.startswith('<='):
    threshold = float(expected_value[2:])  # Extract from position 2
    return actual_value <= threshold
elif isinstance(expected_value, str) and expected_value.startswith('>='):
    threshold = float(expected_value[2:])  # Extract from position 2
    return actual_value >= threshold
elif isinstance(expected_value, str) and expected_value.startswith('<'):
    threshold = float(expected_value[1:])  # Extract from position 1
    return actual_value < threshold
# ... continue with other operators
```

### 7. Combat Failure Loops and Goal Duplication

**Problem**: Character gets stuck in combat failure loops when `combat_not_viable=true` due to:
1. Duplicate emergency equipment upgrade goals causing application termination
2. Goal state generation using comparison operators instead of numeric values

**Symptoms**:
```
Error executing goal template 'upgrade_weapon': invalid literal for int() with base 10: '=3'
🚨 Selected emergency goal 'emergency_equipment_upgrade' (priority 98) - TERMINATES
```

**Prevention**:
- **AVOID** duplicate goal definitions with similar functionality
- **CONSOLIDATE** equipment upgrade logic into single goal hierarchy with emergency priorities
- **USE** numeric target states, not comparison operators in GOAP goal templates
- **VERIFY** emergency goals can actually execute without terminating the application

**Goal Design Patterns**:
```yaml
# CORRECT - Numeric target state for GOAP
upgrade_weapon:
  target_state:
    character_level: 3  # Numeric value, not ">=3"
    has_better_weapon: true
    character_safe: true

# CORRECT - Emergency priority without duplication
goal_selection_rules:
  emergency:
    - condition:
        combat_not_viable: true
        character_level: "<=5"  # Condition parsing (OK here)
      goal: "upgrade_weapon"  # Reuse existing goal
      priority: 96  # High priority for emergency
```

**Combat Failure Recovery**:
- **DETECT** combat viability using win rate analysis in `state_engine.py`
- **ESCALATE** to equipment upgrade goals when combat consistently fails
- **BOOTSTRAP** low-level characters through multi-step equipment progression
- **VERIFY** goal execution proceeds without parsing errors or termination

### 8. Action Context Preservation

**Problem**: Information from one action (like weapon selection) not being available to subsequent actions
```
Knowledge-based planning failed: No target item specified for analysis
```

**Root Cause**: Actions were not properly using ActionContext to preserve information for subsequent actions.

**Prevention**:
- **USE** ActionContext's `set_result()` method to preserve data
- **AVOID** hard-coded key mappings for preserved data
- **ENSURE** actions include all necessary keys for compatibility
- **PRESERVE** entire action context between plan iterations

**Fix Pattern**:
```python
# In action that generates data
if hasattr(self, '_context') and self._context:
    self._context.set_result('target_item', selected_item)
    self._context.set_result('item_code', selected_item)

# In controller - avoid hard-coded preservation
if not hasattr(self, 'action_context'):
    self.action_context = {}
# Context persists automatically between actions
```

## Validation Requirements

**MANDATORY** verification steps before claiming any fix is complete:

### 1. Unit Test Verification
```bash
python -m unittest  # Must pass 100%
```
- **ALL** tests must pass without failures
- **NEW** tests must be created for fixed bugs to prevent regressions
- **METHOD** signatures updated if parameters change (e.g., fight_data addition)

### 2. Runtime Validation
```bash
./run.sh  # Run for at least 30 seconds
```
- **MONITOR** for expected behavior (combat, movement, learning)
- **CHECK** log messages indicate fixes are working:
  - `🕐 Cooldown detected` for cooldown handling
  - `⚔️ Combat vs {monster}: {result}` for combat logging
  - `🧠 Combat learning` for combat results recording
  - `💰 XP gained from {monster}: {amount}` for detailed combat data

### 3. Data Persistence Verification
```bash
# Check that data files are being updated with real game data
ls -la data/*.yaml
cat data/knowledge.yaml | grep -A5 "combat_results"
```
- **VERIFY** `total_combats` increases during gameplay
- **CONFIRM** `combat_results` arrays contain combat records
- **CHECK** no test data in production files

## Emergency Debugging

**When fixes don't work as expected:**

1. **Check character state refresh**: Logs should show "Updated character cooldown expiration"
2. **Monitor action execution flow**: Look for "Action {name} executed successfully" vs "Action {name} failed"
3. **Trace learning callbacks**: Search logs for "🔍 Processing attack learning" and fight data extraction
4. **Verify action context preservation**: Check that data persists between actions
5. **Confirm cache behavior**: Look for cache hit/miss messages during map exploration

**Common fix validation failures:**
- Tests pass but runtime fails → Check action parameter mappings and context passing
- Runtime works but data not persisting → Verify learning callbacks and save() calls
- Cooldowns still causing issues → Check character state refresh timing
- Combat data missing specific fields → Verify fight_data extraction and conversion
- Goal condition parsing fails → Check compound operator handling in `_check_goal_condition`
- Application terminates on goal selection → Check for duplicate emergency goals and consolidate
- GOAP execution fails on numeric parsing → Verify goal target_state uses numeric values, not operators
- Combat failure loops persist → Check combat viability detection and goal escalation priorities
- Action context not preserved → Verify actions use `set_result()` and context persists between iterations