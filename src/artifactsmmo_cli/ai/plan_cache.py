"""Live in-session commitment to a computed GOAP plan. A passive value object:
the reuse-vs-replan decision lives in ai.should_replan, not here."""

from collections.abc import Mapping
from dataclasses import dataclass

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal


@dataclass
class PlanCache:
    """The plan the bot is currently executing, plus the cursor into it."""

    selected_goal: Goal
    plan: list[Action]
    crafting_target: str | None
    plan_level: int
    """The character level the plan was made at: a level-up re-decides
    (`should_replan` trigger 4)."""
    goal_repr: str
    cursor: int = 0
    cycles_since_replan: int = 0
    step_target: int | None = None
    """Holding of the current step's drop item at which the cursor may advance.

    A batched gather is a planner abstraction: the API gathers one unit per
    call with a cooldown, so N units are N cycles. The advance condition is a
    STATE PREDICATE, not an execution counter, and that choice is load-bearing:
    a lucky multi-unit drop, another character draining the shared bank, or a
    bag that fills mid-batch all resolve without bookkeeping, and no mutable
    progress lives on the shared Action instance.

    A fight planned for a drop (`FightAction.drop_target`, Phase 2d-L1c) is
    armed the same way on the drop item: a drop is stochastic, so the fight
    repeats until the bag holds the units the plan counted on, and the legs
    after it find their inputs.

    None for every other step, which is then trivially satisfied.
    """

    def current(self) -> Action | None:
        """The step about to execute, or None when the plan is exhausted."""
        if self.cursor >= len(self.plan):
            return None
        return self.plan[self.cursor]

    def advance(self) -> None:
        self.cursor += 1

    def exhausted(self) -> bool:
        return self.cursor >= len(self.plan)

    def arm_step(self, inventory: Mapping[str, int], game_data: GameData) -> None:
        """Snapshot the current step's completion target. Call on every advance
        and on every plan install (fresh decide or resumed commitment)."""
        output = _output(self.current(), game_data)
        self.step_target = None if output is None else inventory.get(output[0], 0) + output[1]

    def batch_satisfied(self, inventory: Mapping[str, int], game_data: GameData) -> bool:
        """True when the armed step's target holding has been reached. Always
        True for a step with no target (step_target is None), so such an
        advance behaves exactly as it did before batching existed."""
        output = _output(self.current(), game_data)
        if self.step_target is None or output is None:
            return True
        return inventory.get(output[0], 0) >= self.step_target


def _output(action: Action | None, game_data: GameData) -> tuple[str, int] | None:
    """The (item, units) a step must add before the cursor moves on: a gather's
    drop, or a planned fight's drop; None for any other step. A single gather
    is armed too: a secondary drop (algae from a gudgeon spot) can come up
    empty, and the leg after it needs what it was planned to deliver. The
    walk's gather and drop routes yield one per application, so a gather's
    quantity IS the units its leg was planned for (`CommittedLoop`)."""
    if isinstance(action, GatherAction):
        return action.drop_item(game_data), action.quantity
    if isinstance(action, FightAction):
        return action.drop_target
    return None
