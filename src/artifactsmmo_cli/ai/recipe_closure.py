"""Recipe-closure helpers: the gather/craft action scope for producing items.

Walks an item's crafting recipe down to its gathered resources, returning the
set of resource codes to gather and the set of intermediate item codes to
craft. Goals use this to restrict the planner's branching factor to the actions
that can actually contribute to producing a target item, instead of every
gather/craft in the game.

PURE CORES (mechanical-extraction P3a): the recipe walks are pure functions
over plain data (`recipes` mapping, `drops` mapping) so they can be
mechanically extracted to Lean (`formal/Formal/Extracted/RecipeClosure.lean`)
and bridged against the hand model `formal/Formal/RecipeClosure.lean`. The
public wrappers preserve the original GameData-taking API exactly, reading the
`crafting_recipes` / `resource_drops` accessors and forwarding.

The recursions are FUEL-BOUNDED (the shopping_list precedent): each core
threads an explicit `fuel` seeded with `len(recipes) + 1`, which no input can
exhaust — every frame that recurses marks a DISTINCT recipe key in its visited
set first (threaded for `_closure_visited`, per-path for `_raw_units` /
`_closure_demand`), so recursion depth never exceeds `len(recipes) + 1` even
on cyclic recipe graphs. The bound exists so the extracted Lean model recurses
structurally on a `Nat` fuel.

Visited sets are insertion-ordered `dict[str, int]` membership maps
(`code -> 1`) rather than Python sets: the extracted image is an association
list, and all reads go through order-independent `dict.get`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Protocol, runtime_checkable


@runtime_checkable
class _HasRecipes(Protocol):
    """Structural subset of GameData used by the public recipe-closure wrappers.

    A Protocol avoids importing GameData here, which would create a circular
    dependency when GameData imports recipe_cost_memo which imports this module.
    All concrete callers pass a GameData instance, which satisfies this protocol
    via structural subtyping.
    """

    @property
    def crafting_recipes(self) -> Mapping[str, dict[str, int]]: ...

    @property
    def resource_drops(self) -> Mapping[str, str]: ...


def _closure_visited(fuel: int, material: str, recipes: Mapping[str, dict[str, int]],
                     visited: dict[str, int]) -> dict[str, int]:
    """DFS-mark `material` and every transitive recipe sub-material into the
    THREADED `visited` membership map (the shared visited set of the original
    closure DFS). Returns the updated map; cycle-safe via the revisit guard."""
    if fuel <= 0:
        return visited
    if visited.get(material, 0) == 1:
        return visited
    visited[material] = 1
    recipe = recipes.get(material, {})
    for sub_mat, _qty in recipe.items():
        visited = _closure_visited(fuel - 1, sub_mat, recipes, visited)
    return visited


def _raw_units(fuel: int, item: str, recipes: Mapping[str, dict[str, int]],
               visited: dict[str, int]) -> int:
    """Total raw-resource quantity gathered to craft one `item`, multiplying
    ingredient quantities down the recipe tree. A raw (gathered) or unknown
    item costs 1. `visited` is PER-PATH (each child gets a copy extended with
    `item`), so cyclic recipes terminate via the revisit guard (revisit -> 1)."""
    if fuel <= 0:
        return 1
    if visited.get(item, 0) == 1:
        return 1
    recipe = recipes.get(item, {})
    if len(recipe) == 0:
        return 1
    deeper = dict(visited)
    deeper[item] = 1
    total = 0
    for sub, qty in recipe.items():
        total = total + qty * _raw_units(fuel - 1, sub, recipes, deeper)
    return total


def _closure_demand(fuel: int, root: str, multiplier: int,
                    recipes: Mapping[str, dict[str, int]],
                    visited: dict[str, int], out: dict[str, int]) -> dict[str, int]:
    """Accumulate the recipe-closure demand of `root` (x `multiplier`) into the
    THREADED `out` map: the root and every transitive material at its cumulative
    required quantity (max across contributing paths). `visited` is PER-PATH
    (each child walk gets a copy extended with `root`), so cyclic recipes
    terminate; zero/negative-quantity edges are skipped."""
    if fuel <= 0:
        return out
    if visited.get(root, 0) == 1:
        return out
    sub_visited = dict(visited)
    sub_visited[root] = 1
    # Record the root at its own demanded quantity (max across contributors).
    if multiplier > out.get(root, 0):
        out[root] = multiplier
    recipe = recipes.get(root, {})
    for mat, qty_per in recipe.items():
        if qty_per <= 0:
            continue
        out = _closure_demand(fuel - 1, mat, multiplier * qty_per, recipes, sub_visited, out)
    return out


def recipe_closure_pure(roots: list[str], recipes: Mapping[str, dict[str, int]],
                        drops: Mapping[str, str]) -> tuple[set[str], set[str]]:
    """Pure core of `recipe_closure` over plain data: DFS-mark the closure of
    `roots`, then read off the two output sets.

    needed_resources: resource codes whose drop is some material in the closure.
    craftable_mats:    item codes in the closure that have a crafting recipe.
    """
    visited: dict[str, int] = {}
    for root in roots:
        visited = _closure_visited(len(recipes) + 1, root, recipes, visited)
    needed_resources: set[str] = {res for res, drop in drops.items()
                                  if visited.get(drop, 0) == 1}
    craftable_mats: set[str] = {mat for mat, _used in visited.items()
                                if len(recipes.get(mat, {})) > 0}
    return needed_resources, craftable_mats


def recipe_closure(game_data: _HasRecipes, roots: Iterable[str]) -> tuple[set[str], set[str]]:
    """Return (needed_resources, craftable_mats) for producing every item in roots.

    needed_resources: resource codes whose drop is some material in the closure.
    craftable_mats:    item codes in the closure that have a crafting recipe.
    """
    return recipe_closure_pure(list(roots), game_data.crafting_recipes,
                               game_data.resource_drops)


def raw_material_units(game_data: _HasRecipes, item: str, visited: frozenset[str] | None = None) -> int:
    """Total raw-resource quantity gathered to craft one `item`, multiplying
    ingredient quantities down the recipe tree. A raw (gathered) or unknown item
    costs 1. Cyclic recipes terminate via the visited guard (revisit -> 1)."""
    visited = visited or frozenset()
    recipes = game_data.crafting_recipes
    return _raw_units(len(recipes) + 1, item, recipes, {code: 1 for code in visited})


def closure_demand(root: str, multiplier: int, game_data: _HasRecipes,
                   out: dict[str, int], visited: frozenset[str]) -> None:
    """Accumulate the recipe-closure demand of `root` (x `multiplier`) into
    `out`. The root itself and every transitive material are recorded at their
    cumulative required quantity (max across roots). Cycle-safe via `visited`.

    The ONE shared closure-demand implementation: `inventory_profile` (soft
    keep-targets) and `task_reservation` (step-tier reservation) both consume
    it. Mirrored by the proved Lean `closureDemand`
    (formal/Formal/TaskReservation.lean)."""
    recipes = game_data.crafting_recipes
    result = _closure_demand(len(recipes) + 1, root, multiplier, recipes,
                             {code: 1 for code in visited}, dict(out))
    out.clear()
    out.update(result)
