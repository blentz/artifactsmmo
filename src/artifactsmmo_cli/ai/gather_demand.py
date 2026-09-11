"""Which gathering skills the roots on offer actually need, and to what level.

The demand side of the gathering-skill grind gate. `_orphan_skill_roots` offers
a standalone skill climb for every skill no gear target can name, which admits
every gathering skill by construction — gear is crafted by gearcrafting,
weaponcrafting and jewelrycrafting, so mining, woodcutting, fishing and alchemy
fall out as orphans whether or not anything wants them. Live 2026-09-09/10 that
sent R2D2 and Robby to fishing for ~617 cycles each at 0 character XP while
neither needed a fish.

This module answers the question that gate was missing: does any root on offer
bottom out in a leaf this character cannot gather yet? It reads
`RequirementGraph.gather_skill`, the item -> (skill, level) map the
requirement-model unification built and left unconsumed.
"""

from collections.abc import Sequence

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.requirement_projections import requirement_closure
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal, ObtainItem, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from artifactsmmo_cli.ai.world_state import WorldState


def gathering_skills(game_data: GameData) -> frozenset[str]:
    """Skills that gate a gathered leaf, read from the catalogue.

    NOT a hardcoded set: the gate must not name skills individually, or it
    encodes a difference the catalogue does not have. Live this is
    {alchemy, fishing, mining, woodcutting}; cooking gathers nothing and is
    therefore never gated.
    """
    graph = game_data.requirement_graph.graph()
    return frozenset(skill for skill, _level in graph.gather_skill.values())


def _seed(root: MetaGoal, state: WorldState, game_data: GameData,
          ctx: SelectionContext, gathering: frozenset[str]) -> str | None:
    """The item code whose requirements stand in for `root`.

    An `ObtainItem` names its own. A `ReachSkillLevel` names NO item, so its
    demand is invisible to a closure walk — the same blind spot recorded for the
    supply link — and is seeded with the item the character would craft for that
    rung. A root for a GATHERING skill is not seeded: letting it name its own
    grind target would let the root manufacture the demand that admits it.
    """
    if isinstance(root, ObtainItem):
        return root.code
    if isinstance(root, ReachSkillLevel) and root.skill not in gathering:
        return skill_grind_target(root.skill, state, game_data, ctx=ctx)
    return None


def gather_demand(roots: Sequence[MetaGoal], state: WorldState,
                  game_data: GameData, ctx: SelectionContext) -> dict[str, int]:
    """Skill -> the highest UNMET gather level any root's closure requires.

    A skill whose demand is already met is ABSENT rather than present-and-zero,
    so `.get(skill, 0)` is falsy exactly when nothing is asking.
    """
    graph = game_data.requirement_graph.graph()
    gathering = gathering_skills(game_data)
    demand: dict[str, int] = {}
    for root in roots:
        seed = _seed(root, state, game_data, ctx, gathering)
        if seed is None:
            continue
        for item in requirement_closure(graph, [seed]):
            gate = graph.gather_skill.get(item)
            if gate is None:
                continue
            skill, level = gate
            if state.skills.get(skill, 1) < level and level > demand.get(skill, 0):
                demand[skill] = level
    return demand
