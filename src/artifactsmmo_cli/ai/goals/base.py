"""Goal ABC for GOAP planning."""

from abc import ABC, abstractmethod

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


class Goal(ABC):
    """Abstract base class for all GOAP goals."""

    @abstractmethod
    def value(self, state: WorldState, game_data: GameData) -> float:
        """Urgency score. Higher = more urgent. Called every cycle."""

    @abstractmethod
    def is_satisfied(self, state: WorldState) -> bool:
        """Return True when this goal has been achieved."""

    @abstractmethod
    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        """Partial world state the planner targets."""

    def priority(self, state: WorldState, game_data: GameData) -> float:
        """Goal selection weight. Defaults to value(). Override when A* heuristic and selection priority diverge."""
        return self.value(state, game_data)

    def relevant_actions(self, actions: list[Action], state: WorldState, game_data: GameData) -> list[Action]:
        """Filter to actions that can contribute to satisfying this goal.

        Default: all actions. Override to reduce the planner's branching factor.
        """
        return actions

    @property
    def max_depth(self) -> int:
        """Maximum plan depth the planner will explore for this goal. Override for long-horizon goals."""
        return 15

    def __repr__(self) -> str:
        return self.__class__.__name__
