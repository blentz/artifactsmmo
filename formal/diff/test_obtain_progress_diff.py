"""Differential test: the real Python `_obtain_progress` (the deepened gear-root
progress witness in `root_progress.py`) must agree with the proved Lean
`Formal.Liveness.ObtainProgress.obtainProgress` over random finite recipe graphs and
owned (inventory + bank) configurations.

`_obtain_progress(code, state, game_data)` (non-equipped branch) computes the
raw-material-unit-weighted owned count over the target's whole recipe closure:

    Σ_{node ∈ closure_demand(code) ∪ {code}}  (inventory[node] + bank[node]) * raw_material_units(node)

The Lean `obtainProgress r fuel owned nodes` is exactly `Σ_{i ∈ nodes} owned i * rawUnits r
fuel i`, proved monotone (gather ⇒ strict ↑) and craft-invariant
(`Formal/Liveness/ObtainProgress.lean`). This harness feeds the SAME recipe graph, node
set, owned map, and fuel to BOTH the live Python function and the Lean oracle and asserts
the scalar witnesses agree over >= 200 random graphs (acyclic, cyclic, diamond), so the
proof's faithfulness theorems bind the real code.
"""
import random

from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import closure_demand
from artifactsmmo_cli.ai.tiers.root_progress import _obtain_progress
from artifactsmmo_cli.ai.world_state import WorldState
from formal.diff.oracle_client import run_oracle


def _gd(recipes: dict[int, dict[int, int]]) -> GameData:
    gd = GameData()
    gd._crafting_recipes = {str(k): {str(s): q for s, q in v.items()} for k, v in recipes.items()}
    gd._resource_drops = {}
    return gd


def _state(inventory: dict[int, int], bank: dict[int, int]) -> WorldState:
    return WorldState(
        character="t", level=1, xp=0, max_xp=100, hp=100, max_hp=100, gold=0,
        skills={}, x=0, y=0, inventory={str(k): v for k, v in inventory.items()},
        inventory_max=1000, equipment={}, cooldown_expires=None, task_code=None,
        task_type=None, task_progress=0, task_total=0,
        bank_items={str(k): v for k, v in bank.items()}, bank_gold=None,
        pending_items=None, skill_xp={},
    )


def _encode(recipes: dict[int, dict[int, int]], nodes: list[int],
            owned: dict[int, int], fuel: int) -> list[int]:
    triples: list[int] = []
    n_recipe = 0
    for item, sub_map in recipes.items():
        for sub, qty in sub_map.items():
            triples += [item, sub, qty]
            n_recipe += 1
    owned_pairs: list[int] = []
    for node in nodes:
        owned_pairs += [node, owned.get(node, 0)]
    return ([n_recipe] + triples
            + [len(nodes)] + list(nodes)
            + [len(nodes)] + owned_pairs
            + [fuel])


def _run(recipes: dict[int, dict[int, int]], target: int,
         inventory: dict[int, int], bank: dict[int, int]):
    gd = _gd(recipes)
    state = _state(inventory, bank)
    py = _obtain_progress(str(target), state, gd)

    # The exact node set Python sums over (mirrors `_obtain_progress`).
    demand: dict[str, int] = {}
    closure_demand(str(target), 1, gd, demand, frozenset())
    nodes_s = set(demand) | {str(target)}
    nodes = sorted(int(n) for n in nodes_s)
    owned = {n: inventory.get(n, 0) + bank.get(n, 0) for n in nodes}
    fuel = len(gd._crafting_recipes) + 1  # matches raw_material_units' internal fuel

    args = _encode(recipes, nodes, owned, fuel)
    lean = run_oracle("obtain_progress", [args])[0]
    return py, int(lean["obtain_progress"])


def _rand_graph(rng: random.Random, allow_cycle: bool):
    n = rng.randint(1, 7)
    items = list(range(n))
    recipes: dict[int, dict[int, int]] = {}
    for it in items:
        if rng.random() < 0.55:
            n_sub = rng.randint(1, 3)
            subs: dict[int, int] = {}
            for _ in range(n_sub):
                if allow_cycle:
                    sub = rng.randint(0, n - 1)
                else:
                    if it + 1 > n - 1:
                        continue
                    sub = rng.randint(it + 1, n - 1)
                if sub != it or allow_cycle:
                    subs[sub] = rng.randint(1, 5)
            if subs:
                recipes[it] = subs
    return n, recipes


@settings(max_examples=250, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1), cyclic=st.booleans())
def test_obtain_progress_matches_oracle(seed: int, cyclic: bool):
    rng = random.Random(seed)
    n, recipes = _rand_graph(rng, allow_cycle=cyclic)
    target = rng.randint(0, n - 1)
    # Random owned counts across all item codes, split between inventory and bank.
    inventory = {i: rng.randint(0, 6) for i in range(n) if rng.random() < 0.6}
    bank = {i: rng.randint(0, 6) for i in range(n) if rng.random() < 0.4}
    py, lean = _run(recipes, target, inventory, bank)
    assert py == lean, f"py={py} lean={lean} recipes={recipes} target={target} inv={inventory} bank={bank}"
