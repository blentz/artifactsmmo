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
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.intermediate_batch import size_intermediate_craft
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.priority_band import clamp_into_band
from artifactsmmo_cli.ai.recipe_closure import (
    closure_demand,
    gather_serves_closure,
)
from artifactsmmo_cli.ai.requirement_projections import requirement_craftables
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
        its intermediates, withdraw any already-banked mats) plus the
        TaskTrade that submits it — so the planner doesn't branch across
        every gather/craft in the game and time out. Withdraw is included
        so a bot whose materials are already in the bank doesn't re-gather
        the whole stack from scratch (trace 2026-06-05: 14-action gather
        plans while the bank held the same ash_wood)."""
        craftable_mats = requirement_craftables(
            game_data.requirement_graph.graph(), [self._task_code])
        # Build closure demand so intermediate crafts can be inventory-batched.
        chain: dict[str, int] = {}
        closure_demand(self._task_code, self._batch, game_data, chain, frozenset())
        # The withdraw-eligible item codes are (a) every closure material
        # (chain — leaf raw materials like ash_wood included) plus (b)
        # intermediate craftables already in the bank, e.g. ash_plank
        # waiting to be TaskTraded. (GAP-7: was a per-resource primary-drop
        # loop; the widened needed_resources would have admitted junk
        # withdraws — the primary drop of a secondarily-needed resource is
        # not a closure material.)
        withdrawable: set[str] = set(craftable_mats) | set(chain)
        withdrawable.add(self._task_code)  # the task item itself, banked previously
        result: list[Action] = []
        for action in actions:
            if (
                "recovery" in action.tags
                or "deposit" in action.tags
                # GAP-7 admission precision: EFFECTIVE drop in the closure.
                or (isinstance(action, GatherAction) and gather_serves_closure(
                    action.resource_code, action.drop_item_override,
                    game_data.resource_drops, chain))
                or (isinstance(action, TaskTradeAction) and action.code == self._task_code)
                or (isinstance(action, WithdrawItemAction) and action.code in withdrawable)
            ):
                result.append(action)
            elif isinstance(action, CraftAction) and action.code in craftable_mats:
                if action.code == self._task_code:
                    result.append(action)
                else:
                    result.append(size_intermediate_craft(action, chain, state, game_data))
        return result

    @property
    def max_depth(self) -> int:
        return 100

    def serialize(self) -> dict[str, object]:
        return {"type": "PursueTaskGoal",
                "task_code": self._task_code,
                "initial_progress": self._initial_progress,
                "batch": self._batch}

    def __repr__(self) -> str:
        return f"PursueTask({self._task_code})"
