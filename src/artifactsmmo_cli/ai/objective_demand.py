"""The cycle's XP demand and the tools it climbs with, by one fixed point
(plan C Task 1, ruling C1-a).

The skills the goal-action DAG demands come from its roots (`xp_demand`); each
demanded skill climbs faster with its best tool `T*` (`tool_target`, spec
2026-10-18 §2.6), and a tool still to be obtained is a root of its own, whose
closure can demand further skills (a pickaxe's craft demands weaponcrafting and
the mining for its bars). So the tools are found by iteration: demand from the
roots, the tools of the demanded skills, the demand again with those tools as
roots, until the tool set stops growing. Each skill names at most one tool, so
the loop runs at most once per skill, and each skill's tool is looked up once.
"""

from dataclasses import replace

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal
from artifactsmmo_cli.ai.tool_objective import tool_target
from artifactsmmo_cli.ai.world_state import WorldState
from artifactsmmo_cli.ai.xp_demand import demand_roots, xp_demand


def objective_demand(chosen: MetaGoal | None, state: WorldState, game_data: GameData,
                     ctx: SelectionContext) -> SelectionContext:
    """`ctx` with `skill_demand`, `level_demanded` and `objective_tools` set
    from the fixed point above, `chosen` being the last decision's root."""
    tools: dict[str, str | None] = {}
    while True:
        found = _named(tools)
        ctx = replace(ctx, objective_tools=found)
        skills, level = xp_demand(demand_roots(chosen, state, ctx), state, game_data, ctx)
        fresh = sorted(skills - tools.keys())
        for skill in fresh:
            tools[skill] = tool_target(skill, state, game_data, ctx, ctx.now)
        if _named(tools) == found:
            return replace(ctx, skill_demand=skills, level_demanded=level)


def _named(tools: dict[str, str | None]) -> dict[str, str]:
    """The skills whose lookup named a tool, skill -> tool."""
    return {skill: code for skill, code in tools.items() if code is not None}
