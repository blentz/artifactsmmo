"""PURE route-aware lower bound on the ACTIONS needed to obtain an item.

Successor to `ai/min_plan_length`, which models three actions — gather, craft,
equip — and treats **any item without a recipe as a raw gatherable costing one
gather**. It has no notion of vendors, monsters, currency, the bank, or skill
gates, so a route it cannot express is not priced expensively; it is priced at
very nearly nothing, because the item looks raw. Measured at `5a2d1b8d`: a
`backpack` (50,000 gold from `nomadic_merchant`) and a `wolf_hair` (an
open-ended 1-in-N drop farm) each priced at 2 — strictly less than picking two
copper ore off the ground. See `tests/test_ai/test_acquisition_cost_baseline.py`,
which pins those numbers, and `docs/PLAN_unified_acquisition_objective.md`.

THE CURRENCY IS ACTIONS, AND THAT IS LOAD-BEARING. Every term here is a count of
planner actions, comparable to `cycles_to_fifty` under S-004. Anything that is
not an action count — a gold price, a level gap, a wall-clock cooldown, a travel
distance — must be CONVERTED to actions before it enters, or it reintroduces the
seconds/actions confusion that has produced four separate bugs in this project.
`haste` and travel distance are permanently excluded for exactly this reason;
see `audit/stat_projection_completeness.UNPRICED`.

WHY IT IS AN AND/OR WALK, NOT A SUM. `min_gathers` walks a recipe tree where
every node has exactly one way to be satisfied (gather it, or craft it from its
inputs). Real acquisition is a choice: `copper_ore` may be withdrawn from the
bank, gathered from a node, or bought from a vendor, and the cheapest of those
is the one a plan would take. So each node is an OR over `RouteOption`s, and a
CRAFT option is an AND over its inputs. This module is that walk.

VENUE HOPS. Per the plan's decision 2, and settled by the API rather than by
preference: the SERVER runs the A* pathfind, so a move of any length is a single
`/action/move` call, and the documented cooldown is *"5 seconds per map"* —
making distance a DURATION, never a count. So travel contributes **1 action per
DISTINCT venue the plan must visit**, and 0 for a venue already visited (or for
a route with no venue at all). The visited set is threaded through the walk
exactly as `owned` is, because a plan that gathers twenty ore walks to the node
once, not twenty times. Undercounting travel keeps the bound SOUND; overcounting
would not.

SOUNDNESS CONTRACT. This is a LOWER bound on the length of any plan that obtains
`qty` of `item`. Its consumers (`ProgressionGoal.is_plannable`,
`SupplyBankGoal`, and `J`'s `acquire_cost`) use it to PRUNE, so it must never
over-estimate: an over-estimate discards a reachable plan, which is a livelock,
while an under-estimate merely wastes a search. Every modelling choice below
that could go either way is therefore resolved DOWNWARD.

Kept pure — plain mappings, no `GameData`/`WorldState` — so the differential
harness can execute it against the Lean oracle. `ai/acquisition_cost` is the
impure wrapper that hoists `RouteOption`s out of `obtain_sources`.

INERT ON ARRIVAL. Nothing consumes this yet; `J` still calls `min_plan_length`.
That is deliberate — this project has twice shipped an epic whose green commits
were INERT because a second producer answered first
(`feedback_two_plan_producers`), so the model lands and is pinned by its own
tests BEFORE any consumer switches to it, and the switch is a separate commit
with its own live-trace check.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

UNOBTAINABLE_PER_UNIT = 10**6
"""Per-unit cost charged for an item with NO route at all.

Large enough that a chain containing one dominates any real alternative, so a
planner gate reading this bound prunes the chain — which is correct, because
`obtain_sources` naming no route means no action in the pool can serve it.

It is NOT infinity, and the difference matters: two unobtainable chains still
compare by how much OTHER work they carry, so a caller ranking candidates gets a
total order rather than a pile of ties. This mirrors `min_gathers`' existing
fuel-exhaustion convention of accounting the remaining need as raw work rather
than failing.

CAVEAT, RECORDED HONESTLY. `obtain_sources` is STATE-AWARE — it answers "how may
I obtain this RIGHT NOW". An item with no source this cycle (bank unreachable,
workshop unknown, event monster asleep) may be obtainable next cycle. Charging
this bound therefore risks OVER-estimating, the one direction the soundness
contract forbids. It is acceptable here only because every such gate is
re-evaluated every cycle, so the prune is temporary rather than a permanent
verdict. A consumer that CACHES this bound across cycles would break that
argument and must not.
"""


@dataclass(frozen=True)
class RouteOption:
    """One priced way to obtain the item this option is listed under.

    Hoisted from `obtain_sources.Source` by the impure wrapper, which is where
    game data and world state are read. This core sees only numbers.

    Attributes:
        kind: The `SourceKind` value, carried for diagnosis and for the census
            that checks every `SourceKind` has a price. Never decides anything
            here — the walk picks on cost alone, so adding a route kind cannot
            silently change an ordering.
        venue: A code identifying the TILE this route is served at (the resource,
            NPC, monster, or workshop code; the bank). Empty string for a route
            needing no travel. Two routes sharing a venue pay one hop between
            them — the whole reason this is a code and not a boolean.
        actions_per_application: Planner actions for ONE application of this
            route, EXCLUDING travel and excluding the inputs it consumes. One
            gather, one craft, one purchase, one withdraw, one unit-recycle are
            each 1; a DROP is `ceil(expected_kills) * cycles_per_kill`, already
            rounded to whole actions by the wrapper.
        yield_per: Units of the target obtained per application. `>= 1`.
        capacity: Units of the target this route can deliver right now.
            WITHDRAW and RECYCLE are genuinely stock-limited; the rest carry
            `obtain_sources.UNBOUNDED_CAPACITY`.
        inputs: Per-APPLICATION material demand, non-empty only for CRAFT. The
            AND arm of the walk: satisfying this option means also obtaining
            these, recursively.
        unlock: Key naming a PREREQUISITE this route must satisfy before its
            first application — currently a crafting-skill gate
            (`"skill:weaponcrafting:10"`). Empty when the route is ready now.
        unlock_actions: Actions to satisfy `unlock`, paid ONCE however many
            applications follow, and once across every route sharing the key.

    `venue` and `unlock` are the same mechanism at different prices: a
    ONE-TIME cost, keyed, paid the first time a plan needs it. Walking to the
    workshop costs 1; reaching weaponcrafting 10 costs the grind. Modelling the
    gate as a second pay-once key rather than as a new concept is what keeps
    "craft five daggers" from being charged the grind five times — the shape of
    error a per-application term would produce silently.
    """

    kind: str
    venue: str
    actions_per_application: int
    yield_per: int
    capacity: int
    inputs: Mapping[str, int] = field(default_factory=dict)
    unlock: str = ""
    unlock_actions: int = 0


def _cheapest_route(item: str, options: Mapping[str, list[RouteOption]],
                    memo: dict[str, tuple[int, RouteOption | None]],
                    active: frozenset[str]) -> tuple[int, RouteOption | None]:
    """`(unit cost, route)` for the cheapest way to obtain ONE `item`, memoised.

    THE FIX FOR THE BLOW-UP. The first version of this walk chose a route by
    re-walking the whole subtree per route AND, when a route's capacity fell
    short, re-entering the same node with that route removed from a REBUILT
    options mapping. Measured on a realistic holding, `adventurer_vest` — four
    recipe inputs, 82 routes in closure — made **10.1 million** recursive calls
    in 20 seconds without finishing, 2.09 million of them shortfall rebuilds.
    `copper_dagger` (one input) and `iron_sword` (two) finished in ~10ms. The
    cost was exponential in recipe FAN-OUT, which no fixture exercised because
    fixture holdings are small.

    Now each item's unit cost is computed ONCE and cached, so the walk is linear
    in the closure rather than exponential in its fan-out.

    CAPACITY IS DELIBERATELY IGNORED HERE. A capacity limit can only ever make
    acquisition MORE expensive (you exhaust the cheap route and fall back to a
    dearer one), so omitting it keeps this a sound LOWER bound — the direction
    the contract requires, since every consumer PRUNES with it. That is what
    retires the shortfall re-entry entirely rather than merely making it cheaper.
    The old model's mixed withdraw-then-craft plan was a tighter bound; it was
    not affordable, and a bound that does not return is worth nothing.

    `active` guards recipe cycles (`copper_bar` recycles out of a
    `copper_dagger`, which crafts from `copper_bar`): an item already being
    priced on this path is treated as unobtainable rather than recursed into."""
    if item in memo:
        return memo[item]
    routes = options.get(item, [])
    if not routes or item in active:
        return (UNOBTAINABLE_PER_UNIT, None)
    inner = active | {item}
    best: tuple[int, RouteOption | None] | None = None
    for route in routes:
        per_unit = -(-route.actions_per_application // max(1, route.yield_per))
        for material, per_application in route.inputs.items():
            unit, _ = _cheapest_route(material, options, memo, inner)
            per_unit += unit * per_application
        if route.unlock:
            per_unit += route.unlock_actions
        if best is None or per_unit < best[0]:
            best = (per_unit, route)
    # `best` starts at None, NOT at `UNOBTAINABLE_PER_UNIT`. A route whose inputs
    # are themselves unobtainable costs MORE than that sentinel, so seeding the
    # comparison with it discarded the route entirely and collapsed the whole
    # chain to one flat unobtainable — losing the other work it carries, and with
    # it the total order over bad chains that `acquisition_cost`'s finiteness
    # exists to give. Caught by
    # `test_unobtainable_is_finite_so_two_bad_chains_still_compare`.
    assert best is not None  # routes is non-empty here
    memo[item] = best
    return best


def _accumulate(item: str, qty: int, options: Mapping[str, list[RouteOption]],
                memo: dict[str, tuple[int, RouteOption | None]],
                owned: dict[str, int], paid: dict[str, int],
                actions: list[int], fuel: int) -> None:
    """Walk the demand closure once, crediting holdings and collecting the
    PAY-ONCE keys the plan touches.

    Holdings are consumed as they are credited, so a unit spent under one parent
    is not available to a sibling — the invariant that keeps this a bound on one
    coherent plan rather than on an optimistic superposition of plans.

    `paid` maps a pay-once key (a venue, or a skill unlock) to its price, so a
    key touched by several routes is charged once however many times it appears —
    a plan that gathers twenty ore walks to the node once, and a grind that
    unlocks a TIER is paid once for every recipe behind it."""
    if qty <= 0:
        return
    if fuel <= 0:
        # Fuel exhaustion means a CYCLE (an item bought with a currency bought
        # with that item). Charge it as unobtainable rather than returning
        # silently: a silent return prices an unservable loop at almost nothing,
        # which is the opposite of conservative and would make it the most
        # attractive route on the board. Matches `min_gathers`' convention of
        # accounting the remaining need as raw work when its own fuel runs out.
        actions[0] += UNOBTAINABLE_PER_UNIT * qty
        return
    held = owned.get(item, 0)
    used = min(held, qty)
    owned[item] = held - used
    remaining = qty - used
    if remaining <= 0:
        return
    _unit, route = _cheapest_route(item, options, memo, frozenset())
    if route is None:
        actions[0] += UNOBTAINABLE_PER_UNIT * remaining
        return
    applications = -(-remaining // max(1, route.yield_per))
    actions[0] += applications * route.actions_per_application
    if route.venue:
        paid.setdefault(route.venue, 1)
    if route.unlock:
        paid.setdefault(route.unlock, route.unlock_actions)
    for material, per_application in sorted(route.inputs.items()):
        _accumulate(material, per_application * applications, options, memo,
                    owned, paid, actions, fuel - 1)


def acquisition_cost(
    item: str,
    qty: int,
    options: Mapping[str, list[RouteOption]],
    owned: Mapping[str, int],
) -> int:
    """Lower bound on planner actions to obtain `qty` of `item`.

    `options[code]` is every route that can currently produce `code`; a code
    absent from the mapping has no route and is charged
    `UNOBTAINABLE_PER_UNIT` per unit. `owned` is credited (and consumed) first,
    on a private copy — the caller's mapping is never mutated.

    TWO PASSES, BOTH LINEAR. `_cheapest_route` memoises a per-item unit cost;
    `_accumulate` then walks the demand closure once, crediting holdings and
    collecting pay-once keys. Total = per-item actions + the pay-once keys the
    plan touched. See `_cheapest_route` for why the first version of this was
    exponential and what was given up to fix it.

    Fuel-bounded exactly as `min_gathers` is: the seed `len(options) + 1` cannot
    be exhausted by an acyclic route graph, since every recursing frame expands a
    distinct code along its path."""
    actions = [0]
    paid: dict[str, int] = {}
    _accumulate(item, qty, options, {}, dict(owned), paid, actions,
                len(options) + 1)
    return actions[0] + sum(paid.values())
