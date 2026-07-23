"""Lazily-built, self-invalidating `RequirementGraph` accessor.

Placement follows the `RecipeCostMemo` precedent (epic §4.4): a lazily-built
derived structure over the whole recipe table, hung off `GameData`, read-only.
`CACHE_VERSION` does not change — the graph is DERIVED from already-cached data,
never fetched, and the on-disk bundle shape is untouched.

ONE DELIBERATE IMPROVEMENT ON THE PRECEDENT
-------------------------------------------
`RecipeCostMemo` is invalidated only by the `_crafting_recipes` property SETTER,
which fires on rebinding. But `GameData._build_items` and `_build_resources`
populate their maps by IN-PLACE assignment (`game_data.py:1470`, `:1633`), so a
load mutates the source data without ever tripping that setter. The precedent
therefore has a latent staleness window; it is benign today only because nothing
reads `recipe_cost` mid-load.

Copying that would ship a second cache with the same hole. Instead this memo
carries a cheap FINGERPRINT of its inputs and rebuilds when it changes. Three
`len()` calls per access is nothing against a graph build, and it means an
in-place load cannot silently serve a stale graph. The `clear()` hook is kept so
the existing rebind invalidation still works and the precedent still holds.

A fingerprint over sizes catches growth — which is what a load does. It cannot
catch an in-place edit that leaves every size unchanged; `clear()` remains the
contract for that case.
"""

from __future__ import annotations

from collections.abc import Mapping

from artifactsmmo_cli.ai.requirement_graph import (
    RequirementGraph,
    _HasRequirementData,
    build_requirement_graph,
)
from artifactsmmo_cli.ai.requirement_projections import demand_set, requirement_closure
from artifactsmmo_cli.ai.source_kind import SourceKind

#: The synthetic char-progression token in an enriched requirement multiset:
#: its demand-weight is the number of DROP leaves in a root's closure (work that
#: routes through monster kills). Namespaced so it never collides with an item
#: code. Synergy spec 2026-07-19 §3.10 (closure-count weighting, 2026-07-23).
CHAR_XP = "char_xp"

#: Prefix for a synthetic craft/gather-skill token; the suffix is the skill name.
SKILL_PREFIX = "skill:"


class RequirementGraphMemo:
    """Builds `RequirementGraph` on first use and caches it until inputs change."""

    def __init__(self, game_data: _HasRequirementData) -> None:
        self._game_data = game_data
        self._graph: RequirementGraph | None = None
        self._fingerprint: tuple[int, int, int, int] | None = None
        self._demand_cache: dict[str, Mapping[str, int]] = {}
        self._multiset_cache: dict[str, Mapping[str, int]] = {}

    def _current_fingerprint(self) -> tuple[int, int, int, int]:
        """Sizes of the source tables the graph is derived from."""
        return (
            len(self._game_data.crafting_recipes),
            len(self._game_data.all_item_stats),
            len(self._game_data.resource_drops_full),
            len(self._game_data.craft_yields),
        )

    def graph(self) -> RequirementGraph:
        """The current graph, rebuilding if the source tables have grown.

        Repeated calls with unchanged inputs return the SAME object (identity),
        matching `RecipeCostMemo.full_cost`'s contract. The result must not be
        mutated by callers.
        """
        fingerprint = self._current_fingerprint()
        if self._graph is None or self._fingerprint != fingerprint:
            self._graph = build_requirement_graph(self._game_data)
            self._fingerprint = fingerprint
            self._demand_cache = {}     # graph rebuilt -> per-code demands stale
            self._multiset_cache = {}
        return self._graph

    def demand_for(self, code: str) -> Mapping[str, int]:
        """Memoized demand-weighted requirement multiset (item -> quantity) for
        a single root item, `demand_set(graph, [code]).quantities`. The synergy
        B-assembly (spec 2026-07-19 §3.6) computes ~N of these per cycle; caching
        per code honours the feather_coat CPU precedent (residual R3). The cache
        is invalidated with the graph (a rebuilt graph drops it), so it never
        serves a demand from a stale graph."""
        self.graph()   # revalidates the cache against the current fingerprint
        if code not in self._demand_cache:
            self._demand_cache[code] = demand_set(self.graph(), [code]).quantities
        return self._demand_cache[code]

    def requirement_multiset_for(self, code: str) -> Mapping[str, int]:
        """The ENRICHED requirement multiset for synergy overlap (spec §3.10,
        closure-count weighting): item quantities (as `demand_for`) PLUS synthetic
        tokens, so that skill and character-level alignment count alongside shared
        materials. Each token's weight is how much of the root's work it stands
        for — self-scaling, no tuned constant:

        * ``skill:<name>`` — the number of closure items gated by that craft or
          gather skill. Lets a task needing skill X raise gear whose closure
          consumes X (task/grind convergence).
        * ``char_xp`` — the number of DROP leaves in the closure (work that routes
          through monster kills). Lets a drop-routed candidate align with the
          char-level trunk (level-up preference).

        * a CURRENCY item — for a buy-only closure item (e.g. an artifact bought
          from an NPC), the price in its currency, weighted by how many are
          demanded. Without this the real cost of a buy-only root is INVISIBLE to
          synergy: its recipe closure is just itself (`prerequisites` leafs it), so
          an expensive currency grind (e.g. 100 event_ticket per lich_race_medal)
          would score as a one-token root and never be recognised as work that
          serves nothing else. The currency is a real item code, so it overlaps
          other roots' demand naturally.

        Synthetic tokens are namespaced (``skill:`` / ``char_xp``) so they never
        collide with item codes. Memoized with the graph."""
        if code not in self._multiset_cache:
            graph = self.graph()
            out: dict[str, int] = dict(self.demand_for(code))
            closure = requirement_closure(graph, [code])
            for item in closure:
                craft = graph.craft_skill.get(item)
                if craft is not None:
                    key = SKILL_PREFIX + craft[0]
                    out[key] = out.get(key, 0) + 1
                gather = graph.gather_skill.get(item)
                if gather is not None:
                    key = SKILL_PREFIX + gather[0]
                    out[key] = out.get(key, 0) + 1
                if SourceKind.BUY in graph.leaves.get(item, frozenset()):
                    purchases = self._game_data.npc_purchases(item)
                    if purchases:
                        # cheapest buy route's currency cost (price * quantity
                        # demanded) — the real work behind a buy-only item.
                        _npc, price, currency = min(purchases, key=lambda p: p[1])
                        out[currency] = out.get(currency, 0) + price * out.get(item, 1)
            drop_leaves = sum(1 for item in closure
                              if SourceKind.DROP in graph.leaves.get(item, frozenset()))
            if drop_leaves:
                out[CHAR_XP] = drop_leaves
            self._multiset_cache[code] = out
        return self._multiset_cache[code]

    def clear(self) -> None:
        """Drop the cache. Safe to call before any `graph()` call."""
        self._graph = None
        self._fingerprint = None
        self._demand_cache = {}
        self._multiset_cache = {}
