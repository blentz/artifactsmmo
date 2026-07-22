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

from artifactsmmo_cli.ai.requirement_graph import (
    RequirementGraph,
    _HasRequirementData,
    build_requirement_graph,
)


class RequirementGraphMemo:
    """Builds `RequirementGraph` on first use and caches it until inputs change."""

    def __init__(self, game_data: _HasRequirementData) -> None:
        self._game_data = game_data
        self._graph: RequirementGraph | None = None
        self._fingerprint: tuple[int, int, int] | None = None

    def _current_fingerprint(self) -> tuple[int, int, int]:
        """Sizes of the three source tables the graph is derived from."""
        return (
            len(self._game_data.crafting_recipes),
            len(self._game_data.all_item_stats),
            len(self._game_data.resource_drops_full),
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
        return self._graph

    def clear(self) -> None:
        """Drop the cache. Safe to call before any `graph()` call."""
        self._graph = None
        self._fingerprint = None
