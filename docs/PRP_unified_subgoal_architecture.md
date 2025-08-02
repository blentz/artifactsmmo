# Product Requirements Prompt: Unified Sub-Goal Architecture

## Executive Summary

Create a clean, unified architecture for sub-goal integration that eliminates converters and ensures the entire system uses the same facilities. The current sub-goal system is disconnected from GOAP planner - sub-goal requests need to become regular Goal instances through a factory pattern, with only ActionExecutor and GoalManager understanding "sub-goals" while the rest of the system sees only "goals".

## Problem Statement

### Current Architectural Issues
- **Sub-goal disconnect**: SubGoalRequest objects exist independently from the GOAP planning system
- **Converter complexity**: Current approach requires bridges between SubGoalRequest and GOAP target states
- **System fragmentation**: Sub-goals don't use the same facilities as regular goals
- **Scope leakage**: Multiple components need to understand sub-goal concepts

### User Requirements
Based on user feedback:
1. **No converters needed** - SubGoalRequest should become Goal instances directly
2. **Same facilities** - Sub-goals must use identical interfaces as regular goals
3. **Limited scope** - Only Action and GoalManager should understand "sub-goals"
4. **Refactor existing** - Enhance current ActionExecutor instead of creating new components

## Solution Overview

### Unified Sub-Goal Factory Architecture

Transform the disconnected sub-goal system into a unified architecture where:

1. **SubGoalRequest → Goal Factory → Goal Instance** (no converters)
2. **Same GOAP Flow**: Sub-goals use identical `get_target_state()` and GOAP planning
3. **Recursive Execution**: ActionExecutor handles sub-goals with depth-limited recursion
4. **Transparent Integration**: Rest of system only sees Goal objects, never SubGoalRequest

```python
# Clean Architecture Flow
SubGoalRequest → GoalManager.create_goal_from_sub_request() → BaseGoal → get_target_state() → GOAP Planning → Action Execution → Recursive Retry
```

## Research Context

### GOAP Best Practices (2024)
From comprehensive web research:

- **Hierarchical GOAP**: "Break down complex goals into smaller, manageable sub-goals. This approach simplifies planning and execution" ([Excalibur.js GOAP Guide](https://excaliburjs.com/blog/goal-oriented-action-planning/))
- **Dynamic Goal Selection**: "Allow goals to change priority based on the game's context for more adaptive AI" 
- **Factory Pattern Integration**: "This factory also configures the algorithm by injecting appropriate implementations... provides a foundation for a very flexible AI system"

### Factory Pattern Implementation
Following established Python patterns:

- **Modular Design**: "Factory patterns help create reusable components and allow engineers to define the end goal or what they want to achieve" ([Dagster Factory Patterns](https://dagster.io/blog/python-factory-patterns))
- **Decoupling Benefits**: "Goap won't have any dependency on the pathfinding algorithm and can use different types of search algorithms without any changes"

### Recursive Planning with Depth Limits
From Python recursion research:

- **Depth Management**: "Using this along with getrecursionlimit() can help you track exactly how close you are to the limit" ([GeeksforGeeks Python Recursion](https://www.geeksforgeeks.org/python/python-handling-recursion-limit/))
- **Base Case Requirements**: Proper recursive implementations need clear termination conditions

## Precise Method Signatures (Type-Safe Implementation)

### Required Pydantic Models (Eliminate dict and Any types)

```python
# src/ai_player/types/goap_models.py
from pydantic import BaseModel, Field
from typing import Optional, Union
from ..state.game_state import GameState
from ..actions.base_action import BaseAction

class GOAPTargetState(BaseModel):
    """Type-safe replacement for dict[GameState, Any]"""
    target_states: dict[GameState, Union[bool, int, float, str]] = Field(
        default_factory=dict,
        description="Target state values indexed by GameState enum"
    )
    priority: int = Field(default=5, ge=1, le=10, description="Goal priority")
    timeout_seconds: Optional[int] = Field(default=None, description="Max execution time")

class GOAPAction(BaseModel):
    """Type-safe replacement for dict-based action representation"""
    name: str = Field(description="Action name")
    action_type: str = Field(description="Action type for factory")
    parameters: dict[str, Union[bool, int, float, str]] = Field(
        default_factory=dict,
        description="Action parameters"
    )
    cost: int = Field(default=1, ge=0, description="GOAP cost")
    estimated_duration: float = Field(default=1.0, ge=0, description="Estimated seconds")

class GOAPActionPlan(BaseModel):
    """Type-safe replacement for list[dict[str, Any]]"""
    actions: list[GOAPAction] = Field(default_factory=list, description="Ordered action sequence")
    total_cost: int = Field(default=0, ge=0, description="Total plan cost")
    estimated_duration: float = Field(default=0.0, ge=0, description="Estimated total seconds")
    plan_id: str = Field(description="Unique plan identifier for tracking")

class SubGoalExecutionResult(BaseModel):
    """Result of recursive sub-goal execution"""
    success: bool = Field(description="Whether sub-goal chain completed successfully")
    depth_reached: int = Field(ge=0, description="Maximum recursion depth reached")
    actions_executed: int = Field(ge=0, description="Total actions executed in chain")
    execution_time: float = Field(ge=0, description="Total execution time in seconds")
    final_state: Optional['CharacterGameState'] = Field(default=None, description="Final character state")
    error_message: Optional[str] = Field(default=None, description="Error details if failed")

class GoalFactoryContext(BaseModel):
    """Context for goal factory creation"""
    character_state: 'CharacterGameState' = Field(description="Current character state")
    game_data: 'GameData' = Field(description="Available game data")
    parent_goal_type: Optional[str] = Field(default=None, description="Parent goal that requested sub-goal")
    recursion_depth: int = Field(default=0, ge=0, description="Current recursion depth")
    max_depth: int = Field(default=10, ge=1, description="Maximum allowed depth")
```

### Core Method Signatures (Zero Any types, Maximum Pydantic)

```python
# GoalManager - Enhanced with type safety
class GoalManager:
    def create_goal_from_sub_request(
        self,
        sub_goal_request: SubGoalRequest,
        context: GoalFactoryContext
    ) -> BaseGoal:
        """Factory method to convert SubGoalRequest to appropriate Goal instance.
        
        Args:
            sub_goal_request: Pydantic model with sub-goal requirements
            context: Pydantic model with factory context (character state, game data, depth)
            
        Returns:
            BaseGoal: Concrete goal instance (CombatGoal, MovementGoal, etc.)
            
        Raises:
            ValueError: If sub_goal_request.goal_type is not supported
            ValidationError: If context validation fails
        """

    async def plan_to_target_state(
        self,
        current_state: CharacterGameState,
        target_state: GOAPTargetState
    ) -> GOAPActionPlan:
        """Plan actions to reach target state using GOAP.
        
        Args:
            current_state: Pydantic model with current character state
            target_state: Pydantic model with target state requirements
            
        Returns:
            GOAPActionPlan: Pydantic model with ordered action sequence
            
        Raises:
            PlanningError: If no valid plan can be found
        """

    async def select_next_goal(
        self,
        current_state: CharacterGameState
    ) -> GOAPTargetState:
        """Select next achievable goal using enhanced goal system.
        
        Args:
            current_state: Pydantic model with current character state
            
        Returns:
            GOAPTargetState: Pydantic model with target state for GOAP planning
            
        Raises:
            NoValidGoalError: If no feasible goals are available
        """

# ActionExecutor - Enhanced with recursive sub-goal support
class ActionExecutor:
    def __init__(
        self,
        api_client: 'APIClientWrapper',
        cooldown_manager: 'CooldownManager',
        cache_manager: 'CacheManager',
        goal_manager: GoalManager,
        max_subgoal_depth: int = 10,
        subgoal_timeout_seconds: int = 300
    ):
        """Initialize ActionExecutor with type-safe configuration."""

    async def execute_action_with_subgoals(
        self,
        action: BaseAction,
        character_name: str,
        current_state: CharacterGameState,
        depth: int = 0
    ) -> ActionResult:
        """Execute action with recursive sub-goal handling.
        
        Args:
            action: BaseAction instance to execute
            character_name: Character identifier
            current_state: Pydantic model with current character state
            depth: Current recursion depth (0 = top level)
            
        Returns:
            ActionResult: Pydantic model with execution outcome
            
        Raises:
            MaxDepthExceededError: If depth > max_subgoal_depth
            SubGoalExecutionError: If sub-goal chain fails
        """

    async def execute_plan_recursive(
        self,
        plan: GOAPActionPlan,
        character_name: str,
        depth: int = 0
    ) -> SubGoalExecutionResult:
        """Execute plan with recursive sub-goal support.
        
        Args:
            plan: Pydantic model with ordered action sequence
            character_name: Character identifier  
            depth: Current recursion depth
            
        Returns:
            SubGoalExecutionResult: Pydantic model with execution results
            
        Raises:
            MaxDepthExceededError: If depth > max_subgoal_depth
            ExecutionTimeoutError: If execution exceeds timeout
        """

    async def execute_plan(
        self,
        plan: list[BaseAction],  # Keep existing signature for compatibility
        character_name: str
    ) -> bool:
        """Execute plan with BaseAction list (backwards compatibility)."""

# Enhanced Goals Interface - Type-safe target states
class BaseGoal(ABC):
    @abstractmethod
    def get_target_state(
        self,
        character_state: CharacterGameState,
        game_data: GameData
    ) -> GOAPTargetState:
        """Return GOAP target state with type safety.
        
        Args:
            character_state: Pydantic model with current character state
            game_data: Pydantic model with available game data
            
        Returns:
            GOAPTargetState: Pydantic model with target state requirements
            
        Raises:
            InfeasibleGoalError: If goal cannot be achieved with current state
        """

    # Keep existing methods with enhanced type safety
    @abstractmethod
    def calculate_weight(
        self,
        character_state: CharacterGameState,
        game_data: GameData
    ) -> float:
        """Calculate dynamic weight with type-safe inputs."""

    @abstractmethod
    def is_feasible(
        self,
        character_state: CharacterGameState,
        game_data: GameData
    ) -> bool:
        """Check feasibility with type-safe inputs."""

# AI Player Integration - Type-safe orchestration  
class AIPlayer:
    async def plan_actions(
        self,
        current_state: CharacterGameState,
        target_state: GOAPTargetState
    ) -> GOAPActionPlan:
        """Generate action sequence using GOAP planner with type safety.
        
        Args:
            current_state: Pydantic model with current character state
            target_state: Pydantic model with target state requirements
            
        Returns:
            GOAPActionPlan: Pydantic model with ordered action sequence
        """

    async def execute_plan(
        self,
        plan: GOAPActionPlan  # Enhanced type safety
    ) -> bool:
        """Execute planned action sequence with recursive sub-goal support."""
```

### Exception Classes (Type-Safe Error Handling)

```python
# src/ai_player/exceptions.py
class SubGoalExecutionError(Exception):
    """Raised when sub-goal execution fails"""
    def __init__(self, depth: int, sub_goal_type: str, message: str):
        self.depth = depth
        self.sub_goal_type = sub_goal_type
        super().__init__(f"Sub-goal '{sub_goal_type}' failed at depth {depth}: {message}")

class MaxDepthExceededError(SubGoalExecutionError):
    """Raised when max recursion depth is exceeded"""
    def __init__(self, max_depth: int):
        super().__init__(max_depth, "depth_limit", f"Maximum recursion depth {max_depth} exceeded")

class NoValidGoalError(Exception):
    """Raised when no feasible goals are available"""
    pass

class InfeasibleGoalError(Exception):
    """Raised when a goal cannot be achieved with current state"""
    pass

class StateConsistencyError(Exception):
    """Raised when state consistency validation fails during recursive execution"""
    def __init__(self, depth: int, message: str):
        self.depth = depth
        super().__init__(f"State consistency error at depth {depth}: {message}")
```

## Technical Requirements

### 1. StateManager Enhancements for Recursive Sub-Goal Support

The existing StateManager has strong foundational capabilities but requires specific enhancements for unified sub-goal architecture state consistency:

```python
# src/ai_player/state/state_manager.py - New methods to add
class StateManager:
    async def validate_goap_target_state(
        self, 
        target_state: GOAPTargetState
    ) -> bool:
        """Validate GOAPTargetState Pydantic model against current game state and rules.
        
        Args:
            target_state: Pydantic model with target state requirements
            
        Returns:
            bool: True if target state is valid and achievable
            
        Raises:
            StateConsistencyError: If target state validation fails
        """
        try:
            # Convert GOAPTargetState to internal GameState dict format
            target_dict = {
                GameState(key): value 
                for key, value in target_state.target_states.items()
            }
            
            # Use existing validation logic with converted state
            return self._validate_state_rules(target_dict)
            
        except (ValueError, KeyError) as e:
            raise StateConsistencyError(0, f"GOAPTargetState validation failed: {e}")
    
    async def refresh_state_for_parent_action(
        self, 
        depth: int
    ) -> CharacterGameState:
        """Force refresh state after sub-goal completion for parent action retry.
        
        Args:
            depth: Current recursion depth for error context
            
        Returns:
            CharacterGameState: Fresh state for parent action execution
            
        Raises:
            StateConsistencyError: If state refresh fails
        """
        try:
            # Force fresh API sync to get authoritative state
            fresh_state = await self.force_refresh()
            
            # Validate state consistency after refresh
            if not await self.validate_state_consistency():
                raise StateConsistencyError(depth, "State inconsistency detected after refresh")
            
            return fresh_state
            
        except (ConnectionError, TimeoutError) as e:
            raise StateConsistencyError(depth, f"Failed to refresh state: {e}")
    
    def create_goal_factory_context(
        self, 
        parent_goal_type: str, 
        recursion_depth: int,
        max_depth: int = 10
    ) -> GoalFactoryContext:
        """Create context for sub-goal factory with current state and depth tracking.
        
        Args:
            parent_goal_type: Type of goal that requested the sub-goal
            recursion_depth: Current recursion depth
            max_depth: Maximum allowed recursion depth
            
        Returns:
            GoalFactoryContext: Pydantic model with factory context
            
        Raises:
            StateConsistencyError: If cached state is not available
        """
        if self._cached_state is None:
            raise StateConsistencyError(recursion_depth, "No cached state available for factory context")
        
        # Get game data from cache manager if available
        game_data = None
        if self._cache_manager:
            game_data = self._cache_manager.get_game_data()
        
        return GoalFactoryContext(
            character_state=self._cached_state,
            game_data=game_data,
            parent_goal_type=parent_goal_type,
            recursion_depth=recursion_depth,
            max_depth=max_depth
        )
    
    async def validate_recursive_state_transition(
        self,
        pre_state: CharacterGameState,
        post_state: CharacterGameState,
        depth: int
    ) -> bool:
        """Validate state transition during recursive sub-goal execution.
        
        Args:
            pre_state: State before sub-goal execution
            post_state: State after sub-goal execution  
            depth: Recursion depth for error context
            
        Returns:
            bool: True if state transition is valid
            
        Raises:
            StateConsistencyError: If state transition validation fails
        """
        try:
            # Check that critical state values changed appropriately
            if post_state.hp > pre_state.max_hp:
                raise StateConsistencyError(depth, "HP cannot exceed max HP")
            
            if post_state.level < pre_state.level:
                raise StateConsistencyError(depth, "Character level cannot decrease")
            
            # Validate position changes are reasonable (not teleporting)
            distance = abs(post_state.x - pre_state.x) + abs(post_state.y - pre_state.y)
            if distance > 10:  # Reasonable movement limit
                raise StateConsistencyError(depth, f"Unreasonable position change: {distance} tiles")
            
            return True
            
        except StateConsistencyError:
            raise
```

### 2. Enhanced Goals Interface Change (Breaking Change)

```python
# src/ai_player/goals/base_goal.py
class BaseGoal(ABC):
    @abstractmethod
    def get_target_state(self, character_state: CharacterGameState, game_data: GameData) -> GOAPTargetState:
        """Return GOAP target state instead of BaseAction list"""
        pass
    
    # Remove get_plan_steps() entirely - breaking change
    # Keep all other methods: calculate_weight, is_feasible, etc.
```

### 3. Goal Factory Pattern in GoalManager

Following existing `ActionFactory` pattern from `src/ai_player/actions/action_factory.py`:

```python
# src/ai_player/goal_manager.py
class GoalManager:
    def create_goal_from_sub_request(
        self, 
        sub_goal_request: SubGoalRequest, 
        context: GoalFactoryContext
    ) -> BaseGoal:
        """Factory method to convert SubGoalRequest to appropriate Goal instance.
        
        Args:
            sub_goal_request: Pydantic model with sub-goal requirements
            context: GoalFactoryContext with character state, game data, and depth info
            
        Returns:
            BaseGoal: Concrete goal instance that uses GOAP facilities
            
        Raises:
            ValueError: If sub_goal_request.goal_type is not supported
            MaxDepthExceededError: If recursion depth exceeds maximum
        """
        # Check recursion depth limit
        if context.recursion_depth >= context.max_depth:
            raise MaxDepthExceededError(context.max_depth)
        
        # Validate context has required data
        if context.character_state is None:
            raise ValueError("GoalFactoryContext must include character_state")
        
        if sub_goal_request.goal_type == "move_to_location":
            return MovementGoal(
                target_x=sub_goal_request.parameters["target_x"],
                target_y=sub_goal_request.parameters["target_y"]
            )
        elif sub_goal_request.goal_type == "reach_hp_threshold":
            return RestGoal(
                min_hp_percentage=sub_goal_request.parameters["min_hp_percentage"]
            )
        elif sub_goal_request.goal_type == "obtain_item":
            return GatheringGoal(
                item_code=sub_goal_request.parameters["item_code"],
                quantity=sub_goal_request.parameters.get("quantity", 1)
            )
        elif sub_goal_request.goal_type == "equip_item_type":
            return EquipmentGoal(
                item_type=sub_goal_request.parameters["item_type"],
                max_level=sub_goal_request.parameters["max_level"]
            )
        else:
            raise ValueError(f"Unknown sub-goal type: {sub_goal_request.goal_type}")
```

### 4. Refactored ActionExecutor with Recursive Sub-Goals

Enhance existing `src/ai_player/action_executor.py` (no new executor):

```python
class ActionExecutor:
    def __init__(
        self, 
        api_client, 
        cooldown_manager, 
        cache_manager, 
        goal_manager, 
        state_manager: StateManager,
        max_subgoal_depth: int = 10
    ):
        # Existing initialization plus:
        self.goal_manager = goal_manager
        self.state_manager = state_manager
        self.max_subgoal_depth = max_subgoal_depth
    
    async def execute_action_with_subgoals(
        self, 
        action: BaseAction, 
        character_name: str, 
        current_state: CharacterGameState, 
        depth: int = 0
    ) -> ActionResult:
        """Execute action with recursive sub-goal handling and state consistency validation."""
        
        # Depth limit protection
        if depth > self.max_subgoal_depth:
            raise MaxDepthExceededError(self.max_subgoal_depth)
        
        # Capture pre-execution state for validation
        pre_execution_state = current_state.copy()
        
        # Execute action using existing execute_action method
        result = await self.execute_action(action, character_name, current_state)
        
        # Handle sub-goal requests recursively
        if not result.success and result.sub_goal_requests:
            for sub_goal_request in result.sub_goal_requests:
                try:
                    # Create factory context using StateManager
                    context = self.state_manager.create_goal_factory_context(
                        parent_goal_type=type(action).__name__,
                        recursion_depth=depth + 1,
                        max_depth=self.max_subgoal_depth
                    )
                    
                    # Use GoalManager factory to create Goal instance
                    sub_goal = self.goal_manager.create_goal_from_sub_request(
                        sub_goal_request, context
                    )
                    
                    # Get target state using same facility as regular goals
                    target_state = sub_goal.get_target_state(context.character_state, context.game_data)
                    
                    # Use GOAP planning (same facility as regular goals) - validation happens inside
                    sub_plan = await self.goal_manager.plan_to_target_state(
                        context.character_state, target_state
                    )
                    
                    if sub_plan.actions:
                        # Execute sub-plan recursively
                        sub_result = await self.execute_plan_recursive(
                            sub_plan, character_name, depth + 1
                        )
                        
                        if sub_result.success:
                            # Force refresh state after sub-goal completion
                            refreshed_state = await self.state_manager.refresh_state_for_parent_action(depth)
                            
                            # Validate state transition
                            await self.state_manager.validate_recursive_state_transition(
                                pre_execution_state, refreshed_state, depth
                            )
                            
                            # Retry parent action with refreshed state
                            return await self.execute_action_with_subgoals(
                                action, character_name, refreshed_state, depth
                            )
                
                except (StateConsistencyError, MaxDepthExceededError, NoValidGoalError) as e:
                    # Log error and continue with remaining sub-goal requests
                    self.logger.warning(f"Sub-goal execution failed: {e}")
                    continue
        
        return result
    
    async def execute_plan_recursive(
        self, 
        plan: GOAPActionPlan, 
        character_name: str, 
        depth: int
    ) -> SubGoalExecutionResult:
        """Execute plan with recursive sub-goal support and state consistency tracking."""
        start_time = time.time()
        actions_executed = 0
        
        try:
            # Get initial state for result tracking
            initial_state = await self.state_manager.get_current_state()
            
            for goap_action in plan.actions:
                # Convert GOAPAction to BaseAction instance
                action = await self.get_action_by_name(goap_action.name, initial_state)
                if not action:
                    return SubGoalExecutionResult(
                        success=False,
                        depth_reached=depth,
                        actions_executed=actions_executed,
                        execution_time=time.time() - start_time,
                        error_message=f"Action '{goap_action.name}' not found"
                    )
                
                # Get current state for this action
                current_state = await self.state_manager.get_current_state()
                
                # Execute with recursive sub-goal handling
                result = await self.execute_action_with_subgoals(
                    action, character_name, current_state, depth
                )
                
                actions_executed += 1
                
                if not result.success:
                    return SubGoalExecutionResult(
                        success=False,
                        depth_reached=depth,
                        actions_executed=actions_executed,
                        execution_time=time.time() - start_time,
                        error_message=result.message
                    )
            
            # Get final state after all actions
            final_state = await self.state_manager.get_current_state()
            
            return SubGoalExecutionResult(
                success=True,
                depth_reached=depth,
                actions_executed=actions_executed,
                execution_time=time.time() - start_time,
                final_state=final_state
            )
            
        except (MaxDepthExceededError, StateConsistencyError, NoValidGoalError) as e:
            return SubGoalExecutionResult(
                success=False,
                depth_reached=depth,
                actions_executed=actions_executed,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )
```

### 5. GoalManager GOAP Integration with State Consistency

```python
# Additional methods in GoalManager
async def plan_to_target_state(
    self, 
    current_state: CharacterGameState, 
    target_state: GOAPTargetState
) -> GOAPActionPlan:
    """Plan actions to reach target state using GOAP with state validation."""
    # Validate target state before planning
    await self.state_manager.validate_goap_target_state(target_state)
    
    # Convert to GOAP format
    goap_current = current_state.to_goap_state()
    goap_target = {state.value: value for state, value in target_state.target_states.items()}
    
    # Use existing GOAP planner
    planner = await self._create_goap_planner(goap_current, goap_target)
    raw_plan = planner.calculate() if planner else []
    
    if not raw_plan:
        raise NoValidGoalError("GOAP planner could not find valid action sequence")
    
    # Convert to type-safe GOAPActionPlan
    goap_actions = []
    total_cost = 0
    estimated_duration = 0.0
    
    for action_dict in raw_plan:
        goap_action = GOAPAction(
            name=action_dict["name"],
            action_type=action_dict.get("type", action_dict["name"]),
            parameters=action_dict.get("parameters", {}),
            cost=action_dict.get("cost", 1),
            estimated_duration=action_dict.get("duration", 1.0)
        )
        goap_actions.append(goap_action)
        total_cost += goap_action.cost
        estimated_duration += goap_action.estimated_duration
    
    return GOAPActionPlan(
        actions=goap_actions,
        total_cost=total_cost,
        estimated_duration=estimated_duration,
        plan_id=f"plan_{current_state.name}_{time.time()}"
    )
```

## Implementation Blueprint

### Phase 1: Enhanced Goals Interface Update (Breaking Changes)

**Files to Modify:**
- `src/ai_player/goals/base_goal.py` - Update interface
- `src/ai_player/goals/combat_goal.py` - Convert to target states  
- `src/ai_player/goals/crafting_goal.py` - Convert to target states
- `src/ai_player/goals/gathering_goal.py` - Convert to target states
- `src/ai_player/goals/equipment_goal.py` - Convert to target states

**Implementation:**
1. Change `get_plan_steps()` → `get_target_state()` in BaseGoal
2. Update all goal implementations to return `dict[GameState, Any]` 
3. Remove all BaseAction imports from goal files
4. Preserve all intelligence: calculate_weight, is_feasible, etc.

### Phase 2: Goal Factory in GoalManager

**Files to Modify:**
- `src/ai_player/goal_manager.py` - Add factory method

**Implementation:**
1. Add `create_goal_from_sub_request()` method following ActionFactory pattern
2. Handle all SubGoalRequest types: move_to_location, reach_hp_threshold, obtain_item, equip_item_type
3. Add `plan_to_target_state()` method for sub-goal planning
4. Ensure proper error handling for unknown sub-goal types

### Phase 3: ActionExecutor Refactoring

**Files to Modify:**
- `src/ai_player/action_executor.py` - Add recursive sub-goal support

**Implementation:**
1. Add `max_subgoal_depth` configuration parameter
2. Add `execute_action_with_subgoals()` with depth tracking
3. Add `execute_plan_recursive()` method
4. Integrate with GoalManager factory
5. Implement state refresh after sub-goal completion

### Phase 4: Integration and Configuration

**Files to Modify:**
- `src/ai_player/ai_player.py` - Use refactored ActionExecutor
- `config/ai_player.yaml` - Add max_subgoal_depth configuration

**Implementation:**
1. Update AI player to use `execute_action_with_subgoals()`
2. Add configuration support for max depth (default 10)
3. Add diagnostic logging for sub-goal depth analysis
4. Verify action effects (GAINED_EXP: True)

## Critical Context Files

### Existing Patterns to Follow
- **ActionFactory Pattern**: `src/ai_player/actions/action_factory.py` - Abstract factory interface
- **Current ActionExecutor**: `src/ai_player/action_executor.py` - Comprehensive execution with error handling
- **SubGoalRequest Model**: `src/ai_player/goals/sub_goal_request.py` - Well-defined with factory methods
- **Current GoalManager**: `src/ai_player/goal_manager.py` - Has active_sub_goals tracking
- **Enhanced Goals**: `src/ai_player/goals/base_goal.py` and implementations

### External Resources
- **GOAP Best Practices**: https://excaliburjs.com/blog/goal-oriented-action-planning/
- **Factory Pattern Implementation**: https://realpython.com/factory-method-python/
- **Python Recursion Management**: https://www.geeksforgeeks.org/python/python-handling-recursion-limit/
- **Hierarchical Planning**: https://medium.com/@vedantchaudhari/goal-oriented-action-planning-34035ed40d0b

## Configuration Requirements

```yaml
# config/ai_player.yaml
planning:
  max_subgoal_depth: 10  # Tunable via diagnostics
  enable_recursive_subgoals: true
  subgoal_timeout_seconds: 300
  
diagnostics:
  track_subgoal_depth: true
  log_subgoal_chains: true
```

## Validation Gates

All validation commands must pass for implementation acceptance:

```bash
# Code Quality (zero warnings/errors required)
uv run ruff check --fix src/
uv run mypy src/

# Test Coverage Requirements (MANDATORY)
# - 100% coverage for ALL CHANGED CODE (new/modified files)
# - 90% coverage for ENTIRE CODEBASE 
# - 0 test failures, 0 errors, 0 skipped tests
# - 0 new warnings
uv run pytest tests/ -v --tb=short --cov=src --cov-report=term-missing --cov-fail-under=90

# Verify 100% coverage for changed files specifically
uv run pytest tests/ --cov=src/ai_player/goal_manager.py --cov=src/ai_player/action_executor.py --cov-report=term-missing --cov-fail-under=100

# Integration Tests (verify recursive sub-goal execution)
uv run pytest tests/test_ai_player/test_recursive_subgoals.py -v

# Architecture Validation (ensure no converters, unified interfaces)
uv run pytest tests/test_architecture/test_unified_subgoals.py -v
```

## Error Handling Strategy

### Recursive Depth Protection
```python
if depth > self.max_subgoal_depth:
    return ActionResult(success=False, message="Max depth exceeded")
```

### State Consistency
```python
# Always refresh state after sub-goal completion
refreshed_state = await self.get_current_character_state(character_name)
```

### Sub-Goal Factory Validation
```python
if sub_goal_request.goal_type not in SUPPORTED_SUBGOAL_TYPES:
    raise ValueError(f"Unknown sub-goal type: {sub_goal_request.goal_type}")
```

## Testing Strategy

### Coverage Requirements (MANDATORY)
- **100% Test Coverage**: ALL changed/new code must have complete test coverage
- **90% Codebase Coverage**: Entire codebase must maintain 90% coverage minimum
- **Zero Tolerance**: 0 test failures, 0 errors, 0 skipped tests, 0 new warnings
- **Coverage Verification**: Use `--cov-fail-under` flags to enforce requirements

### Unit Tests Required (100% Coverage)
- **Goal Factory Tests**: Verify SubGoalRequest → Goal conversion for all types
  - Test all sub-goal types: move_to_location, reach_hp_threshold, obtain_item, equip_item_type
  - Test error handling for unknown sub-goal types
  - Test parameter validation and edge cases
- **Recursive Execution Tests**: Test depth limits, error handling, state refresh
  - Test recursive depth protection (max_subgoal_depth exceeded)
  - Test successful sub-goal completion and parent action retry
  - Test state refresh mechanisms after sub-goal completion
- **Interface Consistency Tests**: Ensure sub-goals use same facilities as regular goals
  - Verify sub-goals call get_target_state() method
  - Verify sub-goals use identical GOAP planning pipeline
  - Test that no special handling exists for sub-goals beyond factory creation
- **Configuration Tests**: Verify max_subgoal_depth parameter handling
  - Test configuration loading and validation
  - Test runtime depth limit enforcement
  - Test diagnostic logging and depth tracking

### Integration Tests Required (100% Coverage)
- **End-to-End Sub-Goal Chains**: Test movement → combat → healing chains
  - Test multi-level recursive sub-goal execution
  - Verify call stack unwinding and state consistency
  - Test timeout and error propagation through chain
- **GOAP Integration Tests**: Verify sub-goals use identical GOAP planning
  - Test that sub-goals generate valid GOAP target states
  - Verify action sequences are planned identically for sub-goals and regular goals
  - Test GOAP planner integration with factory-created goals
- **State Consistency Tests**: Verify state refresh after sub-goal completion
  - Test character state synchronization after sub-goal success
  - Verify parent action preconditions are met after state refresh
  - Test concurrent state changes during sub-goal execution
- **Error Recovery Tests**: Test depth limit exceeded, invalid sub-goal types
  - Test graceful degradation when max depth exceeded
  - Test error handling for malformed SubGoalRequest objects
  - Test recovery from failed sub-goal execution

### Test File Requirements
All test files must be created/updated to achieve 100% coverage:
- `tests/test_ai_player/test_goal_manager.py` - Goal factory tests
- `tests/test_ai_player/test_action_executor.py` - Recursive execution tests  
- `tests/test_ai_player/test_recursive_subgoals.py` - Integration tests
- `tests/test_architecture/test_unified_subgoals.py` - Architecture validation
- `tests/test_config/test_subgoal_configuration.py` - Configuration tests

## Confidence Score: 9/10

This PRP provides comprehensive context for one-pass implementation success:

✅ **Complete Architecture Design**: Clean factory pattern following existing codebase patterns  
✅ **External Research Integration**: GOAP best practices, factory patterns, recursive planning  
✅ **Existing Codebase Analysis**: ActionFactory pattern, current ActionExecutor, SubGoalRequest model  
✅ **User Requirements Alignment**: No converters, same facilities, limited scope, refactor existing  
✅ **Implementation Blueprint**: Step-by-step tasks with code examples and file references  
✅ **Validation Strategy**: Comprehensive testing with 100% coverage for changes, 90% codebase coverage, zero tolerance for failures  
✅ **Configuration Support**: Tunable parameters and diagnostic capabilities  

**Risk Mitigation**: The only risk factor is the complexity of recursive sub-goal execution, but the comprehensive error handling, depth limits, and state management strategies address this effectively.

**Success Enablers**: 
- Leverages existing ActionFactory pattern from codebase
- Follows established GOAP integration patterns  
- Uses @sentient-agi-reasoning for complex architectural decisions
- **Rigorous Testing Requirements**: 100% coverage for changes, 90% codebase coverage, zero tolerance policy
- Breaking changes are acceptable per user requirements

**Quality Assurance**: The comprehensive testing requirements ensure bulletproof implementation:
- **100% Coverage Mandate**: Every line of changed code must be tested
- **Zero Tolerance Policy**: 0 failures, 0 errors, 0 skipped tests, 0 new warnings
- **Coverage Verification**: Automated enforcement using `--cov-fail-under` flags
- **Comprehensive Test Suite**: Unit tests, integration tests, architecture validation

The agent implementing this PRP should use @sentient-agi-reasoning for complex architectural decisions while maintaining strict adherence to the unified architecture requirements. No converters, no special handling - everything is a Goal using the same facilities.