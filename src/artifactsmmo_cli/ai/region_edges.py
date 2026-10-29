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

import dataclasses
from collections.abc import Iterable, Iterator, Sequence

from artifactsmmo_cli.ai.actions.base import Action, serves_region
from artifactsmmo_cli.ai.actions.transition import MapTransitionAction
from artifactsmmo_cli.ai.catalogue_scope import CatalogueScope
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_model.gate import Door
from artifactsmmo_cli.ai.world_state import GOLD_CODE, WorldState

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
    if not any(not serves_region(a, here) and REGION_EDGE_TAG not in a.tags
               for a in relevant):
        return relevant
    seen = {id(a) for a in relevant}
    return relevant + [a for a in actions
                       if REGION_EDGE_TAG in a.tags and id(a) not in seen]


def region_edge_actions(game_data: GameData) -> list[Action]:
    """One `MapTransitionAction` per transition edge in the catalogue, in tile
    order: the edges the action factory puts in every pool (`build_actions`),
    built here once so the pool and `reachable_regions_now` cross the same
    edges."""
    return [MapTransitionAction(
        portal_x=px, portal_y=py, portal_layer=playr,
        dest_x=dx, dest_y=dy, dest_layer=dlayer,
        conditions=conds,
        travel_region=game_data.region_of(px, py, playr))
        for (px, py, playr), (dx, dy, dlayer, conds) in sorted(
            game_data.world.transition_edges.items())]


def _crossing_walk(state: WorldState, edges: Sequence[Action],
                   game_data: GameData) -> Iterator[tuple[str, list[Action]]]:
    """Every region a chain of applicable crossings from `state` lands in, with
    the fewest crossings that land there first: breadth-first over the region
    edges. Each crossing is applied, so a key or fee the first one spends is
    not available to the second. Each region is entered once (`seen`), so the
    walk ends when the reachable regions are exhausted."""
    frontier: list[tuple[WorldState, list[Action]]] = [(state, [])]
    seen = {game_data.state_region(state)}
    while frontier:
        nxt: list[tuple[WorldState, list[Action]]] = []
        for at, route in frontier:
            here = game_data.state_region(at)
            for edge in edges:
                if edge.travel_region != here or not edge.is_applicable(at, game_data):
                    continue
                landed = edge.apply(at, game_data)
                region = game_data.state_region(landed)
                yield region, [*route, edge]
                if region not in seen:
                    seen.add(region)
                    nxt.append((landed, [*route, edge]))
        frontier = nxt


def crossings(state: WorldState, target: str, edges: Sequence[Action],
              game_data: GameData) -> list[Action] | None:
    """The fewest applicable crossings from `state`'s region into `target`, or
    None: the walk's bridge (`craft_plan_gen._bridge_regions`). It was capped
    at 4 crossings: the island to the sonnengott cavern, and that cavern to
    the raid area, are 5 (the conditions census, 2026-10-10: red_dragon_boots,
    medic_armor declined)."""
    return next((route for region, route in _crossing_walk(state, edges, game_data)
                 if region == target), None)


REACH_MEMO_SIZE = 256
"""Walks `reachable_regions_now` keeps per catalogue: one per distinct
(region, gold, holdings) the cycle asks about. The obtain model asks once per
model, and a cycle builds thousands of models over a handful of states."""

_REACH: "CatalogueScope[tuple[object, ...], frozenset[str]]" = CatalogueScope(REACH_MEMO_SIZE)
"""The walks, scoped per catalogue (`CatalogueScope`: a catalogue's entries
die with it, so no address is ever reused for another's answer)."""


def _reach_key(state: WorldState, game_data: GameData) -> tuple[object, ...]:
    """Everything a crossing's applicability reads (`MapTransitionAction.
    is_applicable`): the region and layer the walk starts from, the gold and
    items it pays with, the items it holds or wears."""
    return (game_data.state_region(state), state.layer, state.gold,
            tuple(sorted(state.inventory.items())),
            tuple(sorted(code for code in state.equipment.values() if code)))


def reachable_regions_now(state: WorldState, game_data: GameData) -> frozenset[str]:
    """The regions the walk can reach from `state` now: its own, and every
    region a chain of crossings applicable from it lands in (`crossings`'s
    walk over the catalogue's edges). The ONE reachability authority for a
    fight's monster (ruling T14a-E): a route whose monster stands in no such
    region is not a route, since the walk could not serve it. Unlike
    `GameData.reachable_regions` (a fee the character could earn counts), a
    crossing is reachable only when it is applicable here: the gold or key
    in hand. Memoised per catalogue (`_REACH`, keyed by `_reach_key`)."""
    memo = _REACH.cache_for(game_data)
    key = _reach_key(state, game_data)
    if key not in memo:
        _REACH.remember(memo, key, frozenset(
            {game_data.state_region(state)}
            | {region for region, _route in _crossing_walk(
                state, region_edge_actions(game_data), game_data)}))
    return memo[key]


def content_reached(code: str, live: Iterable[tuple[int, int]], game_data: GameData,
                    reach: frozenset[str]) -> bool:
    """Some tile of the content `code` (a monster or a resource) — its `live`
    overworld tiles, or any of its tiles on any layer — lies in a region of
    `reach` (`reachable_regions_now`). The one tile test a fight's and a
    gather's SPAWN_KNOWN gate read (rulings T14a-E, I-3)."""
    tiles = [(x, y, "overworld") for x, y in live]
    tiles += game_data.layered_locations(code)
    return any(game_data.region_of(x, y, layer) in reach for x, y, layer in tiles)


_DOORS: "CatalogueScope[tuple[object, ...], tuple[tuple[Door, frozenset[str]], ...]]" = (
    CatalogueScope(REACH_MEMO_SIZE))
"""`door_reaches`' answers, scoped and keyed as `_REACH` is."""


def _holding(state: WorldState, door: Door) -> WorldState:
    """`state` with `door`'s shortfall in hand: its gold in the pocket, its keys
    in the bag."""
    inventory = dict(state.inventory)
    gold = state.gold
    for code, units in door:
        if code == GOLD_CODE:
            gold += units
        else:
            inventory[code] = inventory.get(code, 0) + units
    return dataclasses.replace(state, gold=gold, inventory=inventory)


def door_reaches(state: WorldState, game_data: GameData) -> tuple[tuple[Door, frozenset[str]], ...]:
    """Every door the walk could cross holding its shortfall (Task 14e, M-3),
    with the regions that shortfall adds to `reachable_regions_now`.

    A door is a modeled edge (`MapTransitionAction.shortfall` is not None)
    that `state` cannot cross: a key it lacks (`has_item` or a consumed
    `cost`) or a fee past its pocket. Its reach is the ONE authority's own
    answer asked of `state` holding the shortfall (`_holding`), so a key that
    opens a second door, or a crossing the key's door leads to, is counted as
    the walk would cross them, and a door whose portal the walk cannot reach
    reaches nothing new: it is no door. One door at a time: content past two
    unpaid doors with different keys stays unreached. Edges in tile
    order (`region_edge_actions`); a shortfall two edges share is listed
    once. Memoised as `reachable_regions_now` is (`_DOORS`)."""
    memo = _DOORS.cache_for(game_data)
    key = _reach_key(state, game_data)
    if key not in memo:
        now = reachable_regions_now(state, game_data)
        out: dict[Door, frozenset[str]] = {}
        for edge in region_edge_actions(game_data):
            assert isinstance(edge, MapTransitionAction)
            lack = edge.shortfall(state)
            if not lack:
                continue
            door: Door = tuple(sorted(lack.items()))
            if door in out:
                continue
            beyond = reachable_regions_now(_holding(state, door), game_data) - now
            if beyond:
                out[door] = beyond
        _DOORS.remember(memo, key, tuple(out.items()))
    return memo[key]


def doors_to(code: str, live: Iterable[tuple[int, int]], state: WorldState,
             game_data: GameData) -> tuple[Door, ...]:
    """The doors (`door_reaches`) past which some tile of the content `code`
    lies (`content_reached`), in `door_reaches`' order: the shortfalls that
    would make it reached. Asked of content the walk does not reach now."""
    tiles = list(live)
    return tuple(door for door, beyond in door_reaches(state, game_data)
                 if content_reached(code, tiles, game_data, beyond))
