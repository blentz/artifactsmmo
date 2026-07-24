"""Bid-vs-craft decision: only post a GE buy order for an item when self-crafting
it would be SLOWER than the bid-fill horizon. A posted bid fills asynchronously, so
running a self-craft in parallel is wasted work — this gate (and the open_orders
suppression at the call site) keeps the two mutually exclusive.

Craft-time is estimated purely, in seconds, from static game data: deterministic
gather/craft legs summed directly; DROP legs valued at expected-kills × fight-cost
using the STATIC API drop rate (the A* fight-leg cost is rate-blind, so this
estimator folds the rate in itself). Refining the static rate with learned
drops-per-fight is a documented v2 (the learning store carries no drop rate today).

Built on the requirement-model unification's `RequirementGraph` / `demand_set`
(item-namespaced, drop-aware — see `requirement_graph.py`), not the older
`recipe_closure`, which returns RESOURCE codes (D1) and cannot represent a
drop-only leaf at all (D2). `game_data.requirement_graph.graph()` is the same
memoized accessor `craft_ladder.py` / `craft_plan_gen.py` / `strategy_driver.py`
already read.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.monster_drop_selection import MonsterDropCandidate, _expected_kills
from artifactsmmo_cli.ai.requirement_projections import demand_set
from artifactsmmo_cli.ai.source_kind import SourceKind

# Per-action second estimates aligned with the A* edge costs (combat.py / gathering.py).
_FIGHT_SECONDS = 10.0
_GATHER_SECONDS = 6.0
_CRAFT_SECONDS = 5.0


def closure_leaf_kinds(item: str, game_data: GameData) -> frozenset[SourceKind]:
    """Union of leaf `SourceKind`s over `item`'s full recipe closure — does
    obtaining it ultimately require monster DROPs, or only deterministic
    GATHER/BUY? A "leaf" is a closure material with no crafting recipe (not in
    `graph.edges`); CRAFT itself is an internal node, never a leaf."""
    graph = game_data.requirement_graph.graph()
    demand = demand_set(graph, [item]).quantities
    kinds: set[SourceKind] = set()
    for material in demand:
        if material not in graph.edges:
            kinds |= set(graph.sources(material))
    return frozenset(kinds)


def estimate_craft_seconds(item: str, qty: int, game_data: GameData) -> float:
    """Pure estimate of seconds to self-produce `qty` of `item`, folding the
    static drop rate into DROP legs. Deterministic legs (CRAFT, GATHER, and any
    other non-DROP leaf) cost their flat per-action seconds, scaled by the
    closure-demanded quantity of each material."""
    graph = game_data.requirement_graph.graph()
    demand = demand_set(graph, [item], {item: qty}).quantities
    total = 0.0
    for material, needed in demand.items():
        if material in graph.edges:
            total += _CRAFT_SECONDS * needed
            continue
        drops = game_data.monsters_dropping(material)
        if drops:
            candidates = [
                MonsterDropCandidate(monster_code=mob, rate=rate,
                                     min_quantity=min_q, max_quantity=max_q, distance=0)
                for mob, rate, min_q, max_q in drops
            ]
            expected_kills = min(_expected_kills(c) for c in candidates)
            total += float(expected_kills) * _FIGHT_SECONDS * needed
        else:
            total += _GATHER_SECONDS * needed
    return total


def should_bid(item: str, qty: int, bid_fill_horizon_s: float, game_data: GameData) -> bool:
    """Bid only when self-crafting is strictly slower than we are willing to
    wait for a fill (a live buy-anchor's existence is the caller's job to check
    via `buy_post_price`)."""
    return estimate_craft_seconds(item, qty, game_data) > bid_fill_horizon_s
