"""Static per-item recipe-cost memo over the proved `closure_demand`.

`RecipeCostMemo` lazily computes and caches the transitive recipe demand for a
single unit of any item. The cache is keyed on item code; a second call with the
same code returns the SAME dict object (identity). `clear()` drops the cache so
a recipe reload invalidates stale entries.

The memo delegates ALL computation to the live `closure_demand` function
(formal/Formal/TaskReservation.lean `closureDemand`); it adds no logic of its
own. The differential test in formal/diff/test_recipe_cost_memo_diff.py pins
memo ≡ closure_demand over random acyclic recipe DAGs.
"""

from __future__ import annotations

from artifactsmmo_cli.ai.recipe_closure import closure_demand


class RecipeCostMemo:
    """Memoized transitive recipe demand for one unit of any item.

    Wraps the proved `closure_demand` function; adds only a dict-keyed cache.
    Call `clear()` when the recipe set changes to force recomputation.
    """

    def __init__(self, game_data: object) -> None:
        self._game_data = game_data
        self._cache: dict[str, dict[str, int]] = {}

    def full_cost(self, item: str) -> dict[str, int]:
        """Return the memoized full transitive demand for ONE unit of `item`.

        On a cache miss, delegates to `closure_demand(item, 1, ...)` and
        caches the result. A second call with the same `item` returns the same
        dict object (identity check passes). The returned dict must not be
        mutated by callers.
        """
        if item not in self._cache:
            out: dict[str, int] = {}
            closure_demand(item, 1, self._game_data, out, frozenset())  # type: ignore[arg-type]
            self._cache[item] = out
        return self._cache[item]

    def clear(self) -> None:
        """Drop the entire cache. Safe to call before any full_cost call."""
        self._cache.clear()
