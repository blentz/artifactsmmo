"""TaskCancelGoal: report the urgency of the cancel the task objective's step asked for."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState


class TaskCancelGoal(Goal):
    """Cancel the current task. WHY it should be cancelled is not asked here.

    ONE PRODUCER OF THE CANCEL REASON, AND IT IS NOT THIS CLASS. The goal is
    the task objective's step: `strategy_driver.objective_step_goal` builds it
    for a `ReachTaskOutcome` only after `route.task_cancel_due` (the proved
    `task_worth` verdict) has already decided (Phase 5-2c-iii-c-2 #5; it was the
    TASK_CANCEL means rung). This class once re-derived a cancel reason on its
    own and called the answer the goal's value; a selected goal that reports
    zero urgency is not a harmless disagreement: `priority` is what
    `StrategyArbiter._plan_for_goal` records as the trace's `goal_rank`, and
    BOTH TUI consumers of that panel filter on `priority > 0`.

    So the reason lives in `task_worth` and the scalar lives here. What remains is
    the pocket-coin gate, which is not a second reading of the reason but a
    property of the bag that `TaskCancelAction.is_applicable` reads too.
    """

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        # NO COIN, NO PROPOSAL. `TaskCancelAction.is_applicable` already refuses
        # without a POCKET `tasks_coin` (the server answers HTTP 478), so a goal
        # that can be selected without one is a goal that can only ever return an
        # EMPTY plan — a planning budget spent inside the cooldown window to learn
        # what the state already said. USER (2026-08-25): "we can attempt
        # cancel_task iff we have a task_coin, but if we have no coins we
        # shouldn't waste the cycles."
        #
        # Kept here rather than deferred to the worth verdict like the reason: the goal is
        # also built by hand in tests and by the differential harness, and this is
        # the one condition under which its own action declines.
        if state.inventory.get(TASKS_COIN_CODE, 0) < 1:
            return 0.0
        return 12.0

    def is_satisfied(self, state: WorldState) -> bool:
        return not state.task_code or state.task_total == 0

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"task_code": None, "task_total": 0}

    def __repr__(self) -> str:
        return "TaskCancel"
