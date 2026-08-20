"""Wave 8: the `obtain_sources` <-> `RequirementGraph.leaves` agreement.

`obtain_sources` is the ONE walk of the requirement-model unification epic that
is NOT migrated onto the graph, and legitimately so (R3). It is STATE-AWARE — it
returns the sources ready RIGHT NOW, in priority order, with codes and prices —
and it is pinned against the live planner action pool by two censuses at the
`StrategyArbiter.select` seam. The graph's `leaves` is deliberately its
STATE-FREE counterpart (capability, no readiness gating). Forcing the state-aware
walk onto the state-free graph would break that seam and lose the readiness the
censuses require.

But "kept separate" must not mean "unrelated" — the epic exists because no test
asserted any two walks agree. This test states the exact relationship that DOES
hold, so the pair is a documented agreement rather than an unchecked survivor:

  For every item, the STATE-FREE kinds `obtain_sources` can ever name
  (CRAFT / GATHER / BUY / DROP) are a SUBSET of the graph's `leaves`.

`obtain_sources` only ever GATES the same underlying game data the graph reads
(skill met, workshop known, live location, permanent vendor); it never invents a
capability the data does not support. So a kind it names must be one the graph's
capability set already contains. A violation would mean the graph is BLIND to a
real obtain route — which is exactly how the gold-only BUY leaf hid
currency-buyable items (jasper_crystal, cloth) until this invariant surfaced it.

WITHDRAW and RECYCLE are excluded: they are purely state-dependent kinds (bank
stock, licensed surplus) with no state-free capability to compare against — the
same carveout `obtain_parity_completeness` makes for WITHDRAW, widened to RECYCLE
because the graph's state-free `leaves` models neither (Wave 2 deviation 2).
"""

from __future__ import annotations

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_sources import obtain_sources
from artifactsmmo_cli.ai.requirement_projections import requirement_closure
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.world_state import SKILL_NAMES, WorldState
from artifactsmmo_cli.audit.craft_census import craftable_recipes

#: The kinds with a state-free capability counterpart in `leaves`. WITHDRAW and
#: RECYCLE are state-only (see module docstring).
_STATE_FREE = frozenset({SourceKind.CRAFT, SourceKind.GATHER,
                         SourceKind.BUY, SourceKind.DROP})
#: GE_FILL joins WITHDRAW and RECYCLE in the excluded set, and for the same
#: reason rather than by oversight: it is STATE-dependent. A GE fill exists only
#: while a specific standing sell order does, which is live world state exactly
#: as bank stock is — the graph's state-free `leaves` models capability, and
#: "someone currently has one listed" is not a capability of the item.
_EXCLUDED_AS_STATE_DEPENDENT = frozenset({
    SourceKind.WITHDRAW, SourceKind.RECYCLE, SourceKind.GE_FILL})


def _open_state(game_data: GameData) -> WorldState:
    """A high-capability state: max level, skills, and gold. Opens as many of
    `obtain_sources`' state gates as possible so the subset check is exercised
    against the WIDEST kind set the walk can produce, not a bare one."""
    return scenario_state(
        ScenarioCharacter(
            name="obtain_graph_agreement", level=40, gold=100_000,
            skills={skill: 40 for skill in SKILL_NAMES},
            inventory={}, bank={}, derive_combat_stats=True,
        ),
        game_data,
    )


@pytest.fixture(scope="module")
def closure_items(bundle_game_data: GameData) -> list[str]:
    graph = bundle_game_data.requirement_graph.graph()
    items: set[str] = set()
    for code in craftable_recipes(bundle_game_data):
        items |= requirement_closure(graph, [code])
    return sorted(items)


def test_every_source_kind_is_classified_state_free_or_state_dependent() -> None:
    """The two sets PARTITION `SourceKind` — total, and disjoint.

    Without this, adding a SourceKind silently omits it from `_STATE_FREE` and the
    subset invariant below goes quietly vacuous for the new route: it would assert
    nothing about the very kind just added. This is what made the census green
    rather than correct when GE_FILL landed. Anyone adding SourceKind 8 must
    classify it here, deliberately, and say why.

    SELL is neither: it obtains GOLD, not an item, so it has no `leaves` counterpart
    to be a subset of.
    """
    classified = _STATE_FREE | _EXCLUDED_AS_STATE_DEPENDENT | {SourceKind.SELL}

    assert not (_STATE_FREE & _EXCLUDED_AS_STATE_DEPENDENT), "a kind cannot be both"
    unclassified = set(SourceKind) - classified
    assert not unclassified, (
        f"unclassified SourceKind(s): {sorted(k.name for k in unclassified)} — "
        "add each to _STATE_FREE (the graph models it) or to "
        "_EXCLUDED_AS_STATE_DEPENDENT (it depends on live world state), with a reason")


def test_obtain_sources_state_free_kinds_are_a_subset_of_graph_leaves(
        bundle_game_data: GameData, closure_items: list[str]) -> None:
    graph = bundle_game_data.requirement_graph.graph()
    state = _open_state(bundle_game_data)
    violations: list[tuple[str, list[str]]] = []
    for item in closure_items:
        walk_kinds = {s.kind for s in obtain_sources(
            item, state, bundle_game_data, NO_PROFILE_CONTEXT)} & _STATE_FREE
        graph_kinds = graph.leaves.get(item, frozenset())
        extra = walk_kinds - graph_kinds
        if extra:
            violations.append((item, sorted(k.value for k in extra)))
    assert not violations, (
        "obtain_sources names a state-free kind the graph.leaves is blind to "
        f"(the graph under-reports a real obtain route): {violations[:10]}")


def _anchorable_vendor(item: str, game_data: GameData) -> bool:
    """Does SOME permanent, placed NPC sell `item`? This mirrors the reachability
    precondition `_buy_sources` applies (`obtain_sources.py:272-275`) as a pure
    DATA predicate — it never consults the walk, so a witness chosen with it
    still tests walk behaviour rather than restating it.

    The graph's `leaves` deliberately does NOT apply this gate: it is the
    state-free CAPABILITY view, and a vendor's map placement is world state. So
    the bundle legitimately contains currency-buy items the walk names nothing
    for — all three are sold only by `sorceress`, an NPC with no tile."""
    return any(
        not game_data.is_event_npc(npc_code)
        and game_data.npc_location(npc_code) is not None
        for npc_code, _price, _currency in game_data.npc_purchases(item)
    )


def test_the_invariant_can_fail(bundle_game_data: GameData) -> None:
    """Falsifiability witness: a graph whose BUY leaf reverts to the gold-only
    view must FAIL the subset check, proving it measures real divergence and not
    a tautology. This is the exact regression the Wave 8 fix removed."""
    graph = bundle_game_data.requirement_graph.graph()
    state = _open_state(bundle_game_data)
    # A currency-buyable item: obtain_sources names BUY, and the graph now agrees.
    # `graph.leaves` iterates in hash order, so the witness is taken from a
    # SORTED list: an unsorted `[0]` picked a different item per process and hit
    # an unanchorable one (`sorceress`) in ~9% of runs.
    currency_buys = sorted(
        item for item in graph.leaves
        if SourceKind.BUY in graph.leaves[item]
        and not bundle_game_data.npcs_selling_item(item)  # gold view is blind
        and bundle_game_data.npc_purchases(item)          # but a currency vendor sells it
        and _anchorable_vendor(item, bundle_game_data)    # and the walk can reach it
    )
    assert currency_buys, "no currency-only buy in the bundle — witness is vacuous"
    item = currency_buys[0]
    walk_kinds = {s.kind for s in obtain_sources(
        item, state, bundle_game_data, NO_PROFILE_CONTEXT)} & _STATE_FREE
    # obtain_sources names BUY for this currency-only item...
    assert SourceKind.BUY in walk_kinds
    # ...and a graph whose BUY leaf reverted to the gold-only view would NOT
    # cover it: the subset check would fail. This is what the fix removed.
    gold_only_leaf = graph.leaves[item] - {SourceKind.BUY}
    assert walk_kinds - gold_only_leaf == {SourceKind.BUY}
