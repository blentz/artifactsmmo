"""TaskCancelGoal: report the urgency of the cancel the TASK_CANCEL rung asked for."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState


class TaskCancelGoal(Goal):
    """Cancel the current task. WHY it should be cancelled is not asked here.

    ONE PRODUCER OF THE CANCEL REASON, AND IT IS NOT THIS CLASS. The goal is
    constructed in exactly one place — `strategy_driver.map_means` for
    `MeansKind.TASK_CANCEL` — and `tiers/means.active_means` only names that kind
    after `_fires` has already decided. `_fires` has THREE independent reasons to
    fire: S-048 (the draw advances no progression), the one-level horizon
    (`ai/task_horizon.py`, for a monsters task), and `task_decision == PIVOT`
    (the items arm). This class used to re-derive the third one on its own and
    call the answer the goal's value.

    Measured on the offline corpus (2026-08-25), every cell where the arbiter
    SELECTS this goal: `l32_held_task_open` (the horizon arm — the cell the
    horizon was written for), `l32_held_task_closable` and
    `l32_held_task_workable` (both S-048). All three fired, all three were
    selected, and all three reported `value == 0.0`, because `task_decision`
    answered PURSUE for all three — an in-band monster is not a level-proxy
    pivot. A selected goal that reports zero urgency is not a harmless
    disagreement: `priority` is what `StrategyArbiter._plan_for_goal` records as
    the trace's `goal_rank`, and BOTH TUI consumers of that panel filter on
    `priority > 0` (see the comment at `strategy_driver.py:820`, written when
    that panel last rendered empty for exactly this reason).

    So the reason lives in `_fires` and the scalar lives here. What remains is
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
        # Kept here rather than deferred to `_fires` like the reason: the goal is
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
