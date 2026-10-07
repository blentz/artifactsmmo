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

The roots are the chosen root and the unmet target gear and near-term targets
— everything the objective is building toward.
"""

from collections.abc import Sequence

from artifactsmmo_cli.ai.craft_demand import craft_demand
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gather_demand import gather_demand
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal, ObtainItem, ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.world_state import WorldState


def demand_roots(chosen: MetaGoal | None, state: WorldState,
                 ctx: SelectionContext) -> list[MetaGoal]:
    """The chosen root, then one `ObtainItem` per unworn target or near-term
    target, in a stable order, then the fleet consumable shortfall
    (`ctx.supply_shortfall`: fishing feeds cooking feeds the heal supply)."""
    worn = {code for code in state.equipment.values() if code is not None}
    roots: list[MetaGoal] = [] if chosen is None else [chosen]
    roots.extend(ObtainItem(code, 1)
                 for code in sorted(ctx.target_gear | ctx.near_term_targets) if code not in worn)
    roots.extend(ObtainItem(code, qty) for code, qty in ctx.supply_shortfall)
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
