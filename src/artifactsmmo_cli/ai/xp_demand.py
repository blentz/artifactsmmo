"""Which XP the goal-action DAG still demands (Phase 5-2c-iii-c-2 #5,
increment 4; `docs/PLAN_task_value.md` §9).

USER 2026-10-07: the character-XP / skill-XP seesaw is EMERGENT — "the planner
should be GOAP and A* oriented to produce the emergent seesaw behaviors through
complete definition of goal-action based batch-aware, deduped-actions DAG". So
no phase rule: a task's XP is worth working exactly when the DAG has unmet
demand for it.

* SKILL demand: the skills whose unmet level the roots' requirement closures
  name (`craft_demand` / `gather_demand`, the walks the root offer already
  reads), and a `ReachSkillLevel` root's own skill.
* CHARACTER-LEVEL demand: a `ReachCharLevel` root above the character, or an
  `ObtainItem` root whose item needs a higher level than the character has.

The roots are the chosen root, the missing pieces of the cycle's gear
objective `L*` and the tools `T*` the demanded skills climb with
(`objective_codes`), and a crafter's fleet pieces (`ctx.fleet_pieces`, spec
2026-10-18 §2.5: they count as missing pieces of its joint objective) as the
craft level each needs — everything the objective is building toward.
"""

from collections.abc import Sequence

from artifactsmmo_cli.ai.craft_demand import craft_demand
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gather_demand import gather_demand
from artifactsmmo_cli.ai.objective_codes import objective_codes
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal, ObtainItem, ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.world_state import WorldState


def demand_roots(chosen: MetaGoal | None, state: WorldState,
                 ctx: SelectionContext) -> list[MetaGoal]:
    """The chosen root, then one `ObtainItem` per missing `L*` piece and
    per `T*` tool (`objective_codes`), in a stable order, then one
    `ReachSkillLevel` per fleet piece, its craft skill at the level that gates
    it, offered while the cycle has a gear objective (`resolve_root` offers the
    fleet pieces' roots on the same condition, ruling C2-m3). NOT the fleet consumable shortfall (spec
    2026-10-13 §2): food demand made fishing 'useful XP', which credited the
    food's make price, which kept the food demanded."""
    roots: list[MetaGoal] = [] if chosen is None else [chosen]
    roots.extend(ObtainItem(code, 1) for code in sorted(objective_codes(ctx)))
    if ctx.gear_objective is not None:
        roots.extend(ReachSkillLevel(skill=piece.skill, level=piece.level)
                     for piece in ctx.fleet_pieces)
    return roots


def xp_demand(roots: Sequence[MetaGoal], state: WorldState, game_data: GameData,
              ctx: SelectionContext) -> tuple[frozenset[str], bool]:
    """(the skills the DAG demands above their current level, whether it
    demands character level)."""
    skills = set(craft_demand(roots, state, game_data, ctx))
    skills.update(gather_demand(roots, state, game_data, ctx))
    level = False
    for root in roots:
        if isinstance(root, ReachSkillLevel) and state.skills.get(root.skill, 1) < root.level:
            skills.add(root.skill)
        elif isinstance(root, ReachCharLevel) and state.level < root.level:
            level = True
        elif isinstance(root, ObtainItem):
            stats = game_data.item_stats(root.code)
            if stats is not None and stats.level > state.level:
                level = True
    return frozenset(skills), level
