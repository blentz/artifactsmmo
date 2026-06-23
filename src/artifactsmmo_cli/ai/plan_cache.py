"""Live in-session commitment to a computed GOAP plan. A passive value object:
the reuse-vs-replan decision lives in ai.should_replan, not here."""

from dataclasses import dataclass

from artifactsmmo_cli.ai.actions.base import Action
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

    def current(self) -> Action | None:
        """The step about to execute, or None when the plan is exhausted."""
        if self.cursor >= len(self.plan):
            return None
        return self.plan[self.cursor]

    def advance(self) -> None:
        self.cursor += 1

    def exhausted(self) -> bool:
        return self.cursor >= len(self.plan)
