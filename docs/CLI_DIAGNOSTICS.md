# CLI Diagnostics Documentation

This document provides comprehensive examples and usage patterns for the ArtifactsMMO AI Player CLI diagnostic tools. These commands are essential for troubleshooting GOAP planning, state management, and action execution issues.

## Available Diagnostic Commands

The CLI provides six diagnostic commands for comprehensive system analysis:

1. **`diagnose-state`** - Character state inspection and validation
2. **`diagnose-actions`** - Action analysis and troubleshooting  
3. **`diagnose-plan`** - GOAP planning visualization
4. **`test-planning`** - Planning simulation and testing
5. **`diagnose-weights`** - System configuration diagnostics
6. **`diagnose-cooldowns`** - Cooldown monitoring

## Command Examples

### 1. State Diagnostics (`diagnose-state`)

Analyze character state and validate GameState enum usage:

```bash
# Basic state diagnostics
uv run python -m src.cli.main diagnose-state my_character

# With GameState enum validation
uv run python -m src.cli.main diagnose-state my_character --validate-enum
```

**Sample Output:**
```
=== STATE DIAGNOSTICS: my_character ===

=== API CHARACTER DATA ===
Level: 15
XP: 12500
Gold: 2500
HP: 85/100
Position: (5, 3)
Skin: men1

=== STATE VALIDATION ===
Valid: ✓

=== STATE STATISTICS ===
Character level: 15
Total XP: 12500
Gold: 2500
HP percentage: 85.0%
Total skill levels: 45
Average skill level: 5.6
Progress to max: 33.3%

=== COOLDOWN STATUS ===
On cooldown: False
Remaining seconds: 0
```

### 2. Action Diagnostics (`diagnose-actions`)

Analyze available actions and their properties:

```bash
# List all actions with costs
uv run python -m src.cli.main diagnose-actions --list-all --show-costs

# Character-specific action analysis
uv run python -m src.cli.main diagnose-actions --character my_character --show-preconditions

# Full action analysis with preconditions and effects
uv run python -m src.cli.main diagnose-actions --list-all --show-preconditions --show-costs
```

**Sample Output:**
```
=== ACTION DIAGNOSTICS: my_character ===
Action registry available: True
Total actions analyzed: 15
Executable actions: 8
Cost range: 1 - 5
Action types: Movement(4), Combat(3), Gathering(2), Rest(1)
Registry validation: ✓ Valid

=== INDIVIDUAL ACTIONS (15) ===

[1] Action: move_to_5_5
    Class: MovementAction
    Cost: 1
    Executable: True
    Preconditions:
      cooldown_ready: True
      at_target_location: False
    Effects:
      current_x: 5
      current_y: 5
      at_target_location: True
      cooldown_ready: False
    Validation: preconditions=True, effects=True

[2] Action: fight_chicken
    Class: CombatAction
    Cost: 3
    Executable: False
    Preconditions:
      cooldown_ready: True
      at_monster_location: True
      can_fight: True
    Issues:
      • Precondition not met: at_monster_location = False, required True
```

### 3. Planning Diagnostics (`diagnose-plan`)

Analyze GOAP planning process for specific goals:

```bash
# Basic planning analysis
uv run python -m src.cli.main diagnose-plan my_character "gain xp"

# Verbose planning with step details
uv run python -m src.cli.main diagnose-plan my_character "gain xp" --verbose --show-steps

# Movement goal planning
uv run python -m src.cli.main diagnose-plan my_character --gained-xp true --current-x 5 --current-y 5
```

**Sample Output:**
```
=== PLANNING DIAGNOSTICS: my_character ===
Goal: level=20
Planning system available: True

=== PLANNING ANALYSIS ===
Planning successful: True
Goal reachable: True
Total cost: 45
Planning time: 0.125 seconds

Plan steps (8 actions):
  [1] move_to_chicken_location (cost: 1)
  [2] fight_chicken (cost: 3)
  [3] fight_chicken (cost: 3)
  [4] move_to_bank (cost: 1)
  [5] rest_at_bank (cost: 2)
  [6] move_to_chicken_location (cost: 1)
  [7] fight_chicken (cost: 3)
  [8] level_up (cost: 10)

State Transitions (8):
  Step 1: move_to_chicken_location
  Step 2: fight_chicken
  Step 3: fight_chicken
  Step 4: move_to_bank

=== PERFORMANCE METRICS ===
Planning time: 0.125s
Success: True
Performance class: fast

=== RECOMMENDATIONS (1) ===
  • Plan is efficient - no optimization needed
```

### 4. Planning Simulation (`test-planning`)

Test planning algorithms with mock scenarios:

```bash
# Level progression simulation
uv run python -m src.cli.main test-planning --start-level 1 --goal-level 5 --dry-run

# Custom character and goal testing
uv run python -m src.cli.main test-planning --character my_character --goal "gain_xp"

# Custom state simulation from file
uv run python -m src.cli.main test-planning --mock-state-file tests/fixtures/level_1_state.json

# Performance testing
uv run python -m src.cli.main test-planning --start-level 10 --goal-level 15
```

**Sample Output:**
```
=== Planning Test Results ===
test_time: 2025-07-27T21:45:00.123456
planning_available: True
scenarios_tested: [
  {
    "name": "Level Progression",
    "description": "Increase character level from 1 to 5",
    "success": True,
    "planning_time": 0.089,
    "plan_length": 12,
    "reachable": True,
    "issues": []
  },
  {
    "name": "Gold Accumulation", 
    "description": "Accumulate 1000 gold",
    "success": True,
    "planning_time": 0.156,
    "plan_length": 8,
    "reachable": True,
    "issues": []
  }
]
overall_success: True
performance_summary: {
  "total_scenarios": 3,
  "successful_scenarios": 3,
  "success_rate": 100.0,
  "total_planning_time": 0.267,
  "average_planning_time": 0.089
}
```

### 5. Weight Diagnostics (`diagnose-weights`)

Analyze action weights and GOAP configuration:

```bash
# Basic weight analysis
uv run python -m src.cli.main diagnose-weights

# Detailed cost breakdown
uv run python -m src.cli.main diagnose-weights --show-action-costs
```

**Sample Output:**
```
=== WEIGHT & CONFIGURATION ANALYSIS ===
Configuration valid: ✓

Actions analyzed: 23
Cost range: 1 - 15
Average cost: 4.2

High-cost outliers (2):
  • craft_legendary_item: 15 (x3.6)
  • teleport_action: 12 (x2.9)

Optimization opportunities (3):
  • Large cost variance detected - consider normalizing action costs
  • Very high cost actions detected - may slow down planning
  • Unbalanced action type distribution - some types heavily overrepresented

Recommendations (2):
  • Review 2 high-cost outlier actions
  • Consider 3 optimization opportunities
```

### 6. Cooldown Diagnostics (`diagnose-cooldowns`)

Monitor cooldown management and timing:

```bash
# Basic cooldown status
uv run python -m src.cli.main diagnose-cooldowns my_character

# Continuous monitoring mode
uv run python -m src.cli.main diagnose-cooldowns my_character --monitor
```

**Sample Output:**
```
=== COOLDOWN ANALYSIS: my_character ===
API available: True
Cooldown manager available: True
Character ready: False
Remaining time: 15.3s
Compliance status: on_cooldown
Last action: fight_monster

API cooldown standard: 30s

Monitoring data (1 entries):
  [2025-07-27T21:45:00.123456] active_monitoring
    Ready: False
    Remaining: 15.3s
    Character level: 15
    Character HP: 85
    Character position: (5, 3)

Recommendations (1):
  • Character on cooldown for 15.3s - wait before executing actions
```

## Integration with Development Workflow

### Debugging GOAP Planning Issues

1. **Start with state diagnostics** to ensure character state is valid:
   ```bash
   uv run python -m src.cli.main diagnose-state my_character --validate-enum
   ```

2. **Check action availability** to identify missing preconditions:
   ```bash
   uv run python -m src.cli.main diagnose-actions --character my_character --show-preconditions
   ```

3. **Analyze planning process** for the problematic goal:
   ```bash
   uv run python -m src.cli.main diagnose-plan my_character "gain xp" --verbose --show-steps
   ```

4. **Test with simulations** to isolate issues:
   ```bash
   uv run python -m src.cli.main test-planning --mock-state-file your_test_state.json
   ```

### Performance Optimization Workflow

1. **Analyze action costs** for balance issues:
   ```bash
   uv run python -m src.cli.main diagnose-weights --show-action-costs
   ```

2. **Measure planning performance** for target scenarios:
   ```bash
   uv run python -m src.cli.main diagnose-plan my_character "gain xp" --verbose
   ```

3. **Run performance benchmarks**:
   ```bash
   uv run python -m src.cli.main test-planning --start-level 1 --goal-level 10
   ```

### Production Monitoring

Monitor live character performance with cooldown diagnostics:

```bash
# Check if character is ready for actions
uv run python -m src.cli.main diagnose-cooldowns my_character

# Continuous monitoring during AI player execution
uv run python -m src.cli.main diagnose-cooldowns my_character --monitor
```

## Error Handling and Troubleshooting

### Common Issues and Solutions

**"Action registry not available"**
- The ActionRegistry component isn't initialized
- Solution: Ensure the AI player is properly configured with action registry

**"API client not available"**
- No API connection for real character data
- Solution: Verify TOKEN file exists and contains valid API token

**"Planning diagnostics unavailable"**
- GoalManager component isn't initialized
- Solution: Check that the AI player has been properly set up

**"Goal appears to be unreachable"**
- The specified goal cannot be achieved with available actions
- Solution: Check goal syntax and verify required actions exist

### Debug Mode

For detailed debugging, increase logging level:

```bash
uv run python -m src.cli.main --log-level DEBUG diagnose-plan my_character "gain xp"
```

## Best Practices

1. **Always validate state first** before analyzing planning issues
2. **Use simulation mode** for testing without affecting live characters
3. **Monitor cooldowns** before executing actions to avoid API violations
4. **Check action costs** when optimizing planning performance
5. **Run diagnostics regularly** during development to catch issues early

## Integration with Testing

Include diagnostic commands in your test workflows:

```bash
# Validate state management after character operations
uv run python -m src.cli.main diagnose-state test_character --validate-enum

# Test planning algorithms with known scenarios
uv run python -m src.cli.main test-planning --mock-state-file tests/fixtures/planning_test.json

# Validate action registry after modifications
uv run python -m src.cli.main diagnose-actions --list-all --show-costs
```

These diagnostic tools provide comprehensive visibility into the AI player system, enabling effective troubleshooting, optimization, and monitoring of autonomous character operations.