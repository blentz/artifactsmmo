"""The live `gather_step_target` (Python) must agree with
`Formal.StepDispatch.gatherTarget` (Lean) on the routed (code, qty) — the Piece-C
feasibility decision that, for a depth-UNREACHABLE equippable root, routes the
GatherMaterials goal to the strategy's deepest actionable step instead of the deep
root recipe (which explodes the planner).

Both sides compute `min_gathers(root, 1, recipes, owned)` and compare it to
`equip_max_depth`: ≤ ⇒ keep the root target `(root, 1)`; > ⇒ route to
`(step, step_qty)`. Faithfulness: the Lean `minGathers` credits each item's
holdings at its node and threads `owned` to siblings; the Python `min_gathers`
consumes a shared mutable `owned` depth-first. The two coincide exactly on TREE
recipes (each non-root item the sub of a single parent, no cycles) — the same
generator shape as test_shopping_list_diff.
"""
import random

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.gather_step_target import gather_step_target
from artifactsmmo_cli.ai.min_gathers import min_gathers
from formal.diff.oracle_client import run_oracle

_N = 6
_FUEL = 12  # > tree depth


def _make_tree(seed: int) -> dict[int, dict[int, int]]:
    """Random TREE recipe over items 0..N-1 (each child claimed by one parent,
    children strictly greater — acyclic). Item 0 is the root equippable."""
    rng = random.Random(seed)
    recipes: dict[int, dict[int, int]] = {}
    claimed: set[int] = set()
    for item in range(_N):
        free = [j for j in range(item + 1, _N) if j not in claimed]
        rng.shuffle(free)
        k = rng.randint(0, min(2, len(free)))
        if k == 0:
            continue
        recipe: dict[int, int] = {}
        for j in free[:k]:
            recipe[j] = rng.randint(1, 4)
            claimed.add(j)
        recipes[item] = recipe
    return recipes


def _raw_leaf(recipes: dict[int, dict[int, int]]) -> int:
    """A raw-leaf item code (no recipe) to use as the deepest step; falls back to
    the highest index (always a leaf in the increasing-index tree)."""
    for i in range(_N - 1, -1, -1):
        if not recipes.get(i):
            return i
    return _N - 1


def _oracle_args(recipes, owned, root, step, step_qty, max_depth) -> list[int]:
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
    return [n, *triples, no, *owned_pairs, root, step, step_qty, max_depth, _FUEL]


@settings(max_examples=400, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=10_000),
    owned_seed=st.integers(min_value=0, max_value=10_000),
    step_qty=st.integers(min_value=0, max_value=40),
    max_depth=st.integers(min_value=0, max_value=200),
)
def test_routed_target_matches_lean(seed, owned_seed, step_qty, max_depth):
    recipes = _make_tree(seed)
    rng = random.Random(owned_seed)
    owned = {i: rng.randint(0, 12) for i in range(_N) if rng.random() < 0.5}
    root = 0
    step = _raw_leaf(recipes)
    py_code, py_qty = gather_step_target(root, step, step_qty, recipes, owned, max_depth)
    lean = run_oracle(
        "gather_step_target",
        [_oracle_args(recipes, owned, root, step, step_qty, max_depth)],
    )[0]
    assert (lean["code"], lean["qty"]) == (py_code, py_qty), (
        recipes, owned, step_qty, max_depth, (py_code, py_qty), lean)


def test_unreachable_root_routes_to_step():
    """Deep from-scratch chain (480 ore) over budget -> route to the raw step."""
    recipes = {0: {1: 6}, 1: {2: 8}, 2: {3: 10}}  # boots<-bar6<-ironbar8<-ore10
    owned: dict[int, int] = {}
    py = gather_step_target(0, 3, 480, recipes, owned, 15)
    assert py == (3, 480)
    lean = run_oracle("gather_step_target", [_oracle_args(recipes, owned, 0, 3, 480, 15)])[0]
    assert (lean["code"], lean["qty"]) == py


def test_reachable_root_keeps_root():
    """Holdings cover the chain -> root cost 0 <= budget -> keep (root, 1)."""
    recipes = {0: {1: 6}, 1: {2: 8}, 2: {3: 10}}
    owned = {1: 6}  # 6 of item-1 cover the root recipe -> 0 gathers
    assert min_gathers(0, 1, recipes, owned) == 0
    py = gather_step_target(0, 3, 480, recipes, owned, 15)
    assert py == (0, 1)
    lean = run_oracle("gather_step_target", [_oracle_args(recipes, owned, 0, 3, 480, 15)])[0]
    assert (lean["code"], lean["qty"]) == py


def test_boundary_at_budget_keeps_root():
    """root_cost == max_depth is reachable (strict-> gate) -> keep root."""
    recipes = {0: {1: 15}}
    owned: dict[int, int] = {}
    assert min_gathers(0, 1, recipes, owned) == 15
    py = gather_step_target(0, 1, 15, recipes, owned, 15)
    assert py == (0, 1)
    lean = run_oracle("gather_step_target", [_oracle_args(recipes, owned, 0, 1, 15, 15)])[0]
    assert (lean["code"], lean["qty"]) == py
