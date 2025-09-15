# Incremental Debugging and Implementation Plan for ArtifactsMMO AI Player

## Executive Summary
This plan provides a systematic approach to debug existing issues and incrementally implement the AI player to achieve autonomous gameplay from level 1 to 45. Each phase includes diagnostics, implementation tasks, and validation using sub-agents.

## Current State Assessment

### Working Components
- ✅ CLI framework with diagnostic commands
- ✅ GameState enum for type-safe state management
- ✅ Modular action system with registry
- ✅ API client wrapper with authentication
- ✅ Pydantic models for validation
- ✅ Basic GOAP integration

### Critical Issues
- 🔴 **Crafting Goal Failure**: Attempts impossible single-state targets (see `docs/FIX_CRAFTING_GOAL.md`)
- 🔴 **Sub-goal Architecture**: Needs debugging for recursive execution
- 🔴 **Test Coverage**: Multiple test failures need resolution
- 🟡 **One Class Per File**: Refactoring needed (see `docs/plans/PLAN_one_class_per_file.md`)
- 🟡 **Incomplete Actions**: Many action types not fully implemented

### Missing Features
- ❌ Grand Exchange integration
- ❌ NPC trading system
- ❌ Dynamic event handling
- ❌ Task system integration
- ❌ Elemental combat system
- ❌ Advanced pathfinding
- ❌ Economic intelligence
- ❌ Multi-character coordination

## Phase 1: Diagnostics and Issue Resolution (Days 1-3)

### 1.1 Current State Diagnosis
```bash
# Run comprehensive diagnostics
uv run python -m src.cli.main diagnose-state test_character --validate-enum
uv run python -m src.cli.main diagnose-actions --list-all --show-costs
uv run python -m src.cli.main diagnose-plan test_character "gain xp" --verbose
uv run python -m src.cli.main test-planning --start-level 1 --goal-level 2
```

**Sub-agent Task**: `qa-engineer` - Review diagnostic output and identify all failure points

### 1.2 Fix Critical Crafting Goal Issue
**Reference**: `docs/FIX_CRAFTING_GOAL.md`

**Implementation Tasks**:
1. Convert CraftingGoal to hierarchical sub-goal generator
2. Create MaterialGatheringGoal, WorkshopMovementGoal, CraftExecutionGoal
3. Update GameState enum with material tracking states
4. Enhance GoalManager sub-goal factory
5. Create CraftingAction for final execution

**Sub-agent Task**: `developer` - Implement crafting goal fix following the plan

### 1.3 Fix Test Suite
```bash
# Identify all failing tests
uv run pytest tests/ -v --tb=short > test_failures.txt

# Fix tests incrementally
uv run pytest tests/test_ai_player/ -v
uv run pytest tests/test_game_data/ -v
uv run pytest tests/test_cli/ -v
```

**Sub-agent Task**: `maintenance-support` - Fix all failing tests and achieve 100% pass rate

## Phase 2: Code Organization and Architecture (Days 4-5)

### 2.1 One Class Per File Refactoring
**Reference**: `docs/plans/PLAN_one_class_per_file.md`

**Priority Order**:
1. Split `src/ai_player/state/game_state.py` (GameState, ActionResult, CharacterGameState)
2. Split `src/ai_player/actions/__init__.py` (factories and registry)
3. Split `src/game_data/api_client.py` (TokenConfig, APIClientWrapper, CooldownManager)
4. Split `src/game_data/models.py` (individual model files)

**Sub-agent Task**: `developer` - Execute refactoring plan systematically

### 2.2 Update Import Structure
```python
# Update all imports after refactoring
# Example: src/ai_player/__init__.py
from .state.game_state_enum import GameState
from .state.action_result import ActionResult
from .state.character_game_state import CharacterGameState
```

**Validation**: Run diagnostics after each refactoring phase

## Phase 3: Core Action Implementation (Days 6-10)

### 3.1 Combat System Enhancement
**Goals**: Implement level-appropriate monster targeting with elemental system

**Tasks**:
1. Enhance CombatAction with elemental damage calculations
2. Implement monster selection algorithm (level ± 1)
3. Add retreat logic when HP < 30%
4. Create corruption event handling

**Sub-agent Task**: `developer` - Implement enhanced combat system

### 3.2 Resource Gathering Optimization
**Goals**: Efficient resource collection with skill progression

**Tasks**:
1. Implement tool requirement checking
2. Add resource location caching
3. Create gathering route optimization
4. Implement inventory management

**Sub-agent Task**: `developer` - Implement gathering optimization

### 3.3 Movement and Pathfinding
**Goals**: Efficient pathfinding with obstacle avoidance

**Tasks**:
1. Implement A* pathfinding algorithm
2. Add danger zone avoidance (high-level monsters)
3. Create waypoint system for long journeys
4. Add movement cost optimization

**Sub-agent Task**: `developer` - Implement pathfinding system

## Phase 4: Economic Systems (Days 11-15)

### 4.1 Grand Exchange Integration
**Goals**: Automated trading for profit and resource acquisition

**Tasks**:
1. Create GrandExchangeAction class
2. Implement price monitoring system
3. Add buy/sell decision logic
4. Create profit optimization algorithm

**Sub-agent Task**: `developer` - Implement Grand Exchange system

### 4.2 NPC Trading System
**Goals**: Utilize NPCs for item exchange

**Tasks**:
1. Create NPCTradingAction class
2. Implement NPC location tracking
3. Add trade evaluation logic
4. Create route optimization for trading

**Sub-agent Task**: `developer` - Implement NPC trading

### 4.3 Banking and Inventory Management
**Goals**: Efficient inventory and bank management

**Tasks**:
1. Create BankingAction class
2. Implement inventory optimization algorithm
3. Add automatic banking when inventory full
4. Create item prioritization system

**Sub-agent Task**: `developer` - Implement banking system

## Phase 5: Advanced Goal Management (Days 16-20)

### 5.1 Dynamic Goal Selection
**Goals**: Intelligent goal selection based on game state

**Tasks**:
1. Implement weighted goal scoring (necessity, feasibility, progression, stability)
2. Add emergency goal triggers (low HP, no resources)
3. Create goal chain optimization
4. Implement learning from past performance

**Sub-agent Task**: `developer` - Enhance goal selection system

### 5.2 Task System Integration
**Goals**: Complete game tasks for exclusive rewards

**Tasks**:
1. Create TaskGoal class
2. Implement task requirement parsing
3. Add task prioritization logic
4. Create task completion tracking

**Sub-agent Task**: `developer` - Implement task system

### 5.3 Achievement System
**Goals**: Track and pursue achievements

**Tasks**:
1. Create AchievementTracker class
2. Implement achievement progress monitoring
3. Add achievement-based goal generation
4. Create achievement prioritization

**Sub-agent Task**: `developer` - Implement achievement system

## Phase 6: Skill Progression System (Days 21-25)

### 6.1 Crafting Skills Development
**Goals**: Systematic skill progression for all 8 skills

**Skills to Implement**:
- Mining, Woodcutting, Fishing
- Weaponcrafting, Gearcrafting, Jewelrycrafting
- Cooking, Alchemy

**Tasks**:
1. Create skill-specific goal classes
2. Implement skill leveling strategies
3. Add recipe unlocking logic
4. Create skill priority balancing

**Sub-agent Task**: `developer` - Implement skill progression

### 6.2 Equipment Optimization
**Goals**: Automatic equipment upgrades

**Tasks**:
1. Create EquipmentEvaluator class
2. Implement stat comparison logic
3. Add crafting vs buying decisions
4. Create equipment upgrade planning

**Sub-agent Task**: `developer` - Implement equipment system

## Phase 7: Integration Testing (Days 26-28)

### 7.1 End-to-End Testing
```bash
# Create test character
uv run python -m src.cli.main create-character ai_test_e2e men1

# Run AI for extended period
uv run python -m src.cli.main run-character ai_test_e2e --max-hours 24

# Monitor progress
uv run python -m src.cli.main status-character ai_test_e2e --monitor
```

**Sub-agent Task**: `qa-engineer` - Validate all systems work together

### 7.2 Performance Testing
**Metrics to Track**:
- Actions per minute
- XP gain rate
- Gold accumulation rate
- Skill progression rates
- Goal completion times
- Error recovery rate

**Sub-agent Task**: `qa-engineer` - Measure and optimize performance

### 7.3 Stress Testing
**Scenarios**:
- API rate limit handling
- Cooldown management under load
- Error recovery from API failures
- Memory usage over long runs
- State consistency after errors

**Sub-agent Task**: `qa-engineer` - Stress test all systems

## Phase 8: Advanced Features (Days 29-35)

### 8.1 Multi-Character Coordination
**Goals**: Coordinate multiple characters for efficiency

**Tasks**:
1. Create CharacterCoordinator class
2. Implement resource sharing logic
3. Add character specialization
4. Create team goal planning

**Sub-agent Task**: `developer` - Implement multi-character system

### 8.2 Event Response System
**Goals**: React to dynamic world events

**Tasks**:
1. Create EventMonitor class
2. Implement event detection logic
3. Add event prioritization
4. Create event response strategies

**Sub-agent Task**: `developer` - Implement event system

### 8.3 Learning and Adaptation
**Goals**: Learn from gameplay and improve strategies

**Tasks**:
1. Create PerformanceAnalyzer class
2. Implement strategy evaluation
3. Add parameter tuning
4. Create adaptive goal weights

**Sub-agent Task**: `developer` - Implement learning system

## Phase 9: Optimization and Polish (Days 36-40)

### 9.1 Performance Optimization
**Areas to Optimize**:
- GOAP planning efficiency
- API call batching
- Cache utilization
- Memory management
- Logging performance

**Sub-agent Task**: `devops-engineer` - Optimize system performance

### 9.2 Error Handling Enhancement
**Improvements**:
- Comprehensive error recovery
- Graceful degradation
- Error reporting and analytics
- Automatic retry strategies
- State recovery mechanisms

**Sub-agent Task**: `maintenance-support` - Enhance error handling

### 9.3 Documentation Update
**Documents to Update**:
- Architecture documentation
- API integration guide
- Configuration reference
- Troubleshooting guide
- Performance tuning guide

**Sub-agent Task**: `developer` - Update all documentation

## Phase 10: Final Validation (Days 41-45)

### 10.1 Level 45 Achievement Test
```bash
# Create fresh character
uv run python -m src.cli.main create-character ai_final_test men1

# Run until level 45
uv run python -m src.cli.main run-character ai_final_test --target-level 45

# Generate performance report
uv run python -m src.cli.main report-character ai_final_test --detailed
```

**Success Criteria**:
- Character reaches level 45
- All skills developed appropriately
- Efficient resource utilization
- Minimal errors and downtime
- Optimal goal completion

**Sub-agent Task**: `qa-engineer` - Validate level 45 achievement

### 10.2 System Metrics
**Final Metrics to Achieve**:
- 100% test coverage
- 0 critical bugs
- < 1% error rate
- > 95% uptime
- Consistent progression rate

### 10.3 Release Preparation
**Tasks**:
1. Final code review
2. Performance benchmarks
3. Documentation review
4. Configuration templates
5. Deployment guide

**Sub-agent Task**: `devops-engineer` - Prepare for release

## Validation Checkpoints

### After Each Phase:
1. Run diagnostic commands
2. Execute test suite
3. Check performance metrics
4. Review error logs
5. Validate state consistency

### Daily Validation:
```bash
# Morning check
uv run python -m src.cli.main diagnose-state ai_test --validate-enum
uv run python -m src.cli.main diagnose-actions --list-all

# Evening check
uv run python -m src.cli.main test-planning --start-level 1 --goal-level 45
uv run pytest tests/ -v --tb=short
```

## Risk Mitigation

### High-Risk Areas:
1. **API Rate Limiting**: Implement exponential backoff and request queuing
2. **State Corruption**: Add state validation and recovery mechanisms
3. **Memory Leaks**: Implement proper cleanup and resource management
4. **Infinite Loops**: Add timeout and circuit breaker patterns
5. **Data Loss**: Implement regular state persistence

### Mitigation Strategies:
- Incremental development with validation
- Comprehensive error handling
- Regular state backups
- Performance monitoring
- Automated testing at each phase

## Success Metrics

### Phase Completion Criteria:
- All tasks completed
- Tests passing (100%)
- No critical bugs
- Performance targets met
- Documentation updated

### Overall Success:
- AI reaches level 45 autonomously
- All 8 skills developed
- Efficient resource management
- Stable long-term operation
- Comprehensive error recovery

## Sub-Agent Utilization Summary

### Throughout Implementation:
- **developer**: Core feature implementation
- **qa-engineer**: Testing and validation
- **maintenance-support**: Bug fixes and error handling
- **devops-engineer**: Performance and deployment
- **system-architect**: Architecture decisions
- **requirements-analyst**: Requirement validation

### Coordination:
- Use `general` agent for cross-cutting concerns
- Regular sync points between phases
- Continuous integration of sub-agent outputs

## Timeline Summary

- **Phase 1-2**: Foundation (Days 1-5)
- **Phase 3-4**: Core Systems (Days 6-15)
- **Phase 5-6**: Advanced Features (Days 16-25)
- **Phase 7**: Integration Testing (Days 26-28)
- **Phase 8**: Advanced Capabilities (Days 29-35)
- **Phase 9**: Optimization (Days 36-40)
- **Phase 10**: Final Validation (Days 41-45)

## Next Steps

1. Begin with Phase 1.1 diagnostics immediately
2. Use sub-agents for specialized tasks
3. Validate after each implementation
4. Document issues and solutions
5. Iterate based on findings

This plan provides a clear path from the current state to a fully functional AI player capable of autonomous gameplay to level 45.