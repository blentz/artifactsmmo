"""
Base Goal Abstract Class

This module defines the abstract base class for all enhanced goals in the AI player system.
All specialized goal types must inherit from BaseGoal and implement the required methods
for weighted goal selection, feasibility checking, and GOAP target state generation.
"""

from abc import ABC, abstractmethod

from ..state.character_game_state import CharacterGameState
from ..types.game_data import GameData
from ..types.goap_models import GOAPTargetState


class BaseGoal(ABC):
    """Abstract base class for all intelligent goals in the enhanced goal system.

    This class defines the interface that all specialized goal types must implement
    to participate in weighted goal selection and strategic planning. Each goal
    must be able to calculate its own weight, determine feasibility, generate
    action plans, and assess its progression value.
    """

    @abstractmethod
    def calculate_weight(self, character_state: CharacterGameState, game_data: GameData) -> float:
        """Calculate dynamic weight based on current conditions.

        Parameters:
            character_state: Current character state with all attributes
            game_data: Complete game data from cache manager (monsters, items, maps, etc.)

        Return values:
            Float weight score (0.0 to 10.0) indicating goal priority

        This method implements multi-factor weighted scoring considering:
        - Necessity (40%): Required for progression (HP critical, missing gear, level blocks)
        - Feasibility (30%): Can be accomplished with current resources/state
        - Progression Value (20%): Contributes to reaching level 5 with appropriate gear
        - Stability (10%): Reduces error potential and maintains steady progress
        """
        pass

    @abstractmethod
    def is_feasible(self, character_state: CharacterGameState, game_data: GameData) -> bool:
        """Check if goal can be pursued with current character state.

        Parameters:
            character_state: Current character state with all attributes
            game_data: Complete game data from cache manager

        Return values:
            Boolean indicating whether goal can be reasonably pursued

        This method validates that the goal is achievable given current:
        - Character level, skills, and equipment
        - Available game data (monsters, resources, items)
        - Location accessibility and resource availability
        - No blocking conditions or impossible requirements
        """
        pass

    @abstractmethod
    def get_target_state(
        self,
        character_state: CharacterGameState,
        game_data: GameData
    ) -> GOAPTargetState:
        """Return GOAP target state with type safety.
        
        Parameters:
            character_state: Pydantic model with current character state
            game_data: Pydantic model with available game data
            
        Return values:
            GOAPTargetState: Pydantic model with target state requirements
            
        This method generates a target state that can be achieved using GOAP planning.
        The target state defines the desired conditions that will satisfy this goal,
        allowing the GOAP planner to find the optimal action sequence to reach it.
        """
        pass

    @abstractmethod
    def get_progression_value(self, character_state: CharacterGameState) -> float:
        """Calculate contribution to reaching level 5 with appropriate gear.

        Parameters:
            character_state: Current character state with all attributes

        Return values:
            Float value (0.0 to 1.0) indicating progression contribution

        This method evaluates how much this goal contributes to the primary
        success criteria: reaching level 5 with all equipment slots filled
        with level-appropriate gear (item.level <= 5). Higher values indicate
        goals that directly advance toward this objective.
        """
        pass

    @abstractmethod
    def estimate_error_risk(self, character_state: CharacterGameState) -> float:
        """Estimate the risk of errors or failures when pursuing this goal.

        Parameters:
            character_state: Current character state with all attributes

        Return values:
            Float risk score (0.0 to 1.0) where 0.0 is lowest risk

        This method provides a default implementation that can be overridden
        by specialized goals to provide more accurate risk assessment based
        on goal-specific factors like combat danger, resource scarcity, etc.
        """
        pass

    @abstractmethod
    def generate_sub_goal_requests(
        self,
        character_state: CharacterGameState,
        game_data: GameData
    ) -> list["SubGoalRequest"]:
        """Generate sub-goal requests for runtime dependencies.

        Parameters:
            character_state: Current character state with all attributes
            game_data: Complete game data from cache manager

        Return values:
            List of SubGoalRequest instances for dependencies

        This method identifies runtime dependencies that must be satisfied
        before this goal can be pursued effectively. Sub-goals may include
        movement, healing, equipment changes, or resource acquisition.
        """
        pass

    def validate_game_data(self, game_data: GameData) -> None:
        """Validate that all required game data is present and non-empty.

        Parameters:
            game_data: Game data object to validate

        Raises:
            ValueError: If required game data is missing or invalid

        This method ensures that the goal has access to all necessary game data
        for making intelligent decisions. All enhanced goals must validate their
        data dependencies to prevent hardcoded fallbacks.
        """
        # Use the GameData's built-in validation which includes all the checks
        # for required attributes and data structure integrity
        game_data.validate_required_data()
