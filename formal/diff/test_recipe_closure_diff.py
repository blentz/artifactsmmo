"""Differential test: real Python `recipe_closure` / `_raw_units` must
agree with the proved Lean oracle over random finite recipe graphs.

`recipe_closure(game_data, roots)` does a DFS over `_crafting_recipes` (item ->
{sub: qty}) and `_resource_drops` (resource -> drop_item), returning
`(needed_resources, craftable_mats)`. `_raw_units` (via the `raw_units` helper)
recursively sums `qty * units(sub)` with a visited guard making revisits / raw
items cost 1 (cyclic-safe).

We use integer item/resource codes (the model uses `Nat`) and a real GameData
carrying only `crafting_recipes` and `resource_drops`. The same recipe graph is
encoded for the Lean oracle (flat int args). We assert:
* `needed_resources` sets match,
* `craftable_mats` sets match,
* `_raw_units(query)` values match,
over >= 200 random graphs including CYCLIC and DIAMOND shapes.
"""
import random

from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import (
    _closure_demand,
    _raw_units,
    recipe_closure,
)


def raw_units(game_data, item):
    """Raw-material units for `item`, in the LIVE production call shape.

    Wave 1 deleted the `raw_material_units` wrapper this test used to call —
    it had zero production callers, so the differential was verifying a shim
    one indirection away from the code the bot runs. `_raw_units` IS live
    (`task_batch.craft_batch_size_pure`), and this reproduces that call
    exactly: fuel `len(recipes) + 1`, explicit yields, empty visited. The
    Lean oracle side is unchanged — it always modelled `_raw_units`.
    """
    recipes = game_data.crafting_recipes
    return _raw_units(len(recipes) + 1, item, recipes,
                      game_data.craft_yields, {})
from formal.diff.oracle_client import run_oracle


def _gd(recipes: dict[int, dict[int, int]], drops: dict[int, int]) -> GameData:
    gd = GameData()
    gd._crafting_recipes = {str(k): {str(s): q for s, q in v.items()} for k, v in recipes.items()}
    gd._resource_drops = {str(r): str(d) for r, d in drops.items()}
    return gd


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
    gd = _gd(recipes, drops)
    needed, craft = recipe_closure(gd, [str(x) for x in roots])
    py_needed = sorted(int(x) for x in needed)
    py_craft = sorted(int(x) for x in craft)
    py_units = raw_units(gd, str(query))

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
    assert py_units == lean["raw_units"], f"units mismatch: {ctx} lean={lean}"


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
    assert py_units == lean["raw_units"]
    # units(top) = 2*units(a) + 3*units(b) = 2*(5*1) + 3*(7*1) = 10 + 21 = 31
    assert py_units == 31


def test_cyclic_graph_terminates_and_binds():
    """Cycle: 0 -> 1, 1 -> 0. _raw_units must terminate (revisit -> 1)
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
    assert py_units == lean["raw_units"] == 6


# ---------------------------------------------------------------------------
# Yield-parameterised differential tests (Task 6 / feat/batch-craft-yield).
# Exercises the ⌈m/Y⌉ ceil-batch semantics added to `_raw_units` /
# `_closure_demand` in Tasks 4-5.  The oracle routes:
#   * _raw_units → recipe_closure kind (parseYieldFn at p3+2)
#   * _closure_demand    → task_reservation kind (parseYieldFn at qBase+2+nQuery)
#     via reservedDemand(r, y, fuel, {taskCode=root, taskTotal=multiplier,
#     taskProgress=0, taskIsItems=True}).
# ---------------------------------------------------------------------------


def _gd_with_yields(
    recipes: dict[int, dict[int, int]],
    drops: dict[int, int],
    yields: dict[int, int],
) -> GameData:
    """GameData with string-keyed recipes, drops, AND craft_yields."""
    gd = _gd(recipes, drops)
    gd._craft_yields = {str(k): v for k, v in yields.items()}
    return gd


def _encode_args_yield(
    recipes: dict[int, dict[int, int]],
    drops: dict[int, int],
    roots: list[int],
    query: int,
    fuel: int,
    yields: dict[int, int],
) -> list[int]:
    """Base recipe_closure encoding + optional trailing yield block
    [nY, item0, y0, item1, y1, ...] appended after fuel."""
    args = _encode_args(recipes, drops, roots, query, fuel)
    if yields:
        args.append(len(yields))
        for item, y in yields.items():
            args += [item, y]
    return args


def _encode_demand_via_tr(
    recipes: dict[int, dict[int, int]],
    root: int,
    multiplier: int,
    queries: list[int],
    fuel: int,
    yields: dict[int, int],
) -> list[int]:
    """Encode a task_reservation request that exercises closureDemand(root, multiplier)
    via reservedDemand with taskIsItems=1, taskTotal=multiplier, taskProgress=0,
    nNeeded=0, nOwned=0, then a trailing yield block [nY, item, y, ...]."""
    triples = [(item, sub, qty) for item, subs in recipes.items()
               for sub, qty in subs.items()]
    args: list[int] = [len(triples)]
    for item, sub, qty in triples:
        args += [item, sub, qty]
    # taskIsItems=1, taskCode=root, taskTotal=multiplier, taskProgress=0
    args += [1, root, multiplier, 0]
    args += [0]                          # nNeeded
    args += [0]                          # nOwned
    args += [len(queries)] + list(queries)
    args += [fuel]
    if yields:
        args += [len(yields)]
        for item, y in yields.items():
            args += [item, y]
    return args


def _rand_yields_nonempty(
    rng: random.Random,
    recipes: dict[int, dict[int, int]],
) -> dict[int, int]:
    """Yields for items with recipes — at least one Y>1 entry (2, 3, or 4)."""
    crafted = list(recipes.keys())
    yields: dict[int, int] = {rng.choice(crafted): rng.choice([2, 3, 4])}
    for item in crafted:
        if item not in yields and rng.random() < 0.5:
            yields[item] = rng.randint(2, 4)
    return yields


@settings(max_examples=200, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
def test_yield_raw_units_matches_lean(seed):
    """_raw_units with Y>1 yields must agree with the recipe_closure oracle.
    Exercises the parseYieldFn + rawUnits ceil-batch arithmetic path."""
    rng = random.Random(seed)
    recipes, drops, roots, query, fuel = _rand_graph(rng, allow_cycle=False)
    if not recipes:
        return
    yields = _rand_yields_nonempty(rng, recipes)
    gd = _gd_with_yields(recipes, drops, yields)
    py_units = raw_units(gd, str(query))
    args = _encode_args_yield(recipes, drops, roots, query, fuel, yields)
    lean = run_oracle("recipe_closure", [args])[0]
    ctx = f"recipes={recipes} yields={yields} query={query}"
    assert py_units == lean["raw_units"], f"raw_units mismatch: {ctx} lean={lean}"


@settings(max_examples=200, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
def test_yield_closure_demand_matches_lean(seed):
    """_closure_demand with Y>1 yields must agree with the task_reservation oracle.
    Exercises the parseYieldFn + closureDemand ceil-batch arithmetic path."""
    rng = random.Random(seed)
    recipes, drops, roots, query, fuel = _rand_graph(rng, allow_cycle=False)
    if not recipes:
        return
    crafted = list(recipes.keys())
    yields = _rand_yields_nonempty(rng, recipes)
    root = rng.choice(crafted)
    multiplier = rng.randint(1, 12)
    all_codes: set[int] = set(recipes.keys())
    for subs in recipes.values():
        all_codes.update(subs.keys())
    all_items = list(range(max(all_codes) + 1))
    str_recipes = {str(k): {str(s): q for s, q in v.items()} for k, v in recipes.items()}
    str_yields = {str(k): v for k, v in yields.items()}
    py_demand = _closure_demand(fuel, str(root), multiplier, str_recipes, str_yields, {}, {})
    args = _encode_demand_via_tr(recipes, root, multiplier, all_items, fuel, yields)
    lean = run_oracle("task_reservation", [args])[0]
    ctx = f"recipes={recipes} yields={yields} root={root} mult={multiplier}"
    for idx, q in enumerate(all_items):
        lean_val = lean["demand_vals"][idx]
        py_val = py_demand.get(str(q), 0)
        assert py_val == lean_val, f"demand mismatch at {q}: py={py_val} lean={lean_val} {ctx}"


def test_pin_yield2_ceil_demand():
    """Deterministic pin: yield-2 root (potion), need 3 → ⌈3/2⌉=2 crafts → 2 herbs.

    Kills the 'drop ceil in batches' mutant (floor(3/2)=1 → 1 herb ≠ 2)
    and the 'drop batch scaling' mutant (3*1=3 herbs ≠ 2).
    Also pins raw_units of potion: herb is raw (cost 1); ⌈1/2⌉=1."""
    # potion(0) needs herb(1)×1 per craft; 2 potions per craft.
    recipes = {0: {1: 1}}
    drops: dict[int, int] = {}
    yields = {0: 2}
    multiplier = 3
    fuel = 4
    queries = [0, 1]
    py_demand = _closure_demand(
        fuel, "0", multiplier, {"0": {"1": 1}}, {"0": 2}, {}, {}
    )
    lean = run_oracle("task_reservation", [
        _encode_demand_via_tr(recipes, 0, multiplier, queries, fuel, yields)
    ])[0]
    assert py_demand == {"0": 3, "1": 2}, f"closure demand wrong: {py_demand}"
    assert py_demand.get("0", 0) == lean["demand_vals"][0], f"oracle q=0 mismatch: {lean}"
    assert py_demand.get("1", 0) == lean["demand_vals"][1], f"oracle q=1 mismatch: {lean}"
    gd = _gd_with_yields(recipes, drops, yields)
    py_units = raw_units(gd, "0")
    lean_rc = run_oracle("recipe_closure", [
        _encode_args_yield(recipes, drops, [0], 0, fuel, yields)
    ])[0]
    assert py_units == 1, f"raw_units of potion should be ⌈1/2⌉=1, got {py_units}"
    assert py_units == lean_rc["raw_units"], f"oracle raw_units mismatch: {lean_rc}"


def test_pin_yield3_nondivisible():
    """Deterministic pin: yield-3 root (bar), need 5 → ⌈5/3⌉=2 crafts → 2×4=8 ore.

    Kills the 'drop ceil in batches' mutant (floor(5/3)=1 → 4 ore ≠ 8)
    and the 'drop batch scaling' mutant (5*4=20 ore ≠ 8).
    Also pins raw_units of bar: total=4×1=4; ⌈4/3⌉=2."""
    # bar(0) needs ore(1)×4 per craft; 3 bars per craft.
    recipes = {0: {1: 4}}
    drops: dict[int, int] = {}
    yields = {0: 3}
    multiplier = 5
    fuel = 4
    queries = [0, 1]
    py_demand = _closure_demand(
        fuel, "0", multiplier, {"0": {"1": 4}}, {"0": 3}, {}, {}
    )
    lean = run_oracle("task_reservation", [
        _encode_demand_via_tr(recipes, 0, multiplier, queries, fuel, yields)
    ])[0]
    assert py_demand == {"0": 5, "1": 8}, f"closure demand wrong: {py_demand}"
    assert py_demand.get("0", 0) == lean["demand_vals"][0], f"oracle q=0 mismatch: {lean}"
    assert py_demand.get("1", 0) == lean["demand_vals"][1], f"oracle q=1 mismatch: {lean}"
    gd = _gd_with_yields(recipes, drops, yields)
    py_units = raw_units(gd, "0")
    lean_rc = run_oracle("recipe_closure", [
        _encode_args_yield(recipes, drops, [0], 0, fuel, yields)
    ])[0]
    assert py_units == 2, f"raw_units of bar should be ⌈4/3⌉=2, got {py_units}"
    assert py_units == lean_rc["raw_units"], f"oracle raw_units mismatch: {lean_rc}"
