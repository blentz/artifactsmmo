"""Which CRAFTING skills the roots on offer actually need, and to what level.

One half of `_orphan_skill_roots`' admission rule; `gather_demand` is the
other. USER 2026-10-08, "Only when demanded": a skill gets a standalone climb
exactly when the goal-action DAG demands it — gear, the consumable floor's tier
food, a task — and never for merely trailing the character.

It reads `RequirementGraph.craft_skill`, the item -> (skill, level) map the
requirement-model unification built, exactly as `gather_demand` reads
`gather_skill`. Only `ObtainItem` roots are walked: a `ReachSkillLevel` names no
item, and seeding one with its own grind target would let the climb
manufacture the demand that admits it.
"""

from collections.abc import Sequence

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.requirement_projections import requirement_closure
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal, ObtainItem
from artifactsmmo_cli.ai.world_state import WorldState


def craft_demand(roots: Sequence[MetaGoal], state: WorldState,
                 game_data: GameData, ctx: SelectionContext) -> dict[str, int]:
    """Skill -> the highest UNMET craft level any root's closure requires.

    A skill whose demand is already met is ABSENT rather than present-and-zero,
    so `.get(skill, 0)` is falsy exactly when nothing is asking.

    `ctx` is accepted for signature parity with `gather_demand`, which needs it
    to seed a skill root through `skill_grind_target`; this projection seeds
    nothing and so has no use for it.
    """
    del ctx  # parity with gather_demand; nothing here is seeded
    graph = game_data.requirement_graph.graph()
    demand: dict[str, int] = {}
    for root in roots:
        if not isinstance(root, ObtainItem):
            continue
        for item in requirement_closure(graph, [root.code]):
            gate = graph.craft_skill.get(item)
            if gate is None:
                continue
            skill, level = gate
            if state.skills.get(skill, 1) < level and level > demand.get(skill, 0):
                demand[skill] = level
    return demand
