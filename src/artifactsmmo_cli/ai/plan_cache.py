"""Live in-session commitment to a computed GOAP plan. A passive value object:
the reuse-vs-replan decision lives in ai.should_replan, not here."""

from collections.abc import Mapping
from dataclasses import dataclass

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal


@dataclass
class PlanCache:
    """The plan the bot is currently executing, plus the cursor into it."""

    selected_goal: Goal
    plan: list[Action]
    crafting_target: str | None
    latch_active: bool
    goal_repr: str
    cursor: int = 0
    cycles_since_replan: int = 0
    step_target: int | None = None
    """Holding of the current step's drop item at which the cursor may advance.

    A batched gather is a planner abstraction: the API gathers one unit per
    call with a cooldown, so N units are N cycles (the LevelSkill
    planner-abstraction / player-expansion idiom). The advance condition is a
    STATE PREDICATE, not an execution counter, and that choice is load-bearing:
    a lucky multi-unit drop, another character draining the shared bank, or a
    bag that fills mid-batch all resolve without bookkeeping, and no mutable
    progress lives on the shared Action instance.

    None for every non-batched step, which is then trivially satisfied.
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
        action = self.current()
        qty = getattr(action, "quantity", 1)
        if not isinstance(action, GatherAction) or qty <= 1:
            self.step_target = None
            return
        drop = action.drop_item(game_data)
        self.step_target = inventory.get(drop, 0) + qty

    def batch_satisfied(self, inventory: Mapping[str, int], game_data: GameData) -> bool:
        """True when the armed step's target holding has been reached. Always
        True for a non-batched step (step_target is None), so an unbatched
        advance behaves exactly as it did before batching existed."""
        if self.step_target is None:
            return True
        action = self.current()
        if not isinstance(action, GatherAction):
            return True
        return inventory.get(action.drop_item(game_data), 0) >= self.step_target
