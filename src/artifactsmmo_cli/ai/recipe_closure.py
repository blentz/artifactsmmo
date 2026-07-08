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
`crafting_recipes` / `resource_drops` accessors and forwarding. GAP-7
(2026-07-08): `recipe_closure` additionally slices `resource_drops_full` into
single-drop layers and unions the pure core's `needed_resources` verdict
across them (see `_secondary_drop_layers`) — the widening is pure input
construction; the cores and their Lean images are unchanged.

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

from collections.abc import Container, Iterable, Mapping
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
    def craft_yields(self) -> Mapping[str, int]: ...

    @property
    def resource_drops(self) -> Mapping[str, str]: ...

    @property
    def resource_drops_full(self) -> Mapping[str, list[tuple[str, int, int, int]]]: ...


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
               yields: Mapping[str, int], visited: dict[str, int]) -> int:
    """Total raw-resource quantity gathered to craft one `item`, multiplying
    ingredient quantities down the recipe tree. A raw (gathered) or unknown
    item costs 1. `visited` is PER-PATH (each child gets a copy extended with
    `item`), so cyclic recipes terminate via the revisit guard (revisit -> 1).

    `yields` maps item code to output quantity per craft run (default 1 when
    absent). Per-item raw cost = ⌈(raw inputs per batch) / Y⌉ where Y is the
    node's yield. Consistent with `_closure_demand`'s ceil-batch semantics."""
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
        total = total + qty * _raw_units(fuel - 1, sub, recipes, yields, deeper)
    y = yields.get(item, 1)
    return -(-total // y)  # ⌈total / y⌉


def _closure_demand(fuel: int, root: str, multiplier: int,
                    recipes: Mapping[str, dict[str, int]],
                    yields: Mapping[str, int],
                    visited: dict[str, int], out: dict[str, int]) -> dict[str, int]:
    """Accumulate the recipe-closure demand of `root` (x `multiplier`) into the
    THREADED `out` map: the root and every transitive material at its cumulative
    required quantity (max across contributing paths). `visited` is PER-PATH
    (each child walk gets a copy extended with `root`), so cyclic recipes
    terminate; zero/negative-quantity edges are skipped.

    `yields` maps item code to output quantity per craft run (default 1 when
    absent). Children scale by ⌈multiplier / Y⌉ × qty_per (ceil-batch
    semantics): to produce `multiplier` of a yield-Y node we need ⌈m/Y⌉ craft
    runs, each consuming `qty_per` of each ingredient."""
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
    y = yields.get(root, 1)
    batches = -(-multiplier // y)  # ⌈multiplier / y⌉ craft runs needed
    for mat, qty_per in recipe.items():
        if qty_per <= 0:
            continue
        out = _closure_demand(fuel - 1, mat, batches * qty_per, recipes, yields,
                              sub_visited, out)
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


def _secondary_drop_layers(
    primary: Mapping[str, str],
    full: Mapping[str, list[tuple[str, int, int, int]]],
) -> list[dict[str, str]]:
    """Layer the multi-drop table into single-drop maps the PURE CORE can eat.

    GAP-7 (2026-07-08): `needed_resources` was fed from the primary
    `resource_drops` map only (one rate-best drop per resource), so rare
    SECONDARY drops — small_pearls off trout/bass/salmon fishing spots, gem
    stones off ordinary rocks — never marked their resource as needed and the
    factory's targeted secondary-drop GatherActions were filtered out of every
    GatherMaterials plan (the goal-layer analog of GAP-2's
    `objective._gatherable` blindness, fixed the same day at that layer).

    The proven core's `drops` input is a one-drop-per-resource association
    map, so the widening happens HERE, at input construction: layer k maps
    each resource to its k-th secondary drop (dedup'd, primary excluded,
    table order preserved). The caller unions `needed_resources` across one
    pure-core run per layer — a resource is needed iff ANY of its drops is in
    the closure, and each per-layer verdict is the proven judgment. The pure
    core, its Lean mirror and the diff harness stay byte-identical.
    """
    pending: dict[str, list[str]] = {}
    for res, table in full.items():
        prim = primary.get(res)
        extras: list[str] = []
        for item, _rate, _mn, _mx in table:
            if item != prim and item not in extras:
                extras.append(item)
        if extras:
            pending[res] = extras
    layers: list[dict[str, str]] = []
    depth = max((len(items) for items in pending.values()), default=0)
    for k in range(depth):
        layers.append({res: items[k] for res, items in pending.items()
                       if k < len(items)})
    return layers


def recipe_closure(game_data: _HasRecipes, roots: Iterable[str]) -> tuple[set[str], set[str]]:
    """Return (needed_resources, craftable_mats) for producing every item in roots.

    needed_resources: resource codes SOME drop of which (primary or secondary —
                      see `_secondary_drop_layers`) is a material in the closure.
    craftable_mats:    item codes in the closure that have a crafting recipe.
    """
    root_list = list(roots)
    recipes = game_data.crafting_recipes
    needed, craftable = recipe_closure_pure(root_list, recipes,
                                            game_data.resource_drops)
    # GAP-7: union in the resources reachable only via secondary drops. Each
    # layer is a valid pure-core input; craftable_mats is drop-independent so
    # the first run's result stands.
    for layer in _secondary_drop_layers(game_data.resource_drops,
                                        game_data.resource_drops_full):
        extra_needed, _craftable = recipe_closure_pure(root_list, recipes, layer)
        needed |= extra_needed
    return needed, craftable


def gather_serves_closure(resource_code: str, drop_item_override: str | None,
                          primary_drops: Mapping[str, str],
                          closure_materials: Container[str]) -> bool:
    """GAP-7 admission precision: a GatherAction serves a recipe closure iff
    the item it SIMULATES producing — `drop_item_override` when set (the
    factory's targeted secondary-drop variant), else the resource's primary
    drop — is a closure material.

    The pre-GAP-7 goal-layer admission (`resource_code in needed_resources`)
    admits EVERY drop-variant of a needed resource. With `needed_resources`
    widened to the full drop set that fanned out: any resource with one
    relevant secondary dragged its primary gather and every other secondary
    variant into the search (derived 2026-07-08: CraftPotionsGoal flooded to
    the 70-98K-node cap on four scenarios — the fishing spots' algae arm).
    Admission by EFFECTIVE drop keeps exactly the variants that can satisfy
    the goal; for primary gathers it is equivalent to the old resource-set
    test (a resource was needed iff its primary drop was in the closure).
    """
    effective = drop_item_override if drop_item_override is not None \
        else primary_drops.get(resource_code)
    return effective is not None and effective in closure_materials


def raw_material_units(
    game_data: _HasRecipes,
    item: str,
    visited: frozenset[str] | None = None,
    yields: Mapping[str, int] | None = None,
) -> int:
    """Total raw-resource quantity gathered to craft one `item`, multiplying
    ingredient quantities down the recipe tree. A raw (gathered) or unknown item
    costs 1. Cyclic recipes terminate via the visited guard (revisit -> 1).

    `yields` maps item code to output quantity per craft run; omit (or pass None)
    for all-Y=1 behaviour (today's data, exact no-op)."""
    visited = visited or frozenset()
    recipes = game_data.crafting_recipes
    return _raw_units(len(recipes) + 1, item, recipes,
                      yields if yields is not None else game_data.craft_yields,
                      {code: 1 for code in visited})


def closure_demand(
    root: str,
    multiplier: int,
    game_data: _HasRecipes,
    out: dict[str, int],
    visited: frozenset[str],
    yields: Mapping[str, int] | None = None,
) -> None:
    """Accumulate the recipe-closure demand of `root` (x `multiplier`) into
    `out`. The root itself and every transitive material are recorded at their
    cumulative required quantity (max across roots). Cycle-safe via `visited`.

    `yields` maps item code to output quantity per craft run; omit (or pass None)
    for all-Y=1 behaviour (today's data, exact no-op).

    The ONE shared closure-demand implementation: `inventory_profile` (soft
    keep-targets) and `task_reservation` (step-tier reservation) both consume
    it. Mirrored by the proved Lean `closureDemand`
    (formal/Formal/TaskReservation.lean)."""
    recipes = game_data.crafting_recipes
    result = _closure_demand(len(recipes) + 1, root, multiplier, recipes,
                             yields if yields is not None else game_data.craft_yields,
                             {code: 1 for code in visited}, dict(out))
    out.clear()
    out.update(result)
