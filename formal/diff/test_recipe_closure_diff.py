"""Differential test: real Python `recipe_closure` / `raw_material_units` must
agree with the proved Lean oracle over random finite recipe graphs.

`recipe_closure(game_data, roots)` does a DFS over `_crafting_recipes` (item ->
{sub: qty}) and `_resource_drops` (resource -> drop_item), returning
`(needed_resources, craftable_mats)`. `raw_material_units(game_data, item)`
recursively sums `qty * units(sub)` with a visited guard making revisits / raw
items cost 1 (cyclic-safe).

We use integer item/resource codes (the model uses `Nat`) and a controlled fake
GameData exposing only `_crafting_recipes` and `_resource_drops`. The same
recipe graph is encoded for the Lean oracle (flat int args). We assert:
* `needed_resources` sets match,
* `craftable_mats` sets match,
* `raw_material_units(query)` values match,
over >= 200 random graphs including CYCLIC and DIAMOND shapes.
"""
import random

from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.recipe_closure import raw_material_units, recipe_closure
from formal.diff.oracle_client import run_oracle


class _FakeGameData:
    def __init__(self, recipes: dict[int, dict[int, int]], drops: dict[int, int]):
        self._crafting_recipes = {str(k): {str(s): q for s, q in v.items()} for k, v in recipes.items()}
        self._resource_drops = {str(r): str(d) for r, d in drops.items()}

    def crafting_recipe(self, code: str) -> dict[str, int] | None:
        return self._crafting_recipes.get(code)

    @property
    def resource_drops(self) -> dict[str, str]:
        return self._resource_drops


def _encode_args(recipes: dict[int, dict[int, int]], drops: dict[int, int],
                 roots: list[int], query: int, fuel: int) -> list[int]:
    triples: list[int] = []
    n_recipe = 0
    for item, sub_map in recipes.items():
        for sub, qty in sub_map.items():
            triples += [item, sub, qty]
            n_recipe += 1
    drop_pairs: list[int] = []
    for res, drop in drops.items():
        drop_pairs += [res, drop]
    args = [n_recipe] + triples + [len(drops)] + drop_pairs + [len(roots)] + roots + [query, fuel]
    return args


def _run(recipes, drops, roots, query, fuel):
    gd = _FakeGameData(recipes, drops)
    needed, craft = recipe_closure(gd, [str(x) for x in roots])
    py_needed = sorted(int(x) for x in needed)
    py_craft = sorted(int(x) for x in craft)
    py_units = raw_material_units(gd, str(query))

    args = _encode_args(recipes, drops, roots, query, fuel)
    lean = run_oracle("recipe_closure", [args])[0]
    return py_needed, py_craft, py_units, lean


def _rand_graph(rng: random.Random, allow_cycle: bool):
    """Random recipe graph over item codes 0..n. Edges go to any item (cycles
    possible when allow_cycle); qty in 1..5. Some items are raw (no recipe).
    Resource drops map distinct resource codes to item codes."""
    n = rng.randint(1, 8)
    items = list(range(n))
    recipes: dict[int, dict[int, int]] = {}
    for it in items:
        if rng.random() < 0.5:  # this item has a recipe
            n_sub = rng.randint(1, 3)
            subs: dict[int, int] = {}
            for _ in range(n_sub):
                if allow_cycle:
                    sub = rng.randint(0, n - 1)
                else:
                    # acyclic: only point to strictly higher codes
                    if it + 1 > n - 1:
                        continue
                    sub = rng.randint(it + 1, n - 1)
                if sub != it or allow_cycle:
                    subs[sub] = rng.randint(1, 5)
            if subs:
                recipes[it] = subs
    # resource drops: resource codes 100.. map to some item code
    drops: dict[int, int] = {}
    n_drops = rng.randint(0, 5)
    for d in range(n_drops):
        drops[100 + d] = rng.randint(0, n - 1)
    roots = [rng.choice(items) for _ in range(rng.randint(1, 3))]
    query = rng.choice(items)
    fuel = 2 * n + 4  # >= reachable depth; plenty for the visited-set recursion
    return recipes, drops, roots, query, fuel


@settings(max_examples=240, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
def test_python_matches_lean(seed):
    rng = random.Random(seed)
    allow_cycle = rng.random() < 0.5
    recipes, drops, roots, query, fuel = _rand_graph(rng, allow_cycle)
    py_needed, py_craft, py_units, lean = _run(recipes, drops, roots, query, fuel)
    ctx = (f"recipes={recipes} drops={drops} roots={roots} query={query} "
           f"allow_cycle={allow_cycle}")
    assert py_needed == sorted(lean["needed_resources"]), f"needed mismatch: {ctx} lean={lean}"
    assert py_craft == sorted(lean["craftable_mats"]), f"craftable mismatch: {ctx} lean={lean}"
    assert py_units == lean["raw_material_units"], f"units mismatch: {ctx} lean={lean}"


def test_diamond_graph_binds():
    """Diamond: top -> {a, b}, a -> base, b -> base. base is raw. units(top)
    multiplies through both arms. Pins the shared-subtree case against Lean."""
    # 0=top, 1=a, 2=b, 3=base(raw)
    recipes = {0: {1: 2, 2: 3}, 1: {3: 5}, 2: {3: 7}}
    drops = {100: 3}  # a resource drops the base
    roots = [0]
    query = 0
    fuel = 12
    py_needed, py_craft, py_units, lean = _run(recipes, drops, roots, query, fuel)
    assert py_needed == sorted(lean["needed_resources"])
    assert py_craft == sorted(lean["craftable_mats"])
    assert py_units == lean["raw_material_units"]
    # units(top) = 2*units(a) + 3*units(b) = 2*(5*1) + 3*(7*1) = 10 + 21 = 31
    assert py_units == 31


def test_cyclic_graph_terminates_and_binds():
    """Cycle: 0 -> 1, 1 -> 0. raw_material_units must terminate (revisit -> 1)
    and the closure must capture both items. Pins cyclic safety against Lean."""
    recipes = {0: {1: 2}, 1: {0: 3}}
    drops = {100: 0, 101: 1}
    roots = [0]
    query = 0
    fuel = 8
    py_needed, py_craft, py_units, lean = _run(recipes, drops, roots, query, fuel)
    assert py_craft == sorted(lean["craftable_mats"]) == [0, 1]
    assert py_needed == sorted(lean["needed_resources"]) == [100, 101]
    # units(0) = 2 * units(1, visited={0}) = 2 * (3 * units(0, visited={0,1})=1) = 2*3 = 6
    assert py_units == lean["raw_material_units"] == 6
