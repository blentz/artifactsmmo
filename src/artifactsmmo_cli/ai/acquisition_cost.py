"""Hoist priced `RouteOption`s out of `obtain_sources` for the pure cost walk.

The impure half of the route-aware acquisition cost: this module reads
`GameData` and `WorldState`, `ai/acquisition_cost_core` does the arithmetic.

WHY THE ROUTES COME FROM `obtain_sources` AND NOWHERE ELSE. That module was
written to be *"THE model of how an item can be obtained — the one source of
truth every producer of a plan must consume"*, and it enumerates all six routes
with their yields and capacities. Until now no COST model consumed it: `J`
priced through `min_plan_length` (gather/craft/equip, blind to the other three)
and `bid_vs_craft` priced through its own seconds-denominated walk (which knows
drop farms but not vendors). Two models, disjoint coverage, incomparable units,
and the enumeration they should both have been reading sat unused. This module
is the connection, so a SEVENTH route becomes one edit to `obtain_sources` and
every consumer — including the price — gains it structurally.

The one thing added here that `Source` does not carry is the VENUE and the
per-application ACTION COUNT, because those are pricing concerns and `Source`
answers an availability question. Everything else — which routes exist, their
yields, their capacities, whether the executor can actually serve them — is
`obtain_sources`' answer, unmodified. Restating any of it here would recreate
the divergence the epic exists to remove.
"""

from collections.abc import Mapping
from math import ceil

from artifactsmmo_cli.ai.acquisition_cost_core import RouteOption, acquisition_cost
from artifactsmmo_cli.ai.expected_damage import expected_damage_per_fight
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.fight_loop_cost import cycles_per_kill
from artifactsmmo_cli.ai.monster_drop_selection import (
    MonsterDropCandidate,
    expected_kills,
)
from artifactsmmo_cli.ai.obtain_sources import Source, SourceKind, obtain_sources
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

BANK_VENUE = "bank"
"""Venue code for a bank tile. A constant rather than a per-tile code because
every bank serves the same withdraw, so two withdraws pay one hop between them —
which is what the character actually does."""

EQUIP_ACTIONS = 1
"""One `EquipAction`. Carries no venue: equipping happens wherever the character
is standing."""


def _workshop_venue(skill: str) -> str:
    """Workshop tiles are keyed by SKILL, so two crafts on the same skill pay one
    hop and a jewelry craft after a weapon craft pays two. Prefixed so a skill
    named like an NPC cannot collide with one."""
    return f"workshop:{skill}"


def _drop_actions(monster_code: str, rate: int, min_q: int, max_q: int,
                  state: WorldState, game_data: GameData) -> int:
    """Whole-loop actions to farm ONE unit off `monster_code`.

    Two proved pieces, multiplied, and neither is restated here:
    `expected_kills` (`rate / avg_yield`, exact `Fraction`, proved in
    `Formal.MonsterDropSelection`) times `cycles_per_kill` — the SAME
    fight-plus-forced-rest figure `cheapest_path_to_level` spends, so a drop farm
    and a level grind are quoted in identical units. Using a bare kill count here
    would price the farm at roughly half its real cost, which is the defect
    `fight_loop_cost` was written to fix.

    Rounded UP: a fractional action is still an action the character spends, and
    the objective is an exact integer (S-013)."""
    kills = expected_kills(MonsterDropCandidate(
        monster_code=monster_code, rate=rate, min_quantity=min_q,
        max_quantity=max_q, distance=0))
    per_kill = cycles_per_kill(
        expected_damage_per_fight(state, game_data, monster_code), state.max_hp)
    return max(1, ceil(float(kills) * per_kill))


def _priced(item: str, source: Source, state: WorldState,
            game_data: GameData) -> RouteOption:
    """One `Source` plus its venue and action count.

    `Source.code` already means a different thing per kind (the resource, the
    NPC, the monster, the item to destroy — see `obtain_sources.Source`), and
    for GATHER, BUY and DROP that code IS the venue. CRAFT and RECYCLE happen at
    a workshop, WITHDRAW at a bank; those three are the only ones that need a
    venue derived rather than read."""
    if source.kind is SourceKind.WITHDRAW:
        return RouteOption(kind=source.kind.value, venue=BANK_VENUE,
                           actions_per_application=1, yield_per=source.yield_per,
                           capacity=source.capacity)
    if source.kind is SourceKind.RECYCLE:
        stats = game_data.item_stats(source.code)
        # `obtain_sources` already refused this source unless the item has a
        # crafting_skill, so the skill is present by that gate, not by luck.
        skill = stats.crafting_skill if stats is not None else ""
        return RouteOption(kind=source.kind.value, venue=_workshop_venue(skill or ""),
                           actions_per_application=1, yield_per=source.yield_per,
                           capacity=source.capacity,
                           inputs={source.code: 1})
    if source.kind is SourceKind.CRAFT:
        stats = game_data.item_stats(item)
        skill = stats.crafting_skill if stats is not None else ""
        recipe = game_data.crafting_recipe(item) or {}
        return RouteOption(kind=source.kind.value, venue=_workshop_venue(skill or ""),
                           actions_per_application=1, yield_per=source.yield_per,
                           capacity=source.capacity, inputs=dict(recipe))
    if source.kind is SourceKind.GATHER:
        return RouteOption(kind=source.kind.value, venue=source.code,
                           actions_per_application=1,
                           yield_per=max(1, game_data.max_gather_yield),
                           capacity=source.capacity)
    if source.kind is SourceKind.BUY:
        price, currency = _price_of(item, source.code, game_data)
        return RouteOption(kind=source.kind.value, venue=source.code,
                           actions_per_application=1, yield_per=source.yield_per,
                           capacity=source.capacity, inputs={currency: price})
    rate, min_q, max_q = _drop_table(item, source.code, game_data)
    return RouteOption(
        kind=source.kind.value, venue=source.code,
        actions_per_application=_drop_actions(source.code, rate, min_q, max_q,
                                              state, game_data),
        yield_per=source.yield_per, capacity=source.capacity)


def _price_of(item: str, npc_code: str, game_data: GameData) -> tuple[int, str]:
    """`(price, currency)` this NPC charges for this item.

    `obtain_sources` produced the BUY source from the same `npc_purchases` table,
    so the row exists; the loop re-reads it because `Source` carries only the NPC
    code. A missing row would mean the two calls disagreed about game data
    between them, which cannot happen inside one decision — so this raises rather
    than defaulting, per the API-data rule."""
    for code, price, currency in game_data.npc_purchases(item):
        if code == npc_code:
            return price, currency
    raise KeyError(f"no {npc_code} purchase row for {item}")


def _drop_table(item: str, monster_code: str,
                game_data: GameData) -> tuple[int, int, int]:
    """`(rate, min_quantity, max_quantity)` for this monster's drop of `item`.
    Same contract as `_price_of`: the row exists because `obtain_sources` built
    the DROP source from it."""
    for code, rate, min_q, max_q in game_data.monsters_dropping(item):
        if code == monster_code:
            return rate, min_q, max_q
    raise KeyError(f"no {monster_code} drop row for {item}")


def route_options(item: str, state: WorldState, game_data: GameData,
                  ctx: SelectionContext) -> list[RouteOption]:
    """Every currently-available route to `item`, priced."""
    return [_priced(item, s, state, game_data)
            for s in obtain_sources(item, state, game_data, ctx)]


def acquisition_options(item: str, state: WorldState, game_data: GameData,
                        ctx: SelectionContext) -> dict[str, list[RouteOption]]:
    """`route_options` over the whole closure reachable from `item`.

    The closure follows each route's INPUTS — recipe materials, recycle sources,
    and purchase CURRENCIES alike — so a vendor item priced in `event_ticket`
    pulls in however the tickets themselves are obtained. That currency edge is
    the one `min_plan_length` has no way to represent, and following it is what
    makes a 100-ticket purchase cost more than a free one.

    Cyclic by nature, not by accident: `copper_bar` recycles out of a
    `copper_dagger`, which crafts from `copper_bar`. So the walk needs a visited
    set, and it is checked at POP and nowhere else. An earlier version also
    filtered at push, which made the pop guard unreachable — two guards where
    one is correct, and the redundant one hid the fact that the other was doing
    nothing. The cost walk's own fuel bound handles the cycle when it comes to
    PRICE it; this only has to enumerate."""
    options: dict[str, list[RouteOption]] = {}
    frontier = [item]
    while frontier:
        code = frontier.pop()
        if code in options:
            continue
        routes = route_options(code, state, game_data, ctx)
        options[code] = routes
        for route in routes:
            frontier.extend(route.inputs)
    return options


def acquisition_actions(item: str, qty: int, state: WorldState,
                        game_data: GameData, ctx: SelectionContext,
                        equip: bool) -> int:
    """Lower bound on planner actions to obtain (and optionally equip) `qty` of
    `item`, over every route the executor can currently serve.

    Drop-in shape for `min_plan_length`'s call sites, with `state`/`ctx` added
    because routes are STATE-AWARE — which is the whole point, and also the
    reason `acquisition_cost_core.UNOBTAINABLE_PER_UNIT` must never be cached
    across cycles.

    HOLDINGS ARE THE BAG ONLY, AND THAT IS A CHANGE. `min_plan_length`'s callers
    pass inventory PLUS bank (`branch_objective._held`), because that model has
    no withdraw action and so must treat a banked copy as already in hand. Here
    the bank is a ROUTE — `SourceKind.WITHDRAW`, capacity = the bank's stock —
    so counting it as owned too would credit the same copy twice and price the
    trip to the bank at nothing. A banked item costs one hop plus one withdraw,
    which is what it costs."""
    owned: dict[str, int] = dict(state.inventory)
    options: Mapping[str, list[RouteOption]] = acquisition_options(
        item, state, game_data, ctx)
    return acquisition_cost(item, qty, options, owned) + (
        EQUIP_ACTIONS if equip else 0)
