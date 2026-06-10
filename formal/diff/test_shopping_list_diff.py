"""The live `shopping_list` (Python) must agree with
`Formal.ShoppingList.shoppingList` (Lean) on the TOTAL raw gather work the
bank-aware net list implies AND on the net's key set, over random DAG recipes
with random holdings.

Faithfulness (P2c): BOTH sides thread (and consume) the `owned` dict
depth-first — the Lean hand model was aligned to the Python consume semantics
in extraction P2c, and `Extracted.Bridges.shopping_list_bridge` proves the
mechanically extracted image equal to it universally. The pre-P2c hand model
credited a CONSTANT `owned` function per node instead; that model agreed with
Python on TREE recipes only, and THIS suite's generator then only built trees
(each child claimed by a single parent), which MASKED the divergence: on a
DAG-shaped recipe (one raw material under two parents — the shape real gear
recipes have) the constant model double-credited shared stock where Python
consumes it. The generator now builds DAGs (shared sub-materials across
branches), so any constant-credit regression diverges here.

The compared quantities are the total raw work (sum of the live
`shopping_list` net over RAW-LEAF items, = Lean `netSumRaw`) and the sorted
net keys.
"""
import random

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.shopping_list import shopping_list
from formal.diff.oracle_client import run_oracle

# Item universe: 0..N-1. Index i may only have sub-materials j > i (acyclic).
_N = 6


def _make_dag(seed: int) -> dict[int, dict[int, int]]:
    """Build a random DAG recipe over items 0..N-1: children strictly greater
    than the parent (acyclic), and a child may be claimed by MULTIPLE parents
    (shared sub-materials — the consume-semantics discriminator). Some items
    are raw (no recipe)."""
    rng = random.Random(seed)
    recipes: dict[int, dict[int, int]] = {}
    for item in range(_N):
        pool = list(range(item + 1, _N))
        rng.shuffle(pool)
        k = rng.randint(0, min(2, len(pool)))  # 0..2 sub-materials
        if k == 0:
            continue  # raw item
        recipes[item] = {j: rng.randint(1, 4) for j in pool[:k]}
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
    return [n, *triples, no, *owned_pairs, item, qty]


@settings(max_examples=300, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=10_000),
    qty=st.integers(min_value=0, max_value=8),
    owned_seed=st.integers(min_value=0, max_value=10_000),
)
def test_raw_work_matches_lean(seed, qty, owned_seed):
    recipes = _make_dag(seed)
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
    net keys. This pins the SHORT-CIRCUIT: a fully-covered intermediate's
    sub-materials must NOT appear (they are withdrawn, the subtree is pruned).
    The raw-work metric alone can't see this (a covered subtree adds 0 work)."""
    recipes = _make_dag(seed)
    rng = random.Random(owned_seed)
    owned = {i: rng.randint(0, 12) for i in range(_N) if rng.random() < 0.6}
    net = shopping_list(0, qty, recipes, owned)
    py_keys = sorted(net.keys())
    lean = run_oracle("shopping_list", [_oracle_args(recipes, owned, 0, qty)])[0]
    assert lean["keys"] == py_keys, (recipes, owned, qty, py_keys, lean["keys"])


def test_dag_double_credit_witness():
    """THE P2a model-fidelity witness (documented in Extracted/Bridges.lean,
    closed in P2c): two gear parts (1 and 2) each need 2 of the same ore (3);
    2 banked ore cover only ONE branch. Consume semantics (Python = spec =
    new Lean model): the first branch consumes the 2 ore, the second gathers
    2 -> raw work 2. The pre-P2c constant-credit hand model credited the same
    2 ore under BOTH parents -> raw work 0 (double credit). Tree-only
    generation masked this; this pin keeps the divergence closed."""
    recipes = {0: {1: 1, 2: 1}, 1: {3: 2}, 2: {3: 2}}
    owned = {3: 2}
    py = _raw_leaf_work(0, 1, recipes, owned)
    lean = run_oracle("shopping_list", [_oracle_args(recipes, owned, 0, 1)])[0]
    assert py == 2  # consume: one branch covered, the other gathers 2
    assert lean["raw_work"] == 2
    assert lean["keys"] == sorted(shopping_list(0, 1, recipes, owned).keys())


def test_dag_diamond_one_path_covered():
    """Diamond DAG: item 0 -> {a=1, b=2}, a -> {ore}, b -> {ore}, with owned
    ore covering exactly one path. Consume: raw work 1 (the constant-credit
    model said 0). All four items stay in the net closure (no spurious
    short-circuit of the uncovered branch)."""
    recipes = {0: {1: 1, 2: 1}, 1: {3: 1}, 2: {3: 1}}
    owned = {3: 1}
    py = _raw_leaf_work(0, 1, recipes, owned)
    lean = run_oracle("shopping_list", [_oracle_args(recipes, owned, 0, 1)])[0]
    assert py == 1
    assert lean["raw_work"] == 1
    assert lean["keys"] == [0, 1, 2, 3]


def test_partial_bank_partial_credit():
    """Mutation separator (mirrors the retired Lean pin shopping_pin_partial_bank):
    2 banked bars + 20 banked ore leave exactly 20 ore of raw work. Kills
    `used = 0` (gives 60), `qty + used` (over-counts) and `per_unit * qty`
    (gives 40) deterministically."""
    recipes = {0: {1: 6}, 1: {2: 10}}  # dagger <- bar x6 <- ore x10
    owned = {1: 2, 2: 20}
    py = _raw_leaf_work(0, 1, recipes, owned)
    lean = run_oracle("shopping_list", [_oracle_args(recipes, owned, 0, 1)])[0]
    assert py == 20
    assert lean["raw_work"] == 20


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
