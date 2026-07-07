"""PlanReport: the result of a single no-execute planning cycle (the `plan` CLI)."""

from dataclasses import dataclass, field

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
    # For the chosen objective's recipe: each pure monster-drop input, its dropping
    # monsters, and whether each is winnable with the LIVE loadout. Answers "will the
    # bot actually hunt these?" — an unwinnable drop makes the gear unbuildable.
    drop_inputs: list[dict[str, object]] = field(default_factory=list)
    # Diagnostic injections: the in-memory arbiter state seeded for THIS plan (via the
    # `plan --doom/--committed` flags) to reproduce a live divergence offline. Empty
    # for a normal plan. Echoed so the printed report is honest that the cycle ran
    # with non-default arbiter state.
    simulated_doomed: tuple[str, ...] = ()
    simulated_committed: str | None = None
