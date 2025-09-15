"""
Movement Goal

Simple goal for moving to a specific location.
"""

from ..state.character_game_state import CharacterGameState
from ..state.game_state import GameState
from src.game_data.game_data import GameData
from ..types.goap_models import GOAPTargetState
from .base_goal import BaseGoal


class MovementGoal(BaseGoal):
    """Goal for moving to a specific location."""

    def __init__(self, target_x: int, target_y: int):
        """Initialize movement goal with target coordinates.
        
        Parameters:
            target_x: Target X coordinate
            target_y: Target Y coordinate
        """
        self.target_x = target_x
        self.target_y = target_y

    def calculate_weight(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate weight for movement goal.
        
        Movement goals are typically sub-goals, so they have moderate priority.
        """
        # Higher weight if we're far from the target
        distance = abs(character_state.x - self.target_x) + abs(character_state.y - self.target_y)
        distance_factor = min(1.0, distance / 10.0)

        return 5.0 + distance_factor * 2.0  # 5-7 range

    def is_feasible(self, character_state: CharacterGameState, game_data: GameData) -> bool:
        """Check if movement goal is feasible.
        
        Movement is always feasible unless we're already at the target.
        """
        # Not feasible if already at target location
        if character_state.x == self.target_x and character_state.y == self.target_y:
            return False

        return True

    def get_target_state(
        self,
        character_state: CharacterGameState,
        game_data: GameData
    ) -> GOAPTargetState:
        """Return GOAP target state for movement goal.
        
        This is a simple goal that just requires being at the target location.
        """
        # Simple target state - just need to be at the location
        target_states = {
            GameState.CURRENT_X: self.target_x,
            GameState.CURRENT_Y: self.target_y,
        }

        return GOAPTargetState(
            target_states=target_states,
            priority=5,  # Medium priority
            timeout_seconds=60  # 1 minute timeout for movement
        )

    def get_progression_value(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate contribution to character progression.
        
        Movement itself doesn't contribute to progression, but enables other goals.
        """
        return 0.0  # No direct progression value

    def estimate_error_risk(self, character_state: CharacterGameState) -> float:
        """Estimate the risk of errors or failures when pursuing this goal.
        
        Movement has very low risk - the main risk is getting stuck or pathfinding issues.
        """
        return 0.1  # Very low risk

    def generate_sub_goal_requests(
        self,
        character_state: CharacterGameState,
        game_data: GameData
    ) -> list:
        """Generate sub-goal requests for movement dependencies.
        
        Movement goals are leaf goals - they don't have sub-goals.
        """
        return []  # No sub-goals for movement
