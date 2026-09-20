"""Region-crossing edges survive every goal's action whitelist.

`planner.py` rejects any action whose `travel_region` differs from the
character's current region, and `MapTransitionAction` is the sole edge that
changes region (`actions/base.py`'s `travel_region` docstring). So a goal pool
without those edges can only ever reach OVERWORLD content — whatever else is in
it.

Every goal that overrides `relevant_actions` does so with a whitelist, 32 of the
40 goal files do, and NOT ONE of them listed the `"movement"` tag. The result
was silent and total: the P5b region model emitted its edges, the factory
emitted off-region `FightAction`/`GatherAction` instances that answered
`is_applicable() == True`, and every one of them was filtered out of the pool
before the planner could step to it. That is the mechanical reason the region
model recorded 0 firings in 21,987 cycles.

Live Robby, 2026-09-20 — level 30, 943 XP short of 31, twenty-six days and
4,040 of 4,260 cycles on `LevelSkill` with ZERO fights. His grind target `rat`
is also his held task and lives at `interior:-3,12`::

    relevant_actions: 4 of 1932
       FightAction(rat) admitted: 1
       MapTransitionAction admitted: 0      <- 30 in the pool

    explored=3  created=3  depth=1  plan_len=0

With the edges re-admitted: `explored=17 created=53 depth=5`, and the plan is
`Transition((-3,12,overworld)->(-3,12,interior))` then `Fight(rat)`.

WHY A SHARED RE-ADD RATHER THAN 32 EDITS. An admission rule every producer has
to remember is one that will be forgotten — that is the same lesson
`equipment/slot_occupancy` was re-learned on, where a gate applied at three
call sites and missed at the fourth cost 1,464 wasted equips. Goals stay free to
narrow their pool to the actions that serve them; reaching the place those
actions happen is not a goal's decision to make, so it is not left to them.

WHY IT IS CONDITIONAL. Re-adding the edges UNCONDITIONALLY costs 41x the search
— measured, not feared: total nodes over the 44 scenarios went 1,467 -> 60,662,
and `l22_grey_rung_grind` alone 899 -> 57,554 for a byte-identical 71-action
plan. An edge only ever helps a pool that has something on the far side of it,
and 43 of the 44 scenarios' selected goals have NO off-region action in their
whitelist at all — for them every edge is a dead branch expanded at every node.
So the gate is exactly that question, asked of the goal's OWN whitelist rather
than of the full pool (the pool always carries all 48 off-region actions, so
asking it would gate on nothing).
"""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState

REGION_EDGE_TAG = "movement"
"""The tag on the region-crossing edge. `MapTransitionAction` is the only
carrier today; anything else that can change `state_region` must take this tag
so it is admitted by the same rule rather than by a second list."""


def admit_region_edges(relevant: list[Action], actions: list[Action],
                       state: WorldState, game_data: GameData) -> list[Action]:
    """`relevant` plus the region-crossing edges — but only when `relevant`
    holds work the character cannot reach from where it stands.

    Returns `relevant` unchanged when every admitted action is already in the
    character's region, which is the overwhelmingly common case and the one
    that must stay free: the edges would be pure extra branching at every node
    of a search that could never use them.

    Appended rather than prepended, so a goal's own ordering is untouched, and
    de-duplicated by identity: a goal that already admits the edges (the base
    class's `return actions`) must not receive them twice, or the branch is
    expanded twice at every node.

    Identity, not equality — `Action` subclasses are dataclasses with `eq`, so
    `in` over a list of them is an O(n) chain of field comparisons, and this
    runs once per plan attempt over the whole pool (1,932 actions live).
    """
    here = game_data.state_region(state)
    if not any(a.travel_region != here and REGION_EDGE_TAG not in a.tags
               for a in relevant):
        return relevant
    seen = {id(a) for a in relevant}
    return relevant + [a for a in actions
                       if REGION_EDGE_TAG in a.tags and id(a) not in seen]
