"""
Rest Goal

Goal for recovering HP to a target threshold.
"""

from ..state.character_game_state import CharacterGameState
from ..state.game_state import GameState
from ..types.game_data import GameData
from ..types.goap_models import GOAPTargetState
from .base_goal import BaseGoal


class RestGoal(BaseGoal):
    """Goal for recovering HP to a specific threshold."""

    def __init__(self, min_hp_percentage: float = 0.8):
        """Initialize rest goal with minimum HP percentage.
        
        Parameters:
            min_hp_percentage: Minimum HP percentage to achieve (0.0-1.0)
        """
        self.min_hp_percentage = max(0.0, min(1.0, min_hp_percentage))

    def calculate_weight(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate weight for rest goal.
        
        Higher weight when HP is critically low.
        """
        if character_state.max_hp == 0:
            return 0.0

        current_hp_percentage = character_state.hp / character_state.max_hp
        hp_deficit = self.min_hp_percentage - current_hp_percentage

        if hp_deficit <= 0:
            return 0.0  # No rest needed

        # Critical HP gets very high priority
        if current_hp_percentage < 0.3:
            return 10.0  # Maximum priority
        elif current_hp_percentage < 0.5:
            return 8.0   # High priority
        else:
            return 5.0 + hp_deficit * 3.0  # Moderate priority based on deficit

    def is_feasible(self, character_state: CharacterGameState, game_data: GameData) -> bool:
        """Check if rest goal is feasible.
        
        Rest is feasible if HP is below target and we're not already at max HP.
        """
        if character_state.max_hp == 0:
            return False

        current_hp_percentage = character_state.hp / character_state.max_hp

        # Not feasible if already at or above target
        if current_hp_percentage >= self.min_hp_percentage:
            return False

        # Not feasible if already at max HP
        if character_state.hp >= character_state.max_hp:
            return False

        return True

    def get_target_state(
        self,
        character_state: CharacterGameState,
        game_data: GameData
    ) -> GOAPTargetState:
        """Generate GOAP target state for rest goal.
        
        Returns:
            GOAPTargetState with HP recovery requirements
        """
        target_hp = int(character_state.max_hp * self.min_hp_percentage)

        return GOAPTargetState(
            target_states={
                GameState.HP_CURRENT: target_hp,
                GameState.COOLDOWN_READY: True
            },
            priority=8,  # High priority for survival
            timeout_seconds=300  # 5 minutes should be enough for rest
        )

    def is_completed(self, character_state: CharacterGameState, game_data: GameData) -> bool:
        """Check if rest goal is completed.
        
        Parameters:
            character_state: Current character state
            game_data: Current game data
            
        Returns:
            bool: True if HP is at or above target threshold
        """
        if character_state.max_hp == 0:
            return True  # Edge case

        current_hp_percentage = character_state.hp / character_state.max_hp
        return current_hp_percentage >= self.min_hp_percentage

    def get_progression_value(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate progression value for this goal.
        
        Parameters:
            character_state: Current character state
            game_data: Current game data
            
        Returns:
            float: Progression value (0.0 = no progress, 1.0 = completed)
        """
        if character_state.max_hp == 0:
            return 1.0

        current_hp_percentage = character_state.hp / character_state.max_hp

        if current_hp_percentage >= self.min_hp_percentage:
            return 1.0  # Completed

        # Calculate how much progress we've made toward the target
        progress = current_hp_percentage / self.min_hp_percentage
        return max(0.0, min(1.0, progress))

    def __str__(self) -> str:
        """String representation of the rest goal."""
        return f"RestGoal(min_hp_percentage={self.min_hp_percentage:.1%})"

    def __repr__(self) -> str:
        """Detailed string representation of the rest goal."""
        return f"RestGoal(min_hp_percentage={self.min_hp_percentage})"
