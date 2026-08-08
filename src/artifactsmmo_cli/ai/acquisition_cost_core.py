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


@dataclass(frozen=True)
class _Walk:
    """Threaded walk state: actions so far, holdings not yet spent, and the
    PAY-ONCE keys already settled (venue hops and unlock prerequisites share one
    set, because they are the same mechanism at different prices). Immutable at
    the boundary, copied on entry, so a caller's dicts are never mutated — the
    same contract `min_gathers` keeps."""

    actions: int
    owned: dict[str, int]
    venues: set[str]


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
    on a private copy.

    Fuel-bounded exactly as `min_gathers` is, and for the same reason: the
    recursion must be structural for the extracted Lean model. The seed
    `len(options) + 1` cannot be exhausted by an acyclic route graph, since
    every recursing frame expands a distinct code along its path. A CYCLIC one
    — an item craftable from a material that is bought with a currency bought
    with that item — terminates with the remaining need charged as
    unobtainable, which is conservative in the safe direction."""
    walk = _obtain(len(options) + 1, item, qty, options,
                   _Walk(0, dict(owned), set()))
    return walk.actions


def _obtain(fuel: int, item: str, qty: int,
            options: Mapping[str, list[RouteOption]], walk: _Walk) -> _Walk:
    """Add the cost of one `(item, qty)` node to the threaded walk.

    Held copies are consumed FIRST and are not available to a sibling branch —
    a unit credited under one parent cannot also satisfy another, which is the
    invariant that keeps this a bound on a single coherent plan rather than on
    an optimistic superposition of plans."""
    if fuel <= 0:
        return _Walk(walk.actions + UNOBTAINABLE_PER_UNIT * qty, walk.owned,
                     walk.venues)

    held = walk.owned.get(item, 0)
    used = min(held, qty)
    remaining = qty - used
    owned = dict(walk.owned)
    owned[item] = held - used
    walk = _Walk(walk.actions, owned, walk.venues)
    if remaining <= 0:
        return walk

    routes = options.get(item, [])
    if not routes:
        return _Walk(walk.actions + UNOBTAINABLE_PER_UNIT * remaining,
                     walk.owned, walk.venues)

    # OR over routes: cost each independently from the SAME entry state, then
    # keep the cheapest. Each branch gets its own copy of the walk, so a route
    # we did not take cannot leave its spent holdings or paid venues behind —
    # the bug that would let an unchosen craft's material consumption make the
    # chosen gather look cheaper than it is.
    best: _Walk | None = None
    for route in routes:
        candidate = _apply(fuel, item, remaining, route, options, walk)
        if best is None or candidate.actions < best.actions:
            best = candidate
    assert best is not None  # routes is non-empty here
    return best


def _apply(fuel: int, item: str, need: int, route: RouteOption,
           options: Mapping[str, list[RouteOption]], walk: _Walk) -> _Walk:
    """Cost of satisfying `need` units of `item` through ONE route.

    A route bounded by `capacity` can only cover part of the need; the
    REMAINDER falls back to the other routes via a recursive `_obtain` against
    the options WITHOUT this one. That is what makes a half-full bank produce a
    mixed withdraw-then-gather plan rather than either an over-optimistic
    "withdraw it all" or a pessimistic "ignore the bank"."""
    covered = min(need, route.capacity)
    applications = -(-covered // route.yield_per)  # ceil

    paid = set(walk.venues)
    once = 0
    if route.venue and route.venue not in paid:
        paid.add(route.venue)
        once += 1
    if route.unlock and route.unlock not in paid:
        paid.add(route.unlock)
        once += route.unlock_actions

    inner = _Walk(walk.actions + once + applications * route.actions_per_application,
                  walk.owned, paid)

    # AND over this route's inputs, once per application.
    for material, per_application in sorted(route.inputs.items()):
        inner = _obtain(fuel - 1, material, per_application * applications,
                        options, inner)

    shortfall = need - covered
    if shortfall <= 0:
        return inner
    without = {code: [r for r in routes if r is not route]
               for code, routes in options.items()}
    return _obtain(fuel - 1, item, shortfall, without, inner)
