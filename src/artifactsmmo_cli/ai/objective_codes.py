"""The codes the cycle's gear objective still builds toward (spec 2026-10-18
§2.2, plan C Task 1): the missing `L*` pieces and the tools `T*` the demanded
skills climb with. The one source the skill demand, a task's drop worth and
the skill grind's `wanted` preference read, in place of the old gear sheets.

Its own module, not `gear_objective_context`: that module imports the gear
objective's pricer, and the pricer's own imports reach every reader here
(`task_worth`, the skill grind), so the readers could not import it back.
"""

from artifactsmmo_cli.ai.selection_context import SelectionContext


def objective_codes(ctx: SelectionContext) -> frozenset[str]:
    """The missing `L*` pieces (`ctx.gear_objective.missing`; none while `L*`
    is held or no objective was found) and the tools of `ctx.objective_tools`."""
    tools = frozenset(ctx.objective_tools.values())
    if ctx.gear_objective is None:
        return tools
    return frozenset(piece.code for piece in ctx.gear_objective.missing) | tools
