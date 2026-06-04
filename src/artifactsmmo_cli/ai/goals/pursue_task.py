"""PursueTaskGoal: advance an items-type task by one unit via gather/craft -> TaskTrade.

The PURSUE actuator for items tasks. Re-plans each cycle (the arbiter executes
only plan[0]), so desired_state targets one more traded unit; satisfied the
moment progress advances or the task is full/gone, letting the arbiter re-decide
against fresh API-observed state.
"""

from fractions import Fraction

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.priority_band import clamp_into_band
from artifactsmmo_cli.ai.recipe_closure import recipe_closure
from artifactsmmo_cli.ai.scalar_priority import yield_bonus_for_goal
from artifactsmmo_cli.ai.world_state import WorldState

# Matches the retired FarmItems value (35) so task pursuit slots at the same
# weight as the behavior it restores. This is now the BAND FLOOR — the
# learned-yield bonus can lift priority within [PRIORITY_FLOOR, PRIORITY_CEILING],
# but never above PRIORITY_CEILING < SURVIVAL_FLOOR (70).
PRIORITY_FLOOR = 35.0
"""Priority floor when an items task is being pursued. Mirrors retired
FarmItems(35) so a cold-start (history=None or zero samples) preserves the
pre-Phase-17 priority exactly."""

PRIORITY_CEILING = 50.0
"""Upper bound on the learned-yield contribution. Strictly below the
survival floor (70), preserving Phase-1's ban on unbounded additive priority
bonuses: a discretionary goal can never be reordered above a survival goal."""

# Backwards-compat alias for the original constant name (still re-exported so
# existing callers/tests that import PRIORITY_WHEN_FIRING continue to read the
# cold-start floor value).
PRIORITY_WHEN_FIRING = PRIORITY_FLOOR


class PursueTaskGoal(Goal):
    """Drive gather/craft -> TaskTrade to advance an items-type task one unit."""

    def __init__(self, task_code: str, initial_progress: int, batch: int = 1) -> None:
        self._task_code = task_code
        self._initial_progress = initial_progress
        self._batch = batch

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        if history is None:
            return PRIORITY_FLOOR
        # Phase-17: route the proved scalar_yield projection through the
        # band-clamp. Cold goal (sample_count=0) yields Fraction(0) and the
        # clamp returns exactly PRIORITY_FLOOR — matches the pre-Phase-17
        # constant. EXACT-RATIONAL arithmetic mirrors the Lean Rat model.
        bonus = yield_bonus_for_goal(repr(self), state, game_data, history)
        clamped = clamp_into_band(Fraction(PRIORITY_FLOOR), Fraction(PRIORITY_CEILING), bonus)
        return float(clamped)

    def is_satisfied(self, state: WorldState) -> bool:
        if not state.task_code or state.task_total == 0:
            return True
        if state.task_progress >= state.task_total:
            return True
        return state.task_progress >= self._initial_progress + self._batch

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"task_progress": self._initial_progress + self._batch}

    def relevant_actions(
        self, actions: list[Action], state: WorldState, game_data: GameData
    ) -> list[Action]:
        """Scope to the task item's recipe closure (gather its resources, craft
        its intermediates) plus the TaskTrade that submits it — so the planner
        doesn't branch across every gather/craft in the game and time out."""
        needed_resources, craftable_mats = recipe_closure(game_data, [self._task_code])
        result: list[Action] = []
        for action in actions:
            if "recovery" in action.tags or "deposit" in action.tags or (isinstance(action, GatherAction) and action.resource_code in needed_resources) or (isinstance(action, CraftAction) and action.code in craftable_mats) or (isinstance(action, TaskTradeAction) and action.code == self._task_code):
                result.append(action)
        return result

    @property
    def max_depth(self) -> int:
        return 100

    def __repr__(self) -> str:
        return f"PursueTask({self._task_code})"
