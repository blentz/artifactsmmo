"""Which CRAFTING skills the roots on offer actually need, and to what level.

The mirror of `gather_demand`, for the other half of `_orphan_skill_roots`'
admission rule.

Conjunct 1 of that gate drops every gear-nameable skill — gearcrafting,
weaponcrafting, jewelrycrafting — because gear is crafted BY those skills, so a
gear root that needs one names it through the ordinary prerequisite seam and no
standalone climb is warranted. That reasoning is sound exactly when some gear
root is plannable, and silently wrong when none is: the skill is then excluded
on the strength of a mechanism that has nothing to say about it.

Live Robby 2026-09-13 was the silent case. weaponcrafting 11 against character
level 30 — a gap of -19, the widest on him and twice the runner-up — with an
OPEN rung whose next step was two chicken fights, while the cooking rung he was
actually running asked for 55 crafted porkchops. All five of his gear roots
resolved to `nodes=0, plan_len=0`, and the craft demand of every root on offer
measured `{}`. Nothing asked for weaponcrafting; the conjunct that would have
offered it a rung had excluded it on the assumption that something would.

This module answers the question that conjunct was assuming: does any root on
offer actually require this crafting skill, at a level the character has not
reached? It reads `RequirementGraph.craft_skill`, the item -> (skill, level) map
the requirement-model unification built, exactly as `gather_demand` reads
`gather_skill`.

ASKED ONLY OF ROOTS ALREADY ON OFFER, and that is load-bearing. `gather_demand`
seeds a `ReachSkillLevel` through `skill_grind_target` so an orphan candidate
can demand a gathering skill, and guards against a gathering root seeding
itself. The polarity here is INVERTED — demand SUPPRESSES a candidate rather
than admitting it — so a candidate that seeded itself would name its own grind
target's craft skill and suppress exactly the rung it was asking for. There is
no seeding here at all: a root that names no item contributes nothing.
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
