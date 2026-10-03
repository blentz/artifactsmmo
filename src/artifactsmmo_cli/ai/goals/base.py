"""Goal ABC for GOAP planning."""

from abc import ABC, abstractmethod

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


class Goal(ABC):
    """Abstract base class for all GOAP goals."""

    preemptive: bool = False
    """When True, this goal may interrupt a committed goal mid-pursuit if it
    outranks the commitment (used for HP-critical safety). Non-preemptive goals
    must wait until the committed goal is satisfied or unplannable, which is what
    stops per-cycle goal thrashing."""

    @abstractmethod
    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        """Urgency score. Higher = more urgent."""

    @abstractmethod
    def is_satisfied(self, state: WorldState) -> bool:
        """Return True when this goal has been achieved."""

    @abstractmethod
    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        """Partial world state the planner targets."""

    def priority(self, state: WorldState, game_data: GameData,
                 history: LearningStore | None = None) -> float:
        """Goal selection weight. Defaults to value()."""
        return self.value(state, game_data, history)

    def relevant_actions(self, actions: list[Action], state: WorldState, game_data: GameData) -> list[Action]:
        """Filter to actions that can contribute to satisfying this goal.

        Default: all actions. Override to reduce the planner's branching factor.
        """
        return actions

    def heuristic(self, state: WorldState, game_data: GameData) -> float:
        """Admissible, CONSISTENT estimate of remaining plan cost (seconds), used
        as the planner's A* heuristic. Default 0.0 — Dijkstra, trivially admissible
        and consistent. An overriding goal MUST keep h ≤ true-remaining AND
        h(s) ≤ cost(s,s') + h(s') (monotone), or the visited-set graph search loses
        optimality (formal/Formal/PlannerAdmissibility.lean)."""
        return 0.0

    @property
    def max_depth(self) -> int:
        """Maximum plan depth the planner will explore for this goal. Override for long-horizon goals."""
        return 15

    def __repr__(self) -> str:
        return self.__class__.__name__
