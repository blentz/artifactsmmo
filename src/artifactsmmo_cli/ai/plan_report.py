"""PlanReport: the result of a single no-execute planning cycle (the `plan` CLI)."""

from dataclasses import dataclass

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.tiers.strategy import StrategyDecision


@dataclass(frozen=True)
class PlanReport:
    """What the bot WOULD do this cycle, computed without executing anything.

    `decision` carries the Tier-3 ranking + chosen_root/chosen_step; `selected_goal`
    is the goal the arbiter actually picked; `plan` is the planned action sequence;
    `goals_tried` is the per-goal planner attempt log (nodes / plan_len / timed_out),
    which surfaces explosions (plan_len 0 after thousands of nodes)."""

    decision: StrategyDecision
    selected_goal: Goal | None
    plan: list[Action]
    goals_tried: list[dict[str, object]]
