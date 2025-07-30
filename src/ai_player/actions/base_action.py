"""
Base Action Class for GOAP System

This module defines the abstract base class that all GOAP actions must implement.
It enforces strict GameState enum usage for all state references and provides
a standardized interface for action execution.

The BaseAction class ensures consistency across all action implementations
and integrates seamlessly with the GOAP planning system while maintaining
type safety through the GameState enum.
"""

from abc import ABC, abstractmethod
from typing import Any

from ..state.game_state import ActionResult, GameState
from ..state.character_game_state import CharacterGameState


class BaseAction(ABC):
    """Abstract base class for all GOAP actions.

    All actions must implement this interface and use GameState enum
    for all state references to ensure type safety and consistency.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique action identifier for GOAP system"""
        pass

    @property
    @abstractmethod
    def cost(self) -> int:
        """GOAP planning cost for this action"""
        pass

    @abstractmethod
    def get_preconditions(self) -> dict[GameState, Any]:
        """Required state conditions using GameState enum keys"""
        pass

    @abstractmethod
    def get_effects(self) -> dict[GameState, Any]:
        """State changes after execution using GameState enum keys"""
        pass

    @abstractmethod
    async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
        """Execute action via API and return result with state changes"""
        pass

    def can_execute(self, current_state: CharacterGameState) -> bool:
        """Check if action preconditions are met in current state.

        Parameters:
            current_state: CharacterGameState instance with current character state

        Return values:
            Boolean indicating whether all preconditions are satisfied

        This method validates that the current game state satisfies all the
        preconditions required for this action to be executed, enabling the
        GOAP planner to determine action feasibility.
        """
        preconditions = self.get_preconditions()
        for state_key, required_value in preconditions.items():
            current_value = current_state.get(state_key)

            # Handle missing state keys
            if current_value is None:
                return False

            # Use appropriate comparison based on state type
            if not self._satisfies_precondition(state_key, current_value, required_value):
                return False
        return True

    def _satisfies_precondition(self, state_key: GameState, current_value: Any, required_value: Any) -> bool:
        """Check if a current value satisfies the required value for a specific state key.

        Parameters:
            state_key: The GameState enum key being checked
            current_value: The current value for this state
            required_value: The required value from preconditions

        Return values:
            Boolean indicating whether the current value satisfies the requirement

        This method implements context-aware comparison logic based on the semantic
        meaning of different GameState properties.
        """
        # For numeric states that represent minimums (HP, levels, quantities, etc.)
        # the current value should be >= the required value
        minimum_comparison_states = {
            GameState.HP_CURRENT, GameState.CHARACTER_LEVEL, GameState.CHARACTER_XP,
            GameState.CHARACTER_GOLD, GameState.MINING_LEVEL, GameState.MINING_XP,
            GameState.WOODCUTTING_LEVEL, GameState.WOODCUTTING_XP, GameState.FISHING_LEVEL,
            GameState.FISHING_XP, GameState.WEAPONCRAFTING_LEVEL, GameState.WEAPONCRAFTING_XP,
            GameState.GEARCRAFTING_LEVEL, GameState.GEARCRAFTING_XP, GameState.JEWELRYCRAFTING_LEVEL,
            GameState.JEWELRYCRAFTING_XP, GameState.COOKING_LEVEL, GameState.COOKING_XP,
            GameState.ALCHEMY_LEVEL, GameState.ALCHEMY_XP, GameState.INVENTORY_SPACE_AVAILABLE,
            GameState.BANK_SPACE_AVAILABLE, GameState.BANK_GOLD, GameState.TASK_PROGRESS,
            GameState.PORTFOLIO_VALUE, GameState.ITEM_QUANTITY
        }

        if state_key in minimum_comparison_states:
            # For these states, current value should be >= required value
            try:
                current_float = float(current_value)
                required_float = float(required_value)
                return current_float >= required_float
            except (ValueError, TypeError):
                # Fallback to equality comparison for non-numeric values
                comparison_result = current_value == required_value
                return bool(comparison_result)

        # For all other states (booleans, exact matches, strings), use equality
        comparison_result = current_value == required_value
        return bool(comparison_result)

    def validate_preconditions(self) -> bool:
        """Validate that all preconditions use valid GameState enum keys.

        Parameters:
            None (operates on self)

        Return values:
            Boolean indicating whether all precondition keys are valid GameState enums

        This method verifies that the action's preconditions dictionary only uses
        valid GameState enum keys, ensuring type safety and preventing runtime
        errors in the GOAP planning system.
        """
        preconditions = self.get_preconditions()
        if not isinstance(preconditions, dict):
            return False
        return all(isinstance(key, GameState) for key in preconditions.keys())

    def validate_effects(self) -> bool:
        """Validate that all effects use valid GameState enum keys.

        Parameters:
            None (operates on self)

        Return values:
            Boolean indicating whether all effect keys are valid GameState enums

        This method verifies that the action's effects dictionary only uses
        valid GameState enum keys, ensuring type safety and enabling proper
        state updates after action execution in the GOAP system.
        """
        effects = self.get_effects()
        if not isinstance(effects, dict):
            return False
        return all(isinstance(key, GameState) for key in effects.keys())
