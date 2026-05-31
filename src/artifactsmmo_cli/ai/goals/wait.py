"""WaitGoal: last-resort fallback goal so StrategyArbiter never returns
(None, [], []).

When every other discretionary goal is unplannable (e.g. items task accepted,
no winnable monster, empty history, no other firing means), this goal still
provides a firing candidate: a single WaitAction. The bot spends the cycle
waiting (no API call) instead of stalling forever on "No plan found".

The goal is never satisfied — there is no world state in which "waiting" is
done. StrategyArbiter._plans special-cases WaitGoal and returns
[WaitAction()] directly, so the goal never runs the A* planner. This is the
only sensible bypass because WaitAction is a no-op on WorldState and the
planner's visited-set would prune it.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

WAIT_GOAL_VALUE = 0.5
"""Sub-floor value: lives below every other Phase-18 goal so WaitGoal is the
strict last-resort choice in any band-comparison setting that ranks by
value(). Selection order is positional, not value-driven, so this is
documentation more than enforcement; keep it tiny on purpose."""


class WaitGoal(Goal):
    """Always-firing last-resort goal. Emits a single WaitAction."""

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        return WAIT_GOAL_VALUE

    def is_satisfied(self, state: WorldState) -> bool:
        return False

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {}

    @property
    def max_depth(self) -> int:
        return 1

    def __repr__(self) -> str:
        return "Wait"
