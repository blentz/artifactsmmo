"""The live `shopping_list` (Python) must agree with
`Formal.ShoppingList.rawReq` (Lean) on the TOTAL raw gather work the bank-aware
net list implies, over random TREE recipes with random holdings.

Faithfulness: the Lean `rawReq` credits each item's holdings at its node and
threads `owned` to siblings; the Python `_expand` consumes a shared mutable
`owned` depth-first. The two coincide exactly when every item is credited at most
once — i.e. on TREE recipes where each non-root item is the sub-material of a
single parent (no shared sub-materials, no cycles). The generator below produces
exactly such trees (strictly increasing child indices, each child claimed by one
parent), so the comparison drives the SAME function on both sides.

The compared quantity is the total raw work = sum of the live `shopping_list`
net over RAW-LEAF items (items with no recipe), which equals `rawReq` for trees.
"""
import random

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.shopping_list import shopping_list
from formal.diff.oracle_client import run_oracle

# Item universe: 0..N-1. Index i may only have sub-materials j > i (acyclic),
# and each j is the sub of at most one parent (tree).
_N = 6
_FUEL = 12  # > tree depth


def _make_tree(seed: int) -> dict[int, dict[int, int]]:
    """Build a random tree recipe over items 0..N-1: each child claimed by one
    parent, children strictly greater than parent (acyclic). Some items are
    raw (no recipe)."""
    rng = random.Random(seed)
    recipes: dict[int, dict[int, int]] = {}
    claimed: set[int] = set()
    for item in range(_N):
        # Candidate children: greater indices not yet claimed.
        free = [j for j in range(item + 1, _N) if j not in claimed]
        rng.shuffle(free)
        k = rng.randint(0, min(2, len(free)))  # 0..2 sub-materials
        if k == 0:
            continue  # raw item
        recipe: dict[int, int] = {}
        for j in free[:k]:
            recipe[j] = rng.randint(1, 4)  # per-unit qty
            claimed.add(j)
        recipes[item] = recipe
    return recipes


def _raw_leaf_work(item: int, qty: int, recipes: dict, owned: dict) -> int:
    """Total raw gather work = sum of the shopping_list net over items with no
    recipe (the leaves the planner would gather)."""
    net = shopping_list(item, qty, recipes, owned)
    return sum(v for code, v in net.items() if not recipes.get(code))


def _oracle_args(recipes: dict, owned: dict, item: int, qty: int) -> list[int]:
    triples: list[int] = []
    n = 0
    for parent, recipe in recipes.items():
        for sub, per in recipe.items():
            triples.extend([parent, sub, per])
            n += 1
    owned_pairs: list[int] = []
    no = 0
    for code, q in owned.items():
        owned_pairs.extend([code, q])
        no += 1
    return [n, *triples, no, *owned_pairs, item, qty, _FUEL]


@settings(max_examples=300, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=10_000),
    qty=st.integers(min_value=0, max_value=8),
    owned_seed=st.integers(min_value=0, max_value=10_000),
)
def test_raw_work_matches_lean(seed, qty, owned_seed):
    recipes = _make_tree(seed)
    rng = random.Random(owned_seed)
    owned = {i: rng.randint(0, 12) for i in range(_N) if rng.random() < 0.6}
    item = 0  # root
    py = _raw_leaf_work(item, qty, recipes, owned)
    lean = run_oracle("shopping_list", [_oracle_args(recipes, owned, item, qty)])[0]
    assert lean["raw_work"] == py, (recipes, owned, qty, py, lean)


@settings(max_examples=300, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=10_000),
    qty=st.integers(min_value=0, max_value=8),
    owned_seed=st.integers(min_value=0, max_value=10_000),
)
def test_net_keys_match_lean(seed, qty, owned_seed):
    """The SET of items the net dict records (its keys) must match the Lean
    `touched` model. This pins the SHORT-CIRCUIT: a fully-covered intermediate's
    sub-materials must NOT appear (they are withdrawn, the subtree is pruned).
    The raw-work metric alone can't see this (a covered subtree adds 0 work)."""
    recipes = _make_tree(seed)
    rng = random.Random(owned_seed)
    owned = {i: rng.randint(0, 12) for i in range(_N) if rng.random() < 0.6}
    net = shopping_list(0, qty, recipes, owned)
    py_keys = sorted(net.keys())
    lean = run_oracle("shopping_list", [_oracle_args(recipes, owned, 0, qty)])[0]
    assert lean["keys"] == py_keys, (recipes, owned, qty, py_keys, lean["keys"])


def test_short_circuit_prunes_covered_subtree():
    """Covered intermediate (6 banked bars cover the 6 needed) -> the ore subtree
    is pruned: copper_ore is NOT a net key."""
    recipes = {0: {1: 6}, 1: {2: 10}}  # dagger <- bar x6 <- ore x10
    owned = {1: 6}                      # 6 banked copper_bar fully cover the need
    net = shopping_list(0, 1, recipes, owned)
    assert 2 not in net  # copper_ore subtree pruned (the short-circuit)
    lean = run_oracle("shopping_list", [_oracle_args(recipes, owned, 0, 1)])[0]
    assert lean["keys"] == sorted(net.keys())
    assert 2 not in lean["keys"]


def test_full_bank_zero_work():
    """The live Robby case in miniature: bank covers the base material fully ->
    zero gather work; Lean agrees."""
    recipes = {0: {1: 6}, 1: {2: 10}}  # dagger <- bar x6 <- ore x10
    owned = {2: 485}                    # 485 banked ore
    py = _raw_leaf_work(0, 1, recipes, owned)
    lean = run_oracle("shopping_list", [_oracle_args(recipes, owned, 0, 1)])[0]
    assert py == 0
    assert lean["raw_work"] == 0


def test_no_bank_full_work():
    """No holdings -> full naive work (60 ore for 1 dagger); Lean agrees."""
    recipes = {0: {1: 6}, 1: {2: 10}}
    owned: dict[int, int] = {}
    py = _raw_leaf_work(0, 1, recipes, owned)
    lean = run_oracle("shopping_list", [_oracle_args(recipes, owned, 0, 1)])[0]
    assert py == 60
    assert lean["raw_work"] == 60
