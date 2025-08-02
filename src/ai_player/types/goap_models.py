"""
GOAP Type-Safe Models

This module provides type-safe Pydantic models for the unified sub-goal architecture,
eliminating dict and Any types throughout the GOAP planning system.
"""


from pydantic import BaseModel, Field

from ..actions.base_action import BaseAction
from ..state.character_game_state import CharacterGameState
from ..state.game_state import GameState
from .game_data import GameData


class GOAPTargetState(BaseModel):
    """Type-safe replacement for dict[GameState, Any]"""
    target_states: dict[GameState, bool | int | float | str] = Field(
        default_factory=dict,
        description="Target state values indexed by GameState enum"
    )
    priority: int = Field(default=5, ge=1, le=10, description="Goal priority")
    timeout_seconds: int | None = Field(default=None, description="Max execution time")

    def to_goap_dict(self) -> dict[str, bool | int | float | str]:
        """Convert to GOAP-compatible string-keyed dictionary."""
        return {state.value: value for state, value in self.target_states.items()}

    def __bool__(self) -> bool:
        """Return True if this target state has actual targets to plan for."""
        return bool(self.target_states)

    @classmethod
    def from_goap_dict(cls, goap_dict: dict[str, bool | int | float | str], priority: int = 5) -> 'GOAPTargetState':
        """Create from GOAP string-keyed dictionary."""
        target_states = {}
        for key, value in goap_dict.items():
            try:
                state_enum = GameState(key)
                target_states[state_enum] = value
            except ValueError:
                raise ValueError(f"Invalid GameState key: {key}")

        return cls(target_states=target_states, priority=priority)


class GOAPAction(BaseModel):
    """Type-safe replacement for dict-based action representation"""
    name: str = Field(description="Action name")
    action_type: str = Field(description="Action type for factory")
    parameters: dict[str, bool | int | float | str] = Field(
        default_factory=dict,
        description="Action parameters"
    )
    cost: int = Field(default=1, ge=0, description="GOAP cost")
    estimated_duration: float = Field(default=1.0, ge=0, description="Estimated seconds")

    def to_dict(self) -> dict[str, str | dict | int | float]:
        """Convert to dictionary for legacy GOAP compatibility."""
        return {
            "name": self.name,
            "type": self.action_type,
            "parameters": self.parameters,
            "cost": self.cost,
            "duration": self.estimated_duration
        }


class GOAPActionPlan(BaseModel):
    """Type-safe replacement for list[dict[str, Any]]"""
    actions: list[GOAPAction] = Field(default_factory=list, description="Ordered action sequence")
    total_cost: int = Field(default=0, ge=0, description="Total plan cost")
    estimated_duration: float = Field(default=0.0, ge=0, description="Estimated total seconds")
    plan_id: str = Field(description="Unique plan identifier for tracking")

    @property
    def is_empty(self) -> bool:
        """Check if plan has no actions."""
        return len(self.actions) == 0

    def to_legacy_plan(self) -> list[dict[str, str | dict | int | float]]:
        """Convert to legacy GOAP plan format."""
        return [action.to_dict() for action in self.actions]

    def to_base_actions(
        self,
        action_registry,
        current_state: CharacterGameState,
        game_data: GameData
    ) -> list[BaseAction]:
        """Convert GOAPActions to BaseAction instances using ActionRegistry.
        
        Parameters:
            action_registry: ActionRegistry instance for action lookup
            current_state: Current character state for action generation
            game_data: Game data for parameterized actions
            
        Return values:
            List of BaseAction instances ready for execution
            
        Raises:
            ValueError: If any action cannot be found in registry
        """

        base_actions = []
        for goap_action in self.actions:
            # Get action by name from registry
            action = action_registry.get_action_by_name(
                goap_action.name,
                current_state,
                game_data
            )
            if not action:
                raise ValueError(f"Action '{goap_action.name}' not found in registry")
            base_actions.append(action)
        return base_actions


class SubGoalExecutionResult(BaseModel):
    """Result of recursive sub-goal execution"""
    success: bool = Field(description="Whether sub-goal chain completed successfully")
    depth_reached: int = Field(ge=0, description="Maximum recursion depth reached")
    actions_executed: int = Field(ge=0, description="Total actions executed in chain")
    execution_time: float = Field(ge=0, description="Total execution time in seconds")
    final_state: CharacterGameState | None = Field(default=None, description="Final character state")
    error_message: str | None = Field(default=None, description="Error details if failed")

    @property
    def failed(self) -> bool:
        """Check if sub-goal execution failed."""
        return not self.success

    @property
    def has_error(self) -> bool:
        """Check if execution resulted in an error."""
        return self.error_message is not None


class GoalFactoryContext(BaseModel):
    """Context for goal factory creation"""
    character_state: CharacterGameState = Field(description="Current character state")
    game_data: GameData = Field(description="Available game data")
    parent_goal_type: str | None = Field(default=None, description="Parent goal that requested sub-goal")
    recursion_depth: int = Field(default=0, ge=0, description="Current recursion depth")
    max_depth: int = Field(default=10, ge=1, description="Maximum allowed depth")

    @property
    def at_max_depth(self) -> bool:
        """Check if at maximum recursion depth."""
        return self.recursion_depth >= self.max_depth

    @property
    def can_recurse(self) -> bool:
        """Check if recursion is still allowed."""
        return self.recursion_depth < self.max_depth

    def increment_depth(self) -> 'GoalFactoryContext':
        """Create new context with incremented depth."""
        return self.model_copy(update={'recursion_depth': self.recursion_depth + 1})
